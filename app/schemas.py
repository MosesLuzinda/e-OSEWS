from datetime import datetime

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    source_channel: str = "android"
    reporter_role: str
    district: str
    parish: str
    species_or_patient: str
    syndrome: str
    gestational_weeks: int | None = None
    animal_exposure: bool = False
    rainfall_index: float = 0.0
    ndvi_index: float = 0.0
    temperature_c: float = 0.0
    latitude: float = Field(default=0.0, ge=-90, le=90)
    longitude: float = Field(default=0.0, ge=-180, le=180)


class EventOut(EventCreate):
    id: int
    risk_score: float
    high_risk: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AlertOut(BaseModel):
    id: int
    district: str
    parish: str
    alert_type: str
    severity: str
    signal_score: float
    details: str
    created_at: datetime

    class Config:
        from_attributes = True
