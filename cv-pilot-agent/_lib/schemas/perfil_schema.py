"""Pydantic v2 schema for the canonical perfil.json format.

All fields are optional (nullable) to tolerate partial extraction from CVs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PerfilSchema(BaseModel):
    """Canonical CV profile schema.

    All fields are optional to support partial extraction — a CV may not
    contain every field (e.g. missing GitHub, missing resumen).
    """

    nombre: Optional[str] = Field(None, description="Full name")
    correo: Optional[str] = Field(None, description="Email address")
    telefono: Optional[str] = Field(None, description="Phone number")
    linkedin: Optional[str] = Field(None, description="LinkedIn profile URL")
    github: Optional[str] = Field(None, description="GitHub profile URL")
    cv_url: Optional[str] = Field(None, description="Link to the original CV")
    resumen: Optional[str] = Field(None, description="Professional summary")
    experiencia: Optional[str] = Field(None, description="Work experience (text or structured)")
    educacion: Optional[str] = Field(None, description="Education (text or structured)")
    skills: Optional[str] = Field(None, description="Technical skills")
    extras: dict[str, Any] = Field(default_factory=dict, description="Non-canonical fields")
    fuente: Optional[str] = Field(None, description="Source PDF path")
    generated_at: Optional[str] = Field(None, description="ISO-8601 generation timestamp")

    model_config = {"extra": "allow"}
