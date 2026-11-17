"""Driver activity and individual inspection drill-down."""
import streamlit as st

from src.analytics import pretrips
from src.components.charts import asset_labels, chart, daily_trend
from src.components.heatmap import heatmap
from src.components.kpi_cards import metrics
from src.components.tables import display_times, table

context = st.session_state.context
scope = context.scope
drivers = scope.drivers.set_index("driver_id")
st.title("Driver profiles")
if drivers.empty:
    st.info("No drivers match the reporting period and filters.")
    st.stop()
names = drivers.driver_name.fillna("Unknown").to_dict()
driver_id = st.selectbox("Driver", sorted(names, key=lambda key: (names[key], key)),
                         format_func=lambda key: f"{names[key]} ({key})")
driver = drivers.loc[driver_id].fillna("")
authored = scope.records[scope.records.author_id.eq(driver_id)]
associated = scope.records[scope.records.co_driver_id.eq(driver_id)]
history = scope.records[scope.records.dvir_id.isin(authored.dvir_id) |
                        scope.records.dvir_id.isin(associated.dvir_id)]
pti = pretrips(authored)
st.subheader(names[driver_id])
st.write(f"Driver ID · {driver_id}  |  Currently assigned officer · "
         f"{driver.officer_name or driver.officer_id or 'Unknown'}")
for asset in ("vehicle", "trailer"):
    known = history.dropna(subset=[f"{asset}_id", f"{asset}_name"], how="all")
    labels = asset_labels(known, f"{asset}_name", f"{asset}_id").unique()
    st.write(f"{asset.title()} history · " + (", ".join(sorted(labels)) if len(labels) else "Unknown"))
partners = authored[authored.team_confirmed.astype(bool)]
partner_names = set(asset_labels(partners, "co_driver_name", "co_driver_id"))
partner_names.update(asset_labels(associated, "author_name", "author_id"))
st.write("Co-driver history · " + (", ".join(sorted(partner_names)) if partner_names else "Unknown"))
metrics([("Authored pre-trip DVIRs", len(pti)), ("Distinct PTI dates", pti.inspection_date.nunique())])
last = pti.inspection_date.max() if len(pti) else "No recorded PTI"
st.caption(f"Last recorded PTI · {last}")
heatmap(scope, [driver_id])
chart("PTI submission timeline", daily_trend(pti, scope.dates), "date", "submissions", line=True)

st.subheader("Inspection history")
history = history.sort_values("inspection_time", ascending=False)
columns = ["dvir_id", "inspection_date", "inspection_time", "inspection_type", "vehicle_name",
           "trailer_name", "safety_status", "total_defects"]
view = history[columns].assign(role=history.author_id.eq(driver_id).map({True: "Author", False: "Co-driver"}))
page = table(display_times(view, context.timezone), "inspection-history")
if len(page):
    selected = st.selectbox("Inspect DVIR", history.loc[page, "dvir_id"], index=None,
                            placeholder="Select a DVIR from this page")
    if selected:
        signatures = context.data.dvir_signatures
        defect_rows = context.data.dvir_defects
        st.markdown("**Signatures**")
        st.dataframe(display_times(signatures[signatures.dvir_id.eq(selected)], context.timezone), hide_index=True)
        st.markdown("**Defects and repair information**")
        st.dataframe(display_times(defect_rows[defect_rows.dvir_id.eq(selected)], context.timezone), hide_index=True)
        with st.expander("Original inspection details"):
            st.json(history.loc[history.dvir_id.eq(selected), "raw"].iat[0], expanded=False)
