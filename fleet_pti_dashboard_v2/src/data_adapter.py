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


def identifier(value: object) -> str | None:
    return str(value).strip() or None if type(value) in (str, int) else None


class SourceReport(BaseModel):
    """Version 2 combines separately prepared upstream feeds."""

    schemaVersion: int
    rosterComplete: bool = False
    roster: list[dict[str, Any]]
    dvirs: list[dict[str, Any]]
    driverOfficerAssignments: list[dict[str, Any]]
    vehicleOfficerAssignments: list[dict[str, Any]]
    trainingRecords: list[dict[str, Any]] = Field(default_factory=list)
    teamAssignments: list[dict[str, Any]] = Field(default_factory=list)


def adapt_sources(payload: dict[str, Any]) -> Envelope:
    """Join normalized training rows to the roster using Samsara driver IDs."""
    try:
        report = SourceReport.model_validate(payload)
    except ValidationError:
        raise PayloadError("Version 2 webhook response is missing required source arrays.") from None

    training = {}
    ambiguous = set()
    for row in report.trainingRecords:
        driver_id = identifier(row.get("driver_id"))
        if driver_id is None:
            continue
        status = row.get("training_status")
        if not isinstance(status, str) or status not in {"completed", "incomplete", "not_trained", "unknown"}:
            status = "unknown"
        completed_at = row.get("training_completed_at") if status == "completed" else None
        value = (status, completed_at)
        if driver_id in training and training[driver_id] != value:
            ambiguous.add(driver_id)
        training[driver_id] = value

    drivers = []
    for row in report.roster:
        driver_id = identifier(row.get("id", row.get("driver_id")))
        status, completed_at = ("unknown", None)
        if driver_id not in ambiguous:
            status, completed_at = training.get(driver_id, (status, completed_at))
        drivers.append({**row, "training_status": status, "training_completed_at": completed_at})

    return Envelope(
        inspections=report.dvirs, drivers=drivers,
        driver_assignments=report.driverOfficerAssignments,
        vehicle_assignments=report.vehicleOfficerAssignments,
        team_assignments=report.teamAssignments,
        roster_complete=report.rosterComplete,
    )


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
    if "schemaVersion" in payload:
        if type(payload["schemaVersion"]) is not int or payload["schemaVersion"] != 2:
            raise PayloadError("Unsupported webhook schemaVersion. Expected version 2.")
        return adapt_sources(payload)
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
