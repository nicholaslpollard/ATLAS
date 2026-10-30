from __future__ import annotations

from copy import deepcopy
import json
import pytest

from packages.simulation.options_pair_chronological_runtime_v50 import (
    PairReplayError, replay_pairs,
)
from packages.simulation.options_pair_runtime_journal_v50 import (
    save_runtime_journal,verify_runtime_journal,
)


def simulated():
    return replay_pairs([{
        "opportunity_id":"no_trade_1","strategy_version":"fixture",
        "signal_status":"ABSTAIN","signal_at_utc":"2020-01-02T15:00:00+00:00",
        "reason_codes":["NO_SIGNAL"], "call_identity":"SPY:2020-02-21:270:C",
        "put_identity":"SPY:2020-02-21:270:P","exit_reviews":[],
        "source_context":{"decision_available":"known fixture, not real data"},
    }])


def test_runtime_journal_preserves_all_nontrade_events_and_self_verifies(tmp_path):
    simulation=simulated()
    path=tmp_path/"events.jsonl"
    saved=save_runtime_journal(path,simulation)
    assert saved["runtime_events"]==1
    assert saved["total_journal_records"]==3
    assert verify_runtime_journal(path)==saved
    records=[json.loads(line) for line in path.read_text().splitlines()]
    assert records[0]["event_type"]=="RUN_MANIFEST"
    assert records[1]["payload"]["disposition"]=="ABSTAIN_OR_REJECT_SIGNAL"
    assert records[-1]["event_type"]=="RUN_CLOSEOUT"
    assert records[-1]["payload"]["terminal_equity_if_fully_resolved"]=="100000.00"
    assert records[0]["payload"]["no_historical_fills"]
    with pytest.raises(PairReplayError,match="ALREADY_EXISTS"):
        save_runtime_journal(path,simulation)


def test_mutation_or_truncation_or_unverified_result_fail_closed(tmp_path):
    original=simulated()
    mut=deepcopy(original)
    mut["events"][0]["reason_codes"]=["FABRICATED"]
    with pytest.raises(PairReplayError,match="UNVERIFIED"):
        save_runtime_journal(tmp_path/"wrong.jsonl",mut)
    file=tmp_path/"normal.jsonl"
    save_runtime_journal(file,original)
    x=file.read_text().splitlines()
    x[1]=x[1].replace("NO_SIGNAL","ARTIFICIAL_SIGNAL")
    file.write_text("\n".join(x)+"\n")
    with pytest.raises(PairReplayError,match="DIGEST"):
        verify_runtime_journal(file)
    path=tmp_path/"truncated.jsonl"
    save_runtime_journal(path,original)
    path.write_text("\n".join(path.read_text().splitlines()[:-1])+"\n")
    with pytest.raises(PairReplayError,match="TRUNCATED"):
        verify_runtime_journal(path)
