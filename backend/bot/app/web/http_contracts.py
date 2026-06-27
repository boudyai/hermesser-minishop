"""Shared pydantic bases for typed HTTP request and response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


class HttpBodyModel(BaseModel):
    """Base class for typed request bodies during the incremental refactor."""

    model_config = ConfigDict(extra="ignore")


class HttpResponseModel(BaseModel):
    """Base class for typed response payload objects."""

    model_config = ConfigDict(extra="ignore")

    @field_serializer("*", when_used="json")
    def _serialize_response_value(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value
