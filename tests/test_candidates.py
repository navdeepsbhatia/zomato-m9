"""Offline candidate filter tests. Case ids match docs/edge-case.md."""

import math

import pandas as pd
import pytest

from recommender.config import Settings
from recommender.filtering.candidates import (
    apply_filters,
    budget_bounds,
    score_candidates,
    shortlist,
)
from recommender.models import UserPreferences


def restaurant(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "name": "Sample",
        "address": "1 Road",
        "location": "Banashankari",
        "listed_in_city": "Banashankari",
        "cuisines": ["Italian"],
        "cost_for_two": 500,
        "rating": 4.1,
        "votes": 100,
        "rest_type": "Casual Dining",
        "online_order": True,
        "book_table": False,
        "dish_liked": "Pasta",
        "url": "https://example.test/sample",
    }
    row.update(overrides)
    return row


def table(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def preferences(**overrides: object) -> UserPreferences:
    values: dict[str, object] = {
        "location": "Banashankari",
        "budget": "medium",
        "cuisine": "Italian",
        "min_rating": 3.5,
    }
    values.update(overrides)
    return UserPreferences.model_validate(values)


def names(frame: pd.DataFrame) -> list[str]:
    return [str(name) for name in frame["name"]]


def test_budget_bounds_follow_settings():
    settings = Settings(
        budget_low_min=10,
        budget_low_max=500,
        budget_medium_min=501,
        budget_medium_max=900,
        budget_high_min=901,
    )

    assert budget_bounds("low", settings) == (10, 500)
    assert budget_bounds("medium", settings) == (501, 900)
    assert budget_bounds("high", settings) == (901, None)

    frame = table(
        [
            restaurant(name="Inside", cost_for_two=500),
            restaurant(name="Outside", cost_for_two=501, address="2 Road"),
        ]
    )
    kept = apply_filters(frame, preferences(budget="low"), settings)
    assert names(kept) == ["Inside"]


def test_widened_low_budget_follows_settings():
    settings = Settings(
        budget_low_min=1,
        budget_low_max=100,
        budget_medium_min=101,
        budget_medium_max=150,
        budget_high_min=151,
    )
    frame = table(
        [
            restaurant(name="Low", cost_for_two=100),
            restaurant(name="Medium", cost_for_two=150, address="2 Road"),
            restaurant(name="High", cost_for_two=151, address="3 Road"),
        ]
    )
    widened = apply_filters(
        frame,
        preferences(budget="low"),
        settings,
        budget_mode="widened",
    )
    assert names(widened) == ["Low", "Medium"]


def test_f1_exact_neighborhood_matches_location():
    frame = table(
        [
            restaurant(name="Here", location="Banashankari", listed_in_city="Basavanagudi"),
            restaurant(
                name="Elsewhere",
                location="Jayanagar",
                listed_in_city="Jayanagar",
                address="2 Road",
            ),
        ]
    )
    result = apply_filters(frame, preferences(location="Banashankari"), Settings())
    assert names(result) == ["Here"]


def test_f2_location_match_is_case_insensitive():
    frame = table(
        [
            restaurant(name="Here", location="Banashankari", listed_in_city="Basavanagudi"),
        ]
    )
    result = apply_filters(frame, preferences(location="banashankari"), Settings())
    assert names(result) == ["Here"]


def test_f3_listed_city_matches_when_neighborhood_differs():
    frame = table(
        [
            restaurant(name="Filed here", location="Jayanagar", listed_in_city="Banashankari"),
            restaurant(
                name="Elsewhere",
                location="Jayanagar",
                listed_in_city="Jayanagar",
                address="2 Road",
            ),
        ]
    )
    result = apply_filters(frame, preferences(location="Banashankari"), Settings())
    assert names(result) == ["Filed here"]


def test_f4_user_text_contained_in_location_or_city():
    frame = table(
        [
            restaurant(name="In location", location="Banashankari", listed_in_city="Basavanagudi"),
            restaurant(
                name="In city",
                location="Jayanagar",
                listed_in_city="Banashankari",
                address="2 Road",
            ),
            restaurant(
                name="Neither",
                location="Jayanagar",
                listed_in_city="Jayanagar",
                address="3 Road",
            ),
        ]
    )
    result = apply_filters(frame, preferences(location="Banas"), Settings())
    assert names(result) == ["In location", "In city"]


def test_f6_cuisine_matches_any_token():
    frame = table(
        [
            restaurant(name="Mixed", cuisines=["Cafe", "Mexican", "Italian"]),
            restaurant(name="Text", cuisines="Cafe, Mexican, Italian", address="2 Road"),
            restaurant(name="Other", cuisines=["Chinese", "Thai"], address="3 Road"),
        ]
    )
    result = apply_filters(frame, preferences(cuisine="Italian"), Settings())
    assert names(result) == ["Mixed", "Text"]


def test_f7_cuisine_match_is_case_insensitive():
    frame = table([restaurant(name="Italian place", cuisines=["Italian"])])
    result = apply_filters(frame, preferences(cuisine="italian"), Settings())
    assert names(result) == ["Italian place"]


def test_f8_partial_cuisine_token_does_not_match():
    frame = table(
        [
            restaurant(name="North", cuisines=["North Indian"]),
            restaurant(name="Plain", cuisines=["Indian"], address="2 Road"),
        ]
    )
    result = apply_filters(frame, preferences(cuisine="Indian"), Settings())
    assert names(result) == ["Plain"]


def test_f9_multi_word_cuisine_token_matches():
    frame = table(
        [
            restaurant(name="North", cuisines=["North Indian"]),
            restaurant(name="Plain", cuisines=["Indian"], address="2 Road"),
        ]
    )
    result = apply_filters(frame, preferences(cuisine="North Indian"), Settings())
    assert names(result) == ["North"]


def test_f10_rating_equal_to_the_minimum_is_kept():
    frame = table(
        [
            restaurant(name="Equal", rating=4.0),
            restaurant(name="Above", rating=4.2, address="2 Road"),
        ]
    )
    result = apply_filters(frame, preferences(min_rating=4.0), Settings())
    assert names(result) == ["Equal", "Above"]


def test_f11_rating_below_the_minimum_is_excluded():
    frame = table(
        [
            restaurant(name="Below", rating=3.9),
            restaurant(name="Equal", rating=4.0, address="2 Road"),
        ]
    )
    result = apply_filters(frame, preferences(min_rating=4.0), Settings())
    assert names(result) == ["Equal"]


def test_f12_null_rating_fails_every_minimum_including_zero():
    frame = table(
        [
            restaurant(name="Zero", rating=0.0),
            restaurant(name="Missing", rating=None, address="2 Road"),
        ]
    )
    result = apply_filters(frame, preferences(min_rating=0.0), Settings())
    assert names(result) == ["Zero"]


def test_f13_low_budget_edges():
    frame = table(
        [
            restaurant(name="Floor", cost_for_two=1),
            restaurant(name="Ceiling", cost_for_two=400, address="2 Road"),
            restaurant(name="Next", cost_for_two=401, address="3 Road"),
        ]
    )
    result = apply_filters(frame, preferences(budget="low"), Settings())
    assert names(result) == ["Floor", "Ceiling"]


def test_f14_medium_budget_edges():
    frame = table(
        [
            restaurant(name="Below", cost_for_two=400),
            restaurant(name="Floor", cost_for_two=401, address="2 Road"),
            restaurant(name="Ceiling", cost_for_two=800, address="3 Road"),
            restaurant(name="Above", cost_for_two=801, address="4 Road"),
        ]
    )
    result = apply_filters(frame, preferences(budget="medium"), Settings())
    assert names(result) == ["Floor", "Ceiling"]


def test_f15_high_budget_edge():
    frame = table(
        [
            restaurant(name="Below", cost_for_two=800),
            restaurant(name="Floor", cost_for_two=801, address="2 Road"),
            restaurant(name="Above", cost_for_two=2000, address="3 Road"),
        ]
    )
    result = apply_filters(frame, preferences(budget="high"), Settings())
    assert names(result) == ["Floor", "Above"]


def test_f16_null_cost_is_excluded_for_every_budget():
    for budget, priced in (("low", 200), ("medium", 500), ("high", 900)):
        frame = table(
            [
                restaurant(name="Priced", cost_for_two=priced),
                restaurant(name="Unknown", cost_for_two=None, address="2 Road"),
            ]
        )
        result = apply_filters(frame, preferences(budget=budget), Settings())
        assert names(result) == ["Priced"]


def test_f17_zero_cost_is_outside_the_low_band():
    frame = table(
        [
            restaurant(name="Free", cost_for_two=0),
            restaurant(name="Low", cost_for_two=1, address="2 Road"),
        ]
    )
    result = apply_filters(frame, preferences(budget="low"), Settings())
    assert names(result) == ["Low"]


def test_f18_all_four_filters_keep_only_full_matches():
    frame = table(
        [
            restaurant(name="Match"),
            restaurant(
                name="Other place",
                location="Jayanagar",
                listed_in_city="Jayanagar",
                address="2 Road",
            ),
            restaurant(name="Other cuisine", cuisines=["Chinese"], address="3 Road"),
            restaurant(name="Low rating", rating=3.0, address="4 Road"),
            restaurant(name="Pricey", cost_for_two=900, address="5 Road"),
            restaurant(name="Null rating", rating=None, address="6 Road"),
            restaurant(name="Null cost", cost_for_two=None, address="7 Road"),
        ]
    )
    result = apply_filters(frame, preferences(), Settings())
    assert names(result) == ["Match"]


def test_score_is_rating_times_log_one_plus_votes():
    frame = table(
        [
            restaurant(name="Voted", rating=4.0, votes=10),
            restaurant(name="Zero", rating=4.0, votes=0, address="2 Road"),
            restaurant(name="Unrated", rating=None, votes=80, address="3 Road"),
        ]
    )
    scored = score_candidates(frame)
    assert scored.loc[scored["name"] == "Voted", "score"].item() == pytest.approx(
        4.0 * math.log(1 + 10)
    )
    assert scored.loc[scored["name"] == "Zero", "score"].item() == 0.0
    assert scored.loc[scored["name"] == "Unrated", "score"].item() == 0.0


def test_r1_exact_match_does_not_relax():
    frame = table(
        [
            restaurant(name="Exact"),
            restaurant(
                name="Other cuisine",
                cuisines=["Chinese"],
                rating=5.0,
                votes=10_000,
                address="2 Road",
            ),
        ]
    )
    result, notes = shortlist(frame, preferences(), Settings())
    assert notes == []
    assert names(result) == ["Exact"]


def test_blank_cuisine_keeps_every_cuisine_in_the_neighborhood():
    frame = table(
        [
            restaurant(name="Italian"),
            restaurant(name="Chinese", cuisines=["Chinese"], address="2 Road"),
        ]
    )
    result, notes = shortlist(frame, preferences(cuisine=""), Settings())
    assert notes == []
    assert names(result) == ["Italian", "Chinese"]


def test_r2_impossible_cuisine_drops_only_cuisine():
    frame = table(
        [
            restaurant(name="Nearby", cuisines=["Chinese"]),
            restaurant(
                name="Too far",
                location="Jayanagar",
                listed_in_city="Jayanagar",
                cuisines=["Chinese"],
                address="2 Road",
            ),
            restaurant(name="Low rating", cuisines=["Chinese"], rating=2.0, address="3 Road"),
            restaurant(
                name="Too costly",
                cuisines=["Chinese"],
                cost_for_two=900,
                address="4 Road",
            ),
            restaurant(
                name="Italian outside the band",
                cuisines=["Italian"],
                cost_for_two=900,
                rating=5.0,
                votes=10_000,
                address="5 Road",
            ),
        ]
    )
    result, notes = shortlist(frame, preferences(cuisine="Sushi"), Settings())
    assert notes == ["cuisine"]
    assert names(result) == ["Nearby"]


def test_r3_budget_widens_only_after_cuisine_is_dropped():
    frame = table(
        [
            restaurant(name="Neighbor band", cuisines=["Chinese"], cost_for_two=600),
            restaurant(
                name="Beyond the widened band",
                cuisines=["Italian"],
                cost_for_two=2000,
                address="2 Road",
            ),
        ]
    )
    result, notes = shortlist(
        frame,
        preferences(budget="low", cuisine="Italian"),
        Settings(),
    )
    assert notes == ["cuisine", "budget"]
    assert names(result) == ["Neighbor band"]


def test_r4_low_budget_widens_through_medium():
    frame = table(
        [
            restaurant(name="Floor", cost_for_two=1),
            restaurant(name="Low edge", cost_for_two=400, address="2 Road"),
            restaurant(name="Medium floor", cost_for_two=401, address="3 Road"),
            restaurant(name="Medium edge", cost_for_two=800, address="4 Road"),
            restaurant(name="High", cost_for_two=801, address="5 Road"),
            restaurant(name="Free", cost_for_two=0, address="6 Road"),
            restaurant(name="Unknown", cost_for_two=None, address="7 Road"),
        ]
    )
    widened = apply_filters(frame, preferences(budget="low"), Settings(), budget_mode="widened")
    assert names(widened) == ["Floor", "Low edge", "Medium floor", "Medium edge"]

    only_medium = table(
        [
            restaurant(name="Medium edge", cost_for_two=800, cuisines=["Chinese"]),
            restaurant(name="High", cost_for_two=801, cuisines=["Chinese"], address="2 Road"),
        ]
    )
    result, notes = shortlist(
        only_medium,
        preferences(budget="low", cuisine="Italian"),
        Settings(),
    )
    assert notes == ["cuisine", "budget"]
    assert names(result) == ["Medium edge"]


def test_r5_medium_budget_widens_to_low_and_high():
    frame = table(
        [
            restaurant(name="Free", cost_for_two=0),
            restaurant(name="Floor", cost_for_two=1, address="2 Road"),
            restaurant(name="Low edge", cost_for_two=400, address="3 Road"),
            restaurant(name="Medium", cost_for_two=800, address="4 Road"),
            restaurant(name="High", cost_for_two=801, address="5 Road"),
            restaurant(name="Far", cost_for_two=5000, address="6 Road"),
            restaurant(name="Unknown", cost_for_two=None, address="7 Road"),
        ]
    )
    widened = apply_filters(
        frame,
        preferences(budget="medium"),
        Settings(),
        budget_mode="widened",
    )
    assert names(widened) == ["Floor", "Low edge", "Medium", "High", "Far"]

    only_low = table(
        [
            restaurant(name="Cheap", cost_for_two=1, cuisines=["Chinese"]),
            restaurant(name="Free", cost_for_two=0, cuisines=["Chinese"], address="2 Road"),
        ]
    )
    result, notes = shortlist(
        only_low,
        preferences(budget="medium", cuisine="Italian"),
        Settings(),
    )
    assert notes == ["cuisine", "budget"]
    assert names(result) == ["Cheap"]


def test_r6_high_budget_widens_through_medium():
    frame = table(
        [
            restaurant(name="Low", cost_for_two=400),
            restaurant(name="Medium floor", cost_for_two=401, address="2 Road"),
            restaurant(name="Medium edge", cost_for_two=800, address="3 Road"),
            restaurant(name="High", cost_for_two=801, address="4 Road"),
            restaurant(name="Unknown", cost_for_two=None, address="5 Road"),
        ]
    )
    widened = apply_filters(frame, preferences(budget="high"), Settings(), budget_mode="widened")
    assert names(widened) == ["Medium floor", "Medium edge", "High"]

    only_medium = table(
        [
            restaurant(name="Medium floor", cost_for_two=401, cuisines=["Chinese"]),
            restaurant(name="Low", cost_for_two=400, cuisines=["Chinese"], address="2 Road"),
        ]
    )
    result, notes = shortlist(
        only_medium,
        preferences(budget="high", cuisine="Italian"),
        Settings(),
    )
    assert notes == ["cuisine", "budget"]
    assert names(result) == ["Medium floor"]


def test_r7_minimum_rating_drops_last():
    frame = table(
        [
            restaurant(name="Below", rating=3.0, votes=20, cuisines=["Chinese"], cost_for_two=200),
            restaurant(
                name="Missing",
                rating=None,
                votes=5,
                cuisines=["Chinese"],
                cost_for_two=200,
                address="2 Road",
            ),
            restaurant(
                name="No price",
                rating=2.0,
                cuisines=["Chinese"],
                cost_for_two=None,
                address="3 Road",
            ),
        ]
    )
    result, notes = shortlist(
        frame,
        preferences(cuisine="Sushi", budget="low", min_rating=4.0),
        Settings(),
    )
    assert notes == ["cuisine", "budget", "min_rating"]
    assert names(result) == ["Below", "Missing"]
    assert "No price" not in names(result)


def test_r8_unknown_location_returns_empty_after_full_relaxation():
    frame = table([restaurant(name="Real", location="Banashankari")])
    result, notes = shortlist(frame, preferences(location="Delhi"), Settings())
    assert result.empty
    assert notes == ["cuisine", "budget", "min_rating"]
    assert "score" in result.columns


def test_r9_additional_preferences_are_not_a_filter():
    frame = table(
        [
            restaurant(
                name="Kept",
                rest_type="Quick Bites",
                online_order=True,
                book_table=True,
            ),
            restaurant(name="Other cuisine", cuisines=["Chinese"], address="2 Road"),
        ]
    )
    plain, plain_notes = shortlist(frame, preferences(additional_preferences=""), Settings())
    noted, noted_notes = shortlist(
        frame,
        preferences(additional_preferences="family-friendly, quick service"),
        Settings(),
    )
    assert names(plain) == names(noted) == ["Kept"]
    assert plain_notes == noted_notes == []
    assert plain.loc[0, "rest_type"] == "Quick Bites"
    assert bool(plain.loc[0, "online_order"]) is True
    assert bool(plain.loc[0, "book_table"]) is True


def test_r10_shortlist_keeps_the_highest_scores_up_to_the_cap():
    frame = table(
        [
            restaurant(
                name=f"Place {index:02d}",
                address=f"{index} Road",
                url=f"https://example.test/{index}",
                rating=4.0,
                votes=index,
            )
            for index in range(1, 41)
        ]
    )
    result, notes = shortlist(frame, preferences(), Settings(candidate_limit=15))
    assert notes == []
    assert names(result) == [f"Place {index:02d}" for index in range(40, 25, -1)]
    scores = [float(score) for score in result["score"]]
    assert scores == sorted(scores, reverse=True)
    assert len(result) == 15


def test_r11_shortlist_returns_every_row_under_the_cap():
    frame = table(
        [
            restaurant(name="A", votes=1),
            restaurant(name="B", votes=5, address="2 Road"),
            restaurant(name="C", votes=3, address="3 Road"),
        ]
    )
    result, notes = shortlist(frame, preferences(), Settings(candidate_limit=15))
    assert notes == []
    assert names(result) == ["B", "C", "A"]


def test_r12_tied_scores_keep_original_order():
    frame = table(
        [
            restaurant(name="First", rating=4.2, votes=8),
            restaurant(name="Second", rating=4.2, votes=8, address="2 Road"),
            restaurant(name="Third", rating=4.2, votes=8, address="3 Road"),
        ]
    )
    result, _notes = shortlist(frame, preferences(), Settings())
    assert names(result) == ["First", "Second", "Third"]


def test_r13_zero_votes_score_zero_and_rank_last():
    frame = table(
        [
            restaurant(name="Unvoted", rating=4.0, votes=0),
            restaurant(name="Voted", rating=4.0, votes=10, address="2 Road"),
        ]
    )
    result, notes = shortlist(frame, preferences(), Settings())
    assert notes == []
    assert names(result) == ["Voted", "Unvoted"]
    assert result.loc[result["name"] == "Unvoted", "score"].item() == 0.0
    assert result.loc[result["name"] == "Voted", "score"].item() == pytest.approx(
        4.0 * math.log(1 + 10)
    )


def test_r14_null_rating_scores_zero_after_the_rating_filter_drops():
    frame = table(
        [
            restaurant(
                name="Unrated",
                rating=None,
                votes=400,
                cuisines=["Chinese"],
                cost_for_two=200,
            ),
            restaurant(
                name="Rated",
                rating=3.0,
                votes=50,
                cuisines=["Chinese"],
                cost_for_two=200,
                address="2 Road",
            ),
        ]
    )
    result, notes = shortlist(
        frame,
        preferences(cuisine="Sushi", budget="low", min_rating=4.0),
        Settings(),
    )
    assert notes == ["cuisine", "budget", "min_rating"]
    assert names(result) == ["Rated", "Unrated"]
    assert result.loc[result["name"] == "Unrated", "score"].item() == 0.0
    assert result.loc[result["name"] == "Rated", "score"].item() == pytest.approx(
        3.0 * math.log(1 + 50)
    )


def test_shortlist_does_not_mutate_the_input_frame():
    frame = table([restaurant()])
    before = frame.copy()
    shortlist(frame, preferences(), Settings())
    pd.testing.assert_frame_equal(frame, before)
