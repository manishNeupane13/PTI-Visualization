"""Validate webhook envelopes and select configurable source arrays."""
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class PayloadError(ValueError):
    """A payload cannot safely be used for reporting."""


class Envelope(BaseModel):
    inspections: list[dict[str, Any]]
    drivers: list[dict[str, Any]] = Field(default_factory=list)
    driver_assignments: list[dict[str, Any]] = Field(default_factory=list)
    team_assignments: list[dict[str, Any]] = Field(default_factory=list)
    vehicle_assignments: list[dict[str, Any]] = Field(default_factory=list)
    roster_complete: bool = False


def adapt(payload: object, keys: tuple[str, str, str, str] = (
    "inspections", "drivers", "driverAssignments", "teamAssignments"
)) -> Envelope:
    """Accept raw arrays, Samsara envelopes, and enriched wrappers."""
    if isinstance(payload, list):
        payload = {"data": payload}
    if not isinstance(payload, dict):
        raise PayloadError("Expected an inspection array or webhook envelope.")
    pagination = payload.get("pagination")
    if pagination is not None and (
        not isinstance(pagination, dict)
        or pagination.get("hasNextPage", False) is not False
    ):
        raise PayloadError("Webhook pagination is incomplete or invalid. Return all pages from n8n.")
    inspections, drivers, assignments, teams = keys
    roster = payload.get(drivers, [])
    try:
        return Envelope.model_validate({
            "inspections": payload.get(inspections, payload.get("data")),
            "drivers": roster,
            "driver_assignments": payload.get(assignments, []),
            "team_assignments": payload.get(teams, []),
            "vehicle_assignments": payload.get("vehicleAssignments", []),
            "roster_complete": isinstance(roster, list) and drivers in payload
            and payload.get("rosterComplete") is True,
        })
    except ValidationError:
        raise PayloadError("Webhook arrays are missing or contain invalid records.") from None
