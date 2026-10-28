"""ReportService tested in isolation. unittest.mock.create_autospec plays the role
Mockito plays in Java: the mocks respect the port signatures and let us verify
interactions (assert_called_once_with ~ Mockito.verify)."""
from unittest.mock import create_autospec

import pytest

from app.application.report_service import ReportService
from app.domain.reports.errors import ReportNotFound, UnknownMunicipality
from app.domain.reports.model import Category, Report
from app.domain.reports.ports import ReportRepository
from app.domain.shared.errors import ExternalDataUnavailable
from app.domain.territory.model import Municipality
from app.domain.territory.ports import TerritorialDataPort

BOGOTA = Municipality("11001", "BOGOTÁ, D.C.", "11", "BOGOTÁ, D.C.", "Municipio", 4.65, -74.1)


def report(code="11001"):
    return Report(title="Streetlight off near school", description="Dark street for a week",
                  category=Category.STREETLIGHT, address="Calle 10 # 5-20",
                  latitude=4.6, longitude=-74.08, municipality_code=code)


@pytest.fixture
def repo():
    r = create_autospec(ReportRepository, instance=True)
    r.add.side_effect = lambda rep: rep.with_changes(id=1)
    r.update.side_effect = lambda rep: rep
    return r


@pytest.fixture
def territory():
    return create_autospec(TerritorialDataPort, instance=True)


def test_create_marks_report_as_verified_when_code_exists(repo, territory):
    territory.get_municipality.return_value = BOGOTA
    saved = ReportService(repo, territory).create(report())
    territory.get_municipality.assert_called_once_with("11001")
    assert saved.municipality_verified is True and saved.id == 1


def test_create_rejects_unknown_code_and_never_persists(repo, territory):
    territory.get_municipality.return_value = None
    with pytest.raises(UnknownMunicipality):
        ReportService(repo, territory).create(report("99999"))
    repo.add.assert_not_called()


def test_create_degrades_gracefully_when_open_data_is_down(repo, territory):
    territory.get_municipality.side_effect = ExternalDataUnavailable("divipola", "circuit open", 30)
    saved = ReportService(repo, territory).create(report())
    repo.add.assert_called_once()
    assert saved.municipality_verified is False


def test_create_without_code_does_not_call_territory(repo, territory):
    ReportService(repo, territory).create(report(code=None))
    territory.get_municipality.assert_not_called()


def test_get_missing_report_raises(repo, territory):
    repo.get.return_value = None
    with pytest.raises(ReportNotFound):
        ReportService(repo, territory).get(42)


def test_delete_missing_report_raises(repo, territory):
    repo.delete.return_value = False
    with pytest.raises(ReportNotFound):
        ReportService(repo, territory).delete(42)


def test_update_with_new_code_is_verified_again(repo, territory):
    repo.get.return_value = report(code=None).with_changes(id=7)
    territory.get_municipality.return_value = BOGOTA
    updated = ReportService(repo, territory).update(7, municipality_code="11001")
    territory.get_municipality.assert_called_once_with("11001")
    assert updated.municipality_verified is True
