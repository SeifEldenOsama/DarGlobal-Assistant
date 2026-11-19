# Atlas — DarGlobal & Wasalt Real Estate Assistant

Atlas is a source-grounded real-estate research assistant for publicly available DarGlobal and Wasalt pages. It is deliberately not a generic chatbot: it gathers permitted public documents through source-specific scrapers, normalizes and embeds them, retrieves only relevant chunks, and returns an answer with links to the exact retrieved pages.

> Deployment status: this repository is ready for a Vercel deployment but is not publicly deployed from this workspace. A public URL needs a Vercel account, repository, Supabase project, and `OPENROUTER_API_KEY`; no URL is claimed until that deployment is completed and smoke-tested.

## Research and crawl policy

Research was performed on 18 November 2026.

- DarGlobal's [public project index](https://darglobal.co.uk/projects) links individual project and landing pages. The public [AIDA page](https://darglobal.co.uk/landing-page/aida), for example, has location, amenity, property-type, and FAQ content in HTML.
- Wasalt's [public sale listing index](https://wasalt.sa/en/properties-for-sale-in-saudi-arabia) links public property/project detail pages. Detail pages can contain location, area, bedrooms, amenities, published price, and update information.
- The scrapers do not assume a shared HTML schema. Each checks `robots.txt` at runtime, refuses a policy-disallowed URL, rate-limits requests, and follows only source-owned detail links exposed by that source's public index. They do not use login flows, telephony/WhatsApp actions, CAPTCHAs, private APIs, or anti-bot workarounds.

Policy and public availability can change. If a `robots.txt` policy cannot be fetched or does not allow crawling, the scraper indexes no additional pages for that source and logs the limitation. It does not bypass the condition. Wasalt price and listing data is volatile: the UI only presents a price where the retrieved public page explicitly contains it.

Live CLI checks in this workspace also encountered site-side access controls: DarGlobal served an Incapsula `noindex,nofollow` interstitial for the public project index, and Wasalt returned HTTP 403 for its public listing index. The crawler detects both conditions and stops, so neither response can enter the index. The web-search research above was used only to inspect public page structure; it is not used as scraped chatbot content. Re-run the CLI only when the sites permit the configured bot identity or when the data owner provides an approved export/API.

## Architecture

```text
React + TypeScript UI
        │ REST /api/v1
        ▼
FastAPI presentation layer ────────── SQLite (local) / Postgres (Vercel) conversations
        │
        ▼
AnswerQuestion application use case ─ OpenRouter language-model adapter
        │                                   (live model verification + retries)
        ▼
Vector-store adapter ◄────────────── local Chroma (Docker) / Supabase pgvector (Vercel)
        ▲                                      ▲
Sentence Transformers (local)             OpenRouter free embeddings (Vercel)
        ▲
IngestDocuments use case
        ▲
DarGlobal / Wasalt scrapers → cleaning → normalization → semantic chunks
```

Domain entities and ports do not depend on Chroma, SQLAlchemy, HTTPX, or OpenRouter. Infrastructure adapters are composed exactly once in `backend/app/container.py`.

## Stack and layout

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, HTTPX, Beautiful Soup
- Local `sentence-transformers/all-MiniLM-L6-v2` embeddings; persistent Chroma locally and Supabase Postgres with pgvector in Vercel production
- A small OpenRouter embedding adapter for Vercel, using the currently available free `nvidia/nemotron-3-embed-1b:free` model at 2,048 dimensions. This avoids packaging PyTorch's multi-gigabyte Linux dependency tree inside a 500 MB Vercel Function.
- OpenRouter with its verified `openrouter/free` route by default; React 18, TypeScript, Vite, Tailwind, and Lucide
- Docker Compose for local development and Vercel configurations for production

```text
backend/app/
  api/v1/                 FastAPI routes
  application/            use cases, prompts, cleaning, chunking
  domain/                 entities and dependency ports
  infrastructure/         Chroma, embeddings, LLM, SQLAlchemy, scrapers
  core/                   settings, errors, structured logging
  cli.py                  independent ingestion command
backend/tests/            unit/API tests and saved HTML parser fixtures
frontend/src/             modular React interface and API client
data/                     local persistent runtime data (Git ignored)
```

## Configuration

Copy `.env.example` to `.env` and set the key on the backend only:

```dotenv
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openrouter/free
API_CORS_ORIGINS=http://localhost:5173,http://localhost:8080
```

`OPENROUTER_API_KEY` is not sent to or compiled into the frontend. Other important controls are `SCRAPER_DELAY_SECONDS`, `SCRAPER_MAX_PAGES_PER_SOURCE`, `RETRIEVAL_TOP_K`, `RETRIEVAL_MIN_SCORE`, `CHUNK_SIZE`, and `DATA_DIR`. For the single-project Vercel deployment, frontend and API share a domain; retain `API_CORS_ORIGINS` for local development and do not add a production Vercel URL unless you later split the services.

