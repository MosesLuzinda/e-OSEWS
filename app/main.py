from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sqlite3
import secrets
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "eosews.db"

app = Flask(__name__, template_folder="templates", static_folder="static")
API_TOKEN = os.getenv("EOSEWS_API_TOKEN", "dev-token")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT UNIQUE,
            reporter_ip TEXT,
            reporter_name TEXT,
            reporter_contact TEXT,
            source_channel TEXT DEFAULT 'android',
            reporter_role TEXT NOT NULL,
            district TEXT NOT NULL,
            parish TEXT NOT NULL,
            species_or_patient TEXT NOT NULL,
            syndrome TEXT NOT NULL,
            gestational_weeks INTEGER,
            animal_exposure INTEGER DEFAULT 0,
            rainfall_index REAL DEFAULT 0,
            ndvi_index REAL DEFAULT 0,
            temperature_c REAL DEFAULT 0,
            latitude REAL DEFAULT 0,
            longitude REAL DEFAULT 0,
            risk_score REAL DEFAULT 0,
            high_risk INTEGER DEFAULT 0,
            validation_status TEXT DEFAULT 'ok',
            validation_notes TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            district TEXT NOT NULL,
            parish TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            signal_score REAL DEFAULT 0,
            reporter_latitude REAL,
            reporter_longitude REAL,
            reporter_ip TEXT,
            details TEXT NOT NULL,
            status TEXT DEFAULT 'new',
            reviewed_by TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            district TEXT,
            api_token TEXT NOT NULL UNIQUE,
            is_active INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS environmental_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            district TEXT NOT NULL,
            parish TEXT NOT NULL,
            rainfall_index REAL DEFAULT 0,
            ndvi_index REAL DEFAULT 0,
            temperature_c REAL DEFAULT 0,
            source TEXT DEFAULT 'manual',
            observed_at TEXT NOT NULL,
            created_by TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            action_by TEXT NOT NULL,
            action_note TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            district TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    ensure_event_columns(conn)
    ensure_alert_columns(conn)
    ensure_user_columns(conn)
    seed_default_users(conn)
    conn.commit()
    conn.close()


def ensure_event_columns(conn: sqlite3.Connection):
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
    if "idempotency_key" not in existing_columns:
        conn.execute("ALTER TABLE events ADD COLUMN idempotency_key TEXT")
    if "reporter_ip" not in existing_columns:
        conn.execute("ALTER TABLE events ADD COLUMN reporter_ip TEXT")
    if "validation_status" not in existing_columns:
        conn.execute("ALTER TABLE events ADD COLUMN validation_status TEXT DEFAULT 'ok'")
    if "validation_notes" not in existing_columns:
        conn.execute("ALTER TABLE events ADD COLUMN validation_notes TEXT")
    if "reporter_name" not in existing_columns:
        conn.execute("ALTER TABLE events ADD COLUMN reporter_name TEXT")
    if "reporter_contact" not in existing_columns:
        conn.execute("ALTER TABLE events ADD COLUMN reporter_contact TEXT")


def ensure_alert_columns(conn: sqlite3.Connection):
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(alerts)").fetchall()}
    if "status" not in existing_columns:
        conn.execute("ALTER TABLE alerts ADD COLUMN status TEXT DEFAULT 'new'")
    if "reviewed_by" not in existing_columns:
        conn.execute("ALTER TABLE alerts ADD COLUMN reviewed_by TEXT")
    if "reviewed_at" not in existing_columns:
        conn.execute("ALTER TABLE alerts ADD COLUMN reviewed_at TEXT")
    if "reporter_latitude" not in existing_columns:
        conn.execute("ALTER TABLE alerts ADD COLUMN reporter_latitude REAL")
    if "reporter_longitude" not in existing_columns:
        conn.execute("ALTER TABLE alerts ADD COLUMN reporter_longitude REAL")
    if "reporter_ip" not in existing_columns:
        conn.execute("ALTER TABLE alerts ADD COLUMN reporter_ip TEXT")


def ensure_user_columns(conn: sqlite3.Connection):
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "district" not in existing_columns:
        conn.execute("ALTER TABLE users ADD COLUMN district TEXT")


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def seed_default_users(conn: sqlite3.Connection):
    defaults = [
        ("admin", "admin123", "admin", None, API_TOKEN),
        ("district_kabale", "district123", "district", "Kabale", secrets.token_hex(16)),
        ("district_rubanda", "district123", "district", "Rubanda", secrets.token_hex(16)),
        ("district_isingiro", "district123", "district", "Isingiro", secrets.token_hex(16)),
        ("vht_demo", "vht123", "vht", "Kabale", secrets.token_hex(16)),
    ]
    for username, password, role, district, token in defaults:
        exists = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            conn.execute(
                "UPDATE users SET district = COALESCE(district, ?) WHERE username = ?",
                (district, username),
            )
            continue
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role, district, api_token, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (username, hash_password(password), role, district, token),
        )


def require_api_token(required_roles: set[str] | None = None):
    header_token = request.headers.get("X-API-Token")
    auth_header = request.headers.get("Authorization", "")
    bearer_token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    token = header_token or bearer_token

    conn = get_db()
    user = conn.execute(
        """
        SELECT username, role, district, is_active FROM users WHERE api_token = ?
        """,
        (token,),
    ).fetchone()
    conn.close()

    if not user or int(user["is_active"]) != 1:
        return jsonify({"error": "Unauthorized. Provide valid X-API-Token."}), 401

    if required_roles and user["role"] not in required_roles:
        return jsonify({"error": f"Forbidden for role '{user['role']}'."}), 403

    g.current_user = {"username": user["username"], "role": user["role"], "district": user["district"]}
    return None


