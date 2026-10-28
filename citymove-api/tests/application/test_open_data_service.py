from unittest.mock import call, create_autospec, MagicMock

import pytest

from app.application.open_data_service import DIVIPOLA_DATASET_ID, OpenDataService
from app.application.ports import AnalyticsPort
from app.domain.opendata.ports import DatasetCatalogPort
from app.domain.reports.ports import ReportRepository
from app.domain.shared.errors import ExternalDataUnavailable
from app.domain.territory.ports import TerritorialDataPort


@pytest.fixture
def ports():
    return (create_autospec(TerritorialDataPort, instance=True),
            create_autospec(DatasetCatalogPort, instance=True),
            create_autospec(AnalyticsPort, instance=True),
            create_autospec(ReportRepository, instance=True))


def test_refresh_loads_municipalities_then_reports(ports):
    territory, catalog, analytics, repo = ports
    territory.list_municipalities.return_value = ["m1", "m2"]
    repo.list.return_value = []
    analytics.load_municipalities.return_value = 2
    analytics.load_reports.return_value = 0
    manager = MagicMock()
    manager.attach_mock(analytics.load_municipalities, "load_municipalities")
    manager.attach_mock(analytics.load_reports, "load_reports")

    result = OpenDataService(territory, catalog, analytics, repo).refresh()

    assert result.municipalities_loaded == 2
    assert manager.mock_calls == [call.load_municipalities(["m1", "m2"]), call.load_reports([])]
    catalog.get_metadata.assert_called_once_with(DIVIPOLA_DATASET_ID)


def test_refresh_fails_fast_when_divipola_is_down(ports):
    territory, catalog, analytics, repo = ports
    territory.list_municipalities.side_effect = ExternalDataUnavailable("divipola", "timeout")
    with pytest.raises(ExternalDataUnavailable):
        OpenDataService(territory, catalog, analytics, repo).refresh()
    analytics.load_municipalities.assert_not_called()


def test_missing_provenance_does_not_break_refresh(ports):
    territory, catalog, analytics, repo = ports
    territory.list_municipalities.return_value = []
    repo.list.return_value = []
    catalog.get_metadata.side_effect = ExternalDataUnavailable("catalog", "HTTP 503")
    assert OpenDataService(territory, catalog, analytics, repo).refresh().source is None
