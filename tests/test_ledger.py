from agent_loop_ledger import (
    LedgerVerdict,
    ToolCall,
    classify_error,
    fingerprint,
    inspect_ledger,
)


def test_fingerprint_is_case_whitespace_and_key_order_agnostic():
    a = fingerprint("runSql", {"query": "SELECT * FROM Contacts", "limit": 10})
    b = fingerprint("RUNSQL", {"limit": 10, "query": "  select * from contacts "})
    assert a == b


def test_fingerprint_drops_empty_parameters():
    a = fingerprint("t", {"q": "x", "filter": "", "sort": None})
    b = fingerprint("t", {"q": "x"})
    assert a == b


def test_fingerprint_distinguishes_different_arguments():
    assert fingerprint("t", {"q": "select 1"}) != fingerprint("t", {"q": "select 2"})


def test_fingerprint_handles_nested_lists_and_dicts():
    a = fingerprint("t", {"ids": [1, 2], "meta": {"A": "X"}})
    b = fingerprint("t", {"meta": {"a": " x "}, "ids": [1, 2]})
    assert a == b


def test_fingerprint_handles_missing_args():
    assert fingerprint("ping") == "ping(null)"


def test_inspect_ledger_counts_normalised_repeats_and_names_worst_offender():
    verdict = inspect_ledger(
        [
            ToolCall("runSql", {"query": "select 1"}),
            ToolCall("saveReport", {"id": "r1"}),
            ToolCall("RunSql", {"query": " SELECT 1 "}),
            ToolCall("runSql", {"query": "select 1"}),
        ]
    )
    assert verdict.repeats == 3
    assert verdict.worst_offender == 'runsql({query:"select 1"})'


def test_inspect_ledger_only_looks_at_the_sliding_window():
    calls = [ToolCall("a", {}), ToolCall("a", {})] + [
        ToolCall("b", {"i": i}) for i in range(10)
    ]
    assert inspect_ledger(calls, window=10).repeats == 1
    assert inspect_ledger(calls, window=12).repeats == 2


def test_inspect_ledger_on_no_calls_reports_zero_signals():
    assert inspect_ledger([]) == LedgerVerdict(repeats=0)


def test_varied_calls_returning_the_identical_result_are_stale_results():
    verdict = inspect_ledger(
        [
            ToolCall("runSql", {"query": "select name from contacts"}, output=[]),
            ToolCall(
                "runSql", {"query": "select middle_name from contacts"}, output=[]
            ),
            ToolCall("runSql", {"query": "select * from custom_fields"}, output=[]),
        ]
    )
    assert verdict.repeats == 1
    assert verdict.stale_results == 3
    assert verdict.stale_result_tool == "runSql"


def test_stale_results_are_normalised_and_scoped_per_tool():
    verdict = inspect_ledger(
        [
            ToolCall("search", {"q": "a"}, output={"rows": " NONE "}),
            ToolCall("Search", {"q": "b"}, output={"rows": "none"}),
            ToolCall("fetchDoc", {"id": 1}, output={"rows": "none"}),
        ]
    )
    assert verdict.stale_results == 2
    assert verdict.stale_result_tool == "search"


def test_changing_results_are_not_stale_and_unrecorded_outputs_are_ignored():
    verdict = inspect_ledger(
        [
            ToolCall("t", {"i": 1}, output={"page": 1}),
            ToolCall("t", {"i": 2}, output={"page": 2}),
            ToolCall("t", {"i": 3}),
        ]
    )
    assert verdict.stale_results == 1


def test_a_recorded_none_output_still_counts_as_a_result():
    verdict = inspect_ledger(
        [
            ToolCall("t", {"i": 1}, output=None),
            ToolCall("t", {"i": 2}, output=None),
        ]
    )
    assert verdict.stale_results == 2


def test_trailing_same_class_errors_are_counted_as_a_consecutive_run():
    verdict = inspect_ledger(
        [
            ToolCall("t", {"i": 1}, output="ok"),
            ToolCall("t", {"i": 2}, error=ValueError("bad limit")),
            ToolCall("t", {"i": 3}, error=ValueError("bad offset")),
            ToolCall("t", {"i": 4}, error=ValueError("bad page")),
        ]
    )
    assert verdict.consecutive_errors == 3
    assert verdict.error_class == "ValueError"


def test_a_success_or_a_different_error_class_breaks_the_error_run():
    by_class_change = inspect_ledger(
        [
            ToolCall("t", {"i": 1}, error={"status": 500}),
            ToolCall("t", {"i": 2}, error={"status": 429}),
            ToolCall("t", {"i": 3}, error={"status": 429}),
        ]
    )
    assert by_class_change.consecutive_errors == 2
    assert by_class_change.error_class == "429"

    by_success = inspect_ledger(
        [
            ToolCall("t", {"i": 1}, error={"status": 429}),
            ToolCall("t", {"i": 2}, output="ok"),
        ]
    )
    assert by_success.consecutive_errors == 0
    assert by_success.error_class is None


def test_classify_error_picks_the_most_specific_stable_label():
    assert classify_error(TypeError("x is not callable")) == "TypeError"
    assert classify_error({"code": "ETIMEDOUT", "message": "took 30s"}) == "etimedout"
    assert classify_error({"status": 404, "body": "varies"}) == "404"
    assert classify_error("  Rate Limited ") == "rate limited"
