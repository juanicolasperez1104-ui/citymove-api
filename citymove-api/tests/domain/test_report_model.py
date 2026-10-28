import pytest

from app.domain.reports.errors import InvalidReport, InvalidStatusTransition
from app.domain.reports.model import Category, Report, Status


def make(**kw):
    base = dict(title="Pothole on Av. Boyaca", description="Large pothole, a cyclist fell",
                category=Category.POTHOLE, address="Av. Boyaca con calle 80",
                latitude=4.69, longitude=-74.09)
    base.update(kw)
    return Report(**base)


def test_valid_report_starts_open_and_unverified():
    r = make()
    assert r.status is Status.OPEN and r.municipality_verified is False


@pytest.mark.parametrize("field,value", [("title", "abc"), ("latitude", 95.0),
                                         ("longitude", -200.0), ("municipality_code", "1100")])
def test_invariants_are_enforced(field, value):
    with pytest.raises(InvalidReport) as exc:
        make(**{field: value})
    assert exc.value.field == field


def test_allowed_lifecycle():
    r = make().change_status(Status.IN_PROGRESS).change_status(Status.RESOLVED)
    assert r.status is Status.RESOLVED


@pytest.mark.parametrize("start,target", [(Status.OPEN, Status.RESOLVED),
                                          (Status.RESOLVED, Status.OPEN),
                                          (Status.REJECTED, Status.IN_PROGRESS)])
def test_forbidden_transitions(start, target):
    with pytest.raises(InvalidStatusTransition):
        make(status=start).change_status(target)
