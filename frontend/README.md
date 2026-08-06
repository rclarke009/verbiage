# Verbiage frontend

React + TypeScript + Vite SPA for Verbiage (TanStack Query). Talks to the FastAPI backend; in local dev Vite proxies API requests to `:8000`.

## Run

From the repo root, prefer the two-terminal setup in [../setup.md](../setup.md#local-development-vite--uvicorn-hot-reload-spa) (API on `:8000`, Vite on `:5173`).

Or from this directory after dependencies are installed:

```bash
npm install
npm run dev
```

Production builds are served by the FastAPI app (see root [../README.md](../README.md) and Docker/`render.yaml`).

## Stack

- React + TypeScript + Vite
- TanStack Query for server state
- Supabase Auth (JWT) for signed-in flows; demo mode can skip sign-in when configured on the backend
