"""Driver submission frequency and calendar."""
import streamlit as st

from src.analytics import daily_status, pretrips
from src.components.heatmap import LABELS
from src.filters import officer_key, search
from src.followup import training_followup

from src.analytics import driver_activity
from src.components.heatmap import heatmap
from src.components.tables import table

context = st.session_state.context
scope = context.scope
activity = driver_activity(scope)
st.title("Driver PTI consistency")
st.caption("Days without recorded PTIs counts calendar days in the selected window. "
           "Frequency describes recorded activity. Frequent means recorded on at least half of the "
           "calendar days. Intermittent means recorded on fewer days. "
           "Insufficient information identifies drivers whose only matching pre-trip records are undated.")
activity = training_followup(activity, context.data.training, scope, context.timezone)
left, right = st.columns(2)
frequency = left.selectbox("Submission frequency", ["All", "No recorded PTI", "Intermittent submitter",
                                                     "Frequent submitter", "Insufficient information"])
training_options = sorted(activity.training_follow_up.unique())
follow_up = right.selectbox("Training follow-up", ["All", *training_options])
if frequency != "All":
    activity = activity[activity.activity.eq(frequency)]
if follow_up != "All":
    activity = activity[activity.training_follow_up.eq(follow_up)]
columns = {
    "driver_id": "driver_id", "driver_name": "driver_name", "officer_name": "assigned_safety_officer",
    "submissions": "PTI_submissions", "recorded_days": "days_with_recorded_PTIs",
    "days_without_pti": "days_without_recorded_PTIs", "last_pti": "last_PTI_date",
    "days_since_last_pti": "days_since_last_recorded_PTI", "vehicles": "distinct_vehicles_inspected",
    "co_driver": "co_driver_involvement", "unsafe": "unsafe_inspections",
    "unresolved": "unresolved_defects", "activity": "submission_frequency",
    "training_completed_at": "training_completed_at", "training_follow_up": "training_follow_up",
}
view = activity[list(columns)].rename(columns=columns)
view["assigned_safety_officer"] = view.assigned_safety_officer.fillna(activity.officer_id).fillna("Unknown")
visible = table(view, "driver-consistency", size=20,
                sort_columns=("PTI_submissions", "days_with_recorded_PTIs", "driver_name",
                              "last_PTI_date", "unsafe_inspections", "unresolved_defects"))
st.subheader("Daily PTI activity")
heatmap(scope, view.loc[visible, "driver_id"].tolist())

daily = daily_status(scope, view.driver_id.tolist())
daily.columns = [day.isoformat() for day in daily.columns]
marks = daily.replace(dict(enumerate(LABELS))).rename_axis("driver_id").reset_index()
st.subheader("Daily driver list")
day_col, mark_col = st.columns(2)
selected_day = day_col.selectbox("Inspection date", list(reversed(daily.columns)))
selected_mark = mark_col.selectbox("Daily mark", ["All", *LABELS])
daily_list = view.merge(marks[["driver_id", selected_day]], on="driver_id").rename(
    columns={selected_day: "daily_mark"}
)
if selected_mark != "All":
    daily_list = daily_list[daily_list.daily_mark.eq(selected_mark)]
table(daily_list[["driver_id", "driver_name", "assigned_safety_officer", "daily_mark",
                  "submission_frequency", "training_follow_up"]], "daily-driver-list")

st.subheader("Assigned drivers and vehicles to check")
st.caption("Counts use current assignments and compare against pre-trip DVIRs in the selected "
           "period. Missing matches can be checked in your other PTI platform.")
filters = context.filters
data = context.data
period = pretrips(data.dvir_records[data.dvir_records.inspection_date.isin(scope.dates)])
assigned = data.driver_assignments.merge(data.drivers, on="driver_id", how="left")
assigned = assigned[assigned.officer_id.notna() | assigned.officer_name.notna()]
if filters.officer:
    assigned = assigned[officer_key(assigned).eq(filters.officer)]
assigned = assigned[search(assigned, ["driver_id", "driver_name"], filters.driver)]
vehicles = data.vehicle_assignments
if filters.officer:
    vehicles = vehicles[officer_key(vehicles).eq(filters.officer)]
vehicles = vehicles[search(vehicles, ["vehicle_id", "vehicle_name"], filters.vehicle)]
if assigned.empty and vehicles.empty:
    st.info("No matching assignment records were supplied by the webhook.")
else:
    for label, frame, identity, observed in (
        ("drivers", assigned, "driver_id", period.author_id),
        ("vehicles", vehicles, "vehicle_id", period.vehicle_id),
    ):
        missing = frame[~frame[identity].isin(observed)]
        st.markdown(f"**Assigned {label}**")
        if frame.empty:
            st.caption("No matching assignments supplied.")
            continue
        st.write(f"{frame[identity].nunique():,} assigned · "
                 f"{missing[identity].nunique():,} with no matching pre-trip DVIR")
        by_officer = frame.assign(
            officer=frame.officer_name.fillna(frame.officer_id).fillna("Unknown"),
            officer_key=officer_key(frame), missing_id=frame[identity].where(~frame[identity].isin(observed)),
        ).groupby(["officer_key", "officer"], as_index=False).agg(
            assigned=(identity, "nunique"), no_matching_dvir=("missing_id", "nunique")
        )
        table(by_officer, f"{label}-assignment-summary")
        table(missing, f"{label}-without-dvir")
