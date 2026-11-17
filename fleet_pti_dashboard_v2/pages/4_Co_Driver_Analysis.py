"""Confirmed team involvement and observed equipment sharing."""
import streamlit as st

from src.analytics import confirmed_team_records, shared_vehicles
from src.components.kpi_cards import metrics
from src.components.tables import display_times, table
from src.filters import search

context = st.session_state.context
records = context.scope.records
team_records = context.team_scope.records if context.team_scope is not None else records
teams = confirmed_team_records(team_records, context.data, context.team_officer)
shared = shared_vehicles(records)

st.title("Co-driver analysis")
metrics([("Team-related DVIRs", len(teams)), ("Distinct identified co-drivers", teams.co_driver_id.nunique()),
         ("Vehicles with multiple DVIR authors", len(shared))])
st.caption("Each DVIR counts once and is credited to its author. Team evidence comes from explicit "
           "DVIR enrichment or a matching team assignment.")
query = st.text_input("Search teams", placeholder="DVIR, driver, co-driver, vehicle or officer")
matching = teams[search(teams, ["dvir_id", "author_id", "author_name", "co_driver_id", "co_driver_name",
                                "vehicle_id", "vehicle_name", "author_officer", "co_driver_officer"], query)]
st.subheader("Confirmed driver–co-driver pairs")
st.caption("Pairs are shown in DVIR author order. If both drivers authored inspections, "
           "each author appears in their own row.")
pairs = (
    matching.dropna(subset=["author_id", "co_driver_id"])
    .sort_values("inspection_time")
    .groupby(["author_id", "co_driver_id"], as_index=False)
    .agg(driver=("author_name", "last"), driver_officer=("author_officer", "last"),
         co_driver=("co_driver_name", "last"), co_driver_officer=("co_driver_officer", "last"),
         inspections=("dvir_id", "nunique"), latest_inspection=("inspection_time", "max"))
    .sort_values(["latest_inspection", "inspections"], ascending=False)
    .rename(columns={"author_id": "driver_id"})
)
pairs[["driver", "co_driver"]] = pairs[["driver", "co_driver"]].fillna("Unknown")
table(display_times(pairs[["driver_id", "driver", "driver_officer", "co_driver_id",
                           "co_driver", "co_driver_officer", "inspections", "latest_inspection"]],
                    context.timezone), "confirmed-pairs")
st.subheader("Team inspection records")
columns = ["dvir_id", "inspection_time", "inspection_type", "author_id", "author_name",
           "author_officer", "co_driver_id", "co_driver_name", "co_driver_officer",
           "vehicle_name", "safety_status", "source"]
view = matching[columns].copy()
for column in ("author_id", "author_name", "co_driver_id", "co_driver_name"):
    view[column] = view[column].fillna("Unknown")
table(display_times(view, context.timezone), "team-inspections")
st.subheader("Shared vehicles")
st.caption("Multiple distinct DVIR authors used these vehicles in the filtered records. "
           "This observation alone provides no confirmed team assignment.")
table(shared, "shared-vehicles")
