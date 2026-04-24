from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, schemas


def calculate_risk_score(event: schemas.EventCreate) -> float:
    """
    Lightweight heuristic score for pilot phase.
    Replace with trained model when historical data is available.
    """
    score = 0.1

    syndrome_text = event.syndrome.lower()
    if "fever" in syndrome_text:
        score += 0.2
    if "abortion" in syndrome_text or "miscarriage" in syndrome_text:
        score += 0.3
    if event.animal_exposure:
        score += 0.2

    score += min(max(event.rainfall_index, 0.0), 1.0) * 0.1
    score += min(max(event.ndvi_index, 0.0), 1.0) * 0.05
    if event.temperature_c >= 30:
        score += 0.05

    if event.gestational_weeks is not None and event.gestational_weeks >= 20:
        score += 0.1

    return round(min(score, 1.0), 3)


def create_event_and_alert_if_needed(db: Session, event_in: schemas.EventCreate) -> models.Event:
    risk_score = calculate_risk_score(event_in)
    is_high_risk = risk_score >= 0.7

    event = models.Event(
        **event_in.model_dump(),
        risk_score=risk_score,
        high_risk=is_high_risk,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    recent_count = (
        db.query(func.count(models.Event.id))
        .filter(
            models.Event.district == event.district,
            models.Event.parish == event.parish,
            models.Event.syndrome == event.syndrome,
        )
        .scalar()
    )

    if is_high_risk or (recent_count and recent_count >= 3):
        severity = "high" if is_high_risk else "medium"
        signal_score = risk_score if is_high_risk else min(0.5 + recent_count * 0.1, 0.95)
        details = (
            "High-risk maternal/animal signal detected."
            if is_high_risk
            else "Cluster anomaly: repeated syndrome reports in same parish."
        )

        alert = models.Alert(
            district=event.district,
            parish=event.parish,
            alert_type="risk_signal" if is_high_risk else "cluster_anomaly",
            severity=severity,
            signal_score=round(signal_score, 3),
            details=details,
        )
        db.add(alert)
        db.commit()

    return event
