from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import run_spy_v73_xnys_calendar_source_first as v73
from scripts import run_spy_v69_source_first_multimonth_census as v69
from scripts import run_spy_v65_full_june_offline_simulator_readiness as v65


def test_exchange_holidays_removed_but_real_mwf_remain():
    # NYSE 2025 New Year's, MLK, President's Day, Good Friday, Memorial Day.
    all_months=[
        (1,{1,20}), (2,{17}), (4,{18}), (5,{26})
    ]
    for month, closed_days in all_months:
        days=v73.xnys(date(2025,month,1),date(2025,month,28))
        assert all(d.day not in closed_days for d in days)
        assert all(d.weekday()<5 for d in days)
    june=v73.xnys(date(2025,6,2),date(2025,6,30))
    assert date(2025,6,19) not in june
    assert date(2025,6,23) in june


def test_existing_default_weekday_function_remains_frozen():
    from scripts.run_spy_v56_multi_session_quote_replay import dates_in_window
    june=list(dates_in_window(date(2025,6,16),date(2025,6,20)))
    assert date(2025,6,19) in june
    assert date(2025,6,19) not in v73.xnys(date(2025,6,16),date(2025,6,20))


def test_wrapper_passes_one_calendar_to_source_and_signal_readers(tmp_path):
    log=[]
    calendar=lambda start,end:[date(2025,1,2),date(2025,1,3)]
    def fake_audit(first,last,output):
        log.append(('audit',first,last))
        return {'contract': 'synthetic', 'status':'source'}
    def fake_source_runner(start,end,output_dir,*,audit,session_calendar,emit):
        log.append(('source',session_calendar(start,end)))
        assert audit(date(2025,1,2),date(2025,1,3),
                     tmp_path/'preflight') == {'contract':'synthetic','status':'source'}
        return {'status':'COMPLETE_SOURCE_CENSUS_QUOTE_REFERENCE_ONLY',
                'weekdays':2}
    messages=[]
    out=v73.run(date(2025,1,1),date(2025,1,3),
               tmp_path/'out',calendar=calendar,
               underlying_audit=fake_audit,
               source_runner=fake_source_runner,emit=messages.append)
    assert out['weekdays']==2
    assert log==[
        ('source',[date(2025,1,2),date(2025,1,3)]),
        ('audit',date(2025,1,2),date(2025,1,3))
    ]
    assert messages[0].startswith('STAGE_START V73 XNYS')
    assert any(x.startswith('START V73') for x in messages)
    assert messages[-1].startswith('COMPLETE V73')


def test_core_calendar_gate_rejects_nonmonotonic_injection_without_provider(tmp_path):
    attempts=[]
    def blocked_audit(*a):
        attempts.append(1)
        raise AssertionError('should not run')
    with pytest.raises(v69.V69Error, match='INVALID_EXCHANGE_SESSION'):
        v69.run(date(2025,1,1),date(2025,1,4),tmp_path/'v69',
                audit=blocked_audit,
                session_calendar=lambda a,b:[date(2025,1,3),date(2025,1,2)])
    assert not attempts
    assert not (tmp_path/'v69').exists()
