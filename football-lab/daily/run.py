"""Football Intelligence Lab - daily automated run (DAILY-1.1).

One run does three things, in this order:
  1. retrieve results for predictions already frozen, and score them
  2. discover fixtures kicking off in the next 48 hours
  3. calculate GC-1.1 probabilities from results known now, and freeze them

Frozen rows are append-only. Each carries a SHA-256 chained to the row before it,
and the git commit made by the workflow is the public timestamp.
Source: football-data.org v4 (free plan). No bookmaker data is collected.
Secrets are read from the environment and never printed or written.
"""
import csv, datetime, hashlib, json, math, os, sys, time, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'engine'))
import labsys

VERSION = 'DAILY-1.1'
DATA = os.path.join(HERE, '..', 'data', 'daily')
LEAGUES = ['PL', 'ELC', 'BL1', 'SA', 'PD', 'FL1', 'DED', 'PPL', 'BSA']   # league formats only; cups are not modelled
UTC = datetime.timezone.utc
EAT = datetime.timezone(datetime.timedelta(hours=3))
WINDOW_H = 48          # freeze fixtures kicking off within this many hours
MIN_LEAD_MIN = 15      # never freeze a fixture closer to kick-off than this
DAILY_SAMPLE = 10      # at most this many fixtures frozen per kick-off day (EAT)
DRAW_GAP = 0.05        # DAILY-1.1 draw rule: pick the draw when home and away probabilities are closer than this
PRED_COLS = ['seq', 'fixture_id', 'competition', 'kickoff_utc', 'kickoff_eat', 'home', 'away', 'status', 'reason',
             'p_home', 'p_draw', 'p_away', 'pick', 'xg_home', 'xg_away', 'base_home', 'base_draw', 'base_away',
             'lg_matches', 'h_games', 'a_games', 'engine_version', 'pipeline_version', 'frozen_at_utc', 'prev_hash', 'row_hash']
RES_COLS = ['fixture_id', 'status', 'home_goals', 'away_goals', 'outcome', 'recorded_at_utc']
LOG_COLS = ['run_at_utc', 'trigger', 'requests', 'leagues_ok', 'leagues_failed', 'new_predictions', 'new_abstentions', 'new_results', 'notes']


def rd(name):
    p = os.path.join(DATA, name)
    return list(csv.DictReader(open(p, newline='', encoding='utf-8'))) if os.path.exists(p) else []