def scope_filter(table_alias: str = "") -> tuple[str, list[object]]:
    prefix = f"{table_alias}." if table_alias else ""
    if g.current_user["role"] == "district":
        return f" WHERE {prefix}district = ?", [g.current_user["district"]]
    if g.current_user["role"] == "vht":
        return f" WHERE {prefix}district = ? AND {prefix}source_channel = 'ussd'", [g.current_user["district"]]
    return "", []


def enforce_district_write(district: str):
    role = g.current_user["role"]
    if role == "district" and district != g.current_user["district"]:
        return jsonify({"error": "District users can only write within their district."}), 403
    if role == "vht" and district != g.current_user["district"]:
        return jsonify({"error": "VHT users can only submit within their district."}), 403
    return None


def audit(action: str, resource_type: str, resource_id: str | None = None, district: str | None = None, metadata: str | None = None):
    conn = get_db()
    conn.execute(
        """
        INSERT INTO audit_logs (username, role, action, resource_type, resource_id, district, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.current_user["username"],
            g.current_user["role"],
            action,
            resource_type,
            resource_id,
            district,
            metadata,
            dt.datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def calculate_risk_score(payload: dict) -> float:
    score = 0.1
    syndrome = str(payload.get("syndrome", "")).lower()
    if "fever" in syndrome:
        score += 0.2
    if "abortion" in syndrome or "miscarriage" in syndrome:
        score += 0.3
    if bool(payload.get("animal_exposure", False)):
        score += 0.2

    rainfall = float(payload.get("rainfall_index", 0.0))
    ndvi = float(payload.get("ndvi_index", 0.0))
    temp = float(payload.get("temperature_c", 0.0))
    gest = payload.get("gestational_weeks")

    score += min(max(rainfall, 0.0), 1.0) * 0.1
    score += min(max(ndvi, 0.0), 1.0) * 0.05
    if temp >= 30:
        score += 0.05
    if gest is not None and int(gest) >= 20:
        score += 0.1
    return round(min(score, 1.0), 3)


def validate_event_payload(payload: dict) -> tuple[list[str], list[str], dict]:
    required = ["reporter_role", "district", "parish", "species_or_patient", "syndrome"]
    missing = [k for k in required if not payload.get(k)]
    quality_flags: list[str] = []
    normalized = dict(payload)

    lat = payload.get("latitude")
    lon = payload.get("longitude")
    rainfall = payload.get("rainfall_index")
    ndvi = payload.get("ndvi_index")
    temp = payload.get("temperature_c")

    if lat is not None:
        try:
            normalized["latitude"] = float(lat)
            if not -90 <= normalized["latitude"] <= 90:
                quality_flags.append("latitude_out_of_range")
        except (TypeError, ValueError):
            quality_flags.append("latitude_invalid")

    if lon is not None:
        try:
            normalized["longitude"] = float(lon)
            if not -180 <= normalized["longitude"] <= 180:
                quality_flags.append("longitude_out_of_range")
        except (TypeError, ValueError):
            quality_flags.append("longitude_invalid")

    if rainfall is not None:
        try:
            normalized["rainfall_index"] = float(rainfall)
            if not 0 <= normalized["rainfall_index"] <= 1:
                quality_flags.append("rainfall_index_out_of_range")
        except (TypeError, ValueError):
            quality_flags.append("rainfall_index_invalid")

    if ndvi is not None:
        try:
            normalized["ndvi_index"] = float(ndvi)
            if not 0 <= normalized["ndvi_index"] <= 1:
                quality_flags.append("ndvi_index_out_of_range")
        except (TypeError, ValueError):
            quality_flags.append("ndvi_index_invalid")

    if temp is not None:
        try:
            normalized["temperature_c"] = float(temp)
            if not -50 <= normalized["temperature_c"] <= 80:
                quality_flags.append("temperature_c_out_of_range")
        except (TypeError, ValueError):
            quality_flags.append("temperature_c_invalid")

    if payload.get("gestational_weeks") not in (None, ""):
        try:
            normalized["gestational_weeks"] = int(payload.get("gestational_weeks"))
            if not 1 <= normalized["gestational_weeks"] <= 45:
                quality_flags.append("gestational_weeks_out_of_range")
        except (TypeError, ValueError):
            quality_flags.append("gestational_weeks_invalid")

    return missing, quality_flags, normalized


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "e-OSEWS"})


@app.post("/api/events")
def create_event():
    unauthorized = require_api_token({"vht", "vet", "clinician", "midwife", "district", "admin"})
    if unauthorized:
        return unauthorized

    payload = request.get_json(force=True)
    missing, quality_flags, normalized = validate_event_payload(payload)
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    write_restricted = enforce_district_write(normalized["district"])
    if write_restricted:
        return write_restricted

    idem_key = payload.get("idempotency_key")

    risk_score = calculate_risk_score(normalized)
    high_risk = 1 if risk_score >= 0.7 else 0
    now = dt.datetime.utcnow().isoformat()
    validation_status = "flagged" if quality_flags else "ok"
    validation_notes = json.dumps(quality_flags) if quality_flags else None

    conn = get_db()
    cur = conn.cursor()
    if idem_key:
        existing = cur.execute("SELECT * FROM events WHERE idempotency_key = ?", (idem_key,)).fetchone()
        if existing:
            conn.close()
            return jsonify(dict(existing))
    cur.execute(
        """
        INSERT INTO events (
            reporter_ip, reporter_name, reporter_contact, source_channel, reporter_role, district, parish, species_or_patient, syndrome,
            gestational_weeks, animal_exposure, rainfall_index, ndvi_index, temperature_c,
            latitude, longitude, risk_score, high_risk, validation_status, validation_notes, idempotency_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("ip_address") or request.remote_addr,
            normalized.get("reporter_name"),
            normalized.get("reporter_contact"),
            normalized.get("source_channel", "android"),
            normalized["reporter_role"],
            normalized["district"],
            normalized["parish"],
            normalized["species_or_patient"],
            normalized["syndrome"],
            normalized.get("gestational_weeks"),
            1 if normalized.get("animal_exposure", False) else 0,
            normalized.get("rainfall_index", 0.0),
            normalized.get("ndvi_index", 0.0),
            normalized.get("temperature_c", 0.0),
            normalized.get("latitude", 0.0),
            normalized.get("longitude", 0.0),
            risk_score,
            high_risk,
            validation_status,
            validation_notes,
            idem_key,
            now,
        ),
    )
    event_id = cur.lastrowid

    recent_count = cur.execute(
        """
        SELECT COUNT(*) FROM events
        WHERE district = ? AND parish = ? AND syndrome = ?
        """,
        (normalized["district"], normalized["parish"], normalized["syndrome"]),
    ).fetchone()[0]

    if high_risk or recent_count >= 3:
        severity = "high" if high_risk else "medium"
        signal_score = risk_score if high_risk else round(min(0.5 + recent_count * 0.1, 0.95), 3)
        details = (
            "High-risk maternal/animal signal detected."
            if high_risk
            else "Cluster anomaly: repeated syndrome reports in same parish."
        )
        cur.execute(
            """
            INSERT INTO alerts (
                district, parish, alert_type, severity, signal_score,
                reporter_latitude, reporter_longitude, reporter_ip,
                details, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized["district"],
                normalized["parish"],
                "risk_signal" if high_risk else "cluster_anomaly",
                severity,
                signal_score,
                normalized.get("latitude", 0.0),
                normalized.get("longitude", 0.0),
                payload.get("ip_address") or request.remote_addr,
                details,
                "new",
                now,
            ),
        )

    conn.commit()
    row = cur.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    audit("create", "event", str(event_id), normalized["district"], f"syndrome={normalized['syndrome']}")
    return jsonify(dict(row))


@app.get("/api/events")
def list_events():
    unauthorized = require_api_token({"clinician", "midwife", "district", "admin", "vet"})
    if unauthorized:
        return unauthorized

    limit = int(request.args.get("limit", 100))
    where_sql, where_params = scope_filter()
    high_risk_only = request.args.get("high_risk_only", "false").lower() == "true"
    district_filter = str(request.args.get("district", "")).strip()
    validation_status = str(request.args.get("validation_status", "")).strip().lower()
    allowed_status = {"ok", "flagged", "reviewed", "dismissed"}

    def append_condition(condition: str, param: object | None = None):
        nonlocal where_sql, where_params
        if where_sql:
            where_sql = f"{where_sql} AND {condition}"
        else:
            where_sql = f" WHERE {condition}"
        if param is not None:
            where_params.append(param)

    if high_risk_only:
        append_condition("high_risk = 1")
    if district_filter:
        append_condition("district = ?", district_filter)
    if validation_status:
        if validation_status not in allowed_status:
            return jsonify({"error": "Invalid validation_status filter"}), 400
        append_condition("validation_status = ?", validation_status)

    conn = get_db()
    rows = conn.execute(f"SELECT * FROM events{where_sql} ORDER BY created_at DESC LIMIT ?", where_params + [limit]).fetchall()
    conn.close()
    audit("read", "event_list", metadata=f"limit={limit}")
    return jsonify([dict(r) for r in rows])


@app.get("/api/events/flags")
def list_flagged_events():
    unauthorized = require_api_token({"clinician", "midwife", "district", "admin", "vet"})
    if unauthorized:
        return unauthorized

    limit = int(request.args.get("limit", 100))
    status = str(request.args.get("status", "flagged")).strip().lower()
    district_filter = str(request.args.get("district", "")).strip()
    allowed = {"flagged", "reviewed", "dismissed", "ok", "all"}
    if status not in allowed:
        return jsonify({"error": f"Invalid status filter. Use one of: {', '.join(sorted(allowed))}"}), 400
    where_sql, where_params = scope_filter()
    if status != "all":
        if where_sql:
            where_sql = f"{where_sql} AND validation_status = ?"
            where_params.append(status)
        else:
            where_sql = " WHERE validation_status = ?"
            where_params = [status]
    if district_filter:
        if where_sql:
            where_sql = f"{where_sql} AND district = ?"
        else:
            where_sql = " WHERE district = ?"
        where_params.append(district_filter)

    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM events{where_sql} ORDER BY created_at DESC LIMIT ?",
        where_params + [limit],
    ).fetchall()
    conn.close()

    flagged = []
    for r in rows:
        item = dict(r)
        notes_raw = item.get("validation_notes")
        if notes_raw:
            try:
                item["validation_notes"] = json.loads(notes_raw)
            except json.JSONDecodeError:
                pass
        flagged.append(item)

    audit("read", "event_flags", metadata=f"limit={limit},status={status}")
    return jsonify(flagged)


@app.get("/api/events/flags/summary")
def flagged_events_summary():
    unauthorized = require_api_token({"clinician", "midwife", "district", "admin", "vet"})
    if unauthorized:
        return unauthorized

    where_sql, where_params = scope_filter()
    conn = get_db()
    row = conn.execute(
        f"""
        SELECT
          SUM(CASE WHEN validation_status = 'flagged' THEN 1 ELSE 0 END) AS flagged,
          SUM(CASE WHEN validation_status = 'reviewed' THEN 1 ELSE 0 END) AS reviewed,
          SUM(CASE WHEN validation_status = 'dismissed' THEN 1 ELSE 0 END) AS dismissed,
          SUM(CASE WHEN validation_status = 'ok' THEN 1 ELSE 0 END) AS ok_count,
          COUNT(*) AS total
        FROM events{where_sql}
        """,
        where_params,
    ).fetchone()
    conn.close()

    summary = {
        "flagged": int(row["flagged"] or 0),
        "reviewed": int(row["reviewed"] or 0),
        "dismissed": int(row["dismissed"] or 0),
        "ok": int(row["ok_count"] or 0),
        "all": int(row["total"] or 0),
    }
    audit("read", "event_flags_summary", metadata=json.dumps(summary))
    return jsonify(summary)


@app.patch("/api/events/<int:event_id>/validation-status")
def update_event_validation_status(event_id: int):
    unauthorized = require_api_token({"district", "admin", "clinician", "midwife", "vet"})
    if unauthorized:
        return unauthorized

    payload = request.get_json(force=True)
    new_status = str(payload.get("status", "")).strip().lower()
    valid_statuses = {"flagged", "reviewed", "dismissed", "ok"}
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Use one of: {', '.join(sorted(valid_statuses))}"}), 400

    now = dt.datetime.utcnow().isoformat()
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Event not found"}), 404
    if g.current_user["role"] == "district" and row["district"] != g.current_user["district"]:
        conn.close()
        return jsonify({"error": "Forbidden outside your district."}), 403

    old_status = row["validation_status"] or "ok"
    notes = row["validation_notes"]
    if payload.get("note"):
        try:
            parsed = json.loads(notes) if notes else []
            if not isinstance(parsed, list):
                parsed = [str(parsed)]
        except json.JSONDecodeError:
            parsed = [str(notes)] if notes else []
        parsed.append(f"review_note:{payload['note']}")
        notes = json.dumps(parsed)

    cur.execute(
        """
        UPDATE events
        SET validation_status = ?, validation_notes = ?
        WHERE id = ?
        """,
        (new_status, notes, event_id),
    )
    conn.commit()
    updated = cur.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    audit("update", "event_validation_status", str(event_id), updated["district"], f"{old_status}->{new_status}")
    return jsonify(dict(updated))


@app.get("/api/alerts")
def list_alerts():
    unauthorized = require_api_token({"district", "admin", "clinician", "midwife", "vet"})
    if unauthorized:
        return unauthorized

    limit = int(request.args.get("limit", 100))
    where_sql, where_params = scope_filter()
    district_filter = str(request.args.get("district", "")).strip()
    if district_filter:
        if where_sql:
            where_sql = f"{where_sql} AND district = ?"
        else:
            where_sql = " WHERE district = ?"
        where_params.append(district_filter)
    conn = get_db()
    rows = conn.execute(f"SELECT * FROM alerts{where_sql} ORDER BY created_at DESC LIMIT ?", where_params + [limit]).fetchall()
    conn.close()
    audit("read", "alert_list", metadata=f"limit={limit}")
    return jsonify([dict(r) for r in rows])


@app.get("/")
def home():
    return render_template("landing.html")


@app.get("/site-home")
def site_home():
    return render_template("site/home.html", current_page="home")


@app.get("/report-case")
def report_case_page():
    return render_template("report_case.html")


@app.get("/about")
def site_about():
    return render_template("site/about.html", current_page="about")


@app.get("/design")
def site_design():
    return render_template("site/design.html", current_page="design")


@app.get("/implementation")
def site_implementation():
    return render_template("site/implementation.html", current_page="implementation")


@app.get("/data-ai")
def site_data_ai():
    return render_template("site/data_ai.html", current_page="data_ai")


@app.get("/pilot-evaluation")
def site_pilot():
    return render_template("site/pilot.html", current_page="pilot")


@app.get("/resources")
def site_resources():
    return render_template("site/resources.html", current_page="resources")


@app.get("/contact")
def site_contact():
    return render_template("site/contact.html", current_page="contact")


@app.get("/welcome-legacy")
def landing_legacy():
    """Original single-page splash (optional)."""
    return render_template("landing.html")


@app.get("/assets/logo1.png")
def landing_logo():
    return send_from_directory(BASE_DIR, "logo1.png")


@app.get("/assets/logo.png")
def landing_logo_png():
    preferred = BASE_DIR / "logo.png"
    if preferred.exists():
        return send_from_directory(BASE_DIR, "logo.png")
    return send_from_directory(BASE_DIR, "logo1.png")


@app.get("/dashboard")
def dashboard():
    # Login-gated dashboard: do not preload sensitive rows into HTML source.
    events = []
    alerts = []
    env_rows = []
    stats_row = {
        "total_events": 0,
        "total_alerts": 0,
        "high_risk_events": 0,
        "flagged_events": 0,
        "total_env_points": 0,
    }
    return render_template(
        "dashboard.html",
        events=events,
        alerts=alerts,
        env_rows=env_rows,
        stats=stats_row,
        current_page="dashboard",
    )


@app.get("/api/public/geo/events")
def public_geo_events():
    limit = int(request.args.get("limit", 200))
    high_risk_only = request.args.get("high_risk_only", "false").lower() == "true"
    district = str(request.args.get("district", "")).strip()

    query = "SELECT * FROM events"
    params: list[object] = []
    if high_risk_only:
        query += " WHERE high_risk = 1"
    if district:
        query += " AND district = ?" if "WHERE" in query else " WHERE district = ?"
        params.append(district)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    features = []
    for r in rows:
        if r["latitude"] is None or r["longitude"] is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": {
                    "id": r["id"],
                    "district": r["district"],
                    "parish": r["parish"],
                    "syndrome": r["syndrome"],
                    "risk_score": r["risk_score"],
                    "high_risk": bool(r["high_risk"]),
                    "created_at": r["created_at"],
                },
            }
        )
    return jsonify({"type": "FeatureCollection", "features": features})


@app.get("/api/public/summary")
def public_summary():
    district = str(request.args.get("district", "")).strip()
    where = ""
    params: list[object] = []
    if district:
        where = " WHERE district = ?"
        params.append(district)

    conn = get_db()
    totals = conn.execute(
        f"""
        SELECT
          COUNT(*) AS total_events,
          SUM(CASE WHEN high_risk = 1 THEN 1 ELSE 0 END) AS high_risk_events,
          SUM(CASE WHEN validation_status = 'flagged' THEN 1 ELSE 0 END) AS flagged_events
        FROM events{where}
        """,
        params,
    ).fetchone()
    alerts = conn.execute(
        f"""
        SELECT
          COUNT(*) AS total_alerts,
          SUM(CASE WHEN status = 'new' THEN 1 ELSE 0 END) AS new_alerts,
          SUM(CASE WHEN status = 'investigating' THEN 1 ELSE 0 END) AS investigating_alerts
        FROM alerts{where}
        """,
        params,
    ).fetchone()
    env = conn.execute(
        f"SELECT COUNT(*) AS env_points FROM environmental_observations{where}",
        params,
    ).fetchone()
    conn.close()

    return jsonify(
        {
            "district": district or None,
            "total_events": int(totals["total_events"] or 0),
            "high_risk_events": int(totals["high_risk_events"] or 0),
            "flagged_events": int(totals["flagged_events"] or 0),
            "total_alerts": int(alerts["total_alerts"] or 0),
            "new_alerts": int(alerts["new_alerts"] or 0),
            "investigating_alerts": int(alerts["investigating_alerts"] or 0),
            "env_points": int(env["env_points"] or 0),
        }
    )


@app.get("/api/public/events")
def public_events():
    limit = int(request.args.get("limit", 100))
    high_risk_only = request.args.get("high_risk_only", "false").lower() == "true"
    validation_status = str(request.args.get("validation_status", "")).strip().lower()
    district = str(request.args.get("district", "")).strip()
    allowed_status = {"ok", "flagged", "reviewed", "dismissed"}

    where_sql = ""
    params: list[object] = []

    def append_condition(condition: str, param: object | None = None):
        nonlocal where_sql, params
        if where_sql:
            where_sql = f"{where_sql} AND {condition}"
        else:
            where_sql = f" WHERE {condition}"
        if param is not None:
            params.append(param)

    if high_risk_only:
        append_condition("high_risk = 1")
    if district:
        append_condition("district = ?", district)
    if validation_status:
        if validation_status not in allowed_status:
            return jsonify({"error": "Invalid validation_status filter"}), 400
        append_condition("validation_status = ?", validation_status)

    conn = get_db()
    rows = conn.execute(f"SELECT * FROM events{where_sql} ORDER BY created_at DESC LIMIT ?", params + [limit]).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/public/events/flags")
def public_flagged_events():
    limit = int(request.args.get("limit", 100))
    status = str(request.args.get("status", "flagged")).strip().lower()
    district = str(request.args.get("district", "")).strip()
    allowed = {"flagged", "reviewed", "dismissed", "ok", "all"}
    if status not in allowed:
        return jsonify({"error": f"Invalid status filter. Use one of: {', '.join(sorted(allowed))}"}), 400

    where_sql = ""
    params: list[object] = []
    if status != "all":
        where_sql = " WHERE validation_status = ?"
        params.append(status)
    if district:
        where_sql = f"{where_sql} AND district = ?" if where_sql else " WHERE district = ?"
        params.append(district)

    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM events{where_sql} ORDER BY created_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    conn.close()

    flagged = []
    for r in rows:
        item = dict(r)
        notes_raw = item.get("validation_notes")
        if notes_raw:
            try:
                item["validation_notes"] = json.loads(notes_raw)
            except json.JSONDecodeError:
                pass
        flagged.append(item)
    return jsonify(flagged)


@app.get("/api/public/alerts")
def public_alerts():
    limit = int(request.args.get("limit", 100))
    district = str(request.args.get("district", "")).strip()
    where_sql = ""
    params: list[object] = []
    if district:
        where_sql = " WHERE district = ?"
        params.append(district)
    conn = get_db()
    rows = conn.execute(f"SELECT * FROM alerts{where_sql} ORDER BY created_at DESC LIMIT ?", params + [limit]).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/public/environment")
def public_environment():
    limit = int(request.args.get("limit", 100))
    district = str(request.args.get("district", "")).strip()
    where_sql = ""
    params: list[object] = []
    if district:
        where_sql = " WHERE district = ?"
        params.append(district)
    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM environmental_observations{where_sql} ORDER BY observed_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/geo/events")
def geo_events():
    unauthorized = require_api_token({"district", "admin", "clinician", "midwife", "vet"})
    if unauthorized:
        return unauthorized

    limit = int(request.args.get("limit", 200))
    high_risk_only = request.args.get("high_risk_only", "false").lower() == "true"

    query = "SELECT * FROM events"
    params: list[object] = []
    if high_risk_only:
        query += " WHERE high_risk = 1"
    if g.current_user["role"] == "district":
        query += " AND district = ?" if "WHERE" in query else " WHERE district = ?"
        params.append(g.current_user["district"])
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    features = []
    for r in rows:
        if r["latitude"] is None or r["longitude"] is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": {
                    "id": r["id"],
                    "district": r["district"],
                    "parish": r["parish"],
                    "syndrome": r["syndrome"],
                    "risk_score": r["risk_score"],
                    "high_risk": bool(r["high_risk"]),
                    "created_at": r["created_at"],
                },
            }
        )

    return jsonify({"type": "FeatureCollection", "features": features})


@app.post("/api/ussd/report")
def ussd_report():
    unauthorized = require_api_token({"vht", "vet", "district", "admin"})
    if unauthorized:
        return unauthorized

    payload = request.get_json(silent=True) or {}
    if not payload:
        payload = request.form.to_dict()

    if "text" in payload:
        # Example format:
        # district=Kabale;parish=Kitumba;syndrome=animal abortion;species=cattle;animal_exposure=true
        parsed = {}
        for part in str(payload["text"]).split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            parsed[key.strip().lower()] = value.strip()
        payload = parsed

    district = payload.get("district")
    parish = payload.get("parish")
    syndrome = payload.get("syndrome")
    species = payload.get("species") or payload.get("species_or_patient") or "animal_case"

    if not district or not parish or not syndrome:
        return (
            jsonify(
                {
                    "error": "USSD payload must include district, parish, syndrome.",
                    "example": "district=Kabale;parish=Kitumba;syndrome=animal abortion;species=cattle",
                }
            ),
            400,
        )
    write_restricted = enforce_district_write(district)
    if write_restricted:
        return write_restricted

    event_payload = {
        "source_channel": "ussd",
        "reporter_ip": payload.get("ip_address") or request.remote_addr,
        "reporter_name": payload.get("reporter_name"),
        "reporter_contact": payload.get("reporter_contact"),
        "reporter_role": payload.get("reporter_role", "vht"),
        "district": district,
        "parish": parish,
        "species_or_patient": species,
        "syndrome": syndrome,
        "gestational_weeks": int(payload["gestational_weeks"]) if payload.get("gestational_weeks") else None,
        "animal_exposure": str(payload.get("animal_exposure", "false")).lower() in {"true", "1", "yes"},
        "rainfall_index": float(payload.get("rainfall_index", 0.0)),
        "ndvi_index": float(payload.get("ndvi_index", 0.0)),
        "temperature_c": float(payload.get("temperature_c", 0.0)),
        "latitude": float(payload.get("latitude", 0.0)),
        "longitude": float(payload.get("longitude", 0.0)),
    }

    risk_score = calculate_risk_score(event_payload)
    high_risk = 1 if risk_score >= 0.7 else 0
    now = dt.datetime.utcnow().isoformat()

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO events (
            reporter_ip, reporter_name, reporter_contact, source_channel, reporter_role, district, parish, species_or_patient, syndrome,
            gestational_weeks, animal_exposure, rainfall_index, ndvi_index, temperature_c,
            latitude, longitude, risk_score, high_risk, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_payload["reporter_ip"],
            event_payload["reporter_name"],
            event_payload["reporter_contact"],
            event_payload["source_channel"],
            event_payload["reporter_role"],
            event_payload["district"],
            event_payload["parish"],
            event_payload["species_or_patient"],
            event_payload["syndrome"],
            event_payload["gestational_weeks"],
            1 if event_payload["animal_exposure"] else 0,
            event_payload["rainfall_index"],
            event_payload["ndvi_index"],
            event_payload["temperature_c"],
            event_payload["latitude"],
            event_payload["longitude"],
            risk_score,
            high_risk,
            now,
        ),
    )
    event_id = cur.lastrowid
    if high_risk:
        cur.execute(
            """
            INSERT INTO alerts (
                district, parish, alert_type, severity, signal_score,
                reporter_latitude, reporter_longitude, reporter_ip,
                details, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_payload["district"],
                event_payload["parish"],
                "risk_signal",
                "high",
                risk_score,
                event_payload["latitude"],
                event_payload["longitude"],
                event_payload["reporter_ip"],
                "High-risk signal from USSD/SMS report.",
                "new",
                now,
            ),
        )
    conn.commit()
    row = cur.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    audit("create", "ussd_event", str(event_id), district, f"syndrome={syndrome}")
    return jsonify({"status": "accepted", "event": dict(row)})


