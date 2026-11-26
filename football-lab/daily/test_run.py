"""Offline tests for the daily run. No network, no secrets."""
import datetime, itertools, os, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run as R
UTC = datetime.timezone.utc; T0 = datetime.datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
def iso(t): return t.strftime('%Y-%m-%dT%H:%M:%SZ')
def league(extra_status=None):
    teams = list(range(1, 11)); ms = []; i = 0
    for h, a in itertools.permutations(teams, 2):
        i += 1
        if i <= 60: ms.append(dict(id=i, utcDate=iso(T0 - datetime.timedelta(days=70 - i)), status='FINISHED', homeTeam=dict(id=h, name=f'T{h}'), awayTeam=dict(id=a, name=f'T{a}'), score=dict(fullTime=dict(home=(h * 7 + a) % 4, away=(a * 5 + h) % 3))))
    def fx(i, h, a, dt, st='TIMED'): return dict(id=i, utcDate=iso(T0 + dt), status=st, homeTeam=dict(id=h, name=f'T{h}'), awayTeam=dict(id=a, name=f'T{a}'), score=dict(fullTime=dict(home=None, away=None)))
    ms += [fx(901, 1, 2, datetime.timedelta(hours=5)), fx(902, 3, 4, datetime.timedelta(minutes=5)), fx(903, 5, 6, datetime.timedelta(hours=60)), fx(904, 9, 10, datetime.timedelta(hours=20))]
    return ms
checks = []
def ck(name, cond): checks.append((name, bool(cond))); print('PASS' if cond else 'FAIL', name)
tmp = tempfile.mkdtemp(); R.DATA = tmp
state = dict(ms=league(), calls=0, fail=None)
def fetch(url, headers):
    state['calls'] += 1; code = url.split('/')[-2]
    assert headers.get('X-Auth-Token') == 'k'
    if state['fail'] == code: return 403, None
    return (200, dict(matches=state['ms'])) if code == 'PL' else (200, dict(matches=[]))
out = R.run(fetch=fetch, now=T0, key='k', sleep=lambda s: None)
ids = [r['fixture_id'] for r in out['new_predictions']]
ck('fixture inside the 48h window is frozen', '901' in ids)
ck('fixture 5 minutes from kick-off is not frozen', '902' not in ids)
ck('fixture beyond 48h is not frozen yet', '903' not in ids)
p = [r for r in out['new_predictions'] if r['fixture_id'] == '901'][0]
ck('probabilities sum to 1', abs(float(p['p_home']) + float(p['p_draw']) + float(p['p_away']) - 1) < 0.001)
ck('pick is the most likely outcome', p['pick'] == 'HDA'[[float(p['p_home']), float(p['p_draw']), float(p['p_away'])].index(max(float(p['p_home']), float(p['p_draw']), float(p['p_away'])))])
ck('one request per league', state['calls'] == len(R.LEAGUES))
ck('hash chain verifies', R.verify_chain(R.rd('predictions.csv')))
out2 = R.run(fetch=fetch, now=T0 + datetime.timedelta(hours=1), key='k', sleep=lambda s: None)
ck('second run does not refreeze the same fixture', not [r for r in out2['new_predictions'] if r['fixture_id'] == '901'])
for m in state['ms']:
    if m['id'] == 901: m['status'] = 'FINISHED'; m['score'] = dict(fullTime=dict(home=2, away=2))
    if m['id'] == 904: m['status'] = 'POSTPONED'
out3 = R.run(fetch=fetch, now=T0 + datetime.timedelta(hours=8), key='k', sleep=lambda s: None)
ck('finished fixture gets a result', any(r['fixture_id'] == '901' and r['outcome'] == 'D' for r in out3['new_results']))
ck('postponed fixture recorded without an outcome', any(r['fixture_id'] == '904' and r['outcome'] == '' for r in out3['new_results']))
ck('scoreboard scores exactly one fixture', out3['scoreboard']['overall']['scored'] == 1)
ck('frozen row unchanged after result', [r for r in R.rd('predictions.csv') if r['fixture_id'] == '901'][0]['row_hash'] == p['row_hash'])
out4 = R.run(fetch=fetch, now=T0 + datetime.timedelta(hours=9), key='k', sleep=lambda s: None)
ck('result is not recorded twice', not out4['new_results'])
rows = open(os.path.join(tmp, 'predictions.csv')).read().replace('T1,', 'TX,', 1); open(os.path.join(tmp, 'predictions.csv'), 'w').write(rows)
ck('tampering with a frozen row breaks the chain', not R.verify_chain(R.rd('predictions.csv')))
try: R.run(fetch=fetch, now=T0, key='k', sleep=lambda s: None); ck('run refuses to continue on a broken chain', False)
except SystemExit: ck('run refuses to continue on a broken chain', True)
shutil.rmtree(tmp); tmp = tempfile.mkdtemp(); R.DATA = tmp
out5 = R.run(fetch=fetch, now=T0, key='', sleep=lambda s: None)
ck('missing key: no predictions, failure logged', not out5['new_predictions'] and len(out5['failed']) == len(R.LEAGUES))
state['fail'] = 'PL'; out6 = R.run(fetch=fetch, now=T0, key='k', sleep=lambda s: None)
ck('rejected key or failed league is logged, nothing invented', 'PL:403' in out6['failed'] and not out6['new_predictions'])
state['fail'] = None; state['ms'] = [m for m in league() if m['status'] != 'FINISHED'][:1] + league()[:10]
out7 = R.run(fetch=fetch, now=T0, key='k', sleep=lambda s: None)
ck('too little history: abstain, no pick', all(r['status'] != 'ok' and r['pick'] == '' for r in out7['new_predictions']) and out7['new_predictions'])
shutil.rmtree(tmp)
bad = [n for n, c in checks if not c]; print(f'{len(checks) - len(bad)} of {len(checks)} passed'); sys.exit(1 if bad else 0)
