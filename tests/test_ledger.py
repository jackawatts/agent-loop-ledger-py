from agent_loop_ledger import LedgerVerdict, fingerprint, inspect_ledger


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
            ("runSql", {"query": "select 1"}),
            ("saveReport", {"id": "r1"}),
            ("RunSql", {"query": " SELECT 1 "}),
            ("runSql", {"query": "select 1"}),
        ]
    )
    assert verdict.repeats == 3
    assert verdict.worst_offender == 'runsql({query:"select 1"})'


def test_inspect_ledger_only_looks_at_the_sliding_window():
    calls = [("a", {}), ("a", {})] + [("b", {"i": i}) for i in range(10)]
    assert inspect_ledger(calls, window=10).repeats == 1
    assert inspect_ledger(calls, window=12).repeats == 2


def test_inspect_ledger_on_no_calls_reports_zero_repeats():
    assert inspect_ledger([]) == LedgerVerdict(repeats=0, worst_offender=None)
