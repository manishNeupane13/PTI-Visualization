"""Shared dashboard shell, cached loading, and page context."""
import hashlib
import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st
from pydantic import ValidationError

from .api_client import WebhookError, fetch_report
from .config import ROOT, Settings, settings
from .data_adapter import Envelope, adapt
from .filters import Filters, Scope, apply_filters, driver_population, officer_key, reporting_dates
from .normalization import FleetData, normalize
from .storage import latest_snapshot, save_snapshot


@dataclass
class Context:
    data: FleetData
    scope: Scope
    timezone: str
    team_scope: Scope | None = None
    team_officer: str = ""
    filters: Filters = Filters()


def demo_envelope(today: date, tz: str) -> Envelope:
    payload = json.loads((ROOT / "sample_data" / "sample_dvir.json").read_text(encoding="utf-8"))
    anchor = date.fromisoformat(payload.pop("sampleDate"))
    offset = today - anchor

    def shift(value):
        if isinstance(value, dict):
            return {key: shift(item) for key, item in value.items()}
        if isinstance(value, list):
            return [shift(item) for item in value]
        if isinstance(value, str) and value.startswith("2026-") and len(value) == 10:
            return (date.fromisoformat(value) + offset).isoformat()
        if isinstance(value, str) and value.startswith("2026-") and value.endswith("Z"):
            local = datetime.fromisoformat(value).astimezone(ZoneInfo(tz)) + timedelta(days=offset.days)
            return local.astimezone(timezone.utc).isoformat()
        return value

    return adapt(shift(payload))


@st.cache_data(show_spinner=False, max_entries=12)
def normalized(envelope: Envelope, tz: str) -> FleetData:
    return normalize(envelope, tz)


def live_report(config: Settings, days: int, refresh: bool) -> tuple[Envelope, datetime, str]:
    @st.cache_data(ttl=config.ttl, show_spinner=False, max_entries=12)
    def live(url: str, selected_days: int, keys: tuple[str, str, str, str],
             token: str, timeout: float) -> tuple[Envelope, datetime]:
        with st.spinner("Synchronizing inspections with n8n…"):
            return fetch_report(url, selected_days, keys, token, timeout)

    args = (config.url, days, config.keys, config.token, config.timeout)
    identity = hashlib.sha256(repr(args).encode()).hexdigest()
    session_key = f"last_report_{identity}"
    if refresh:
        live.clear(*args)
    try:
        report, synced = live(*args)
    except WebhookError as error:
        st.error(str(error))
        previous = st.session_state.get(session_key)
        if previous is None and config.sqlite_path:
            try:
                previous = latest_snapshot(config.sqlite_path, identity, days)
            except (sqlite3.Error, ValidationError, ValueError):
                st.warning("The local snapshot could not be loaded.")
        if previous is None:
            st.sidebar.caption("Last successful sync · unavailable")
            st.stop()
        return (*previous, "Saved snapshot")
    if config.sqlite_path and st.session_state.get(f"saved_{identity}") != synced:
        try:
            save_snapshot(config.sqlite_path, identity, days, synced, report)
            st.session_state[f"saved_{identity}"] = synced
        except sqlite3.Error:
            st.warning("The local snapshot could not be saved.")
    st.session_state[session_key] = (report, synced)
    return report, synced, "Live"


def prepare(*, team_page: bool = False, consistency_page: bool = False) -> Context:
    try:
        config = settings()
    except (ValueError, KeyError):
        st.error("Check the dashboard mode, timezone, timeout and cache TTL settings.")
        st.stop()
    today = datetime.now(ZoneInfo(config.timezone)).date()
    sidebar = st.sidebar
    sidebar.divider()
    sidebar.subheader("Reporting filters")
    days = sidebar.radio("Reporting period", (7, 15), format_func=lambda value: f"Last {value} days",
                         horizontal=True)
    refresh = sidebar.button("Refresh", width="stretch")
    if config.mode == "live":
        sidebar.caption("Source · n8n webhook")
        envelope, synced, source = live_report(config, days, refresh)
        sidebar.caption(f"Last successful sync · {synced.astimezone(ZoneInfo(config.timezone)):%b %d, %H:%M:%S %Z}")
    else:
        source = "Demo"
        if refresh:
            normalized.clear()
        envelope = demo_envelope(today, config.timezone)
        sidebar.caption("Source · synthetic demo data")

    dates = reporting_dates(days, today)
    data = normalized(envelope, config.timezone)
    records = data.dvir_records[data.dvir_records.inspection_date.isin(dates)]
    drivers = driver_population(data, records)
    officers = dict(zip(officer_key(drivers), drivers.officer_name.fillna(
        drivers.officer_id.fillna("Unknown")
    )))
    if team_page:
        assignments = data.driver_assignments[
            data.driver_assignments.driver_id.isin(records.co_driver_id)
        ]
        officers.update(dict(zip(officer_key(assignments), assignments.officer_name.fillna(
            assignments.officer_id.fillna("Unknown")
        ))))
    if consistency_page:
        assigned = data.vehicle_assignments
        for key, name in zip(officer_key(assigned), assigned.officer_name.fillna(
            assigned.officer_id.fillna("Unknown")
        )):
            officers.setdefault(key, name)
    co_rows = records.dropna(subset=["co_driver_id"]).drop_duplicates("co_driver_id")
    co_drivers = dict(zip(co_rows.co_driver_id, co_rows.co_driver_name.fillna("Unknown")))

    filters = Filters(
        officer=sidebar.selectbox("Safety officer", ["", *sorted(officers, key=officers.get)],
                                  format_func=lambda key: officers.get(key, "All officers")),
        driver=sidebar.text_input("Driver search", placeholder="Name or driver ID"),
        vehicle=sidebar.text_input("Vehicle search", placeholder="Name or vehicle ID"),
        trailer=sidebar.text_input("Trailer search", placeholder="Name or trailer ID"),
        co_driver=sidebar.selectbox("Co-driver", ["", *sorted(co_drivers, key=co_drivers.get)],
                                    format_func=lambda key: f"{co_drivers[key]} ({key})" if key else "All co-drivers"),
    )
    scope = apply_filters(data, dates, filters)
    badge = {"Live": "green", "Demo": "blue", "Saved snapshot": "orange"}[source]
    st.badge(source, color=badge)
    st.caption(f"{dates[0]:%b %d, %Y} – {dates[-1]:%b %d, %Y} · {config.timezone}")
    st.caption("Expected PTI data unavailable — showing recorded inspection activity only.")
    if source == "Saved snapshot":
        st.warning("Showing a previously synchronized report. Some calendar days may have incomplete coverage.")
    if len(scope.undated) or data.missing_ids:
        st.warning(f"Data quality · {len(scope.undated):,} matching DVIRs without a usable date "
                   f"and {data.missing_ids:,} source records without a DVIR ID were excluded from dated totals.")
        if len(scope.undated):
            with st.expander("Review DVIRs without a usable date"):
                from .components.tables import table

                table(scope.undated[["dvir_id", "author_id", "author_name", "inspection_type",
                                     "safety_status", "vehicle_name"]], "undated")
    team_scope = None
    if team_page:
        sidebar.caption("Team records match the selected officer on either driver.")
        team_scope = apply_filters(data, dates, replace(filters, officer="")) if filters.officer else scope
    return Context(data, scope, config.timezone, team_scope, filters.officer, filters)
