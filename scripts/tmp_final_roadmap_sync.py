from pathlib import Path

p = Path('docs/roadmap.md')
t = p.read_text(encoding='utf-8')

t = t.replace(
    '**B35 retained-artifact robustness is COMPLETE / NO PROMOTION; exact targeted minute perturbations are CURRENT in PR #79.**',
    '**B35 retained-artifact robustness is COMPLETE / NO PROMOTION; exact targeted minute perturbations are MERGED / WORKSTATION RUN PENDING.**')
t = t.replace(
    'PR #79 implements the remaining frozen minute-path perturbations together in one DEVELOPMENT-only, restartable, hash-receipted pass with 27 one-axis-at-a-time strategy/variant profiles and per-group canonical baseline-equivalence gates. It does not refit the selector or rewrite B35 v1 and grants no promotion/PAPER/LIVE/provider/broker/master/future authority.',
    'PR #79 merged to `main` as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`. Its DEVELOPMENT-only, restartable, hash-receipted pass contains 27 one-axis-at-a-time strategy/variant profiles. Unchanged baseline variants reuse the exact accepted canonical B35 outcomes with SHA-256 verification and exact outcome-economic parity checks; only true perturbations are recomputed. It does not refit the selector or rewrite B35 v1 and grants no promotion/PAPER/LIVE/provider/broker/master/future authority.')

start_marker = 'Next Track-B sequence:'
end_marker = 'Full mechanics and methodology anchors remain in `docs/b35_a36_preoutcome_conditional_evidence.md`.'
si = t.find(start_marker)
ei = t.find(end_marker, si)
if si != -1 and ei != -1:
    ei += len(end_marker)
    current = ('Next Track-B sequence: (1) run `.\\.venv\\Scripts\\python.exe '
               'scripts\\run_b35_targeted_perturbations.py --authorize-targeted-perturbations` once from current `main`; '
               '(2) review the 27 diagnostic profiles and record the final B35 research disposition without promotion or v1 rewrite; '
               '(3) freeze only justified B35 v2 challengers plus the 21-family successor/context/confluence contract under new fingerprints; '
               '(4) implement and test the successor library on permitted evidence; '
               '(5) later evaluate genuinely new prospective/future-blind evidence only under a separately frozen authority contract; and '
               '(6) never reuse the consumed master interval. Full mechanics and methodology anchors remain in '
               '`docs/b35_a36_preoutcome_conditional_evidence.md`.')
    t = t[:si] + current + t[ei:]

t = t.replace(
    '**Status: PLANNED SUCCESSOR WORK; B35 DEVELOPMENT REPLAY, CONDITION/SELECTOR, AND RETAINED-ARTIFACT ROBUSTNESS COMPLETE; EXACT TARGETED PERTURBATION PR #79 ACCEPTANCE ACTIVE.**',
    '**Status: PLANNED SUCCESSOR WORK; B35 DEVELOPMENT REPLAY, CONDITION/SELECTOR, AND RETAINED-ARTIFACT ROBUSTNESS COMPLETE; PR #79 MERGED; EXACT TARGETED PERTURBATION WORKSTATION RUN PENDING.**')
t = t.replace('library package therefore targets **18 total families by adding eight new mechanisms**,', 'library package therefore targets **21 total families by adding eleven new mechanisms**,')
t = t.replace('### 19A.2 Eight genuinely new families', '### 19A.2 Eleven genuinely new families')

anchor = 'For every new family freeze before performance: exact timeframe/bar authority;'
additions = '''- `pract_adx_dmi_continuation_v1` — objective DMI directional state plus ADX trend-strength state under one frozen rule; ADX alone never chooses direction.\n- `pract_relative_strength_momentum_v1` — PIT ticker out/underperformance versus SPY over a small frozen horizon set; sector-relative strength remains unavailable until an accepted PIT sector map exists.\n- `pract_session_failed_break_reclaim_v1` — objective breach then bounded reclaim of previous-day high/low and premarket high/low with normalized breach depth, explicit confirmation, sweep-extreme invalidation and one coherent exit hierarchy; no hidden-liquidity claim.\n\n'''
pre = t.split(anchor, 1)[0] if anchor in t else t
if '`pract_session_failed_break_reclaim_v1`' not in pre and anchor in t:
    t = t.replace(anchor, additions + anchor, 1)

