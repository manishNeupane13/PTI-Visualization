"""Defect reporting, resolution, and safety history."""
import pandas as pd
import streamlit as st

from src.components.charts import asset_labels, chart, counts
from src.components.kpi_cards import metrics
from src.components.tables import display_times, table

context = st.session_state.context
records = context.scope.records
defects = context.data.dvir_defects.merge(
    records[["dvir_id", "officer_id", "officer_name"]], on="dvir_id"
)
defects["assigned_safety_officer"] = defects.officer_name.fillna(defects.officer_id).fillna("Unknown")
defects["asset"] = asset_labels(defects, "asset_name", "asset_id")
resolved = defects.resolution_status.eq("Resolved")

st.title("Defects and safety")
st.caption("Unsafe counts describe inspections recorded during the selected period. "
           "Current equipment status requires subsequent inspection and repair information.")
metrics([("Reported defects", len(defects)), ("Resolved defects", resolved.sum()),
         ("Unresolved defects", (~resolved).sum()), ("Unsafe DVIRs", records.safety_status.eq("unsafe").sum())])
left, right = st.columns(2)
with left:
    chart("Defects by type", counts(defects.defect_type, "defect_type"), "defect_type", "records")
with right:
    events = pd.concat([
        defects.reported_time.rename("timestamp").to_frame().assign(event="Reported"),
        defects.loc[resolved, "resolved_time"].rename("timestamp").to_frame().assign(event="Resolved"),
    ]).dropna(subset=["timestamp"])
    events["date"] = events.timestamp.dt.tz_convert(context.timezone).dt.date
    events = events.groupby(["date", "event"]).size().reset_index(name="defects")
    chart("Defect reporting and resolution timeline", events, "date", "defects", color="event")
left, right = st.columns(2)
with left:
    chart("Defects by vehicle · Top 15", counts(defects.loc[defects.asset_type.eq("vehicle"), "asset"], "vehicle").head(15),
          "records", "vehicle", horizontal=True)
with right:
    chart("Defects by trailer · Top 15", counts(defects.loc[defects.asset_type.eq("trailer"), "asset"], "trailer").head(15),
          "records", "trailer", horizontal=True)

st.subheader("Defect records")
columns = ["dvir_id", "asset_type", "asset", "defect_type", "description", "reported_time",
           "resolution_status", "resolved_time", "mechanic_notes", "assigned_safety_officer"]
table(display_times(defects[columns].sort_values("reported_time", ascending=False), context.timezone),
      "defect-records")
