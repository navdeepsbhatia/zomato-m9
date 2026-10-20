"""Offline cleaning tests. Case ids match docs/edge-case.md."""

import pandas as pd
import pytest

from recommender.data.cleaner import CLEANED_COLUMNS, clean_restaurants


def raw_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "url": "https://example.test/default",
        "address": "12 Sample Road",
        "name": "Sample Restaurant",
        "online_order": "No",
        "book_table": "No",
        "rate": "4.1/5",
        "votes": "10",
        "location": "Banashankari",
        "rest_type": "Casual Dining",
        "dish_liked": "Pasta",
        "cuisines": "Italian",
        "approx_cost(for two people)": "500",
        "listed_in(city)": "Banashankari",
    }
    row.update(overrides)
    return row


def _frame(rows: list[dict[str, object]], *, heavy: bool = False) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if heavy:
        frame["phone"] = "080 42297555"
        frame["reviews_list"] = "RATED a very long review"
        frame["menu_item"] = "Masala Dosa"
    return frame


@pytest.fixture(scope="module")
def cleaned() -> pd.DataFrame:
    dish = "P" * 500
    rows = [
        raw_row(
            url="https://example.test/c1",
            name="Rating Place",
            rate="4.1/5",
            votes="2,556",
            cuisines="Cafe, Mexican, Italian",
            **{"approx_cost(for two people)": "1,200"},
        ),
        raw_row(
            url="https://example.test/c2",
            name="Spaced Rating",
            address="2 Rating Road",
            rate="4.1 / 5",
        ),
        raw_row(url="https://example.test/c3", name="New Place", address="3 Rating Road", rate="NEW"),
        raw_row(url="https://example.test/c4", name="Dash Place", address="4 Rating Road", rate="-"),
        raw_row(url="https://example.test/c5-blank", name="Blank Rate", address="5 Rating Road", rate=""),
        raw_row(url="https://example.test/c5-null", name="Null Rate", address="6 Rating Road", rate=None),
        raw_row(url="https://example.test/c6", name="Bare Rating", address="7 Rating Road", rate="4.1"),
        raw_row(
            url="https://example.test/c7",
            name="Word Rating",
            address="8 Rating Road",
            rate="Excellent",
        ),
        raw_row(
            url="https://example.test/c9",
            name="Spaced Cost",
            address="9 Cost Road",
            **{"approx_cost(for two people)": " 800 "},
        ),
        raw_row(
            url="https://example.test/c10-blank",
            name="Blank Cost",
            address="10 Cost Road",
            **{"approx_cost(for two people)": ""},
        ),
        raw_row(
            url="https://example.test/c10-dash",
            name="Dash Cost",
            address="11 Cost Road",
            **{"approx_cost(for two people)": "-"},
        ),
        raw_row(
            url="https://example.test/c10-null",
            name="Null Cost",
            address="12 Cost Road",
            **{"approx_cost(for two people)": None},
        ),
        raw_row(url="https://example.test/c12", name="Missing Votes", address="13 Vote Road", votes=None),
        raw_row(
            url="https://example.test/c14",
            name="Cuisine Spaces",
            address="14 Cuisine Road",
            cuisines="Cafe,  Italian,, Thai ",
        ),
        raw_row(
            url="https://example.test/c15-null",
            name="Null Cuisine",
            address="15 Cuisine Road",
            cuisines=None,
        ),
        raw_row(
            url="https://example.test/c15-blank",
            name="Blank Cuisine",
            address="16 Cuisine Road",
            cuisines="",
        ),
        raw_row(url="https://example.test/c16-blank", name="", address="17 Name Road"),
        raw_row(url="https://example.test/c16-space", name="   ", address="18 Name Road"),
        raw_row(
            url="https://example.test/c17-low",
            name="Spice Hub",
            address="1 MG Road",
            votes="10",
        ),
        raw_row(
            url="https://example.test/c17-high",
            name="Spice Hub",
            address="1 MG Road",
            votes="50",
            rate="4.4/5",
        ),
        raw_row(
            url="https://example.test/c18-first",
            name="Equal Votes",
            address="2 MG Road",
            votes="5",
            dish_liked="First dish",
        ),
        raw_row(
            url="https://example.test/c18-second",
            name="Equal Votes",
            address="2 MG Road",
            votes="5",
            dish_liked="Second dish",
        ),
        raw_row(url="https://example.test/c19-a", name="Branch Place", address="Address A", votes="3"),
        raw_row(url="https://example.test/c19-b", name="Branch Place", address="Address B", votes="4"),
        raw_row(
            url="https://example.test/c20-yes",
            name="Flags Yes",
            address="20 Flag Road",
            online_order="Yes",
            book_table="Yes",
        ),
        raw_row(
            url="https://example.test/c20-no",
            name="Flags No",
            address="21 Flag Road",
            online_order="No",
            book_table="No",
        ),
        raw_row(
            url="https://example.test/c20-null",
            name="Flags Null",
            address="22 Flag Road",
            online_order=None,
            book_table=None,
        ),
        raw_row(
            url="https://example.test/c20-lower",
            name="Flags Lower",
            address="23 Flag Road",
            online_order="yes",
            book_table="yes",
        ),
        raw_row(
            url="https://example.test/c21",
            name="Long Dish",
            address="24 Dish Road",
            dish_liked=dish,
        ),
        raw_row(
            url="https://example.test/c22",
            name="Null Dish",
            address="25 Dish Road",
            dish_liked=None,
        ),
        raw_row(
            url="https://example.test/c24",
            name="  CafÃ© Down The Alley  ",
            address="  26 Alley Road  ",
            location="  Banashankari  ",
            **{"listed_in(city)": "  Basavanagudi  "},
        ),
    ]
    return clean_restaurants(_frame(rows, heavy=True))


