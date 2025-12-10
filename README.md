## Vertikal Agent Website

A Flask-based website and admin panel for Vertikal Agent with blogging, lead capture, and AI agent routes. Includes rich blog editing with image uploads, Markdown paste, SEO fields, tags, analytics, and visitor logging.

### Tech Stack
- **Backend**: Flask, SQLAlchemy, Flask-Migrate
- **DB**: MySQL (docker-compose) or any SQLAlchemy-supported DB (Postgres by default if `DATABASE_URL` not set)
- **Frontend**: Jinja2 + Tailwind (via CDN)
- **Editor**: Quill with Markdown paste support
- **Prod Server (Docker)**: Gunicorn

---

## Quick Start (Local)

Prereqs:
- Python 3.11+
- `uv` (fast Python package manager)

Setup:
```bash
# from webisite/
uv sync
cp .env.example .env  # if present; otherwise create a minimal .env (see ENV below)
```

Run DB migrations:
```bash
uv run flask --app main db upgrade
```

Start the app:
```bash
# Option A: Flask dev server (http://127.0.0.1:5000)
uv run flask --app main run

# Option B: Python entrypoint (reads DEBUG from config)
uv run python main.py
```

Create an admin user:
```bash
uv run flask --app main create-admin
```

Log in to Admin:
- Navigate to `/admin/login`
- Then manage posts via `/admin/blogs/manage`

---

## Quick Start (Docker)

Start services:
```bash
docker compose up -d
```

Run DB migrations inside the web container:
```bash
docker compose exec web uv run flask --app main db upgrade
```

Create an admin:
```bash
docker compose exec web uv run flask --app main create-admin
```

The app serves on `http://localhost:8000`.

---

## Configuration (ENV)

Set these in your shell or `.env`:
- `SECRET_KEY` (required in production)
- `DATABASE_URL` (SQLAlchemy URL)
  - Docker compose uses: `mysql+pymysql://root:root@db/vertikal_agent`
  - Default (if unset): a Postgres Neon URL from `src/config.py`
- OpenAI (optional, for AI features):
  - `OPENAI_API_KEY`
  - `OPENAI_AGENT_MODEL` (default: `gpt-4o-mini`)
  - `OPENAI_SYSTEM_PROMPT`
- LiveKit (optional, for voice agent):
  - `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
  - `LIVEKIT_AGENT_ID`, `LIVEKIT_AGENT_TEMPLATE`
  - `LIVEKIT_STATIC_TOKEN`, `LIVEKIT_STATIC_ROOM`, `LIVEKIT_STATIC_IDENTITY`

---

## Blog Features

### Create/Edit Posts
- Route: `/admin/blogs/new` and `/admin/blogs/<id>/edit`
- Required: Title, content
- Optional: Subtitle, tags (comma-separated), SEO fields (meta title/description/keywords), excerpt
- Slugs auto-generated and de-duplicated
- Posts are published on save

### Cover Images
- Two options:
  - Paste a cover URL
  - Upload a cover file (PNG/JPG/JPEG/GIF/WEBP)
- Uploaded covers stored at: `src/static/uploads/blog_covers/`

### Inline Images (Story Body)
- Click the image button in the editor toolbar → select a local file
- File uploads to `/admin/blogs/upload-image`
- Stored at: `src/static/uploads/blog_images/`
- Allowed: `png`, `jpg`, `jpeg`, `gif`, `webp`
- Display rules:
  - Editor: responsive, centered, max-height 480px
  - Blog page: responsive, centered, lazy-loaded, max-height 640px

### Markdown Paste
- Paste Markdown directly into the editor; it auto-converts to rich text (headings, lists, code blocks, bold/italics, links, images).

### Tags and Filters
- Tags are created on the fly
- Blog list supports filtering via `?tag=<slug>`

### Analytics and Views
- Each post view is recorded with device and basic geo lookup
- Admin manage page shows basic read stats

### Spacing and Typography
- Published content ensures visible spacing between paragraphs and lists
- Links are styled with underline for readability

---

## Public Pages
- Blog list: `/admin/blog` (public listing via website blueprint routing)
- Blog detail: `/admin/blog/<slug>`

Note: Depending on how routing is mounted in your environment, blog URLs might be exposed via website routes as well. The templates live under `src/templates/`.

---

## Commands Cheat Sheet
```bash
# Migrations
uv run flask --app main db init       # first-time only
uv run flask --app main db migrate    # when models change
uv run flask --app main db upgrade    # apply migrations

# Admin user
uv run flask --app main create-admin

# Run dev
uv run flask --app main run
```

Docker:
```bash
docker compose up -d
docker compose logs -f web
docker compose exec web uv run flask --app main db upgrade
docker compose exec web uv run flask --app main create-admin
```

---

## File Structure Highlights
- `main.py`: Flask app setup, CLI commands, blueprints
- `src/config.py`: environment configuration
- `src/models/database.py`: SQLAlchemy models and `db`
- `src/route/admin_route/admin.py`: Admin routes (blogs, users, analytics)
- `src/templates/`: Jinja templates (blog pages, admin UI)
- `src/static/`: static assets; uploads under `uploads/`
- `migrations/`: Alembic migrations

---

## Troubleshooting
- Images don’t render:
  - Ensure `/static/` is reachable and file exists under `src/static/uploads/...`
  - Verify allowed extensions (PNG/JPG/JPEG/GIF/WEBP)
- No spacing between blocks:
  - The blog detail template enforces margins for paragraphs/lists. If you added custom CSS, verify it doesn’t override `.blog-content` rules.
- DB connection issues:
  - Verify `DATABASE_URL` and that the DB service is reachable
  - For Docker: `docker compose ps` and check `db` health
- Migrations:
  - Run `db upgrade` again if you changed DBs or containers

---

## Production Notes
- Use the Dockerfile and `docker-compose.yml` or your preferred orchestrator
- Place the app behind a reverse proxy (Nginx) for TLS and static caching
- Set a strong `SECRET_KEY` and a production-grade `DATABASE_URL`
- Consider offloading static files to a CDN for performance

---

## License
Proprietary – All rights reserved (adjust per your needs).


