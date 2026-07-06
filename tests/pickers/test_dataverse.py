from datetime import datetime, timezone
from unittest.mock import MagicMock

from clabe.pickers.dataverse import _SUGGESTIONS_TABLE, _get_subjects_by_acquisition_type

_GROUPBY = "groupby((aibs_mouse_id/aibs_mouse_id),aggregate(createdon with max as latest_created))"


def test_get_subjects_by_acquisition_type_dedupes_and_ignores_annotations():
    client = MagicMock()
    client.query.return_value = [
        {
            "aibs_dim_mice_aibs_mouse_id": "123456",
            "aibs_dim_mice_aibs_mouse_id@OData.Community.Display.V1": "x",
            "latest_created": "2026-06-01T00:00:00Z",
        },
        {"aibs_dim_mice_aibs_mouse_id": "123456", "latest_created": "2026-06-01T00:00:00Z"},
        {"aibs_dim_mice_aibs_mouse_id": None, "latest_created": "2026-06-01T00:00:00Z"},
    ]

    subjects = _get_subjects_by_acquisition_type(client, "AindVrForaging")

    assert subjects == ["123456"]
    client.query.assert_called_once_with(
        _SUGGESTIONS_TABLE,
        apply=f"filter(aibs_task_name eq 'AindVrForaging')/{_GROUPBY}",
    )


def test_get_subjects_by_acquisition_type_returns_sorted_results():
    client = MagicMock()
    client.query.return_value = [
        {"aibs_dim_mice_aibs_mouse_id": "222", "latest_created": "2026-06-01T00:00:00Z"},
        {"aibs_dim_mice_aibs_mouse_id": "111", "latest_created": "2026-06-02T00:00:00Z"},
    ]

    subjects = _get_subjects_by_acquisition_type(client, "AindVrForaging")

    assert subjects == ["111", "222"]


def test_get_subjects_by_acquisition_type_applies_created_after_filter():
    client = MagicMock()
    client.query.return_value = []

    created_after = datetime(2026, 5, 1, 12, 30, 0, tzinfo=timezone.utc)
    _get_subjects_by_acquisition_type(client, "AindVrForaging", created_after=created_after)

    client.query.assert_called_once_with(
        _SUGGESTIONS_TABLE,
        apply=(f"filter(aibs_task_name eq 'AindVrForaging' and createdon ge 2026-05-01T12:30:00Z)/{_GROUPBY}"),
    )


def test_get_subjects_by_acquisition_type_none_only_filters_by_date():
    client = MagicMock()
    client.query.return_value = []

    created_after = datetime(2026, 5, 1, 12, 30, 0, tzinfo=timezone.utc)
    _get_subjects_by_acquisition_type(client, None, created_after=created_after)

    client.query.assert_called_once_with(
        _SUGGESTIONS_TABLE,
        apply=f"filter(createdon ge 2026-05-01T12:30:00Z)/{_GROUPBY}",
    )


def test_get_subjects_by_acquisition_type_none_without_date_has_no_filter():
    client = MagicMock()
    client.query.return_value = []

    _get_subjects_by_acquisition_type(client, None)

    client.query.assert_called_once_with(_SUGGESTIONS_TABLE, apply=_GROUPBY)


def test_get_subjects_by_acquisition_type_caps_to_max_subjects_most_recent():
    client = MagicMock()
    client.query.return_value = [
        {"aibs_dim_mice_aibs_mouse_id": "oldest", "latest_created": "2026-01-01T00:00:00Z"},
        {"aibs_dim_mice_aibs_mouse_id": "newest", "latest_created": "2026-06-01T00:00:00Z"},
        {"aibs_dim_mice_aibs_mouse_id": "middle", "latest_created": "2026-03-01T00:00:00Z"},
    ]

    subjects = _get_subjects_by_acquisition_type(client, "AindVrForaging", max_subjects=2)

    # capped to the 2 most recent by latest_created, then alphabetized for display
    assert subjects == ["middle", "newest"]


def test_get_subjects_by_acquisition_type_max_subjects_none_disables_cap():
    client = MagicMock()
    client.query.return_value = [
        {"aibs_dim_mice_aibs_mouse_id": "a", "latest_created": "2026-01-01T00:00:00Z"},
        {"aibs_dim_mice_aibs_mouse_id": "b", "latest_created": "2026-06-01T00:00:00Z"},
    ]

    subjects = _get_subjects_by_acquisition_type(client, "AindVrForaging", max_subjects=None)

    assert subjects == ["a", "b"]
