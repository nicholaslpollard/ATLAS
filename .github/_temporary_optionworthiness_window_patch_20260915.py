from pathlib import Path

analyzer = Path('packages/backtesting/successor_optionworthiness_analysis.py')
text = analyzer.read_text(encoding='utf-8')
old = '''            native_timeframe,
            direction,
            count(*) AS comparable_opportunities,
'''
new = '''            native_timeframe,
            direction,
            CASE WHEN native_timeframe = '1d' THEN 'THROUGH_20_SESSIONS'
                 ELSE 'ENTRY_TO_ACTUAL_EXIT' END AS excursion_window,
            count(*) AS comparable_opportunities,
'''
if text.count(old) < 1:
    raise SystemExit('route summary marker not found')
text = text.replace(old, new, 1)
old = '''                native_timeframe,
                direction,
                threshold AS move_threshold,
'''
new = '''                native_timeframe,
                direction,
                CASE WHEN native_timeframe = '1d' THEN 'THROUGH_20_SESSIONS'
                     ELSE 'ENTRY_TO_ACTUAL_EXIT' END AS excursion_window,
                threshold AS move_threshold,
'''
if old not in text:
    raise SystemExit('threshold marker not found')
text = text.replace(old, new, 1)
old = '''            native_timeframe,
            direction,
            count(*) AS selected_comparable,
'''
new = '''            native_timeframe,
            direction,
            CASE WHEN native_timeframe = '1d' THEN 'THROUGH_20_SESSIONS'
                 ELSE 'ENTRY_TO_ACTUAL_EXIT' END AS excursion_window,
            count(*) AS selected_comparable,
'''
if old not in text:
    raise SystemExit('fold marker not found')
text = text.replace(old, new, 1)
old = '''            r.native_timeframe,
            r.direction,
            r.comparable_opportunities AS selected_comparable,
'''
new = '''            r.native_timeframe,
            r.direction,
            r.excursion_window,
            r.comparable_opportunities AS selected_comparable,
'''
if old not in text:
    raise SystemExit('diagnostic marker not found')
text = text.replace(old, new, 1)
analyzer.write_text(text, encoding='utf-8')

contract = Path('packages/strategies/successor_optionworthiness_contract.py')
text = contract.read_text(encoding='utf-8')
old = '''            "directional_mfe_percent_threshold_frequency": True,
            "directional_mae_percent_threshold_frequency": True,
'''
new = '''            "directional_mfe_percent_threshold_frequency": True,
            "directional_mae_percent_threshold_frequency": True,
            "excursion_window_semantics": {
                "daily": "THROUGH_20_SESSIONS",
                "intraday": "ENTRY_TO_ACTUAL_EXIT",
            },
'''
if old not in text:
    raise SystemExit('contract supported marker not found')
text = text.replace(old, new, 1)
old = '''            "exact_time_to_1_2_3_5_percent_favorable_move": (
                "MFE_PERSISTS_MAGNITUDE_BUT_NOT_TIMESTAMP_OF_THRESHOLD_CROSSING"
            ),
'''
new = '''            "exact_time_to_1_2_3_5_percent_favorable_move": (
                "MFE_PERSISTS_MAGNITUDE_BUT_NOT_TIMESTAMP_OF_THRESHOLD_CROSSING"
            ),
            "daily_5_session_mfe_mae_threshold_frequency": (
                "DAILY_RETAINED_MFE_MAE_COVERS_THE_20_SESSION_WINDOW_NOT_THE_PRIMARY_5_SESSION_WINDOW"
            ),
'''
if old not in text:
    raise SystemExit('contract unavailable marker not found')
text = text.replace(old, new, 1)
contract.write_text(text, encoding='utf-8')

cli = Path('scripts/run_successor_optionworthiness.py')
text = cli.read_text(encoding='utf-8')
old = '''            f"primary={pct(row.get('mean_primary_net_return'))} stress={pct(row.get('mean_stress_net_return'))} "
            f"MFE>=1/2/3/5%={pct(row.get('p_mfe_ge_1pct'))}/{pct(row.get('p_mfe_ge_2pct'))}/"
'''
new = '''            f"primary={pct(row.get('mean_primary_net_return'))} stress={pct(row.get('mean_stress_net_return'))} "
            f"excursion_window={row.get('excursion_window')} "
            f"MFE>=1/2/3/5%={pct(row.get('p_mfe_ge_1pct'))}/{pct(row.get('p_mfe_ge_2pct'))}/"
'''
if old not in text:
    raise SystemExit('cli marker not found')
