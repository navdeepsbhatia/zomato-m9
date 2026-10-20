# Evaluation

How to judge this project against [implementation-plan.md](implementation-plan.md). A phase passes only when every exit check for that phase passes. The project passes when Phase 8 passes, which includes the offline suite from Phases 3–6 and the manual UI cases.

All product code is Python. Automated checks stay offline: `pytest` must not download Hugging Face and must not call a live LLM. Use in-memory frames and a fake client. Detailed inputs and expected results for those tests live in [edge-case.md](edge-case.md).

## How to score

Each check is pass or fail. Record the command output or the screen you saw.

| Result | Rule |
| --- | --- |
| Pass | The expected behavior in that check happened. |
| Fail | The behavior was missing, wrong, or the check raised an unexpected error. |
| Blocked | An earlier phase failed, so this check could not run. |

There is no partial credit inside a check. A phase passes when all of its checks pass.

Run the eval in phase order. Fix a failing phase before scoring the next one.

## Phase 1 — Project foundation

| ID | Check | Pass when |
| --- | --- | --- |
| E1.1 | Install | `pip install -r requirements.txt` completes. The file lists `datasets`, `pandas`, `pyarrow`, `pydantic`, `openai`, `python-dotenv`, `streamlit`, and `pytest`. |
| E1.2 | Layout | These paths exist: `app/main.py`, `app/server.py`, `src/recommender/__init__.py`, `src/recommender/config.py`, `src/recommender/health.py`, `src/recommender/data/__init__.py`, `src/recommender/filtering/__init__.py`, `src/recommender/llm/__init__.py`, `tests/`, `data/processed/.gitkeep`. |
| E1.3 | Env template | `.env.example` lists `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `DATA_CACHE_PATH`, `CANDIDATE_LIMIT`, and `DEFAULT_TOP_N`. |
| E1.4 | Ignore rules | `.gitignore` covers `.env`, `__pycache__/`, `.pytest_cache/`, `.venv/`, and `data/processed/*.csv`. |
| E1.5 | Defaults | With the optional variables unset, `Settings` uses candidate limit 15, top-n 5, and budget bands low 1–400, medium 401–800, high 801 and above. |
| E1.6 | Secrets | `.env.example` is present for commit. A real `.env` is ignored. |

## Phase 2 — Domain models

| ID | Check | Pass when |
| --- | --- | --- |
| E2.1 | Models | `src/recommender/models.py` defines `UserPreferences`, `Restaurant`, `Recommendation`, and `RecommendationResult`. |
| E2.2 | Preference fields | `UserPreferences` has location, budget (`low`, `medium`, `high`), cuisine, `min_rating`, `additional_preferences`, and `top_n`. |
| E2.3 | Result fields | `Recommendation` has rank, name, cuisines, rating, cost for two, explanation, and url. `RecommendationResult` has preferences, summary, items, `candidate_count`, `relaxed_filters`, and source `llm` or `fallback`. |
| E2.4 | Invalid input | Budget outside the three labels, `min_rating` outside 0–5, and blank location or cuisine raise validation errors. |
| E2.5 | Round trip | A valid `UserPreferences` survives `model_dump` then `model_validate` with the same field values. Stripped location and cuisine stay stripped. |

## Phase 3 — Data ingestion and cache

Command: `pytest tests/test_cleaner.py`

The test file must not open a network connection.

| ID | Check | Pass when |
| --- | --- | --- |
| E3.1 | Cleaner tests | `pytest tests/test_cleaner.py` passes. |
| E3.2 | Ratings | `4.1/5` becomes 4.1. `NEW`, `-`, and blank become null. |
| E3.3 | Cost and votes | A cost with a comma parses to an int. Unparseable cost becomes null. Votes with a comma parse to an int. Missing votes become 0. |
| E3.4 | Cuisines | Comma-separated cuisines become stripped tokens. Null becomes an empty list. |
| E3.5 | Dedupe | Same normalized name and address collapse to the row with the higher vote count. |
| E3.6 | Dropped columns | `phone`, `reviews_list`, and `menu_item` are absent from the cleaned frame. |
| E3.7 | Working columns | Cleaned output includes name, address, location, `listed_in_city`, cuisines, `cost_for_two`, rating, votes, `rest_type`, `online_order`, `book_table`, `dish_liked`, and url. |
| E3.8 | First cache build | A manual load with no CSV file writes `data/processed/restaurants.csv`. |
| E3.9 | Cache hit | A second load reads that file and does not call `load_dataset`. |
| E3.10 | Download failure | If the download fails and the cache file is missing, the loader raises. The caller does not continue to the LLM. |

E3.8–E3.10 are manual. E3.1–E3.7 are the automated gate for this phase.

## Phase 4 — Candidate filtering

Command: `pytest tests/test_candidates.py`

| ID | Check | Pass when |
| --- | --- | --- |
| E4.1 | Filter tests | `pytest tests/test_candidates.py` passes. |
| E4.2 | Combined filters | A known neighborhood, cuisine, rating, and budget return only rows that match all four. |
| E4.3 | Location | Match is case-insensitive and succeeds when the user text equals or is contained in `location` or `listed_in_city`. |
| E4.4 | Cuisine token | `Italian` matches a token inside `Cafe, Mexican, Italian`. A query that is only part of a token, such as `Indian` against `North Indian`, does not match. |
| E4.5 | Rating | Rows with `rating >= min_rating` stay. Null ratings drop while the rating filter is on. |
| E4.6 | Budget edges | Low includes 1 and 400. Medium includes 401 and 800. High includes 801 and above. Null cost drops. |
| E4.7 | Relaxation order | Exact match leaves `relaxed_filters` empty. An impossible cuisine returns rows and records `cuisine`. The budget widens only after cuisine is dropped. Minimum rating drops last. |
| E4.8 | Budget widen | Low also accepts medium. Medium accepts low and high. High also accepts medium. |
| E4.9 | No location match | An unknown location returns an empty frame and records `cuisine`, `budget`, and `min_rating`. Location stays required. |
| E4.10 | Shortlist size | Results are ordered by `rating * log(1 + votes)` descending and capped at `candidate_limit` (default 15). |
| E4.11 | Free text | `additional_preferences` does not add or remove rows. |

## Health endpoint

Command: `pytest tests/test_health.py`

The probe is local. It does not download Hugging Face and does not call the model.

| ID | Check | Pass when |
| --- | --- | --- |
| EH.1 | Health tests | `pytest tests/test_health.py` passes with no network. |
| EH.2 | Ready | A readable cache and a set key return `status` `ok` and HTTP 200. The body does not contain the key. |
| EH.3 | No key | A readable cache and a blank key return `degraded` and HTTP 200. The LLM check names the fallback. |
| EH.4 | No cache | A missing cache returns `unavailable` and HTTP 503, and does not call `load_dataset`. |
| EH.5 | Bad cache | An unreadable cache returns `unavailable` and HTTP 503, and does not download the dataset again. |

## Phase 5 — LLM prompt, client, and parser

Command: `pytest tests/test_parser.py`

Parser tests use fixture JSON. They do not call the provider.

| ID | Check | Pass when |
| --- | --- | --- |
| E5.1 | Parser tests | `pytest tests/test_parser.py` passes. |
| E5.2 | Prompt shape | `build_messages` returns a system message and a user message. The user message includes preferences and the candidate fields name, location, cuisines, `cost_for_two`, rating, votes, `rest_type`, `online_order`, `book_table`, and `dish_liked`. |
| E5.3 | Prompt size | The payload contains no `reviews_list`, `menu_item`, or `phone`. |
| E5.4 | Grounded facts | For valid JSON, cuisine, rating, cost, and url on each recommendation are copied from the matching candidate. A rating or cost written by the model is ignored. |
| E5.5 | Unknown name | A restaurant name absent from the candidate frame is dropped. |
| E5.6 | All names unknown | Non-JSON, or JSON whose names are all unknown, raises `InvalidModelOutput`. |
| E5.7 | Partial list | When at least one name matches and fewer than `top_n` remain, the parser pads from unused candidates in score order. |
| E5.8 | Client contract | `LLMClient.complete` returns the message string. It uses temperature 0.2 and JSON object response format. Timeouts and HTTP errors propagate. Parsing stays in the parser. |

## Phase 6 — Recommendation service

Command: `pytest tests/test_service.py`

Use a fake client and a tiny frame.

| ID | Check | Pass when |
| --- | --- | --- |
| E6.1 | Service tests | `pytest tests/test_service.py` passes. |
| E6.2 | Success path | Valid model JSON yields `source="llm"` and facts from the candidate rows. |
| E6.3 | Padding still counts as llm | A partial parsed list padded to `top_n` keeps `source="llm"`. |
| E6.4 | Invalid model output | `InvalidModelOutput` yields `source="fallback"` and the same candidate facts. |
| E6.5 | Missing key | A blank or unset `LLM_API_KEY` returns fallback cards and does not raise. |
| E6.6 | Transport failure | Timeout and HTTP errors return fallback cards. |
| E6.7 | Fallback content | Fallback summary says ordering used rating and number of votes. Each explanation names cuisine, rating, cost for two, and location, and does not claim the model wrote it. |
| E6.8 | Empty shortlist | `items` is empty, `candidate_count` is 0, relaxation notes are present, and the summary restates the filters. The client is not called. |
| E6.9 | Download failure | A missing cache plus a failed download raises before any LLM call. |

## Phase 7 — Streamlit UI

Start with `streamlit run app/server.py`. That serves `app/main.py` and `GET /api/health`.

| ID | Check | Pass when |
| --- | --- | --- |
| E7.1 | App opens | The form renders. |
| E7.2 | Imports | `app/main.py` calls `RecommendationService` and the domain models. It does not import `datasets` or `openai`. |
| E7.3 | Controls | Location text (placeholder Banashankari), budget select of low/medium/high, cuisine text (placeholder Italian), rating slider 0.0–5.0 step 0.1 default 3.5, additional-preferences text area, and a submit button are present. |
| E7.4 | Main query | Banashankari, medium, Italian, minimum rating 3.5 shows up to five cards. Each card has name, cuisine, rating, cost, and an explanation. |
| E7.5 | Card fields | Each card also shows rank and a link to `url`. |
| E7.6 | No API key | The same submit still shows cards and a fallback note that live explanations need a key. |
| E7.7 | Relaxation note | A query that widens a filter shows which constraints were relaxed. |
| E7.8 | Empty state | A location that matches nothing shows an empty state restating location, cuisine, budget, and minimum rating. |
| E7.9 | Validation | A blank location or cuisine shows the Pydantic error on the form and does not run a recommendation. |
| E7.10 | Cache error | A failed download with no cache shows a page error and skips the recommendation call. |
| E7.11 | Health route | `GET /api/health` returns the readiness JSON. A readable cache and a set key are `ok` with HTTP 200. A missing key is `degraded` with HTTP 200. A missing or unreadable cache is `unavailable` with HTTP 503. The body does not contain the key, and the probe does not download the dataset or call the model. |

## Phase 8 — End-to-end

Run this only after E1 through E7 are scored.

### Automated

```text
pytest tests/test_cleaner.py tests/test_candidates.py tests/test_health.py tests/test_parser.py tests/test_service.py
```

| ID | Check | Pass when |
| --- | --- | --- |
| E8.1 | Full offline suite | The command above passes with no network and no live LLM call. |

### Manual script

Run the app twice.

| ID | Check | Pass when |
| --- | --- | --- |
| E8.2 | First launch | The first run creates `data/processed/restaurants.csv`. |
| E8.3 | Second launch | The second run starts from that file and does not download the dataset again. |
| E8.4 | Grounded happy path | Banashankari, Italian, medium, rating 3.5, additional text `quick service` shows up to 5 cards. Name, cuisine, rating, and cost match the cached row. The explanation refers to the fit. |
| E8.5 | Cuisine relaxation | A cuisine that exists only in another neighborhood still returns results, and `cuisine` appears in the relaxation note. |
| E8.6 | Unknown location | Location text that matches nothing shows the empty state. The page does not dump an LLM traceback. |
| E8.7 | Key removed | With `LLM_API_KEY` removed, cards use fallback ranking and the fallback note is visible. |
| E8.8 | Key present | With `LLM_API_KEY` and `LLM_MODEL` set, source is llm and the explanations are model-written sentences. |
| E8.9 | No invented rows | Every card name is in the final shortlist. Rating and cost on the card equal the cached row for that restaurant. |
| E8.10 | Workflow coverage | One live run shows all five stages: cached dataset, preference form, filtered shortlist, ranked explanations, and result cards. |
| E8.11 | Git hygiene | The CSV cache is the only derived data file, and it is gitignored. |

## Recommendation quality

Use E8.4 and E8.8, five cards from a live llm response. Score each card, then average.

| Criterion | Pass | Fail |
| --- | --- | --- |
| Faithfulness | Name, cuisine, rating, and cost match the cache. | Any fact disagrees with the cache, or the name was not in the shortlist. |
| Preference fit | The explanation uses the requested cuisine, budget band, rating, or the extra text when that signal is available on the row. | The explanation ignores the preferences and only restates the name. |
| Local facts | Claims about service style use `rest_type`, `online_order`, `book_table`, or `dish_liked` from that row. | The explanation asserts amenities or dishes that are absent from the row. |

A live run passes recommendation quality when every card passes faithfulness, and at least four of five pass preference fit. Local-facts failures fail that card only. They do not by themselves fail the phase if faithfulness passed.

Fallback cards (E8.7) are scored only on faithfulness and on the template rules in E6.7. They are not scored on model-written preference fit.

## Out of scope

Do not fail the project for lacking user accounts, saved searches, a database server, or a vector index. Retrieval is pandas filtering on the cached table.

## Score sheet

| Phase | Checks | Passed | Failed | Blocked | Phase result |
| --- | --- | --- | --- | --- | --- |
| 1 Foundation | E1.1–E1.6 | | | | |
| 2 Models | E2.1–E2.5 | | | | |
| 3 Data | E3.1–E3.10 | | | | |
| 4 Filtering | E4.1–E4.11 | | | | |
| Health | EH.1–EH.5 | | | | |
| 5 LLM | E5.1–E5.8 | | | | |
| 6 Service | E6.1–E6.9 | | | | |
| 7 UI | E7.1–E7.11 | | | | |
| 8 End-to-end | E8.1–E8.11 | | | | |

Project result: pass when Phase 8 is pass.
