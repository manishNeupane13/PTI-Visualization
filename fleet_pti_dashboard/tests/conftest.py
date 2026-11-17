"""Shared synthetic records."""
import pytest


@pytest.fixture
def dvir():
    return {
        "id": "X1", "type": "preTrip", "startTime": "2026-11-15T06:00:00Z",
        "endTime": "2026-11-15T06:10:00Z", "safetyStatus": "safe",
        "authorSignature": {"signatoryUser": {"id": "D1", "name": "Alex"}},
        "vehicle": {"id": "V1", "name": "Tractor"}, "vehicleDefects": [], "trailerDefects": [],
    }
