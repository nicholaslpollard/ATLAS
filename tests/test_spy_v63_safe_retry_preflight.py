from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import (
    normalize_source_requirement,
)
from scripts.run_spy_v63_prior_option_surface_source import (
    PriorOptionSourceError, REQUEST, QUOTE_METHOD,
    preflight_same_query_no_repeat,
)


def source_db(tmp_path,state):
    path=tmp_path/"receipts.sqlite3"
    con=sqlite3.connect(path)
    con.execute("CREATE TABLE sources(query_id TEXT,request_json TEXT,state TEXT)")
    req=normalize_source_requirement(QUOTE_METHOD,dict(REQUEST))
    qid=_fingerprint(req)
    if state is not None:
        con.execute("INSERT INTO sources VALUES (?,?,?)",(
            qid,json.dumps(req,sort_keys=True,separators=(",",":")),state))
    con.commit()
    con.close()
    return SimpleNamespace(resolved_path=lambda name:path),qid


@pytest.mark.parametrize("state",["FAILED_RETRYABLE","IN_FLIGHT"])
def test_timeout_and_uncertain_dispatch_are_blocked_even_after_lease(tmp_path,state):
    settings,qid=source_db(tmp_path,state)
    with pytest.raises(PriorOptionSourceError,match="AMBIGUOUS_PRIOR_DISPATCH"):
        preflight_same_query_no_repeat(settings)


@pytest.mark.parametrize("state",["ARCHIVED","NO_DATA_EXPLICIT"])
def test_verifiable_completed_receipts_allowed_cache_only(tmp_path,state):
    settings,qid=source_db(tmp_path,state)
    p=preflight_same_query_no_repeat(settings)
    assert p["query_id"]==qid
    assert p["cache_only"] is True
    assert p["state"]==state


def test_no_prior_registration_permits_one_new_read_through(tmp_path):
    settings,qid=source_db(tmp_path,None)
    p=preflight_same_query_no_repeat(settings)
    assert p["query_id"]==qid
    assert p["state"]=="NOT_REGISTERED"
    assert p["cache_only"] is False


def test_unknown_state_refuses_no_retry(tmp_path):
    settings,_=source_db(tmp_path,"DISPATCHED_UNKNOWN")
    with pytest.raises(PriorOptionSourceError,match="UNKNOWN_PRIOR_DISPATCH_STATE"):
        preflight_same_query_no_repeat(settings)


def test_invalid_fingerprint_or_request_identity_refused(tmp_path):
    settings,qid=source_db(tmp_path,"ARCHIVED")
    con=sqlite3.connect(settings.resolved_path(""))
    con.execute("UPDATE sources SET request_json=?",(json.dumps({"method":"no"}),))
    con.commit()
    con.close()
    with pytest.raises(PriorOptionSourceError,match="PRIOR_QUERY_FINGERPRINT_CONFLICT"):
        preflight_same_query_no_repeat(settings)
