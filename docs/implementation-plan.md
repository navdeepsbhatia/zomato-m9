# Implementation Plan

Phase-wise plan for the Python restaurant recommendation app. Each phase builds on the previous one and stays inside the design in [architecture.md](architecture.md) and the scope in [problemStatement.md](problemStatement.md).

All code is Python. Tests stay offline: no Hugging Face download and no live LLM call inside `pytest`.

## How to use this plan

Work the phases in order. A phase is finished only when its exit criteria pass. Later phases call the public functions from earlier ones and do not reimplement them.

```text
Phase 1  Project foundation
Phase 2  Domain models
Phase 3  Data ingestion and cache
Phase 4  Candidate filtering
Phase 5  Groq prompt, client, and parser
Phase 6  Recommendation service
Phase 7  Streamlit UI
Phase 8  End-to-end check
```

## APIs

Record of the APIs in this system. The app does not expose a recommendation REST API. A person uses the Streamlit page. Two external APIs are called from Python, and this app exposes one health route.

| API | Direction | What it does |
| --- | --- | --- |
| Hugging Face dataset API | This app calls Hugging Face | Downloads the Zomato train split once, when `data/processed/restaurants.csv` does not exist yet. |
| Groq chat API | This app calls Groq | Ranks the filtered shortlist and writes the summary and explanations. |
| `GET /api/health` | A probe calls this app | Reports whether the local cache is readable and whether an LLM key is set. |

### 1. Hugging Face dataset API

`load_raw_dataset()` calls `datasets.load_dataset("ManikaSaini/zomato-restaurant-recommendation", split="train")`.

The call fetches the public Zomato restaurant table, about 51,717 Bangalore listings. The loader keeps the working columns, the cleaner turns them into the processed table, and that table is written to `data/processed/restaurants.csv`. A later request reads the CSV and does not call Hugging Face again. `GET /api/health` does not call this API. If the download fails and the cache file is missing, the recommendation request stops before any model call.

### 2. Groq chat API

The live model provider is Groq. `LLMClient.complete` sends one chat completion with the OpenAI Python SDK pointed at Groq's OpenAI-compatible endpoint. Groq documents that client setup. The planned settings are:

| Setting | Value |
| --- | --- |
| `LLM_API_KEY` | Groq API key from the Groq console. |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | `openai/gpt-oss-120b`, Groq's free-tier OpenAI GPT-OSS 120B model. |
| `LLM_TIMEOUT_SECONDS` | `30` |

The call uses temperature 0.2 and `response_format={"type": "json_object"}`. Groq accepts that JSON mode on its chat models. The prompt must tell the model to return JSON.

The call runs after filtering, and only when the Groq key is set and the shortlist is not empty. The payload is the user preferences plus up to 15 candidate restaurants. The model ranks those rows, writes a short explanation for each, and returns a one-paragraph summary. It is limited to the given restaurants and must not change rating or cost. If the key is missing, the call times out, Groq returns an error, or the JSON cannot be used, this API is skipped and the same shortlist is ranked by rating and votes. `pytest` does not call Groq.

### 3. `GET /api/health`

`app/server.py` mounts this route on the same server as the Streamlit page. Start with `streamlit run app/server.py`, then request `http://127.0.0.1:8501/api/health`.

The route reads the local restaurant cache and checks that `LLM_API_KEY` is set. It does not download the dataset and does not call the model. The JSON body has `status` plus `cache`, `llm`, and `huggingface` checks. The key is never included.

| `status` | Meaning | HTTP |
| --- | --- | --- |
| `ok` | The cache is readable and `LLM_API_KEY` is set. | 200 |
| `degraded` | The cache is readable and the key is missing. Recommendations use the rating-and-votes fallback. | 200 |
| `unavailable` | The cache is missing or cannot be read. | 503 |

## Phase 1 — Project foundation

**Goal.** A runnable Python package with dependencies, settings, and ignore rules, before any recommendation logic.

**Workflow covered.** Implementation constraint: Python for dataset handling, filtering, LLM calls, and the UI.

