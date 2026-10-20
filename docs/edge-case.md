# Edge Cases

Corner cases for the restaurant recommendation app. Expected behavior follows [architecture.md](architecture.md) and [implementation-plan.md](implementation-plan.md).

Each case has an id. Offline tests should cite the id in the test name or docstring. Cases marked **Manual** need a running app or a live dataset cache. Everything else belongs in `pytest` with in-memory frames or a fake LLM client.

The dataset is Bangalore neighborhood listings. A city name such as Delhi or Bangalore is a location mismatch, not a supported city filter.

## 1. Preference validation

Handled by `UserPreferences` before any filter or LLM call. The UI shows the field error and does not call `recommend`.

| ID | Scenario | Input | Expected behavior |
| --- | --- | --- | --- |
| P1 | Blank location | `location=""` | Validation error. |
| P2 | Whitespace-only location | `location="   "` | Treated as blank after strip. Validation error. |
| P3 | Blank cuisine | `cuisine=""` | Validation error. |
| P4 | Whitespace-only cuisine | `cuisine="  "` | Treated as blank after strip. Validation error. |
| P5 | Location and cuisine with surrounding spaces | `"  Banashankari  "`, `"  Italian "` | Stored stripped. Filter uses the stripped value. |
| P6 | Rating below range | `min_rating=-0.1` | Validation error. |
| P7 | Rating above range | `min_rating=5.1` | Validation error. |
| P8 | Rating at the ends of the slider | `min_rating=0.0` and `5.0` | Accepted. |
| P9 | Unknown budget | `budget="cheap"` | Validation error. |
| P10 | `top_n` of zero or negative | `top_n=0` | Validation error. |
| P11 | Empty additional preferences | `additional_preferences=""` | Accepted. Omitted from ranking pressure. Prompt still receives the field. |
| P12 | Very long additional preferences | Several thousand characters | Accepted. Passed through as prompt text. It does not change hard filters. |

## 2. Cleaning and cache

`clean_restaurants` output columns are the working fields only. `phone`, `reviews_list`, and `menu_item` are absent even when the raw frame contains them.

| ID | Scenario | Input | Expected behavior |
| --- | --- | --- | --- |
| C1 | Normal rating | `rate="4.1/5"` | `rating=4.1`. |
| C2 | Rating with spaces | `rate="4.1 / 5"` | `rating=4.1`. |
| C3 | New listing | `rate="NEW"` | `rating` is null. |
| C4 | Dash rating | `rate="-"` | `rating` is null. |
| C5 | Blank or null rating | `""` or null | `rating` is null. |
| C6 | Rating without a slash | `rate="4.1"` | `rating=4.1`. |
| C7 | Non-numeric rating | `rate="Excellent"` | `rating` is null. |
| C8 | Cost with a thousands comma | `"1,200"` | `cost_for_two=1200`. |
| C9 | Cost with spaces | `" 800 "` | `cost_for_two=800`. |
| C10 | Unparseable cost | `""`, `"-"`, null | `cost_for_two` is null. |
| C11 | Votes with a comma | `"2,556"` | `votes=2556`. |
| C12 | Missing votes | null | `votes=0`. |
| C13 | Cuisine list | `"Cafe, Mexican, Italian"` | `["Cafe", "Mexican", "Italian"]`. |
| C14 | Cuisine extra spaces and empty tokens | `"Cafe,  Italian,, Thai "` | `["Cafe", "Italian", "Thai"]`. |
| C15 | Missing cuisines | null or `""` | Empty list. |
| C16 | Blank name | `name=""` or `"   "` | Row dropped. |
| C17 | Duplicate name and address | Two rows, votes 10 and 50 | One row remains, the one with `votes=50`. |
| C18 | Duplicate name and address, equal votes | Two rows, same votes, different `url` | One row remains. Keep the first row after a stable sort by `votes` descending. |
| C19 | Same name, different address | Two branches | Both rows remain. |
| C20 | Online order and booking flags | `"Yes"`, `"No"`, null, `"yes"` | Only exact `Yes` becomes true. Every other value becomes false. |
| C21 | Long `dish_liked` | 500 characters | Truncated to 200 characters. |
| C22 | Null `dish_liked` | null | Empty string. |
| C23 | Heavy columns present | `reviews_list` over 1 MB, `menu_item`, `phone` | Those columns are not in the cleaned frame and are not written to the CSV. |
| C24 | Mojibake in a name | `"CafÃ© Down The Alley"` | Value is kept as stored after strip. The cleaner does not guess an encoding repair. |
| C25 | Cache file already exists | Second `load_processed_table` call | Read the CSV. Do not call Hugging Face. **Manual** for the real file. |
| C26 | Download fails and cache is missing | Network error, no CSV | Raise a clear error. The service does not call the LLM. |
| C27 | Download fails and cache exists | Network error, CSV present | Return the cached table. |
| C28 | Cache file is unreadable | Truncated or non-CSV bytes at `DATA_CACHE_PATH` | Raise a clear read error. Do not call the LLM. Do not silently re-download in the request path. |
| C29 | Every row has a blank name | Frame of blank names | Cleaned frame is empty. Later filters return no candidates. |

