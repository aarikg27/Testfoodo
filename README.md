# Testfoodo

Testfoodo is a mobile-first UMD dining hall nutrition tracker. It imports current menus from `nutrition.umd.edu`, lets users log servings against daily macro goals, saves favorites and meals, and recommends available combinations that fit remaining calories, protein, carbohydrates, and fat.

## Stack

- **Frontend:** vanilla HTML, CSS, and JavaScript on Cloudflare Pages
- **API and accounts:** FastAPI on Render
- **Database:** Neon PostgreSQL
- **Menu importer:** Python Playwright request client, scheduled with GitHub Actions

The frontend also has a guest mode backed by browser storage. Creating a new account migrates guest goals, logs, favorites, and dietary settings when possible.

## Project layout

```text
backend/
  app/
    main.py                 FastAPI application
    models.py               SQLAlchemy database models
    scraper.py              UMD menu and nutrition scraper
    recommendations.py      Macro combination scoring
    routers/                API endpoints
  schema.sql                Reviewable Neon/PostgreSQL schema
  tests/                    Parser, auth, and recommendation tests
frontend/
  index.html                Dashboard structure
  styles.css                Responsive UI
  app.js                    Goals, logs, accounts, filters, and recommendations
render.yaml                 Render free web-service blueprint
.github/workflows/scrape.yml
```

## Local setup

Python 3.12 is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd backend
python -m app.db_init
python -m app.seed_demo
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
python3 -m http.server 5173
```

Open [http://localhost:5173](http://localhost:5173). API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

SQLite is used automatically for local development. `python -m app.seed_demo` inserts a small same-day menu for UI development only; do not run it against production.

## Run the real scraper

From `backend/` with the environment active:

```bash
python -m app.scraper --days 7
```

Useful options:

```bash
python -m app.scraper --date 2026-08-31 --days 1 --hall 19
python -m app.scraper --days 7 --force-nutrition-refresh
```

UMD hall source IDs are `16` for South Campus, `19` for Yahentamitsi, and `51` for 251 North. Nutrition records are cached for 30 days by default, while daily availability is always replaced idempotently for the requested hall/date scope.

The importer records warnings and completion counts in `scrape_runs`. Two or three unavailable label pages do not discard the rest of a successful menu refresh.

## API overview

Public endpoints:

```text
GET  /health
GET  /api/v1/halls?date=2026-08-31
GET  /api/v1/foods?hall=yahentamitsi&date=2026-08-31&meal=Lunch
GET  /api/v1/scrape-status
POST /api/v1/recommendations
```

Account endpoints:

```text
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
GET    /api/v1/users/me/goals
PUT    /api/v1/users/me/goals
GET    /api/v1/users/me/logs
POST   /api/v1/users/me/logs
PATCH  /api/v1/users/me/logs/{id}
DELETE /api/v1/users/me/logs/{id}
GET    /api/v1/users/me/favorites
POST   /api/v1/users/me/favorites
GET    /api/v1/users/me/saved-meals
POST   /api/v1/users/me/saved-meals
```

Passwords are hashed with Argon2. Login tokens are random, revocable, expire automatically, and are stored only as SHA-256 hashes in the database. The frontend stores the active bearer token locally. For a larger public launch, add email verification, password-reset email, and distributed login rate limiting or replace local authentication with a managed provider.

## Free deployment

### 1. Neon

1. Create a free Neon project without adding a payment method.
2. Copy its pooled connection string, including `sslmode=require`.
3. Keep it private. Never put it in the frontend or commit it to Git.

The API creates tables and the three dining halls automatically on its first start. You can alternatively run `backend/schema.sql` in the Neon SQL editor.

### 2. Render

1. In Render, create a new Blueprint from this repository. It will read `render.yaml`.
2. Choose the free web-service plan.
3. Set the secret `DATABASE_URL` to the Neon connection string.
4. After Render gives you the final `onrender.com` URL, update `frontend/config.js` if it differs from `https://testfoodo-api.onrender.com/api/v1`.

Free Render services sleep after inactivity, so the first API request can take about a minute.

### 3. Cloudflare Pages

1. Create a Pages project from the GitHub repository.
2. Set the production branch to `main`.
3. Leave the build command blank.
4. Set the build output directory to `frontend`.
5. After Cloudflare gives you the final `pages.dev` hostname, set Render's `ALLOWED_ORIGINS` to that exact origin and the local origins, separated by commas.

Example:

```text
https://testfoodo.pages.dev,http://localhost:5173,http://127.0.0.1:5173
```

### 4. Scheduled menu refresh

In GitHub, open **Settings → Secrets and variables → Actions** and create a repository secret named `DATABASE_URL` containing the Neon connection string. The included workflow runs each morning and can also be started manually from the Actions tab.

## Testing

```bash
cd backend
../.venv/bin/pytest -q
```

The tests use saved, minimal UMD HTML fixtures so parser changes can be checked without repeatedly requesting the live site.

## Nutrition and allergen notice

UMD describes its nutrition analysis as approximate. Testfoodo displays that warning in the interface. Dietary and allergen labels are informational and must not be treated as a guarantee; users should verify ingredients with dining staff.

