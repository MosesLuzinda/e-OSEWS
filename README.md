# e-OSEWS MVP

Minimal Electronic One Health Early Warning Surveillance System for RVF.

## Features
- REST API for creating and listing RVF surveillance events.
- Risk scoring for maternal/animal RVF signals.
- Auto alert generation for high-risk and cluster anomalies.
- Simple dashboard at `/` with events, alerts, and key counts.
- District-scoped permissions for district and VHT users.
- Alert status workflow with action history.
- Environmental observation ingestion and listing.
- Audit logging of API operations.
- Live Leaflet map and token-driven dashboard controls.
- SQLite storage for easy pilot deployment.

## Run
1. Install dependencies:
   - `python -m pip install -r requirements.txt`
2. Start server:
   - `python -m app.main`
   - Optional token override: set `EOSEWS_API_TOKEN=my-secret-token`
3. Open:
   - `http://127.0.0.1:8000/`

## Deploy on Render
1. Push this project to GitHub/GitLab.
2. In Render, click **New +** -> **Blueprint**.
3. Connect your repo and select branch.
4. Render will detect `render.yaml` and create a web service.
5. Deploy, then open:
   - `https://<your-render-service>.onrender.com/`

### Render config used
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --bind 0.0.0.0:$PORT app.main:app`
- Env var: `EOSEWS_API_TOKEN` (auto-generated in Blueprint)
- Runtime pin: `runtime.txt` (`python-3.11.9`)

### Important production note
- Current DB is SQLite (`eosews.db`), which is fine for pilot/demo but not ideal for scale.
- For multi-user production, migrate to managed Postgres.
- On Render Free, filesystem is ephemeral, so SQLite data may reset on restart/redeploy.

### First deploy checklist
- Set `EOSEWS_API_TOKEN` in Render Environment (or keep generated value).
- Redeploy after every config change.
- Verify `GET /health` returns 200.
- Verify login works at `/report-case`.
- Submit one test event and confirm it appears on `/dashboard`.

## Authentication
- API endpoints require a token in either:
  - `X-API-Token: dev-token`, or
  - `Authorization: Bearer dev-token`
- Change default token with environment variable `EOSEWS_API_TOKEN`.
- You can login to retrieve tokens with:
  - `POST /api/auth/login` using `username` and `password`

### Seeded users (MVP)
- `admin` / `admin123` (role: `admin`)
- `district_kabale` / `district123` (role: `district`)
- `district_rubanda` / `district123` (role: `district`)
- `district_isingiro` / `district123` (role: `district`)
- `vht_demo` / `vht123` (role: `vht`)

## API
- `GET /health`
- `POST /api/events`
- `GET /api/events?limit=100`
- `GET /api/alerts?limit=100`
- `POST /api/ussd/report`
- `GET /api/geo/events?limit=200&high_risk_only=false`
- `PATCH /api/alerts/{id}/status`
- `GET /api/alerts/{id}/history`
- `POST /api/auth/login`
- `POST /api/environment`
- `GET /api/environment?limit=100`
- `GET /api/audit-logs?limit=100`
- `GET /api/summary?district=Kabale`
- `GET /api/geo/environment?limit=200`

### Sample payload
```json
{
  "source_channel": "android",
  "reporter_role": "midwife",
  "district": "Kabale",
  "parish": "Kitumba",
  "species_or_patient": "pregnant_woman",
  "syndrome": "fever and miscarriage",
  "gestational_weeks": 24,
  "animal_exposure": true,
  "rainfall_index": 0.8,
  "ndvi_index": 0.7,
  "temperature_c": 31,
  "latitude": -1.25,
  "longitude": 29.98
}
```

### Sample USSD payload
```json
{
  "text": "district=Kabale;parish=Kitumba;syndrome=animal abortion;species=cattle;animal_exposure=true"
}
```

### Sample login payload
```json
{
  "username": "district_kabale",
  "password": "district123"
}
```

### Sample environment payload
```json
{
  "district": "Kabale",
  "parish": "Kitumba",
  "rainfall_index": 0.82,
  "ndvi_index": 0.61,
  "temperature_c": 29.5,
  "source": "remote_sensing"
}
```