## 3. Hard filters

Location, cuisine, minimum rating, and budget apply together on the original pass. Comparison of location and cuisine is case-insensitive.

| ID | Scenario | Input | Expected behavior |
| --- | --- | --- | --- |
| F1 | Exact neighborhood | Location `Banashankari`, row location `Banashankari` | Row kept. |
| F2 | Location case difference | `"banashankari"` | Row kept. |
| F3 | Listed city holds the text | User text equals `listed_in_city` while `location` differs | Row kept. |
| F4 | User text is contained in the field | Field `Banashankari`, query `Banas` | Row kept. Short queries over-match. The UI does not block them. |
| F5 | City name from the problem examples | Location `Delhi` or `Bangalore` | No neighborhood equals that string. Result is empty unless a field happens to contain the substring. |
| F6 | Cuisine token match | Cuisines `Cafe, Mexican, Italian`, query `Italian` | Row kept. |
| F7 | Cuisine case difference | Query `italian` | Row kept. |
| F8 | Query is not a whole token | Cuisines include `North Indian`, query `Indian` | Row excluded. Match is on a full token. |
| F9 | Multi-word token | Query `North Indian` | Row kept when that exact token exists. |
| F10 | Rating equal to the minimum | `rating=4.0`, `min_rating=4.0` | Row kept. |
| F11 | Rating just below the minimum | `rating=3.9`, `min_rating=4.0` | Row excluded. |
| F12 | Null rating with a minimum set | `rating` null, `min_rating=0.0` | Row excluded. A null rating fails the rating filter at every threshold, including 0. |
| F13 | Low budget edges | Cost `1` and `400` | Both are low. Cost `401` is not low. |
| F14 | Medium budget edges | Cost `401` and `800` | Both are medium. Cost `400` and `801` are not medium. |
| F15 | High budget edge | Cost `801` and above | High. Cost `800` is not high. |
| F16 | Null cost | `cost_for_two` null | Excluded by every budget. |
| F17 | Cost of zero | `cost_for_two=0` | Excluded. Low starts at 1. |
| F18 | All four filters pass | Location, cuisine, rating, and cost all match | Row kept. |
| F19 | One filter fails | Any single mismatch | Row excluded on the original pass. |

## 4. Relaxation and shortlist

Stop at the first step that returns at least one row. Record only the constraints that were actually dropped or widened.

| ID | Scenario | Input | Expected behavior |
| --- | --- | --- | --- |
| R1 | Original filters match | Any non-empty exact match | `relaxed_filters` is empty. Later steps do not run. |
| R2 | Cuisine misses, other filters hit | Cuisine absent in that neighborhood | Drop cuisine only. `relaxed_filters=["cuisine"]`. Returned rows may serve other cuisines. |
| R3 | Cuisine and exact budget miss | Matches appear in the neighboring band | Widen budget by one step. `relaxed_filters` contains `cuisine` and `budget`. |
| R4 | Low budget widened | Budget `low` | Accept low and medium (`1` to `800`). |
| R5 | Medium budget widened | Budget `medium` | Accept low, medium, and high (cost `>= 1`). |
| R6 | High budget widened | Budget `high` | Accept medium and high (cost `>= 401`). |
| R7 | Rating is the last blocker | Rows exist only with rating below the minimum, or with a null rating | Drop the rating filter. `relaxed_filters` contains `min_rating`. |
| R8 | Nothing matches location | Location text matches no `location` or `listed_in_city` | Empty frame after all four steps. `relaxed_filters` lists `cuisine`, `budget`, and `min_rating`. Location is never dropped. |
| R9 | Additional preferences | `"family-friendly, quick service"` | No row is removed or required because of this text. `rest_type`, `online_order`, and `book_table` stay on the candidate for the prompt. |
| R10 | More matches than the cap | 40 matching rows, `candidate_limit=15` | 15 rows, highest score first. |
| R11 | Fewer matches than the cap | 3 matching rows | All 3 rows. The cap does not invent rows. |
| R12 | Score ties | Same rating and same votes | Stable sort by score descending keeps the original relative order. |
| R13 | Votes are zero | `votes=0`, rating present | `score = rating * log(1)` which is `0`. The row stays in the shortlist and ranks below any positive score. |
| R14 | Null rating reaches scoring | Rating filter was dropped in R7, row rating is null | Score treats null rating as `0` so the sort stays numeric. The row can fill the shortlist only after higher scores. |
| R15 | `top_n` larger than the shortlist | 2 candidates, `top_n=5` | At most 2 recommendations. |

