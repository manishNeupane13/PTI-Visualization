"""Exercise navigation, cache refresh, and inspection drill-down."""
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def preserve_navigation_mode(monkeypatch):
    """AppTest creates a fresh PagesManager on every run; the real server keeps it."""
    from streamlit.runtime import pages_manager

    class TestPath(type(Path())):
        def exists(self):
            if self == ROOT / "pages":
                return False
            return super().exists()

    monkeypatch.setattr(pages_manager, "Path", TestPath)


def app() -> AppTest:
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)


def test_demo_navigation_and_drilldown(monkeypatch):
    monkeypatch.setenv("PTI_MODE", "demo")
    dashboard = app().run()
    assert not dashboard.exception
    assert len(dashboard.metric) == 8
    dashboard.sidebar.radio[0].set_value(15).run()
    for path in sorted((ROOT / "pages").glob("*.py"))[1:]:
        dashboard.switch_page(f"pages/{path.name}").run()
        assert not dashboard.exception
    dashboard.switch_page("pages/3_Driver_Profiles.py").run()
    next(widget for widget in dashboard.selectbox if widget.label == "Driver").set_value("D001").run()
    next(widget for widget in dashboard.selectbox if widget.label == "Inspect DVIR").select_index(0).run()
    assert not dashboard.exception
    assert dashboard.json


def test_live_cache_refresh_and_empty_report(monkeypatch):
    monkeypatch.setenv("PTI_MODE", "live")
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://test.invalid/test-dashboard-cache")
    monkeypatch.setenv("PTI_SQLITE_PATH", "")
    with patch("requests.Session.get") as get:
        get.return_value.status_code = 200
        get.return_value.json.return_value = {"data": []}
        dashboard = app().run()
        assert not dashboard.exception
        assert get.call_count == 1
        dashboard.sidebar.text_input[0].set_value("Alex").run()
        assert not dashboard.exception
        assert get.call_count == 1
        dashboard.sidebar.radio[0].set_value(15).run()
        assert not dashboard.exception
        assert get.call_count == 2
        dashboard.sidebar.button[0].click().run()
        assert not dashboard.exception
        assert get.call_count == 3
        assert [call.kwargs["params"]["days"] for call in get.call_args_list] == [7, 15, 15]
        for path in sorted((ROOT / "pages").glob("*.py"))[1:]:
            dashboard.switch_page(f"pages/{path.name}").run()
            assert not dashboard.exception


def test_team_officer_can_match_co_driver(monkeypatch):
    monkeypatch.setenv("PTI_MODE", "demo")
    dashboard = app().run().switch_page("pages/4_Co_Driver_Analysis.py").run()
    officer = next(widget for widget in dashboard.sidebar.selectbox if widget.label == "Safety officer")
    officer.set_value("id:SO002").run()
    assert not dashboard.exception
    pairs = dashboard.dataframe[0].value
    assert ((pairs["Driver ID"] == "D001") & (pairs["Co Driver ID"] == "D002")).any()
