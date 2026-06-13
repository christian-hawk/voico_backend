from datetime import datetime

from app.modules.calls.schema import CallLabel, CallStatus

URL = "/api/calls"


async def test_caller_name_partial_match(client, make_call):
    target = await make_call(caller_name="Jane Doe")
    await make_call(caller_name="Someone Else")

    resp = await client.get(URL, params={"caller_name": "ane Do"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["id"] == str(target.id)


async def test_caller_name_is_case_insensitive(client, make_call):
    await make_call(caller_name="Jane Doe")

    resp = await client.get(URL, params={"caller_name": "jane doe"})

    assert resp.json()["total"] == 1


async def test_caller_name_does_not_match_null(client, make_call):
    await make_call(caller_name=None)
    await make_call(caller_name="Jane Doe")

    resp = await client.get(URL, params={"caller_name": "a"})

    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["caller_name"] == "Jane Doe"


async def test_caller_name_escapes_like_wildcards(client, make_call):
    await make_call(caller_name="100% legit")
    await make_call(caller_name="100x co")
    await make_call(caller_name="under_score")
    await make_call(caller_name="underXscore")

    percent = await client.get(URL, params={"caller_name": "100%"})
    underscore = await client.get(URL, params={"caller_name": "under_"})

    assert [c["caller_name"] for c in percent.json()["data"]] == ["100% legit"]
    assert [c["caller_name"] for c in underscore.json()["data"]] == ["under_score"]


async def test_caller_name_empty_returns_422(client, make_call):
    await make_call()

    resp = await client.get(URL, params={"caller_name": ""})

    assert resp.status_code == 422


async def test_caller_name_accents_do_not_fold_case(client, make_call):
    # SQLite's lower() folds ASCII only: 'm' matches 'M', but 'Í' never lowers to 'í'
    await make_call(caller_name="María García")

    lowercase = await client.get(URL, params={"caller_name": "maría"})
    uppercase = await client.get(URL, params={"caller_name": "MARÍA"})

    assert lowercase.json()["total"] == 1
    assert uppercase.json()["total"] == 0


async def test_phone_digits_match_across_formatting(client, make_call):
    await make_call(phone_number="+1 (555) 201-4832")

    for term in ["555 201", "5552014832", "(555) 201"]:
        resp = await client.get(URL, params={"phone_number": term})
        assert resp.json()["total"] == 1, term


async def test_phone_wrong_digits_do_not_match(client, make_call):
    await make_call(phone_number="+1 (555) 201-4832")

    resp = await client.get(URL, params={"phone_number": "999 888"})

    assert resp.json()["total"] == 0


async def test_phone_term_without_digits_matches_literally(client, make_call):
    await make_call(phone_number="+1 (555) 201-4832")
    await make_call(phone_number="+44 20 7946 0812")

    resp = await client.get(URL, params={"phone_number": "("})

    assert resp.json()["total"] == 1
    assert resp.json()["data"][0]["phone_number"] == "+1 (555) 201-4832"


async def test_label_exact_match(client, make_call):
    target = await make_call(label=CallLabel.sales_inquiry)
    await make_call(label=CallLabel.support)
    await make_call(label=None)

    resp = await client.get(URL, params={"label": "Sales inquiry"})

    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["id"] == str(target.id)
    assert body["data"][0]["label"] == "Sales inquiry"


async def test_label_invalid_returns_422(client, make_call):
    await make_call()

    resp = await client.get(URL, params={"label": "bogus"})

    assert resp.status_code == 422


async def test_label_enum_name_returns_422(client, make_call):
    # the query param parses by enum value ("Sales inquiry"), not member name
    await make_call(label=CallLabel.sales_inquiry)

    resp = await client.get(URL, params={"label": "sales_inquiry"})

    assert resp.status_code == 422


async def test_min_duration_is_inclusive(client, make_call):
    await make_call(duration_seconds=99)
    await make_call(duration_seconds=100)

    resp = await client.get(URL, params={"min_duration": 100})

    assert [c["duration_seconds"] for c in resp.json()["data"]] == [100]


async def test_max_duration_is_inclusive(client, make_call):
    await make_call(duration_seconds=100)
    await make_call(duration_seconds=101)

    resp = await client.get(URL, params={"max_duration": 100})

    assert [c["duration_seconds"] for c in resp.json()["data"]] == [100]


async def test_duration_range_excludes_null(client, make_call):
    await make_call(duration_seconds=50)
    await make_call(duration_seconds=150)
    await make_call(duration_seconds=250)
    await make_call(duration_seconds=None)

    resp = await client.get(URL, params={"min_duration": 100, "max_duration": 200})

    assert [c["duration_seconds"] for c in resp.json()["data"]] == [150]


async def test_min_duration_zero_includes_zero_excludes_null(client, make_call):
    await make_call(duration_seconds=0)
    await make_call(duration_seconds=None)

    resp = await client.get(URL, params={"min_duration": 0})

    assert [c["duration_seconds"] for c in resp.json()["data"]] == [0]


async def test_min_greater_than_max_returns_422(client, make_call):
    await make_call(duration_seconds=100)

    resp = await client.get(URL, params={"min_duration": 300, "max_duration": 100})

    assert resp.status_code == 422
    assert resp.json()["detail"] == "min_duration cannot exceed max_duration"


async def test_negative_duration_returns_422(client, make_call):
    await make_call()

    resp = await client.get(URL, params={"min_duration": -1})

    assert resp.status_code == 422


async def test_filters_combine_with_and(client, make_call):
    target = await make_call(
        caller_name="Jane Doe", label=CallLabel.sales_inquiry, duration_seconds=200
    )
    await make_call(caller_name="Jane Doe", label=CallLabel.support, duration_seconds=200)
    await make_call(caller_name="Jane Doe", label=CallLabel.sales_inquiry, duration_seconds=50)
    await make_call(caller_name="Bob Stone", label=CallLabel.sales_inquiry, duration_seconds=200)

    resp = await client.get(
        URL,
        params={"caller_name": "jane", "label": "Sales inquiry", "min_duration": 100},
    )

    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["id"] == str(target.id)


async def test_filters_combine_with_status(client, make_call):
    await make_call(caller_name="Jane Doe", status=CallStatus.success)
    await make_call(caller_name="Jane Doe", status=CallStatus.in_progress)

    resp = await client.get(URL, params={"caller_name": "jane", "status": "success"})

    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["status"] == "success"


async def test_filters_with_pagination(client, make_call):
    for _ in range(3):
        await make_call(caller_name="Jane Doe")
    await make_call(caller_name="Someone Else")

    first = await client.get(URL, params={"caller_name": "jane", "page": 1, "page_size": 2})
    second = await client.get(URL, params={"caller_name": "jane", "page": 2, "page_size": 2})

    assert first.json()["total"] == 3
    assert first.json()["total_pages"] == 2
    assert len(first.json()["data"]) == 2
    assert len(second.json()["data"]) == 1


async def test_page_beyond_filtered_range_returns_empty(client, make_call):
    await make_call(caller_name="Jane Doe")

    resp = await client.get(URL, params={"caller_name": "jane", "page": 99})

    body = resp.json()
    assert resp.status_code == 200
    assert body["data"] == []
    assert body["total"] == 1


async def test_sort_duration_asc_puts_nulls_last(client, make_call):
    await make_call(duration_seconds=300)
    await make_call(duration_seconds=100)
    await make_call(duration_seconds=None)

    resp = await client.get(URL, params={"sort_by": "duration_seconds", "sort_dir": "asc"})

    assert [c["duration_seconds"] for c in resp.json()["data"]] == [100, 300, None]


async def test_sort_duration_desc_puts_nulls_last(client, make_call):
    await make_call(duration_seconds=300)
    await make_call(duration_seconds=100)
    await make_call(duration_seconds=None)

    resp = await client.get(URL, params={"sort_by": "duration_seconds", "sort_dir": "desc"})

    assert [c["duration_seconds"] for c in resp.json()["data"]] == [300, 100, None]


async def test_sort_caller_name_puts_nulls_last(client, make_call):
    await make_call(caller_name="Bob Stone")
    await make_call(caller_name="Alice Reed")
    await make_call(caller_name=None)

    resp = await client.get(URL, params={"sort_by": "caller_name", "sort_dir": "asc"})

    assert [c["caller_name"] for c in resp.json()["data"]] == ["Alice Reed", "Bob Stone", None]


async def test_sort_by_label_orders_alphabetically(client, make_call):
    # the DB stores enum member names; their alphabetical order happens to
    # coincide with the display values' order for the current six labels
    await make_call(label=CallLabel.support)
    await make_call(label=CallLabel.appointment)
    await make_call(label=CallLabel.complaint)
    await make_call(label=None)

    resp = await client.get(URL, params={"sort_by": "label", "sort_dir": "asc"})

    assert [c["label"] for c in resp.json()["data"]] == [
        "Appointment",
        "Complaint",
        "Support",
        None,
    ]


async def test_sort_by_invalid_returns_422(client, make_call):
    await make_call()

    resp = await client.get(URL, params={"sort_by": "created_at"})

    assert resp.status_code == 422


async def test_sort_dir_invalid_returns_422(client, make_call):
    await make_call()

    resp = await client.get(URL, params={"sort_by": "caller_name", "sort_dir": "sideways"})

    assert resp.status_code == 422


async def test_sort_dir_without_sort_by_keeps_default_order(client, make_call):
    older = await make_call(created_at=datetime(2026, 1, 1, 10, 0, 0))
    newer = await make_call(created_at=datetime(2026, 1, 2, 10, 0, 0))

    resp = await client.get(URL, params={"sort_dir": "desc"})

    ids = [c["id"] for c in resp.json()["data"]]
    assert ids == [str(newer.id), str(older.id)]


async def test_sort_by_without_sort_dir_defaults_to_asc(client, make_call):
    await make_call(duration_seconds=200)
    await make_call(duration_seconds=100)

    resp = await client.get(URL, params={"sort_by": "duration_seconds"})

    assert [c["duration_seconds"] for c in resp.json()["data"]] == [100, 200]


async def test_default_order_is_newest_first(client, make_call):
    older = await make_call(created_at=datetime(2026, 1, 1, 10, 0, 0))
    newer = await make_call(created_at=datetime(2026, 1, 2, 10, 0, 0))

    resp = await client.get(URL)

    ids = [c["id"] for c in resp.json()["data"]]
    assert ids == [str(newer.id), str(older.id)]


async def test_sort_pagination_is_stable_across_ties(client, make_call):
    expected = set()
    for _ in range(5):
        call = await make_call(duration_seconds=100)
        expected.add(str(call.id))

    seen: set[str] = set()
    for page in [1, 2, 3]:
        resp = await client.get(
            URL,
            params={"sort_by": "duration_seconds", "page": page, "page_size": 2},
        )
        seen.update(c["id"] for c in resp.json()["data"])

    assert seen == expected


async def test_counts_stay_global_under_filters(client, make_call):
    # decided behavior: counts have no documented use case under filters,
    # so they keep the cheapest semantics (always global; only total filters)
    await make_call(caller_name="Jane Doe", status=CallStatus.success)
    await make_call(caller_name="Someone Else", status=CallStatus.success)
    await make_call(caller_name="Another One", status=CallStatus.failed)

    resp = await client.get(URL, params={"caller_name": "jane"})

    body = resp.json()
    assert body["total"] == 1
    assert body["counts"] == {"in_progress": 0, "success": 2, "failed": 1}
