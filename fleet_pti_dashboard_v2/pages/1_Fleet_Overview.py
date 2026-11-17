"""Fleet overview."""
import pandas as pd
import streamlit as st

from src.analytics import driver_activity, pretrips
from src.components.charts import GRAY, GREEN, RED, YELLOW, chart, counts, daily_trend
from src.components.kpi_cards import metrics
from src.components.tables import display_times, table

context = st.session_state.context
scope = context.scope
pti = pretrips(scope.records)
drivers = driver_activity(scope)
recorded = drivers.submissions.gt(0)

st.title("Fleet overview")
roster_ids = context.data.drivers.driver_id
population_label = "Drivers in roster" if context.data.roster_complete else "Drivers observed in DVIR records"
population_count = drivers.driver_id.isin(roster_ids).sum() if context.data.roster_complete else len(drivers)
metrics([
    (population_label, population_count),
    ("Drivers with recorded PTI", recorded.sum()),
    ("Drivers with no recorded PTI", (drivers.activity == "No recorded PTI").sum()),
    ("Pre-trip DVIR submissions", len(pti)),
    ("Drivers with multiple PTIs", drivers.submissions.gt(1).sum()),
    ("Unsafe pre-trip DVIRs", pti.safety_status.eq("unsafe").sum()),
    ("Unresolved pre-trip defects", pti.unresolved_defects.sum()),
    ("Co-driver-related pre-trip DVIRs", pti.team_confirmed.sum()),
])
if context.data.roster_complete and population_count < len(drivers):
    st.caption(f"Driver activity also includes {len(drivers) - population_count:,} observed authors outside the roster.")
left, right = st.columns(2)
with left:
    chart("Daily PTI submissions", daily_trend(pti, scope.dates), "date", "submissions", line=True)
with right:
    officers = pti.officer_name.fillna(pti.officer_id.fillna("Unknown"))
    chart("PTIs by assigned safety officer", counts(officers, "officer"), "officer", "records")
left, right = st.columns(2)
with left:
    frequency = counts(drivers.activity, "activity")
    chart("Drivers by submission frequency", frequency, "activity", "records", color="activity",
          colors={"Frequent submitter": GREEN, "Intermittent submitter": YELLOW,
                  "No recorded PTI": GRAY, "Insufficient information": YELLOW})
with right:
    statuses = pti.safety_status.where(pti.safety_status.isin(["safe", "unsafe"]), "unknown")
    chart("Pre-trip DVIR safety status", counts(statuses.str.title(), "status"), "status", "records",
          color="status", colors={"Safe": GREEN, "Unsafe": RED, "Unknown": YELLOW})
left, right = st.columns(2)
with left:
    defects = pd.DataFrame({"asset": ["Vehicle", "Trailer"],
                            "defects": [pti.vehicle_defects.sum(), pti.trailer_defects.sum()]})
    chart("Defects by asset type", defects, "asset", "defects")
with right:
    top = drivers[recorded].head(10).copy()
    top["driver"] = top.driver_name.fillna("Unknown") + " (" + top.driver_id + ")"
    chart("Top 10 drivers by recorded PTIs", top, "submissions", "driver", horizontal=True)

with st.expander("Filtered pre-trip DVIRs"):
    columns = ["dvir_id", "author_id", "author_name", "inspection_time", "vehicle_name",
               "trailer_name", "safety_status", "total_defects", "unresolved_defects"]
    table(display_times(pti[columns], context.timezone), "pre-trip-dvirs")
