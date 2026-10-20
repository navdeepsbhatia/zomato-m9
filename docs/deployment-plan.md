# Deployment plan

Deploy the recommender as two public pieces:

- **Railway** runs the Python backend: restaurant cache, filtering, Groq ranking, and fallback.
- **Vercel** serves the dark Table page. The browser calls Railway directly.

Streamlit stays a local way to run the page. Vercel cannot host `streamlit run`. Railway should not serve the Streamlit UI.

Today the only HTTP route is `GET /api/health` inside the Streamlit process (`app/server.py`). The split below has to land in the repo before either host can serve this product.

## Target shape

```text
Browser  →  Vercel (static Table page)
              │
              │  HTTPS, CORS limited to the Vercel origin
              ▼
           Railway (one Python process)
              │
              ├── data/processed/restaurants.csv
              └── Groq  https://api.groq.com
```

One Railway replica. Each process loads the CSV into memory. A second replica would keep its own copy and would not share a file written on local disk.

The browser talks to Railway. Do not proxy recommendations through a Vercel function. Groq can take up to `LLM_TIMEOUT_SECONDS` (30s), and the API key must stay on Railway.

## What each side owns

| Railway | Vercel |
| --- | --- |
| `src/recommender/` | The Table page: form, cards, empty, error, fallback, and relaxed-filter states |
| `GET /api/health` | Build-time `VITE_API_URL` pointing at the Railway URL |
| `GET /api/locations` | No API key, no CSV, no Python |
| `POST /api/recommendations` | |
| `LLM_API_KEY` and the restaurant CSV | |

`app/main.py` is the behavior reference for the Vercel page: neighborhood list, budget `low` / `medium` / `high`, optional cuisine, minimum rating `0.0`–`5.0` step `0.1` default `3.5`, optional notes, then summary, relaxation note, fallback note, and cards (rank, name, cuisines, rating, cost for two, explanation, link).

## Backend contract

Add a small ASGI app, separate from `st.App`, that calls `RecommendationService` and `health_response`. Suggested module: `app/api.py`.

| Method | Path | Body | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET` | `/api/health` | none | `200` with the existing health JSON | `503` when the cache is missing or unreadable |
| `GET` | `/api/locations` | none | `200` `{"locations": ["Banashankari", ...]}` | `503` on `DatasetDownloadError` or `CacheReadError` |
| `POST` | `/api/recommendations` | `UserPreferences` JSON | `200` with `RecommendationResult` JSON | `422` on validation; `503` on cache errors |

`POST` fields: `location` (required string), `budget` (`low`, `medium`, `high`), `cuisine` (string, may be empty), `min_rating` (0.0–5.0), `additional_preferences` (string), `top_n` (optional, default 5).

The health body stays as it is today: `ok` when the cache is readable and `LLM_API_KEY` is set, `degraded` when the cache is readable and the key is empty, `unavailable` when the cache cannot be used. The body never includes the key. The probe does not download the dataset and does not call Groq.

A missing key still returns cards from `POST /api/recommendations` with `source: "fallback"`. The page shows the fallback note.

CORS allows only the Vercel origin, from `ALLOWED_ORIGINS` (comma-separated). Credentials are unnecessary. Methods: `GET`, `POST`, `OPTIONS`.

Start command, from the repo root:

```text
python -m uvicorn app.api:app --host 0.0.0.0 --port $PORT
```

Railway sets `PORT`. Listening on `127.0.0.1` is unreachable inside the container.

Python on Railway: **3.12**. This laptop is on 3.15; `pandas` and `pyarrow` wheels are reliable on 3.12. Add `uvicorn` to `requirements.txt` when the API module is added. `pytest` may stay; it does not change runtime behavior.

## Environment

### Railway

| Variable | Required | Value |
| --- | --- | --- |
| `LLM_API_KEY` | For live explanations | Groq key. Empty is allowed and yields fallback cards plus health `degraded`. |
| `LLM_BASE_URL` | No | Unset. Client uses `https://api.groq.com/openai/v1`. |
| `LLM_MODEL` | No | Unset. Client uses `openai/gpt-oss-120b`. |
| `LLM_TIMEOUT_SECONDS` | No | `30` |
| `DATA_CACHE_PATH` | No | `data/processed/restaurants.csv` |
| `CANDIDATE_LIMIT` | No | `15` |
| `DEFAULT_TOP_N` | No | `5` |
| `ALLOWED_ORIGINS` | Yes | The production Vercel URL, for example `https://table.vercel.app`. Add preview origins only if those deploys must call production. |

