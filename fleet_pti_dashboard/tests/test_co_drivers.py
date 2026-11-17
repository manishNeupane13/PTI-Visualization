from datetime import date

from src.analytics import driver_activity, shared_vehicles
from src.data_adapter import adapt
from src.filters import Filters, apply_filters, reporting_dates
from src.normalization import normalize


def test_signatures_team_mapping_and_shared_vehicles(dvir):
    dvir["secondSignature"] = {"signatoryUser": {"id": "D2", "name": "Alex"}}
    dvir["thirdSignature"] = {"signatoryUser": {"id": "M1", "name": "Mechanic"}}
    authored_by_partner = {**dvir, "id": "X2",
                           "authorSignature": {"signatoryUser": {"id": "D2", "name": "Alex"}}}
    data = normalize(adapt({"inspections": [dvir, authored_by_partner], "teamAssignments": [
        {"dvir_id": "X2", "driver_id": "D2", "co_driver_id": "D1"},
        {"dvir_id": "X1", "driver_id": "someone_else", "co_driver_id": "D2"},
    ]}), "UTC")
    scope = apply_filters(data, reporting_dates(7, date(2026, 11, 15)), Filters())
    assert len(data.dvir_signatures) == 6
    assert data.team_assignments.dvir_id.tolist() == ["X2"]
    assert data.team_assignments.co_driver_id.tolist() == ["D1"]
    assert shared_vehicles(scope.records).distinct_authors.tolist() == [2]
    assert driver_activity(scope).set_index("driver_id").submissions.to_dict() == {"D1": 1, "D2": 1}


def test_named_partner_without_id_is_retained(dvir):
    dvir["co_driver_name"] = "Jordan"
    data = normalize(adapt([dvir]), "UTC")
    assert data.team_assignments.co_driver_name.tolist() == ["Jordan"]
    assert data.team_assignments.co_driver_id.isna().all()