Shortlist score is `rating * log(1 + votes)`. The UI does not show the score.

## 5. Prompt and model output

The prompt receives the compact candidate fields only: `name`, `location`, `cuisines`, `cost_for_two`, `rating`, `votes`, `rest_type`, `online_order`, `book_table`, `dish_liked`.

| ID | Scenario | Input | Expected behavior |
| --- | --- | --- | --- |
| L1 | Empty shortlist | No rows after relaxation | The service returns an empty `items` list and does not call the LLM. |
| L2 | Heavy fields in the source row | Candidate built from a cleaned row | Prompt JSON has no `reviews_list`, `menu_item`, `phone`, or `address`. |
| L3 | Dish text already truncated | `dish_liked` of 200 characters from C21 | Prompt sends those 200 characters. |
| L4 | Valid JSON | Summary plus `top_n` exact names | `source="llm"`. Cuisine, rating, cost, and url are copied from the candidate row. |
| L5 | Model adds a restaurant | Name not in the shortlist | That item is dropped. |
| L6 | Model changes facts | JSON includes a different rating or cost | Ignored. Displayed rating and cost come from the candidate row. |
| L7 | Every name is unknown | No name matches | Raise `InvalidModelOutput`. Service uses fallback. |
| L8 | Some names match | 2 of 5 names match, `top_n=5` | Keep the 2. Pad to 5 from unused candidates in score order. `source` stays `llm`. |
| L9 | Non-JSON body | Prose, or JSON wrapped in Markdown fences | Raise `InvalidModelOutput`. Service uses fallback. |
| L10 | Missing `summary` or `recommendations` | Either key absent | Raise `InvalidModelOutput`. |
| L11 | `recommendations` is not a list | A string or object | Raise `InvalidModelOutput`. |
| L12 | Empty recommendations array | `[]` | Raise `InvalidModelOutput`. Padding runs only after at least one name matches. |
| L13 | Duplicate names in the payload | Same candidate named twice | Keep the first. Later copies are ignored. |
| L14 | Two candidates share a display name | Same `name`, different `address` and `url` | Name join uses the first shortlist row with that name, which is the higher score. Document the pair in the result by that row's url. |
| L15 | Name differs by case or spaces | `"jalsa"` or `"Jalsa "` while the candidate is `Jalsa` | Treated as unknown. Match is exact after the cleaner has already stripped the stored name. |
| L16 | Ranks out of order or duplicated | Model returns rank 3 then 1 | Display order follows the list order of valid items, then pads. Ranks are renumbered from 1. |
| L17 | Empty explanation on a valid name | `explanation=""` | Keep the item. The card shows a blank explanation rather than switching the whole result to fallback. |
| L18 | More items than `top_n` | Model returns 10 names | Keep the first `top_n` valid names. |
| L19 | Timeout | Call exceeds `LLM_TIMEOUT_SECONDS` | Service catches it and uses fallback. |
| L20 | HTTP or provider error | 401, 429, 500, or connection error | Service catches it and uses fallback. |
| L21 | Missing API key | `LLM_API_KEY` unset or blank | Do not call the provider. Fallback ranking. UI states that live explanations need a key. |
| L22 | Whitespace API key | `LLM_API_KEY="   "` | Treated as missing. Same path as L21. |
| L23 | `response_format` rejected by the provider | Provider error about JSON mode | Same path as L20. Fallback ranking. |
| L24 | Instructions inside additional preferences | Text that tells the model to ignore the candidate list or invent a restaurant | Parser still drops unknown names. Displayed facts still come from candidate rows. |

## 6. Fallback ranking

Used for L7, L9–L12, L19–L22. Also used when the provider cannot be reached for any other client exception.