### Tasks

1. Create the package layout from the architecture:

```text
app/main.py
app/server.py
src/recommender/__init__.py
src/recommender/config.py
src/recommender/health.py
src/recommender/data/__init__.py
src/recommender/filtering/__init__.py
src/recommender/llm/__init__.py
tests/
data/processed/.gitkeep
```

2. Add `requirements.txt` with pinned-minimum versions of `datasets`, `pandas`, `pyarrow`, `pydantic`, `openai`, `python-dotenv`, and `streamlit`. Add `pytest` for tests.
3. Add `.env.example` with `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `DATA_CACHE_PATH`, `CANDIDATE_LIMIT`, and `DEFAULT_TOP_N`.
4. Add `.gitignore` entries for `.env`, `__pycache__/`, `.pytest_cache/`, `.venv/`, and `data/processed/*.csv`.
5. Implement `Settings` in `src/recommender/config.py`:
   - Load `.env` with `python-dotenv`.
   - Expose LLM settings, cache path, `candidate_limit` (default 15), `default_top_n` (default 5).
   - Expose budget edges: low `1–400`, medium `401–800`, high `801+`.
6. Leave `app/main.py` as the Streamlit page placeholder. The form arrives in Phase 7. `app/server.py` is the process entry and mounts `GET /api/health`.

### Exit criteria

- `pip install -r requirements.txt` succeeds.
- `Settings` reads defaults when the optional variables are unset.
- `.env` is gitignored. `.env.example` is committed.

## Phase 2 — Domain models

**Goal.** Typed inputs and outputs so every later module shares one contract.

**Workflow covered.** User input fields and the result card fields.

### Tasks

1. Implement these Pydantic models in `src/recommender/models.py`:
   - `UserPreferences` — `location`, `budget` (`low` | `medium` | `high`), `cuisine`, `min_rating` (0.0 to 5.0), `additional_preferences` (default empty string), `top_n` (default from settings, bounded to a positive integer).
   - `Restaurant` — cleaned fields listed in the architecture domain model.
   - `Recommendation` — `rank`, `name`, `cuisines`, `rating`, `cost_for_two`, `explanation`, `url`.
   - `RecommendationResult` — `preferences`, `summary`, `items`, `candidate_count`, `relaxed_filters`, `source` (`llm` | `fallback`).
2. Strip `location` and `cuisine` and reject blank values.
3. Add `InvalidModelOutput` in `src/recommender/llm/parser.py` only as a placeholder exception if the parser module does not exist yet. The full parser is Phase 5. Prefer defining the exception next to the parser in Phase 5 and keeping Phase 2 limited to the four models.

### Exit criteria

- Invalid budget, rating outside 0–5, and blank location or cuisine raise validation errors.
- A valid `UserPreferences` instance round-trips through `model_dump` and `model_validate`.

## Phase 3 — Data ingestion and cache

**Goal.** Turn the Hugging Face Zomato split into a small local CSV table the filter can query.

**Workflow covered.** Data ingestion: load the dataset and extract name, location, cuisine, cost, and rating.

### Tasks

1. Implement `src/recommender/data/loader.py`:
   - `load_raw_dataset()` calls `datasets.load_dataset("ManikaSaini/zomato-restaurant-recommendation", split="train")` and returns a pandas DataFrame.
   - Select only the working columns: `url`, `address`, `name`, `online_order`, `book_table`, `rate`, `votes`, `location`, `rest_type`, `dish_liked`, `cuisines`, `approx_cost(for two people)`, `listed_in(city)`.
   - Do not keep `phone`, `reviews_list`, or `menu_item`.
2. Implement `src/recommender/data/cleaner.py` with `clean_restaurants(df) -> pd.DataFrame`:
   - Strip `name` and `address`. Drop rows with a blank name.
   - Normalize `location` and `listed_in(city)` by stripping whitespace. Rename `listed_in(city)` to `listed_in_city` and `approx_cost(for two people)` to `cost_for_two`.
   - Parse `rate` into `rating`: take the number before `/`. Map `NEW`, `-`, and blanks to null.
   - Parse `cost_for_two` by removing commas. Unparseable values become null.
   - Parse `votes` to int, commas removed, missing as 0.
   - Split `cuisines` on commas into a list of stripped tokens. Null becomes an empty list.
   - Map `online_order` and `book_table` from `Yes` to true.
   - Truncate `dish_liked` to 200 characters.
   - Dedupe on normalized `name` + `address`, keeping the row with the highest `votes`.
3. Implement `load_processed_table(settings)`:
   - If `DATA_CACHE_PATH` exists, read the CSV file and return it.
   - Otherwise download, clean, write CSV, and return the frame.
   - If the download fails and the cache is missing, raise a clear error. Callers must not continue to the LLM.
4. Add `tests/test_cleaner.py` with a small in-memory DataFrame covering:
   - `4.1/5`, `NEW`, `-`, and blank ratings.
   - Cost strings that contain commas.
   - Cuisine splitting.
   - Dedupe keeping the higher-vote row.
   - Confirmation that `reviews_list` is not required and is absent from the output columns.

### Exit criteria

- `pytest tests/test_cleaner.py` passes with no network.
- A manual run writes `data/processed/restaurants.csv`.
- A second call reads the cache and does not call `load_dataset`.

## Phase 4 — Candidate filtering

**Goal.** Deterministic shortlist from user preferences, including the relaxation rules.

**Workflow covered.** Integration layer: filter and prepare restaurant data before the prompt.

### Tasks

1. Implement `src/recommender/filtering/candidates.py`:
   - `budget_bounds(budget, settings) -> tuple[int, int | None]`.
   - `apply_filters(df, preferences, settings, *, cuisine=True, rating=True, budget_mode="exact") -> pd.DataFrame`.
   - Location matches when the user text equals or is contained in `location` or `listed_in_city`, case-insensitive.
   - Cuisine matches any token, case-insensitive.
   - Minimum rating keeps `rating >= min_rating` and drops null ratings.
   - Budget keeps `cost_for_two` inside the band and drops null costs.
   - `score_candidates(df)` sets `score = rating * log(1 + votes)`.
   - `shortlist(df, preferences, settings) -> tuple[pd.DataFrame, list[str]]`.
2. Relaxation inside `shortlist`, stopping at the first non-empty result:
   1. Original filters. `relaxed_filters` stays empty.
   2. Drop cuisine. Record `cuisine`.
   3. Widen budget by one step (low also accepts medium, medium accepts low and high, high also accepts medium). Record `budget`.
   4. Drop minimum rating. Record `min_rating`.
3. Sort by `score` descending and keep `settings.candidate_limit` rows (default 15).
4. `additional_preferences` is not a filter.
5. Add `tests/test_candidates.py` for each hard filter, both edges of each budget band, the relaxation order, and the shortlist cap.

### Exit criteria

- `pytest tests/test_candidates.py` passes with no network.
- A known neighborhood, cuisine, rating, and budget returns only matching rows.
- An impossible cuisine still returns rows and records `cuisine` in `relaxed_filters`.
- A query that fails every step returns an empty frame and the full relaxation list.

## Phase 5 — LLM prompt, client, and parser

**Goal.** Turn a shortlist into a grounded JSON ranking from Groq, and reject anything the model invents.

**Workflow covered.** Prompt design, the Groq chat call, ranking, explanations, and the optional summary.

**Provider.** Groq's free tier, through the OpenAI SDK. `LLM_BASE_URL` is `https://api.groq.com/openai/v1` and `LLM_MODEL` is `openai/gpt-oss-120b` (OpenAI GPT-OSS 120B). `LLM_API_KEY` is a free Groq API key. Tests stay offline and do not call Groq.

### Tasks

1. Implement `src/recommender/llm/prompt.py`:
   - `build_messages(preferences, candidates) -> list[dict]`.
   - System message: rank only the given restaurants, do not change rating or cost, use `additional_preferences`, return JSON only, explanations of two or three sentences.
   - User message: preferences plus a compact candidate array with `name`, `location`, `cuisines`, `cost_for_two`, `rating`, `votes`, `rest_type`, `online_order`, `book_table`, and `dish_liked`.
   - Ask for exactly `top_n` items, `rank` starting at 1.
2. Implement `src/recommender/llm/client.py`:
   - `LLMClient.complete(messages) -> str` using the OpenAI SDK with `base_url` `https://api.groq.com/openai/v1`.
   - Read the Groq key, base URL, model, and timeout from `Settings`. The planned model is `openai/gpt-oss-120b`.
   - `temperature` 0.2.
   - Request `response_format={"type": "json_object"}`.
   - Return message content only. Do not parse JSON here.
   - Let timeouts and HTTP errors from Groq propagate for the service to catch.
3. Implement `src/recommender/llm/parser.py`:
   - `parse_recommendations(content, candidates, top_n) -> tuple[str, list[Recommendation]]`.
   - Require `summary` and `recommendations`.
   - Keep an item only when `name` matches a candidate exactly.
   - Copy cuisines, rating, cost, and url from that candidate.
   - If some names match but fewer than `top_n` remain, pad from unused candidates in score order. The service will mark this `source = llm`.
   - Raise `InvalidModelOutput` when the body is not JSON or no name matches.
4. Add `tests/test_parser.py`:
   - Valid JSON becomes recommendations whose facts match the candidates.
   - An extra unknown restaurant is dropped.
   - A partial list is padded to `top_n`.
   - Non-JSON and a payload with no usable names raise `InvalidModelOutput`.

### Exit criteria

- `pytest tests/test_parser.py` passes with no network.
- Prompt payload contains no `reviews_list`, `menu_item`, or `phone`.
- Parser output never contains a name that was absent from the candidate frame.

## Phase 6 — Recommendation service

**Goal.** One function the UI can call: preferences in, `RecommendationResult` out, including fallback.

**Workflow covered.** Full path from filtered rows to ranked explanations.

### Tasks

1. Implement `RecommendationService` in `src/recommender/service.py` with `recommend(preferences: UserPreferences) -> RecommendationResult`.
2. Follow the architecture sequence:
   1. Preferences are already validated by Pydantic before this call.
   2. Load the processed table, building the cache on first use.
   3. Shortlist with Phase 4.
   4. If the shortlist is empty, return a result with an empty `items` list, `candidate_count` 0, the relaxation notes, and a summary that restates the filters.
   5. Otherwise build messages, call the Groq client, and parse.
   6. On success, set `source` to `llm`. Padding inside the parser still counts as `llm`.
   7. On missing API key, timeout, HTTP error, or `InvalidModelOutput`, build the fallback result.
3. Fallback:
   - Sort the shortlist by `score` descending and take `top_n`.
   - Summary states that ordering used rating and number of votes.
   - Each explanation names cuisine, rating, cost for two, and location, and does not claim the model wrote it.
   - `source` is `fallback`.
4. Join displayed facts from the candidate row, never from model JSON fields other than `name`, `rank`, and `explanation`.
5. Add a service test with a fake client and a tiny frame:
   - Successful JSON yields `source = llm`.
   - `InvalidModelOutput` yields `source = fallback` and the same candidate facts.
   - An empty shortlist does not call the client.

### Exit criteria

- Service tests pass offline.
- A missing `LLM_API_KEY` returns fallback cards instead of raising.
- A download failure with no cache raises before any LLM call.

## Phase 7 — Streamlit UI

**Goal.** A single page where a person enters preferences and reads the top recommendations.

**Workflow covered.** User input and output display.

### Tasks

1. Replace the placeholder in `app/main.py`.
2. The page imports `RecommendationService` and the domain models only. It does not import `datasets` or `openai`.
3. Form:
   - Location text input, placeholder `Banashankari`.
   - Budget select: `low`, `medium`, `high`.
   - Cuisine text input, placeholder `Italian`.
   - Minimum rating slider, 0.0 to 5.0, step 0.1, default 3.5.
   - Additional preferences text area, placeholder `family-friendly, quick service`.
   - Submit button.
4. On submit, build `UserPreferences` and call `service.recommend`.
5. Render:
   - Summary paragraph.
   - A note listing `relaxed_filters` when that list is non-empty.
   - A note when `source` is `fallback`, including the case of a missing API key.
   - One card per item: rank, name, cuisines, rating, cost for two, explanation, and a link to `url`.
   - An empty state that restates location, cuisine, budget, and minimum rating when `items` is empty.
6. Show Pydantic validation errors next to the form.
7. Show the cache-download error as a page error and skip the recommendation call.

### Exit criteria

- `streamlit run app/server.py` opens the form in `app/main.py`.
- `GET /api/health` on that server returns the readiness JSON from `check_health`.
- Submitting Banashankari, medium budget, Italian, and minimum rating 3.5 shows up to five cards with name, cuisine, rating, cost, and an explanation.
- With no API key, the same submit still shows cards and the fallback note.
- Widening a filter surfaces the relaxation note.

## Phase 8 — End-to-end check

**Goal.** Confirm the workflow in the problem statement against a running app.

### Tasks

1. Run `pytest` and confirm the cleaner, candidate, health, parser, and service tests pass offline.
2. Run `streamlit run app/server.py` twice. The first recommendation creates `data/processed/restaurants.csv`. The second run starts without downloading the dataset again. `GET /api/health` reports the cache and does not download it.
3. Exercise these cases in the UI:

| Case | Expected |
| --- | --- |
| Banashankari, Italian, medium, rating 3.5, extra text "quick service" | Up to 5 cards. Facts match the dataset. Explanation mentions the fit. |
| A cuisine that exists in another neighborhood only | Results appear with `cuisine` listed under relaxed filters. |
| Location text that matches nothing, even after relaxation | Empty state. No LLM error dumped on the page. |
| `LLM_API_KEY` removed | Fallback ranking and the fallback note. |
| `LLM_API_KEY` set to a Groq key, with `LLM_BASE_URL=https://api.groq.com/openai/v1` and `LLM_MODEL=openai/gpt-oss-120b` | `source` is llm and explanations are Groq-written sentences. |
| `GET /api/health` with a readable cache and a key | `status` is `ok` and HTTP status is 200. The body does not contain the key. |
| `GET /api/health` with the key removed | `status` is `degraded` and HTTP status is 200. |
| `GET /api/health` with the cache missing or unreadable | `status` is `unavailable`, HTTP status is 503, and the dataset is not downloaded. |

4. Confirm a result card never shows a restaurant that failed the final shortlist, and never shows a rating or cost that differs from the cached row.

### Exit criteria

- The five workflow stages in the problem statement are visible in one run: cached dataset, preference form, filtered shortlist, ranked explanations, and the result cards.
- Offline tests pass.
- The CSV cache is the only derived data file, and it is gitignored.

## Suggested order of files

| Phase | Files |
| --- | --- |
| 1 | `requirements.txt`, `.env.example`, `.gitignore`, `src/recommender/config.py`, package `__init__.py` files |
| 2 | `src/recommender/models.py` |
| 3 | `src/recommender/data/loader.py`, `src/recommender/data/cleaner.py`, `tests/test_cleaner.py` |
| 4 | `src/recommender/filtering/candidates.py`, `tests/test_candidates.py` |
| 5 | `src/recommender/llm/prompt.py`, `client.py`, `parser.py`, `tests/test_parser.py` |
| 6 | `src/recommender/service.py`, `tests/test_service.py` |
| 7 | `app/main.py`, `app/server.py` |
| Health | `src/recommender/health.py`, `app/server.py`, `tests/test_health.py` |
| 8 | No new modules. Manual pass plus `pytest`. |

## Out of scope for every phase

User accounts, saved searches, a database server, and a vector index stay out of this plan. Retrieval remains pandas filtering on the cached table.