def append(name, rows, cols):
    if not rows: return
    p = os.path.join(DATA, name); new = not os.path.exists(p)
    with open(p, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new: w.writeheader()
        w.writerows(rows)


def http_fetch(url, headers):
    """Returns (status_code, parsed_json_or_None). Never logs headers."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, None


def parse_t(s): return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)


def outcome(h, a): return 'H' if h > a else 'A' if a > h else 'D'


def inputs_for(match, finished):
    """Model inputs from matches finished before now. `finished` = list of (home_id, away_id, hg, ag)."""
    hid, aid = match['homeTeam']['id'], match['awayTeam']['id']
    hm = [m for m in finished if m[0] == hid]; am = [m for m in finished if m[1] == aid]
    return dict(lg_home_goals=sum(m[2] for m in finished), lg_away_goals=sum(m[3] for m in finished), lg_matches=len(finished),
                h_games=len(hm), h_gf=sum(m[2] for m in hm), h_ga=sum(m[3] for m in hm),
                a_games=len(am), a_gf=sum(m[3] for m in am), a_ga=sum(m[2] for m in am))


def most_likely(p): return 'HDA'[[float(p['p_home']), float(p['p_draw']), float(p['p_away'])].index(max(float(p['p_home']), float(p['p_draw']), float(p['p_away'])))]


def select_pick(r):
    """DAILY-1.1 selection. Probabilities are untouched; only the pick changes."""
    if abs(r['p_home'] - r['p_away']) < DRAW_GAP: return 'D', 'draw rule: home and away within 5 points'
    return r['most_likely'], ''


def sample_rank(fid): return hashlib.sha256(('sample|' + str(fid)).encode()).hexdigest()


def row_hash(row):
    body = '|'.join(str(row[c]) for c in PRED_COLS if c != 'row_hash')
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def verify_chain(preds):
    prev = 'GENESIS'
    for r in preds:
        if r['prev_hash'] != prev or row_hash(r) != r['row_hash']: return False
        prev = r['row_hash']
    return True


def brier(p, o): return sum((p[i] - (1 if 'HDA'[i] == o else 0)) ** 2 for i in range(3))
def logloss(p, o): return -math.log(max(1e-9, p['HDA'.index(o)]))


def scoreboard(preds, results, now):
    res = {r['fixture_id']: r for r in results if r['status'] == 'FINISHED'}
    rows = [(p, res[p['fixture_id']]) for p in preds if p['status'] == 'ok' and p['fixture_id'] in res]
    def block(rs):
        n = len(rs)
        if not n: return dict(scored=0)
        mp = [[float(p['p_home']), float(p['p_draw']), float(p['p_away'])] for p, _ in rs]
        bp = [[float(p['base_home']), float(p['base_draw']), float(p['base_away'])] for p, _ in rs]
        o = [r['outcome'] for _, r in rs]
        hit = sum(p['pick'] == r['outcome'] for p, r in rs); lo, hi = labsys.wilson(hit, n)
        dp = [(p, r) for p, r in rs if p['pick'] == 'D']
        return dict(scored=n, model_correct=hit, model_accuracy=round(hit / n, 4), accuracy_95ci=[round(lo, 4), round(hi, 4)],
                    most_likely_pick_correct=sum(most_likely(p) == r['outcome'] for p, r in rs), draw_picks=len(dp), draw_picks_correct=sum(r['outcome'] == 'D' for _, r in dp), always_home_correct=o.count('H'), outcomes=dict(H=o.count('H'), D=o.count('D'), A=o.count('A')),
                    model_brier=round(sum(brier(mp[i], o[i]) for i in range(n)) / n, 4), base_rate_brier=round(sum(brier(bp[i], o[i]) for i in range(n)) / n, 4),
                    model_log_loss=round(sum(logloss(mp[i], o[i]) for i in range(n)) / n, 4), base_rate_log_loss=round(sum(logloss(bp[i], o[i]) for i in range(n)) / n, 4),
                    mean_pick_probability=round(sum(max(x) for x in mp) / n, 4))
    cal = []
    for lo_, hi_ in [(0, .2), (.2, .3), (.3, .4), (.4, .5), (.5, .6), (.6, 1.01)]:
        pts = [(float(p[k]), 1 if r['outcome'] == o else 0) for p, r in rows for k, o in (('p_home', 'H'), ('p_draw', 'D'), ('p_away', 'A')) if lo_ <= float(p[k]) < hi_]
        if pts: cal.append(dict(bin=f'{lo_:.1f}-{min(hi_, 1):.1f}', n=len(pts), mean_predicted=round(sum(x for x, _ in pts) / len(pts), 4), observed=round(sum(y for _, y in pts) / len(pts), 4)))
    by_day = {}
    for p, r in rows: by_day.setdefault(p['kickoff_eat'][:10], []).append((p, r))
    return dict(generated_at_utc=now.strftime('%Y-%m-%d %H:%M'), pipeline_version=VERSION, engine_version=labsys.ENGINE_VERSION,
                frozen_total=len(preds), predictions=sum(p['status'] == 'ok' for p in preds), abstentions=sum(p['status'] != 'ok' for p in preds),
                awaiting_result=sum(p['status'] == 'ok' and p['fixture_id'] not in res for p in preds), chain_intact=verify_chain(preds),
                overall=block(rows), by_competition={c: block([x for x in rows if x[0]['competition'] == c]) for c in sorted({p['competition'] for p, _ in rows})},
                by_day={d: block(v) for d, v in sorted(by_day.items())},
                by_pipeline_version={v: block([x for x in rows if x[0]['pipeline_version'] == v]) for v in sorted({p['pipeline_version'] for p, _ in rows})}, calibration=cal,
                note='Benchmark is the league base rate at freeze time and an always-home pick. No bookmaker prices are collected, so there is no market comparison here.')


def run(fetch=http_fetch, now=None, key=None, sleep=time.sleep, trigger='manual'):
    now = now or datetime.datetime.now(UTC); os.makedirs(DATA, exist_ok=True)
    preds = rd('predictions.csv'); results = rd('results.csv')
    if not verify_chain(preds): raise SystemExit('predictions.csv hash chain is broken - refusing to continue')
    have = {p['fixture_id'] for p in preds}; done = {r['fixture_id'] for r in results}
    pending = {p['fixture_id'] for p in preds} - done
    reqs = 0; ok = []; failed = []; new_p = []; new_r = []; notes = []
    if not key:
        notes.append('FOOTBALL_DATA_API_KEY not set'); failed = list(LEAGUES)
    else:
        for i, code in enumerate(LEAGUES):
            if i: sleep(7)                                   # free plan: 10 requests a minute
            st, js = fetch(f'https://api.football-data.org/v4/competitions/{code}/matches', {'X-Auth-Token': key}); reqs += 1
            if st == 429: sleep(61); st, js = fetch(f'https://api.football-data.org/v4/competitions/{code}/matches', {'X-Auth-Token': key}); reqs += 1
            if st != 200 or not js or 'matches' not in js:
                failed.append(f'{code}:{st}'); continue
            ok.append(code); ms = js['matches']
            fin = [(m['homeTeam']['id'], m['awayTeam']['id'], m['score']['fullTime']['home'], m['score']['fullTime']['away']) for m in ms
                   if m['status'] == 'FINISHED' and m['score']['fullTime']['home'] is not None and parse_t(m['utcDate']) < now]
            for m in ms:                                      # 1. results for frozen predictions
                fid = str(m['id'])
                if fid in pending and m['status'] in ('FINISHED', 'POSTPONED', 'CANCELLED', 'AWARDED', 'SUSPENDED'):
                    h, a = m['score']['fullTime']['home'], m['score']['fullTime']['away']; fin_ok = m['status'] == 'FINISHED' and h is not None
                    if m['status'] == 'SUSPENDED': continue
                    new_r.append(dict(fixture_id=fid, status=m['status'], home_goals=h if fin_ok else '', away_goals=a if fin_ok else '',
                                      outcome=outcome(h, a) if fin_ok else '', recorded_at_utc=now.strftime('%Y-%m-%d %H:%M')))
            n = len(fin); base = [sum(outcome(x[2], x[3]) == o for x in fin) / n for o in 'HDA'] if n else ['', '', '']
            for m in ms:                                      # 2-3. discover and freeze
                fid = str(m['id'])
                if fid in have or m['status'] not in ('SCHEDULED', 'TIMED') or not m['homeTeam'].get('id') or not m['awayTeam'].get('id'): continue
                ko = parse_t(m['utcDate']); lead = (ko - now).total_seconds() / 60
                if not (MIN_LEAD_MIN <= lead <= WINDOW_H * 60): continue
                inp = inputs_for(m, fin); r = labsys.model(inp); good = r['status'] == 'ok'
                new_p.append(dict(fixture_id=fid, competition=code, kickoff_utc=ko.strftime('%Y-%m-%d %H:%M'), kickoff_eat=ko.astimezone(EAT).strftime('%Y-%m-%d %H:%M'),
                                  home=m['homeTeam']['name'], away=m['awayTeam']['name'], status=r['status'], reason=select_pick(r)[1] if good else r['reason'],
                                  p_home=r.get('p_home', ''), p_draw=r.get('p_draw', ''), p_away=r.get('p_away', ''), pick=select_pick(r)[0] if good else '',
                                  xg_home=r.get('xg_home', ''), xg_away=r.get('xg_away', ''),
                                  base_home=round(base[0], 4) if n else '', base_draw=round(base[1], 4) if n else '', base_away=round(base[2], 4) if n else '',
                                  lg_matches=inp['lg_matches'], h_games=inp['h_games'], a_games=inp['a_games'],
                                  engine_version=labsys.ENGINE_VERSION, pipeline_version=VERSION, frozen_at_utc=now.strftime('%Y-%m-%d %H:%M:%S')))
    used = {}                                                # sample: a fixed number per kick-off day, chosen by hash, not by judgement
    for p in preds: used[p['kickoff_eat'][:10]] = used.get(p['kickoff_eat'][:10], 0) + 1
    keep = []
    for r in sorted(new_p, key=lambda r: sample_rank(r['fixture_id'])):
        d = r['kickoff_eat'][:10]
        if used.get(d, 0) < DAILY_SAMPLE: used[d] = used.get(d, 0) + 1; keep.append(r)
    skipped = len(new_p) - len(keep); new_p = keep
    if skipped: notes.append(f'{skipped} eligible fixtures outside the daily sample')
    new_p.sort(key=lambda r: (r['kickoff_utc'], r['fixture_id']))
    prev = preds[-1]['row_hash'] if preds else 'GENESIS'; seq = len(preds)
    for r in new_p:
        seq += 1; r['seq'] = seq; r['prev_hash'] = prev; r['row_hash'] = prev = row_hash(r)
    append('predictions.csv', new_p, PRED_COLS); append('results.csv', new_r, RES_COLS)
    append('run_log.csv', [dict(run_at_utc=now.strftime('%Y-%m-%d %H:%M'), trigger=trigger, requests=reqs, leagues_ok=' '.join(ok), leagues_failed=' '.join(failed),
                                new_predictions=sum(r['status'] == 'ok' for r in new_p), new_abstentions=sum(r['status'] != 'ok' for r in new_p),
                                new_results=len(new_r), notes='; '.join(notes))], LOG_COLS)
    sb = scoreboard(rd('predictions.csv'), rd('results.csv'), now)
    json.dump(sb, open(os.path.join(DATA, 'scoreboard.json'), 'w'), indent=1)
    return dict(ok=ok, failed=failed, new_predictions=new_p, new_results=new_r, scoreboard=sb)


def probe_api_football(key, now, fetch=http_fetch):
    """Records plan and quota for API-Football. Account identity fields are dropped. Costs one quota request."""
    out = dict(checked_at_utc=now.strftime('%Y-%m-%d %H:%M'))
    if not key: out['status'] = 'API_FOOTBALL_API_KEY not set'
    else:
        h = {'x-apisports-key': key}
        st, js = fetch('https://v3.football.api-sports.io/status', h); out['status_http'] = st
        r = (js or {}).get('response') or {}
        if isinstance(r, dict):
            out['plan'] = (r.get('subscription') or {}).get('plan'); out['active'] = (r.get('subscription') or {}).get('active'); out['requests'] = r.get('requests')
        out['status_errors'] = str((js or {}).get('errors'))[:300].replace(key, '[hidden]')
        st, js = fetch('https://v3.football.api-sports.io/fixtures?date=' + now.strftime('%Y-%m-%d'), h); out['fixtures_today_http'] = st
        out['fixtures_today_count'] = (js or {}).get('results'); out['fixtures_today_errors'] = str((js or {}).get('errors'))[:300].replace(key, '[hidden]')
        lg = {}
        for f in ((js or {}).get('response') or []):
            k = f"{f['league']['country']} - {f['league']['name']}"; lg[k] = lg.get(k, 0) + 1
        out['fixtures_today_leagues'] = len(lg); out['fixtures_today_sample'] = dict(sorted(lg.items(), key=lambda x: -x[1])[:25])
    json.dump(out, open(os.path.join(DATA, 'api_football_probe.json'), 'w'), indent=1); return out


if __name__ == '__main__':
    now = datetime.datetime.now(UTC)
    out = run(key=os.environ.get('FOOTBALL_DATA_API_KEY', '').strip(), trigger=os.environ.get('GITHUB_EVENT_NAME', 'manual'), now=now)
    print('leagues ok:', out['ok'], '| failed:', out['failed'], '| new frozen rows:', len(out['new_predictions']), '| new results:', len(out['new_results']))
    pr = probe_api_football(os.environ.get('API_FOOTBALL_API_KEY', '').strip(), now)
    print('api-football probe: http', pr.get('status_http'), 'plan', pr.get('plan'))