The application checks the live OpenRouter model catalogue before generation. A configured named model must be present; `openrouter/free` is accepted only if the catalogue reports one or more current `:free` models. The official [free-model route](https://openrouter.ai/collections/free-models) lets OpenRouter choose an active free model rather than relying on an expired hard-coded ID.

## Local development

Prerequisites: Python 3.12+, Node 22+, and an OpenRouter key to generate answers.

```powershell
Copy-Item .env.example .env
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.local.txt
$env:DATA_DIR = "..\data"
python -m app.cli ingest --source all
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The UI is `http://localhost:5173`; interactive API documentation is `http://localhost:8000/docs`.

### Ingestion

Ingestion does not run at API startup:

```powershell
cd backend
python -m app.cli ingest --source darglobal
python -m app.cli ingest --source wasalt
python -m app.cli ingest --source all --rebuild
```

Documents receive a deterministic ID from their canonical URL and cleaned content. Vector-store upserts make repeat runs idempotent for unchanged chunks. `--rebuild` clears only the configured local Chroma collection or pgvector rows before storing current, permitted documents.

## Docker

```powershell
Copy-Item .env.example .env
# Add OPENROUTER_API_KEY to .env
docker compose up --build -d
docker compose run --rm backend python -m app.cli ingest --source all
```

The web app runs at `http://localhost:8080`, API at `http://localhost:8000`, and the `app-data` named volume persists SQLite and Chroma. Backend and frontend are separate non-root services; in Compose the frontend reverse-proxies `/api/` to the backend.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/chat` | Grounded answer, citations, conversation ID |
| `GET` | `/api/v1/health` | API and vector-store status |
| `GET` | `/api/v1/sources` | Indexed source/chunk statistics |
| `GET` | `/api/v1/projects` | Project cards where project metadata exists |
| `GET` | `/api/v1/conversations/{id}` | Persisted history for that UUID |

`POST /chat` accepts `{ "question": "...", "conversation_id": "optional UUID" }`. If no relevant evidence passes the similarity threshold, it returns a transparent no-information answer without calling the LLM. The API builds returned source links from actual retrieved chunks only.

## Tests

```powershell
cd backend
pytest -q
```

Tests cover cleaning/canonicalization, semantic chunking and metadata preservation, source-specific parsing with saved HTML fixtures, retrieval thresholding, API health/validation, no-context RAG behavior, and missing OpenRouter credentials. Unit tests do not call external services.

## Deployment: Vercel

Deploy this repository as **one Vercel Services project** from the repository root. The root `vercel.json` defines independently built `web` (Vite) and `api` (FastAPI) services and routes `/api/*` to FastAPI while routing every other path to the frontend. Both share one public domain, so the browser calls `/api` directly and production CORS configuration is not required for the bundled frontend.

Vercel's Python runtime supports FastAPI and Python 3.12, but Function filesystems are read-only except for temporary `/tmp` storage. Therefore, production uses one Supabase Postgres database: standard tables persist conversations and its `pgvector` extension persists/query embeddings. It does not use SQLite or local Chroma files. See Vercel's [Python runtime](https://vercel.com/docs/functions/runtimes/python), [filesystem model](https://vercel.com/docs/functions/runtimes), and Supabase's [vector-column documentation](https://supabase.com/docs/guides/ai/vector-columns).

1. Push the repository to GitHub, GitLab, or Bitbucket.
2. In Vercel, select **Add New → Project**, import the repository, and leave **Root Directory** as the repository root (`.`). Select the **Services** application preset. Vercel reads the root `vercel.json`; do not import `backend` or `frontend` individually.
3. In Supabase, enable the `vector` extension under **Database → Extensions**. From **Connect**, copy the Transaction Pooler connection string, change its prefix from `postgresql://` to `postgresql+psycopg://`, and remove `?pgbouncer=true` if shown. The application configures Psycopg/PgBouncer compatibility itself.
4. Add these **Production** environment variables in the Vercel project: `APP_ENV=production`, `LOG_LEVEL=INFO`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL=openrouter/free`, `VECTOR_STORE=pgvector`, and `DATABASE_URL` with that converted Supabase URL. Also add `EMBEDDING_PROVIDER=openrouter`, `EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b:free`, and `EMBEDDING_DIMENSION=2048`. Do not set `DATA_DIR` or `CHROMA_*` values for Vercel.
5. Deploy. Your frontend is available at `https://YOUR-APP.vercel.app`; the API is available on the same domain at `https://YOUR-APP.vercel.app/api/v1/health`.
6. Run ingestion from a trusted local or CI runner using the same production embedding configuration, otherwise its vectors cannot be compared to Vercel's query vectors. From `backend/`, load the same `DATABASE_URL` and `OPENROUTER_API_KEY`, then run:

   ```powershell
   $env:VECTOR_STORE = "pgvector"
   $env:EMBEDDING_PROVIDER = "openrouter"
   $env:EMBEDDING_MODEL = "nvidia/nemotron-3-embed-1b:free"
   $env:EMBEDDING_DIMENSION = "2048"
   python -m app.cli ingest --source all --rebuild
   ```

   Do not run ingestion inside a Vercel request function; crawling and batch embedding are unsuitable for request-time serverless work. The pgvector store labels vectors with their model/dimension profile and retrieves only matching vectors, preventing accidental mixing of local and production embedding spaces.
7. Smoke-test the home page, `/api/v1/health`, an answer with a source citation, and source links before publishing the URL.

Before ingesting, run `python -m scripts.verify_supabase` from `backend/` with those two variables set. It confirms that the connection works and that the `vector` extension is enabled.

## Known limitations

- Free-model availability and rate limits change. Configuration, upstream, and rate-limit failures are returned explicitly.
- Vercel installs `backend/requirements.txt`, which intentionally excludes Chroma, Sentence Transformers, and PyTorch to remain below the Python Function size limit. `backend/requirements.local.txt` supplies those dependencies for local development, tests, Docker, and local-only ingestion.
- Local Docker uses SQLite and a persistent Chroma directory. Vercel production instead uses Supabase Postgres and pgvector because the function filesystem is not durable.
- The initial crawl is capped at 25 pages per source. Raise it only after policy and capacity review.
- Nothing in the product infers prices, property availability, amenities, or investment returns.
