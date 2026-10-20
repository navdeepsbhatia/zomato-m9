"""Cache reads and failed downloads stay offline."""

from pathlib import Path

import pandas as pd
import pytest

from recommender.config import Settings
from recommender.data.cleaner import CLEANED_COLUMNS
from recommender.data.loader import (
    DATASET_ID,
    WORKING_COLUMNS,
    CacheReadError,
    DatasetDownloadError,
    load_processed_table,
    load_raw_dataset,
)


class _FakeDataset:
    def __init__(self, frame: pd.DataFrame, column_names: list[str]) -> None:
        self._frame = frame
        self.column_names = column_names
        self.removed: list[str] = []

    def remove_columns(self, columns: list[str]) -> "_FakeDataset":
        self.removed = list(columns)
        return self

    def to_pandas(self) -> pd.DataFrame:
        return self._frame.copy()


def _raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "url": "https://example.test/jalsa",
                "address": "  21st Main  ",
                "name": " Jalsa ",
                "online_order": "Yes",
                "book_table": "No",
                "rate": "4.1/5",
                "votes": "775",
                "location": " Banashankari ",
                "rest_type": "Casual Dining",
                "dish_liked": "Pasta",
                "cuisines": "North Indian, Chinese",
                "approx_cost(for two people)": "800",
                "listed_in(city)": " Banashankari ",
                "phone": "080",
                "reviews_list": "x" * 1000,
                "menu_item": "Pasta",
                "listed_in(type)": "Buffet",
            }
        ]
    )


def test_raw_dataset_keeps_working_columns_only(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_load(name: str, split: str) -> _FakeDataset:
        captured["name"] = name
        captured["split"] = split
        return _FakeDataset(_raw_frame(), list(_raw_frame().columns))

    monkeypatch.setattr("recommender.data.loader.load_dataset", fake_load)
    frame = load_raw_dataset()

    assert captured == {"name": DATASET_ID, "split": "train"}
    assert list(frame.columns) == WORKING_COLUMNS
    for column in ("phone", "reviews_list", "menu_item", "listed_in(type)"):
        assert column not in frame.columns


def test_processed_table_writes_csv_then_reads_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    downloads = {"count": 0}

    def fake_load(name: str, split: str) -> _FakeDataset:
        downloads["count"] += 1
        assert name == DATASET_ID
        assert split == "train"
        return _FakeDataset(_raw_frame(), list(_raw_frame().columns))

    monkeypatch.setattr("recommender.data.loader.load_dataset", fake_load)
    path = tmp_path / "processed" / "restaurants.csv"
    settings = Settings(data_cache_path=path)

    first = load_processed_table(settings)
    assert path.is_file()
    assert downloads["count"] == 1
    assert list(first.columns) == CLEANED_COLUMNS
    assert first.iloc[0]["name"] == "Jalsa"
    assert first.iloc[0]["cuisines"] == ["North Indian", "Chinese"]
    saved = path.read_text(encoding="utf-8")
    assert "North Indian, Chinese" in saved
    assert saved.splitlines()[0].startswith("name,address,location")

    def fail_load(*args: object, **kwargs: object) -> None:
        raise AssertionError("load_dataset should not run when the cache exists")

    monkeypatch.setattr("recommender.data.loader.load_dataset", fail_load)
    second = load_processed_table(settings)

    pd.testing.assert_frame_equal(first, second)
    assert downloads["count"] == 1


def test_c26_download_failure_without_cache_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def fail_load(*args: object, **kwargs: object) -> None:
        raise OSError("network down")

    monkeypatch.setattr("recommender.data.loader.load_dataset", fail_load)
    path = tmp_path / "restaurants.csv"
    with pytest.raises(DatasetDownloadError, match="do not call the model") as exc:
        load_processed_table(Settings(data_cache_path=path))
    assert isinstance(exc.value.__cause__, OSError)
    assert not path.exists()


def test_c28_unreadable_cache_is_not_redownloaded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    path = tmp_path / "restaurants.csv"
    path.write_bytes(b"\xff\xfe not csv")

    def fail_load(*args: object, **kwargs: object) -> None:
        raise AssertionError("load_dataset should not run for an unreadable cache")

    monkeypatch.setattr("recommender.data.loader.load_dataset", fail_load)
    with pytest.raises(CacheReadError, match="Do not download"):
        load_processed_table(Settings(data_cache_path=path))