@app.post("/api/auth/login")
def login():
    payload = request.get_json(force=True)
    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    conn = get_db()
    user = conn.execute(
        """
        SELECT username, role, district, api_token, is_active, password_hash
        FROM users WHERE username = ?
        """,
        (username,),
    ).fetchone()
    conn.close()

    if not user or int(user["is_active"]) != 1:
        return jsonify({"error": "Invalid credentials"}), 401

    if user["password_hash"] != hash_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify(
        {
            "username": user["username"],
            "role": user["role"],
            "district": user["district"],
            "api_token": user["api_token"],
            "is_admin": user["role"] == "admin",
        }
    )


@app.get("/api/users")
def list_users():
    unauthorized = require_api_token({"admin"})
    if unauthorized:
        return unauthorized

    conn = get_db()
    rows = conn.execute(
        """
        SELECT username, role, district, api_token, is_active
        FROM users
        ORDER BY username ASC
        """
    ).fetchall()
    conn.close()
    audit("read", "users")
    return jsonify([dict(r) for r in rows])


@app.post("/api/users")
def create_user():
    unauthorized = require_api_token({"admin"})
    if unauthorized:
        return unauthorized

    payload = request.get_json(force=True)
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    role = str(payload.get("role", "")).strip().lower()
    district = payload.get("district")
    allowed_roles = {"admin", "district", "vht", "vet", "clinician", "midwife"}

    if not username or not password or not role:
        return jsonify({"error": "username, password and role are required"}), 400
    if role not in allowed_roles:
        return jsonify({"error": f"Invalid role. Use one of: {', '.join(sorted(allowed_roles))}"}), 400

    conn = get_db()
    cur = conn.cursor()
    exists = cur.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone()
    if exists:
        conn.close()
        return jsonify({"error": "Username already exists"}), 409

    token = secrets.token_hex(16)
    cur.execute(
        """
        INSERT INTO users (username, password_hash, role, district, api_token, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (username, hash_password(password), role, district, token),
    )
    conn.commit()
    row = cur.execute(
        "SELECT username, role, district, api_token, is_active FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    audit("create", "user", username, district)
    return jsonify(dict(row)), 201


@app.patch("/api/users/<username>")
def update_user(username: str):
    unauthorized = require_api_token({"admin"})
    if unauthorized:
        return unauthorized

    payload = request.get_json(force=True)
    allowed_roles = {"admin", "district", "vht", "vet", "clinician", "midwife"}
    updates: list[str] = []
    params: list[object] = []

    if "role" in payload:
        role = str(payload.get("role", "")).strip().lower()
        if role not in allowed_roles:
            return jsonify({"error": f"Invalid role. Use one of: {', '.join(sorted(allowed_roles))}"}), 400
        updates.append("role = ?")
        params.append(role)

    if "district" in payload:
        district = payload.get("district")
        updates.append("district = ?")
        params.append(district)

    if "is_active" in payload:
        updates.append("is_active = ?")
        params.append(1 if bool(payload.get("is_active")) else 0)

    if payload.get("reset_api_token") is True:
        updates.append("api_token = ?")
        params.append(secrets.token_hex(16))

    if payload.get("password"):
        updates.append("password_hash = ?")
        params.append(hash_password(str(payload["password"])))

    if not updates:
        return jsonify({"error": "No valid updates provided."}), 400

    conn = get_db()
    cur = conn.cursor()
    existing = cur.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    sql = f"UPDATE users SET {', '.join(updates)} WHERE username = ?"
    cur.execute(sql, params + [username])
    conn.commit()
    updated = cur.execute(
        "SELECT username, role, district, api_token, is_active FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    audit("update", "user", username, metadata=json.dumps({"fields": updates}))
    return jsonify(dict(updated))


@app.patch("/api/alerts/<int:alert_id>/status")
def update_alert_status(alert_id: int):
    unauthorized = require_api_token({"district", "admin"})
    if unauthorized:
        return unauthorized

    payload = request.get_json(force=True)
    status = payload.get("status")
    valid = {"new", "investigating", "confirmed", "dismissed", "resolved"}
    if status not in valid:
        return jsonify({"error": f"Invalid status. Use one of: {', '.join(sorted(valid))}"}), 400

    now = dt.datetime.utcnow().isoformat()
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT id, district, status FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Alert not found"}), 404
    if g.current_user["role"] == "district" and row["district"] != g.current_user["district"]:
        conn.close()
        return jsonify({"error": "Forbidden outside your district."}), 403
    prev_status = row["status"]

    cur.execute(
        """
        UPDATE alerts
        SET status = ?, reviewed_by = ?, reviewed_at = ?
        WHERE id = ?
        """,
        (status, g.current_user["username"], now, alert_id),
    )
    cur.execute(
        """
        INSERT INTO alert_actions (alert_id, previous_status, new_status, action_by, action_note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (alert_id, prev_status, status, g.current_user["username"], payload.get("note"), now),
    )
    conn.commit()
    updated = cur.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    conn.close()
    audit("update", "alert_status", str(alert_id), updated["district"], f"{prev_status}->{status}")
    return jsonify(dict(updated))


@app.get("/api/alerts/<int:alert_id>/history")
def alert_history(alert_id: int):
    unauthorized = require_api_token({"district", "admin", "clinician", "midwife", "vet"})
    if unauthorized:
        return unauthorized

    conn = get_db()
    alert_row = conn.execute("SELECT id, district FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    if not alert_row:
        conn.close()
        return jsonify({"error": "Alert not found"}), 404
    if g.current_user["role"] == "district" and alert_row["district"] != g.current_user["district"]:
        conn.close()
        return jsonify({"error": "Forbidden outside your district."}), 403

    rows = conn.execute(
        "SELECT * FROM alert_actions WHERE alert_id = ? ORDER BY created_at DESC",
        (alert_id,),
    ).fetchall()
    conn.close()
    audit("read", "alert_history", str(alert_id), alert_row["district"])
    return jsonify([dict(r) for r in rows])


@app.post("/api/environment")
def create_environment_observation():
    unauthorized = require_api_token({"district", "admin", "vet", "clinician", "midwife"})
    if unauthorized:
        return unauthorized

    payload = request.get_json(force=True)
    required = ["district", "parish"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    write_restricted = enforce_district_write(payload["district"])
    if write_restricted:
        return write_restricted

    observed_at = payload.get("observed_at", dt.datetime.utcnow().isoformat())
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO environmental_observations (
            district, parish, rainfall_index, ndvi_index, temperature_c, source, observed_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["district"],
            payload["parish"],
            float(payload.get("rainfall_index", 0.0)),
            float(payload.get("ndvi_index", 0.0)),
            float(payload.get("temperature_c", 0.0)),
            payload.get("source", "manual"),
            observed_at,
            g.current_user["username"],
        ),
    )
    env_id = cur.lastrowid
    conn.commit()
    row = cur.execute("SELECT * FROM environmental_observations WHERE id = ?", (env_id,)).fetchone()
    conn.close()
    audit("create", "environment_observation", str(env_id), payload["district"])
    return jsonify(dict(row)), 201


@app.get("/api/environment")
def list_environment_observations():
    unauthorized = require_api_token({"district", "admin", "vet", "clinician", "midwife"})
    if unauthorized:
        return unauthorized

    limit = int(request.args.get("limit", 100))
    where_sql, where_params = scope_filter()
    district_filter = str(request.args.get("district", "")).strip()
    if district_filter:
        if where_sql:
            where_sql = f"{where_sql} AND district = ?"
        else:
            where_sql = " WHERE district = ?"
        where_params.append(district_filter)
    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM environmental_observations{where_sql} ORDER BY observed_at DESC LIMIT ?",
        where_params + [limit],
    ).fetchall()
    conn.close()
    audit("read", "environment_list", metadata=f"limit={limit}")
    return jsonify([dict(r) for r in rows])


@app.get("/api/geo/environment")
def geo_environment():
    unauthorized = require_api_token({"district", "admin", "vet", "clinician", "midwife"})
    if unauthorized:
        return unauthorized

    limit = int(request.args.get("limit", 200))
    where_sql, where_params = scope_filter()
    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM environmental_observations{where_sql} ORDER BY observed_at DESC LIMIT ?",
        where_params + [limit],
    ).fetchall()
    conn.close()
    features = []
    for r in rows:
        # Environmental records may not have GPS in this MVP; skip map projection.
        # If lat/lon is added later, this endpoint can return point features.
        features.append(
            {
                "district": r["district"],
                "parish": r["parish"],
                "rainfall_index": r["rainfall_index"],
                "ndvi_index": r["ndvi_index"],
                "temperature_c": r["temperature_c"],
                "source": r["source"],
                "observed_at": r["observed_at"],
            }
        )
    audit("read", "environment_geo", metadata=f"limit={limit}")
    return jsonify({"records": features})


