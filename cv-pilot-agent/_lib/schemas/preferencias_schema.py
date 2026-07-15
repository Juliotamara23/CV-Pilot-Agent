"""Pydantic v2 schema for the canonical preferencias.json format.

All fields are optional (nullable) to tolerate partial extraction.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class PreferenciasSchema(BaseModel):
    """User preferences schema for CV-Pilot.

    Mirrors the fields from preferencias.md, including the orphan
    pdf_soporte field the user added manually.
    """

    mimetismo: Optional[Any] = Field(None, description="Mimetismo activation (bool or dict)")
    sector: Optional[str] = Field(None, description="Preferred job sector")
    tono: Optional[str] = Field(None, description="Preferred tone")
    idioma: Optional[str] = Field(None, description="Application language")
    gmail_drafts: Optional[bool] = Field(None, description="Enable Gmail draft generation")
    outlook_drafts: Optional[bool] = Field(None, description="Enable Outlook draft generation")
    pdf_soporte: Optional[bool] = Field(True, description="PDF support flag (user-added field)")
    notas_adicionales: Optional[str] = Field(None, description="Additional notes")
    extras: dict[str, Any] = Field(default_factory=dict, description="Non-canonical fields")

    model_config = {"extra": "allow"}