text = text.replace(old, new, 1)
old = '''    print("  exact time-to-threshold: unavailable from retained artifacts; not claimed", flush=True)
'''
new = '''    print("  daily MFE/MAE threshold frequencies use the retained THROUGH_20_SESSIONS window; they are not 5-session hit rates", flush=True)
    print("  exact time-to-threshold: unavailable from retained artifacts; not claimed", flush=True)
'''
text = text.replace(old, new, 1)
cli.write_text(text, encoding='utf-8')

tests = Path('tests/test_successor_optionworthiness_analysis.py')
text = tests.read_text(encoding='utf-8')
old = '''    assert int(selected.comparable_opportunities) == 1
    assert abs(float(selected.mean_mfe) - 0.06) < 1e-12
'''
new = '''    assert int(selected.comparable_opportunities) == 1
    assert selected.excursion_window == "THROUGH_20_SESSIONS"
    assert abs(float(selected.mean_mfe) - 0.06) < 1e-12
'''
if old not in text:
    raise SystemExit('test route marker not found')
text = text.replace(old, new, 1)
old = '''    daily = rows[0]
    assert daily["selected_comparable"] == 1
'''
new = '''    daily = rows[0]
    assert daily["selected_comparable"] == 1
    assert daily["excursion_window"] == "THROUGH_20_SESSIONS"
    assert rows[1]["excursion_window"] == "ENTRY_TO_ACTUAL_EXIT"
'''
if old not in text:
    raise SystemExit('test diagnostic marker not found')
text = text.replace(old, new, 1)
tests.write_text(text, encoding='utf-8')

replacements = {
    'README.md': (
        'reports route/direction MFE/MAE distributions, 1/2/3/5% favorable/adverse excursion frequencies, daily 1/5/20-session behavior, intraday holding-time behavior, selected-fold stability, and an exact 28-route / 21-family implementation inventory.',
        'reports route/direction MFE/MAE distributions, 1/2/3/5% favorable/adverse excursion frequencies, daily 1/5/20-session behavior, intraday holding-time behavior, selected-fold stability, and an exact 28-route / 21-family implementation inventory. Daily retained MFE/MAE covers the full 20-session diagnostic window, while intraday MFE/MAE covers entry-to-actual-exit; the report labels this explicitly and does not reinterpret daily threshold hits as five-session hits.'
    ),
    'docs/roadmap.md': (
        'Per route/direction it records return and MFE/MAE distributions, 1/2/3/5% favorable-excursion and adverse-breach frequencies, available daily horizon behavior, intraday holding-time behavior, and selected-fold persistence/concentration.',
        'Per route/direction it records return and MFE/MAE distributions, 1/2/3/5% favorable-excursion and adverse-breach frequencies, available daily horizon behavior, intraday holding-time behavior, and selected-fold persistence/concentration. Daily retained MFE/MAE is explicitly labeled `THROUGH_20_SESSIONS`; intraday excursion is `ENTRY_TO_ACTUAL_EXIT`. The daily primary return remains the separate five-session outcome, so 20-session MFE threshold frequencies are never described as five-session hit rates.'
    ),
    'docs/strategy_evidence_register.md': (
        'with route/direction return distributions, MFE/MAE distributions, favorable/adverse threshold frequencies, daily 1/5/20-session diagnostics, intraday holding-time diagnostics, selected-fold stability/concentration, and the exact observed 28-route / 21-economic-family implementation inventory.',
        'with route/direction return distributions, MFE/MAE distributions, favorable/adverse threshold frequencies, daily 1/5/20-session diagnostics, intraday holding-time diagnostics, selected-fold stability/concentration, and the exact observed 28-route / 21-economic-family implementation inventory. Daily retained MFE/MAE is a 20-session excursion window and is labeled as such; intraday MFE/MAE is entry-to-actual-exit. No five-session MFE threshold frequency is claimed from the 20-session extrema.'
    ),
}
for path_str, (old, new) in replacements.items():
    path = Path(path_str)
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'document marker not found: {path_str}')
    path.write_text(text.replace(old, new, 1).rstrip() + '\n', encoding='utf-8')

Path('.github/_temporary_optionworthiness_window_patch_20260915.py').unlink(missing_ok=True)
Path('.github/workflows/_temporary_optionworthiness_window_patch_20260915.yml').unlink(missing_ok=True)