old_heading = '### 19A.3 Confluence is evidence, not vote counting'
if old_heading in t:
    context = '''### 19A.3 Shared PIT context and confluence are separate from strategy definitions\n\nThe successor run records a bounded shared context vector for incremental testing: broad-market alignment/volatility state; ticker relative strength/weakness versus SPY; one higher-timeframe trend representation; ATR-normalized trend maturity/extension; opening/premarket/same-time volume participation; overnight gap; price band; signal time; realized volatility; and liquidity/execution quality. Sector-relative strength waits for an accepted PIT sector map. Context is measured first and is not automatically a hard filter.\n\nOpening Range receives two high-priority successor policies inside the same economic family: `orb_stocks_in_play_5m_v1`, testing abnormal same-time opening participation plus a 5-minute range break, and a versioned 15-minute close + bounded retest/hold confirmation challenger. Their agreement is not independent confluence. The failed-break/reclaim family is distinct from pivot breakout because one tests rejection/reversal after a structural breach while the other tests continuation through structure.\n\nPortfolio loss limits, simultaneous-position capital competition, strategy exposure, concentration/correlation admission and account-level risk belong to the later account/PAPER simulation layer. Anchored VWAP, sector-relative strength, Level-2/order-book, options-flow/GEX and intraday fundamental conditioning wait for their own objective PIT/source contracts. Fixed arbitrary stop percentages/R:R, psychology rules, discretionary watchlists, Fibonacci/ICT/FVG/order-block terminology and generic indicator stacks are not added from practitioner anecdotes.\n\n### 19A.4 Confluence is evidence, not vote counting'''
    t = t.replace(old_heading, context, 1)
    t = t.replace('### 19A.4 Post-result diagnosis and bounded refinement', '### 19A.5 Post-result diagnosis and bounded refinement', 1)
    t = t.replace('### 19A.5 Efficient shared implementation', '### 19A.6 Efficient shared implementation', 1)
    t = t.replace('### 19A.6 Ordered successor work after B35', '### 19A.7 Ordered successor work after B35', 1)

t = t.replace(
    '3. **CURRENT:** retained-artifact robustness is complete with fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107`, 0/13 selected-cell BH-FDR rejections, Deflated-Sharpe probability 0 for all five profiles, and no promotion. Accept PR #79, then run its one-pass exact DEVELOPMENT minute perturbations; review the 27 diagnostic variant profiles and record final B35 research disposition without rewriting v1 or refitting the selector.',
    '3. **CURRENT:** retained-artifact robustness is complete with fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107`, 0/13 selected-cell BH-FDR rejections, Deflated-Sharpe probability 0 for all five profiles, and no promotion. PR #79 is merged as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`; run its one-pass exact DEVELOPMENT minute perturbations on the workstation, then review the 27 diagnostic profiles and record final B35 disposition without rewriting v1 or refitting the selector.')
t = t.replace('4. Freeze the exact **eight-new-family** successor contract, justified B35 v2 candidates, and confluence feature schema; bind the six daily plus four B34 families as retained baseline lineage.', '4. Freeze the exact **eleven-new-family / 21-family-total** successor contract, justified B35 v2 candidates, shared PIT context schema and confluence feature schema; bind the six daily plus four B34 families as retained baseline lineage.')
t = t.replace('5. Implement shared PIT indicators/pivots and the eight independent new evaluators; run source-only, semantic and exact-equivalence tests.', '5. Implement shared PIT indicators/pivots/context and the eleven independent new evaluators; run source-only, semantic and exact-equivalence tests.')

immediate = '''## 21. Immediate next action\n\n1. Pull current `main`; PR #79 is merged and the targeted perturbation package is accepted.\n2. Run `.\\.venv\\Scripts\\python.exe scripts\\run_b35_targeted_perturbations.py --authorize-targeted-perturbations` once. The run is DEVELOPMENT-only, restartable, reuses exact accepted baseline outcomes, opens no consumed-master/future-blind data, and grants no promotion/PAPER/LIVE authority.\n3. Review `analysis_v1/robustness_v1/targeted_minute_perturbations_v1/summary.json`, update the Strategy Evidence Register, and select only bounded B35 v2 challengers justified by the perturbation plus existing diagnostic evidence.\n4. Freeze the successor **21-family** roster, exact new/challenger specifications, shared PIT context vector, multiplicity/trials accounting and separate confluence/ranking contract before opening successor performance.\n5. Implement and run the broad successor historical experiment on permitted evidence. Preserve standalone family results before confluence; measure win rate together with payoff ratio, net expectancy/R, drawdown/tail loss, cost decay, MFE/MAE, support, stability, concentration and abstention.\n6. Track A Product may continue independently where evidence boundaries permit. Operational/qualifying PAPER and LIVE remain governed by their separate authority gates.\n\n'''
start = t.find('## 21. Immediate next action')
end = t.find('## 22. Retained exact historical validator statements', start)
if start != -1 and end != -1:
    t = t[:start] + immediate + t[end:]

t = t.replace('## 21. Living Strategy Evidence Register', '## 23. Living Strategy Evidence Register')
t = t.replace('B35 canonical replay and the first strategy x condition / selector profile are\ncomplete. The current Track-B gate is the remaining preregistered B35 robustness and\nfinal research-disposition package. Do not rerun the canonical minute replay and do\nnot freeze condition-gated v2 rules until robustness is complete.', 'B35 canonical replay, strategy x condition/selector analysis, and retained-artifact robustness are complete. The current Track-B gate is the merged PR #79 targeted minute-perturbation workstation run and final B35 research disposition. Do not rerun the canonical minute replay and do not freeze condition-gated v2 rules until the targeted perturbation evidence is reviewed.')
t = t.replace('After B35 robustness closes, freeze successor strategy versions and the broader\n18-family/confluence package under new fingerprints.', 'After the targeted perturbation evidence closes B35, freeze successor strategy versions and the broader\n21-family/context/confluence package under new fingerprints.')

# Remove duplicate appended successor B36; retain the earlier literature-anchored B36.
dup = '\n### B36 — Successor 21-family Strategy Laboratory\n'
idx = t.find(dup)
if idx != -1:
    t = t[:idx].rstrip() + '\n'

p.write_text(t, encoding='utf-8')
print('roadmap reconciled')