### Vercel

| Variable | Required | Value |
| --- | --- | --- |
| `VITE_API_URL` | Yes | Railway public origin, no trailing slash, for example `https://week1lab1-production.up.railway.app`. |

Set `VITE_API_URL` for Production before the first Vercel build. Changing it requires a new build. Do not put `LLM_API_KEY` on Vercel.

## Restaurant cache

`data/processed/restaurants.csv` is about 7 MB and is listed in `.gitignore`, so a GitHub deploy does not contain it. `GET /api/health` returns `503` until the file is readable, and Railway will treat that as a failed deploy if `/api/health` is the health check.

Ship the file in the image:

1. Confirm the local CSV exists and opens.
2. Stop ignoring `data/processed/restaurants.csv` for the deploy commit, or `COPY` it in a Dockerfile from a build context that includes it.
3. Set Railway's health check path to `/api/health` and expect HTTP 200.

Do not depend on the health probe to create the file. It never downloads. A first-request Hugging Face download also fails the health check during boot and disappears when Railway replaces the container.

Outbound HTTPS from Railway must reach `https://api.groq.com`. Hugging Face is only needed if you choose not to ship the CSV.

## Release order

Deploy the backend first so the frontend build has a live API URL.

1. Run the offline tests: `pytest tests/test_cleaner.py tests/test_candidates.py tests/test_health.py tests/test_parser.py tests/test_service.py`.
2. Add `app/api.py` with the three routes and CORS. Keep recommendation logic in `RecommendationService`.
3. Add the Vercel app that implements the Table page and calls `VITE_API_URL`.
4. Include `restaurants.csv` in what Railway builds.
5. Push the repo. Confirm `.env` is not in the commit.
6. Create a Railway service from that repo. One replica. Builder: Dockerfile or Railpack/Nixpacks with the uvicorn start command. Health check: `GET /api/health`.
7. Set the Railway variables, including `LLM_API_KEY` and `ALLOWED_ORIGINS`.
8. Open `https://<railway-host>/api/health` and confirm `status` is `ok`.
9. Create a Vercel project from the frontend directory. Framework preset matching that app (Vite or Next). Set `VITE_API_URL` to the Railway origin. Deploy.
10. Copy the Vercel production URL into Railway `ALLOWED_ORIGINS` and redeploy the backend if it was not known in step 7.
11. Run the checks below against the Vercel URL.

## Verification

| Check | Pass when |
| --- | --- |
| Railway health | `GET /api/health` is HTTP 200 and `"status": "ok"`. The JSON has no API key. |
| Locations | `GET /api/locations` returns a non-empty list including `Banashankari`. |
| Direct recommend | `POST /api/recommendations` with Banashankari, `medium`, Italian, `min_rating` 3.5 returns up to five items. Each item has rank, name, cuisines, rating, cost for two, explanation, and url. |
| Vercel page | The dark Table page loads from the Vercel URL. The neighborhood control lists locations from the API. |
| Search | The same Banashankari / medium / Italian / 3.5 search shows cards and **Open restaurant** when `url` is present. |
| Fallback | Clear `LLM_API_KEY` on Railway, redeploy, and search again. Cards still appear, with the fallback note. Health is `degraded` and still HTTP 200. |
| Empty and errors | A query that matches nothing shows the empty note with location, cuisine, budget, and minimum rating. A stopped Railway process shows the page error state, not a blank screen. |
| CORS | The Vercel origin can call Railway. A different origin cannot. |
| Secrets | Railway logs, Vercel env, and the health JSON do not print `LLM_API_KEY`. |

## Rollback

Redeploy the previous Railway deployment, then the previous Vercel deployment. Host variables stay in place, so the Groq key does not need to be pasted again.

If the bad release was a broken CSV, restore the previous file and redeploy Railway. If the bad release was CORS or `VITE_API_URL`, fix the variable and redeploy only the side that reads it. A Vercel env change needs a new Vercel build.

## Out of scope

Accounts, a database, more than one Railway replica, a custom domain, and sending recommendations through Vercel serverless functions. Add a domain later by updating `ALLOWED_ORIGINS` and `VITE_API_URL`.