@app.get("/api/audit-logs")
def list_audit_logs():
    unauthorized = require_api_token({"admin", "district"})
    if unauthorized:
        return unauthorized

    limit = int(request.args.get("limit", 100))
    where_sql, where_params = scope_filter()
    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM audit_logs{where_sql} ORDER BY created_at DESC LIMIT ?",
        where_params + [limit],
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/summary")
def summary():
    unauthorized = require_api_token({"admin", "district", "clinician", "midwife", "vet"})
    if unauthorized:
        return unauthorized

    district = request.args.get("district")
    if g.current_user["role"] == "district":
        district = g.current_user["district"]

    conn = get_db()
    where = ""
    params: list[object] = []
    if district:
        where = " WHERE district = ?"
        params.append(district)

    totals = conn.execute(
        f"""
        SELECT
          COUNT(*) AS total_events,
          SUM(CASE WHEN high_risk = 1 THEN 1 ELSE 0 END) AS high_risk_events,
          SUM(CASE WHEN validation_status = 'flagged' THEN 1 ELSE 0 END) AS flagged_events
        FROM events{where}
        """,
        params,
    ).fetchone()
    alerts = conn.execute(
        f"""
        SELECT
          COUNT(*) AS total_alerts,
          SUM(CASE WHEN status = 'new' THEN 1 ELSE 0 END) AS new_alerts,
          SUM(CASE WHEN status = 'investigating' THEN 1 ELSE 0 END) AS investigating_alerts
        FROM alerts{where}
        """,
        params,
    ).fetchone()
    env = conn.execute(
        f"SELECT COUNT(*) AS env_points FROM environmental_observations{where}",
        params,
    ).fetchone()
    conn.close()
    audit("read", "summary", district=district)
    return jsonify(
        {
            "district": district,
            "total_events": int(totals["total_events"] or 0),
            "high_risk_events": int(totals["high_risk_events"] or 0),
            "flagged_events": int(totals["flagged_events"] or 0),
            "total_alerts": int(alerts["total_alerts"] or 0),
            "new_alerts": int(alerts["new_alerts"] or 0),
            "investigating_alerts": int(alerts["investigating_alerts"] or 0),
            "env_points": int(env["env_points"] or 0),
        }
    )


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