| ID | Scenario | Input | Expected behavior |
| --- | --- | --- | --- |
| B1 | Ordered fallback | Shortlist with mixed scores | Items follow score descending, length `min(top_n, shortlist)`. |
| B2 | Summary text | Any fallback | Summary says the order used rating and number of votes. |
| B3 | Explanation template | Any fallback item | Text includes cuisine, rating, cost for two, and location. It does not say the model wrote the text. |
| B4 | Source flag | Any fallback | `source="fallback"`. |
| B5 | Null rating on a fallback card | Row survived R7 with a null rating | Template states that a rating is unavailable. Cost and location still appear. |
| B6 | Null cost on a fallback card | Possible only if a future config disables the budget filter | Template states that cost is unavailable. Current budget rules exclude null cost before this point. |
| B7 | UI note | `source="fallback"` | Page shows the fallback note, including the missing-key wording when the key is absent. |

## 7. Service and UI

`app/main.py` calls `RecommendationService` only. `GET /api/health` is mounted by `app/server.py` and does not call `recommend`.

| ID | Scenario | Input | Expected behavior |
| --- | --- | --- | --- |
| U1 | Validation failure | P1–P4, P6, P7, P9, P10 | Field errors on the form. `recommend` is not called. |
| U2 | Cache build failure | C26 | Page error. No recommendation request and no LLM call. |
| U3 | Unreadable cache | C28 | Page error. No LLM call. |
| U4 | Happy path | Banashankari, Italian, medium, rating 3.5 | Up to 5 cards. Each card shows rank, name, cuisines, rating, cost for two, explanation, and the url link. **Manual.** |
| U5 | Relaxed result | Cuisine that misses the neighborhood | Cards render, plus a note that lists `cuisine`. **Manual.** |
| U6 | Empty after relaxation | R8 | Empty state restates location, cuisine, budget, and minimum rating. No stack trace. |
| U7 | Missing key in the UI | L21 | Cards from fallback plus the fallback note. **Manual.** |
| U8 | Live key | Valid `LLM_API_KEY` and model | Explanations are the model sentences. Facts still match the cached row. **Manual.** |
| U9 | Second submit | Same form submitted again | A new `recommend` call. The dataset is read from cache. |
| U10 | Slider ends | Minimum rating `0.0` or `5.0` | Request uses that exact value. At `5.0`, only a perfect rating passes the original rating filter. |
| U11 | `candidate_limit` smaller than `top_n` | Limit 3, `top_n` 5 | At most 3 cards. |
| U12 | Custom cache path | `DATA_CACHE_PATH` points at another file | Loader reads and writes that path. |
| U13 | Budget edges changed in settings | Low max set to 500 | Filter uses 500. Tests that assume 400 must pass settings explicitly. |

## 8. Health endpoint

`GET /api/health` reads the cache and the LLM key. It does not call Hugging Face or the model, and the body never contains the key.

| ID | Scenario | Input | Expected behavior |
| --- | --- | --- | --- |
| H1 | Cache readable and key set | CSV parses, `LLM_API_KEY` non-blank | `status="ok"`, HTTP 200. Cache, llm, and huggingface checks are ok. Hugging Face is not called. |
| H2 | Key missing | Readable cache, blank key | `status="degraded"`, HTTP 200. Cache check is ok. LLM check says the fallback ranking is available. |
| H3 | Cache missing | `DATA_CACHE_PATH` does not exist | `status="unavailable"`, HTTP 503. Detail says the next recommendation request will try Hugging Face. `load_dataset` is not called. |
| H4 | Cache unreadable | File exists but is not the restaurant table | `status="unavailable"`, HTTP 503. Detail says the app will not download the dataset again. `load_dataset` is not called. |
| H5 | Key secrecy | Key is `super-secret-key` | That string is absent from the JSON body. |
| H6 | Whitespace key | `LLM_API_KEY="   "` | Treated as missing. Same status as H2. |

## 9. Cases to lock in tests

Minimum automated coverage, mapped to the implementation-plan test modules.

| Module | IDs |
| --- | --- |
| `tests/test_cleaner.py` | C1, C3, C4, C5, C8, C10, C11, C13, C14, C16, C17, C18, C19, C20, C21, C23 |
| `tests/test_candidates.py` | F1, F2, F6, F8, F10, F11, F12, F13, F14, F15, F16, R1, R2, R4, R5, R6, R8, R9, R10, R13, R14 |
| `tests/test_health.py` | H1, H2, H3, H4, H5, H6 |
| `tests/test_parser.py` | L4, L5, L6, L7, L8, L9, L12, L13, L15 |
| `tests/test_service.py` | L1, L21, B1, B4, U6 |

Manual checks in Phase 8 cover U4, U5, U7, U8, C25, and C26.