def _row(frame: pd.DataFrame, url: str) -> pd.Series:
    matches = frame.loc[frame["url"] == url]
    assert len(matches) == 1
    return matches.iloc[0]


def test_c1_normal_rating(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c1")["rating"] == pytest.approx(4.1)


def test_c2_rating_with_spaces(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c2")["rating"] == pytest.approx(4.1)


def test_c3_new_listing_rating_is_null(cleaned: pd.DataFrame):
    assert pd.isna(_row(cleaned, "https://example.test/c3")["rating"])


def test_c4_dash_rating_is_null(cleaned: pd.DataFrame):
    assert pd.isna(_row(cleaned, "https://example.test/c4")["rating"])


def test_c5_blank_or_null_rating_is_null(cleaned: pd.DataFrame):
    assert pd.isna(_row(cleaned, "https://example.test/c5-blank")["rating"])
    assert pd.isna(_row(cleaned, "https://example.test/c5-null")["rating"])


def test_c6_rating_without_slash(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c6")["rating"] == pytest.approx(4.1)


def test_c7_non_numeric_rating_is_null(cleaned: pd.DataFrame):
    assert pd.isna(_row(cleaned, "https://example.test/c7")["rating"])


def test_c8_cost_with_thousands_comma(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c1")["cost_for_two"] == 1200


def test_c9_cost_with_spaces(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c9")["cost_for_two"] == 800


def test_c10_unparseable_cost_is_null(cleaned: pd.DataFrame):
    for url in (
        "https://example.test/c10-blank",
        "https://example.test/c10-dash",
        "https://example.test/c10-null",
    ):
        assert pd.isna(_row(cleaned, url)["cost_for_two"])


def test_c11_votes_with_comma(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c1")["votes"] == 2556


def test_c12_missing_votes_are_zero(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c12")["votes"] == 0


def test_c13_cuisine_list(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c1")["cuisines"] == ["Cafe", "Mexican", "Italian"]


def test_c14_cuisine_extra_spaces_and_empty_tokens(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c14")["cuisines"] == ["Cafe", "Italian", "Thai"]


def test_c15_missing_cuisines_are_an_empty_list(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c15-null")["cuisines"] == []
    assert _row(cleaned, "https://example.test/c15-blank")["cuisines"] == []


def test_c16_blank_name_rows_are_dropped(cleaned: pd.DataFrame):
    assert "https://example.test/c16-blank" not in set(cleaned["url"])
    assert "https://example.test/c16-space" not in set(cleaned["url"])


def test_c17_dedupe_keeps_higher_vote_row(cleaned: pd.DataFrame):
    kept = cleaned.loc[cleaned["name"] == "Spice Hub"]
    assert len(kept) == 1
    assert kept.iloc[0]["votes"] == 50
    assert kept.iloc[0]["url"] == "https://example.test/c17-high"


def test_c18_equal_votes_keep_the_first_row(cleaned: pd.DataFrame):
    kept = cleaned.loc[cleaned["name"] == "Equal Votes"]
    assert len(kept) == 1
    assert kept.iloc[0]["url"] == "https://example.test/c18-first"
    assert kept.iloc[0]["dish_liked"] == "First dish"


def test_c19_same_name_different_address_both_remain(cleaned: pd.DataFrame):
    kept = cleaned.loc[cleaned["name"] == "Branch Place"]
    assert set(kept["address"]) == {"Address A", "Address B"}


def test_c20_only_exact_yes_is_true(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c20-yes")["online_order"]
    assert _row(cleaned, "https://example.test/c20-yes")["book_table"]
    for url in (
        "https://example.test/c20-no",
        "https://example.test/c20-null",
        "https://example.test/c20-lower",
    ):
        row = _row(cleaned, url)
        assert bool(row["online_order"]) is False
        assert bool(row["book_table"]) is False


def test_c21_long_dish_liked_is_truncated(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c21")["dish_liked"] == "P" * 200


def test_c22_null_dish_liked_is_empty(cleaned: pd.DataFrame):
    assert _row(cleaned, "https://example.test/c22")["dish_liked"] == ""


def test_c23_heavy_columns_are_absent(cleaned: pd.DataFrame):
    assert list(cleaned.columns) == CLEANED_COLUMNS
    for column in ("phone", "reviews_list", "menu_item", "rate", "listed_in(city)"):
        assert column not in cleaned.columns


def test_c23_reviews_list_is_not_required():
    frame = _frame([raw_row(url="https://example.test/plain")])
    assert "reviews_list" not in frame.columns
    cleaned = clean_restaurants(frame)
    assert list(cleaned.columns) == CLEANED_COLUMNS
    assert cleaned.iloc[0]["url"] == "https://example.test/plain"


def test_c24_name_is_kept_after_strip(cleaned: pd.DataFrame):
    row = _row(cleaned, "https://example.test/c24")
    assert row["name"] == "CafÃ© Down The Alley"
    assert row["address"] == "26 Alley Road"
    assert row["location"] == "Banashankari"
    assert row["listed_in_city"] == "Basavanagudi"


def test_c29_every_blank_name_yields_an_empty_frame():
    frame = _frame(
        [
            raw_row(name="", url="https://example.test/blank-1"),
            raw_row(name="   ", url="https://example.test/blank-2"),
        ]
    )
    cleaned = clean_restaurants(frame)
    assert cleaned.empty
    assert list(cleaned.columns) == CLEANED_COLUMNS
