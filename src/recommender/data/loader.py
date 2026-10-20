"""Download the Zomato split and cache the cleaned table as CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from datasets import load_dataset

from recommender.config import Settings
from recommender.data.cleaner import CLEANED_COLUMNS, clean_restaurants

DATASET_ID = "ManikaSaini/zomato-restaurant-recommendation"
WORKING_COLUMNS = [
    "url",
    "address",
    "name",
    "online_order",
    "book_table",
    "rate",
    "votes",
    "location",
    "rest_type",
    "dish_liked",
    "cuisines",
    "approx_cost(for two people)",
    "listed_in(city)",
]
DROPPED_COLUMNS = ["phone", "reviews_list", "menu_item"]


class DatasetDownloadError(RuntimeError):
    """The dataset could not be downloaded and no local cache exists."""


class CacheReadError(RuntimeError):
    """The CSV cache exists but could not be read."""


def load_raw_dataset() -> pd.DataFrame:
    """Load the train split and keep only the working columns."""
    dataset = load_dataset(DATASET_ID, split="train")
    drop = [column for column in DROPPED_COLUMNS if column in dataset.column_names]
    if drop:
        dataset = dataset.remove_columns(drop)
    frame = dataset.to_pandas()
    missing = [column for column in WORKING_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(
            "Zomato dataset is missing required columns: " + ", ".join(missing)
        )
    return frame.loc[:, WORKING_COLUMNS].copy()


def load_processed_table(settings: Settings) -> pd.DataFrame:
    """Return the cleaned restaurant table, building the CSV cache on first use.

    A missing cache and a failed download raise `DatasetDownloadError`. An
    existing cache that cannot be read raises `CacheReadError`. Callers stop
    before any model request in both cases.
    """
    path = Path(settings.data_cache_path)
    if path.exists():
        try:
            return _read_cache(path)
        except Exception as exc:
            raise CacheReadError(
                f"Could not read the restaurant cache at {path}. "
                "Stop here. Do not download the dataset again or call the model."
            ) from exc

    try:
        raw = load_raw_dataset()
    except Exception as exc:
        raise DatasetDownloadError(
            "Could not download the Zomato dataset and no local cache exists "
            f"at {path}. Stop here and do not call the model."
        ) from exc

    cleaned = clean_restaurants(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f"{path.name}.tmp"
    try:
        _write_cache(cleaned, temporary)
        temporary.replace(path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return cleaned


def _cuisines_to_text(value: object) -> str:
    if value is None or isinstance(value, str):
        return "" if value is None else value
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, (list, tuple)):
        items = value
    else:
        try:
            items = list(value)
        except TypeError:
            return str(value)
    return ", ".join(str(item).strip() for item in items if str(item).strip())


def _write_cache(frame: pd.DataFrame, path: Path) -> None:
    """Write a UTF-8 CSV that a spreadsheet or text editor can open.

    Cuisines are stored as one comma-separated cell. Lists are not written.
    """
    stored = frame.copy()
    stored["cuisines"] = [_cuisines_to_text(value) for value in stored["cuisines"]]
    stored.to_csv(path, index=False, encoding="utf-8")


def _cuisine_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    try:
        if bool(pd.isna(value)):
            return []
    except (TypeError, ValueError):
        pass
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    try:
        return [str(item) for item in list(value) if str(item).strip()]
    except TypeError:
        return []


def _as_bool(value: object) -> bool:
    return str(value).strip().lower() == "true"


def _read_cache(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8", keep_default_na=False, na_values={
        "cost_for_two": [""],
        "rating": [""],
    })
    if "cuisines" in frame.columns:
        frame["cuisines"] = [_cuisine_list(value) for value in frame["cuisines"]]
    if "cost_for_two" in frame.columns:
        frame["cost_for_two"] = pd.to_numeric(frame["cost_for_two"], errors="coerce").astype("Int64")
    if "rating" in frame.columns:
        frame["rating"] = pd.to_numeric(frame["rating"], errors="coerce").astype("Float64")
    if "votes" in frame.columns:
        frame["votes"] = pd.to_numeric(frame["votes"], errors="coerce").fillna(0).astype("int64")
    for column in ("online_order", "book_table"):
        if column in frame.columns:
            frame[column] = frame[column].map(_as_bool)
    missing = [column for column in CLEANED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(
            "Restaurant cache is missing columns: " + ", ".join(missing)
        )
    return frame.loc[:, CLEANED_COLUMNS].copy()
