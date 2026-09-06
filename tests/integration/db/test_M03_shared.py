from datetime import UTC, datetime


def test_M03_opaque_ids_are_non_sequential_strings():
    from pivot.shared.ids import new_id, validate_id

    first = new_id("document")
    second = new_id("document")

    assert isinstance(first, str)
    assert first != second
    assert validate_id(first)
    assert first.startswith("doc_")
    assert not first.removeprefix("doc_").isdigit()


def test_M03_utc_helpers_return_timezone_aware_utc():
    from pivot.shared.time import ensure_utc, utc_now

    now = utc_now()
    assert now.tzinfo is UTC
    assert ensure_utc(datetime(2026, 9, 6, 8, 0, tzinfo=None)).tzinfo is UTC
    assert ensure_utc(datetime(2026, 9, 6, 8, 0, tzinfo=UTC)) == datetime(
        2026, 9, 6, 8, 0, tzinfo=UTC
    )
