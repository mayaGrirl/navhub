# Nav

A link directory with a separate Vue frontend and FastAPI backend. They are meant to share one domain: pages on `/`, API on `/api`. See `deploy/nginx.conf`.

## Stack

- Frontend: Vue 3, Vite, Vue Router, Pinia, Element Plus
- Backend: FastAPI, MySQL, Redis
- Proxy pool: a second Python app in `proxy-pool`. The directory calls it only when `PROXY_POOL_URL` is set.

## Run

Start MySQL and Redis, then:

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Or `docker compose up` from this folder.

On first API start, the admin URL fragment is written to `backend/data/admin_gate.txt`. Open `http://127.0.0.1:5173/<that fragment>` after logging in as the admin. Default admin is `admin@example.com` / `change-me-now`. Change both before any public deploy. The admin must enable an authenticator code before editing.

The adult tab is an empty 18+ link section. It does not crawl adult sites. Paid-video parsers are not part of this project.
