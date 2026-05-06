import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_channel: Mapped[str] = mapped_column(String(30), default="android")
    reporter_role: Mapped[str] = mapped_column(String(40))
    district: Mapped[str] = mapped_column(String(50), index=True)
    parish: Mapped[str] = mapped_column(String(80))
    species_or_patient: Mapped[str] = mapped_column(String(80))
    syndrome: Mapped[str] = mapped_column(String(120))
    gestational_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    animal_exposure: Mapped[bool] = mapped_column(Boolean, default=False)
    rainfall_index: Mapped[float] = mapped_column(Float, default=0.0)
    ndvi_index: Mapped[float] = mapped_column(Float, default=0.0)
    temperature_c: Mapped[float] = mapped_column(Float, default=0.0)
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    district: Mapped[str] = mapped_column(String(50), index=True)
    parish: Mapped[str] = mapped_column(String(80), index=True)
    alert_type: Mapped[str] = mapped_column(String(50), default="anomaly")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    signal_score: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
