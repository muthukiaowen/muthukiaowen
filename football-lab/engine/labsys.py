"""Jackpot Lab engine, version LAB-1.0.
One module, one workflow: validate -> evidence -> possibilities -> probabilities -> market -> review -> approve+freeze
-> results -> score. Every stage reads and writes plain CSV/JSON files inside one round directory, and every stage
refuses to run if the stage before it is incomplete. Nothing here uses odds as a model input."""
import csv, json, math, hashlib, os, sys, datetime
EAT=datetime.timezone(datetime.timedelta(hours=3))
def now(): return datetime.datetime.now(EAT).strftime('%Y-%m-%d %H:%M')
class LabError(Exception): pass
class SourceUnavailable(Exception): pass
# ---------- file helpers ----------
def rd(p):
    if not os.path.exists(p): return []
    with open(p,encoding='utf-8',newline='') as f: return list(csv.DictReader(f))
def wr(p,rows,cols):
    with open(p,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def sha(p):
    with open(p,'rb') as f: return hashlib.sha256(f.read()).hexdigest()
def frozen(d): return os.path.exists(f'{d}/freeze_manifest.json')
def guard_unfrozen(d,what):
    if frozen(d): raise LabError(f'round is frozen: {what} refused. Record a correction instead.')
# ---------- schemas ----------
EV_COLS=['evidence_id','fixture_id','team','player','topic','claim','category','source_name','source_url','published_at','retrieved_at','confidence','corroborated_by','state','factor_type','factor_direction']
EV_CAT={'verified_fact','reported','unknown','interpretation'}; EV_STATE={'confirmed','disputed','outdated','unresolved'}; EV_CONF={'high','medium','low'}
TOPICS={'form','home_away','goals','underlying_stats','head_to_head','tactics','player_form','team_news','squad_depth','coaching','standings','stakes','schedule','weather_pitch','other'}
FACTORS={'','key_absence','coaching_change','short_rest','stakes'}; DIRS={'','home','away','caution','none'}
PO_COLS=['fixture_id','outcome','supporting_evidence_ids','contradicting_evidence_ids','scenarios','dependencies','uncertainties','change_conditions','completed_at']
MI_COLS=['fixture_id','league','lg_home_goals','lg_away_goals','lg_matches','h_games','h_gf','h_ga','a_games','a_gf','a_ga','source_url','retrieved_at']
PR_COLS=['fixture_id','engine','engine_version','status','reason','xg_home','xg_away','p_home','p_draw','p_away','p_home_lo','p_home_hi','p_draw_lo','p_draw_hi','p_away_lo','p_away_hi','most_likely','second_most_likely','top_scorelines','material_assumptions','generated_at']
PD_COLS=['fixture_id','method_id','method_version','label','engine','lineage','independent_source','p_home','p_draw','p_away','core_pick','override','override_factors','pick','coverage','generated_at_EAT','row_version','correction_reason']
RS_COLS=['fixture_id','outcome','score','status','settlement_treatment','source_1','source_2','recorded_at_EAT','row_version','correction_reason']
OD_COLS=['fixture_id','snapshot','capture_time_EAT','source','odds_home','odds_draw','odds_away']
# ---------- 1. fixtures ----------
def validate_fixtures(d):
    fx=rd(f'{d}/fixtures.csv'); errs=[]; seen=set()
    if not fx: raise LabError('no fixtures.csv')
    for f in fx:
        for k in('fixture_id','home','away','kickoff_EAT'):
            if not f.get(k): errs.append(f"{f.get('fixture_id','?')}: missing {k}")
        if f['fixture_id'] in seen: errs.append(f"duplicate fixture {f['fixture_id']}")
        seen.add(f['fixture_id'])
    if errs: raise LabError('; '.join(errs))
    return fx
# ---------- 2. evidence ----------
def validate_evidence(d):
    ev=rd(f'{d}/evidence.csv'); ids={f['fixture_id'] for f in validate_fixtures(d)}; errs=[]; seen=set()
    for e in ev:
        i=e['evidence_id']
        if i in seen: errs.append(f'{i}: duplicate id')
        seen.add(i)
        if e['fixture_id'] not in ids: errs.append(f'{i}: unknown fixture')
        if e['category'] not in EV_CAT: errs.append(f'{i}: bad category')
        if e['state'] not in EV_STATE: errs.append(f'{i}: bad state')
        if e['confidence'] not in EV_CONF: errs.append(f'{i}: bad confidence')
        if e['topic'] not in TOPICS: errs.append(f'{i}: bad topic')
        if e['factor_type'] not in FACTORS or e['factor_direction'] not in DIRS: errs.append(f'{i}: bad factor coding')
        if not e['claim'] or not e['retrieved_at']: errs.append(f'{i}: claim and retrieved_at are required')
        if e['category'] in('verified_fact','reported') and not (e['source_name'] and e['source_url'].startswith('http')): errs.append(f'{i}: a fact or report needs a source name and URL')
        if e['category']=='verified_fact' and e['state']=='disputed': errs.append(f'{i}: a disputed claim cannot be a verified fact')
    if errs: raise LabError('; '.join(errs))
    return ev
def add_unknown(d,fixture_id,team,topic,what,why):
    guard_unfrozen(d,'adding evidence')
    ev=rd(f'{d}/evidence.csv'); n=len(ev)+1
    ev.append(dict(evidence_id=f'E{n:04d}',fixture_id=fixture_id,team=team,player='',topic=topic,claim=f'NOT FOUND: {what} ({why})',category='unknown',source_name='',source_url='',published_at='',retrieved_at=now(),confidence='low',corroborated_by='',state='unresolved',factor_type='',factor_direction=''))
    wr(f'{d}/evidence.csv',ev,EV_COLS)
def fetch_with(adapter,d,fixture_id,team,topic):
    """Source adapters return evidence rows. If a source is down the gap is recorded as an unknown, never guessed."""
    try: return adapter(fixture_id,team,topic)
    except SourceUnavailable as e:
        add_unknown(d,fixture_id,team,topic,f'{topic} for {team}',f'source unavailable: {e}'); return []
def coverage(d):
    ev=rd(f'{d}/evidence.csv'); mi={m['fixture_id'] for m in rd(f'{d}/model_inputs.csv')}; out={}
    for f in rd(f'{d}/fixtures.csv'):
        def srcs(team): return {e['source_url'] for e in ev if e['fixture_id']==f['fixture_id'] and e['team']==team and e['topic']=='team_news' and e['category'] in('verified_fact','reported') and e['state']=='confirmed'}
        h,a=len(srcs(f['home'])),len(srcs(f['away']))
        out[f['fixture_id']]='none' if f['fixture_id'] not in mi else 'high' if h>=2 and a>=2 else 'medium' if h+a>=1 else 'low'
    return out
# ---------- 3. possibilities ----------
def validate_possibilities(d,fixture_id=None):
    po=rd(f'{d}/possibilities.csv'); evid={e['evidence_id'] for e in rd(f'{d}/evidence.csv')}; done=set(); errs=[]
    by={}
    for p in po: by.setdefault(p['fixture_id'],{})[p['outcome']]=p
    for fid,o in by.items():
        ok=set(o)=={'H','D','A'}
        for k,p in o.items():
            for col in('supporting_evidence_ids','contradicting_evidence_ids'):
                for i in filter(None,p[col].replace(';',' ').split()):
                    if i!='none' and i not in evid: errs.append(f'{fid} {k}: evidence {i} does not exist'); ok=False
            if not p['supporting_evidence_ids'] or not p['contradicting_evidence_ids'] or not p['uncertainties']: ok=False
        if ok: done.add(fid)
    if errs: raise LabError('; '.join(errs))
    return done if fixture_id is None else fixture_id in done
# ---------- 4. probability and scenario engine (GC-1.1 = GC-1.0 calculation + ranges and scenarios) ----------
K=4; MIN_VENUE=4; MIN_LEAGUE=40; ENGINE='goals_core'; ENGINE_VERSION='GC-1.1'
def pois(k,m): return math.exp(-m)*m**k/math.factorial(k)
def grid(lh,la,n=12): return [[pois(i,lh)*pois(j,la) for j in range(n+1)] for i in range(n+1)]
def hda(lh,la):
    g=grid(lh,la); H=sum(g[i][j] for i in range(13) for j in range(13) if i>j); D=sum(g[i][i] for i in range(13)); A=sum(g[i][j] for i in range(13) for j in range(13) if i<j); s=H+D+A
    return [H/s,D/s,A/s]
def model(m):
    try: v={k:float(m[k]) for k in MI_COLS[2:11]}
    except (ValueError,KeyError): return dict(status='insufficient_evidence',reason='model inputs missing or not numeric')
    if v['lg_matches']<MIN_LEAGUE: return dict(status='insufficient_evidence',reason=f"league has {int(v['lg_matches'])} matches, minimum {MIN_LEAGUE}")
    if v['h_games']<MIN_VENUE or v['a_games']<MIN_VENUE: return dict(status='insufficient_evidence',reason=f'fewer than {MIN_VENUE} venue games for a team')
    LH=v['lg_home_goals']/v['lg_matches']; LA=v['lg_away_goals']/v['lg_matches']
    ah=(v['h_gf']+K*LH)/(v['h_games']+K); da=(v['a_ga']+K*LH)/(v['a_games']+K); aa=(v['a_gf']+K*LA)/(v['a_games']+K); dh=(v['h_ga']+K*LA)/(v['h_games']+K)
    lh=ah*da/LH; la=aa*dh/LA; p=hda(lh,la)
    # uncertainty: each expected-goals value moved by one standard error of the goal counts behind it
    se_h=lh*math.sqrt(1/(v['h_gf']+K*LH)+1/(v['a_ga']+K*LH)); se_a=la*math.sqrt(1/(v['a_gf']+K*LA)+1/(v['h_ga']+K*LA))
    alts=[hda(max(.05,lh+x*se_h),max(.05,la+y*se_a)) for x in(-1,1) for y in(-1,1)]+[p]
    lo=[min(a[i] for a in alts) for i in range(3)]; hi=[max(a[i] for a in alts) for i in range(3)]
    order=sorted(range(3),key=lambda i:-p[i]); g=grid(lh,la)
    sc=sorted(((g[i][j],f'{i}-{j}') for i in range(7) for j in range(7)),reverse=True)[:3]
    flips=len({max(range(3),key=lambda i:a[i]) for a in alts})>1
    return dict(status='ok',reason='',xg_home=round(lh,3),xg_away=round(la,3),p_home=round(p[0],4),p_draw=round(p[1],4),p_away=round(p[2],4),
        p_home_lo=round(lo[0],4),p_home_hi=round(hi[0],4),p_draw_lo=round(lo[1],4),p_draw_hi=round(hi[1],4),p_away_lo=round(lo[2],4),p_away_hi=round(hi[2],4),
        most_likely='HDA'[order[0]],second_most_likely='HDA'[order[1]],top_scorelines='; '.join(f'{s} {100*q:.1f}%' for q,s in sc),
        material_assumptions=('most likely outcome changes within the uncertainty range; ' if flips else '')+f'venue samples {int(v["h_games"])} home / {int(v["a_games"])} away games; independent Poisson understates draws; no player or tactical inputs')
def run_probabilities(d):
    guard_unfrozen(d,'recalculating probabilities'); validate_evidence(d); done=validate_possibilities(d); mi={m['fixture_id']:m for m in rd(f'{d}/model_inputs.csv')}; out=[]
    for f in validate_fixtures(d):
        fid=f['fixture_id']; base=dict(fixture_id=fid,engine=ENGINE,engine_version=ENGINE_VERSION,generated_at=now())
        if fid not in done: r=dict(status='blocked',reason='three-outcome assessment not complete')
        elif fid not in mi: r=dict(status='insufficient_evidence',reason='no model inputs recorded')
        else: r=model(mi[fid])
        base.update(r); out.append(base)
    wr(f'{d}/probabilities.csv',out,PR_COLS); return out
# ---------- 5. market ----------
def market_row(h,dr,a):
    try: o=[float(h),float(dr),float(a)]
    except (TypeError,ValueError): return None
    if min(o)<=1: return None
    raw=[1/x for x in o]; s=sum(raw); p=[x/s for x in raw]; top=max(p)
    return dict(raw=raw,margin=s-1,p=p,fav='none' if sum(abs(x-top)<1e-9 for x in p)>1 else 'HDA'[p.index(top)])
def run_market(d):
    snaps=rd(f'{d}/odds_snapshots.csv'); out={}
    for f in validate_fixtures(d):
        rows=sorted([s for s in snaps if s['fixture_id']==f['fixture_id']],key=lambda s:int(s['snapshot']))
        ms=[(r,market_row(r['odds_home'],r['odds_draw'],r['odds_away'])) for r in rows]
        last=ms[-1] if ms else (None,None); first=next((m for m in ms if m[1]),(None,None))
        out[f['fixture_id']]=dict(snapshots=len(rows),used_snapshot=last[0]['snapshot'] if last[0] else '',capture_time=last[0]['capture_time_EAT'] if last[0] else '',
            complete=bool(last[1]),p=[round(x,4) for x in last[1]['p']] if last[1] else None,margin=round(last[1]['margin'],4) if last[1] else None,favourite=last[1]['fav'] if last[1] else '',
            movement=[round(last[1]['p'][i]-first[1]['p'][i],4) for i in range(3)] if last[1] and first[1] and len(ms)>1 else None)
    json.dump(out,open(f'{d}/market.json','w'),indent=1); return out
# ---------- methods and lineage ----------
def methods(): return json.load(open(os.path.join(os.path.dirname(__file__),'methods.json')))
def fid_select(fid,pr,ev):
    """FID-v1.0 section 6: probabilities are never altered; a pick may move to the second outcome only by this rule."""
    p=[float(pr['p_home']),float(pr['p_draw']),float(pr['p_away'])]; order=sorted(range(3),key=lambda i:-p[i]); top,sec='HDA'[order[0]],'HDA'[order[1]]
    side={'home':'H','away':'A','caution':'D'}
    conf=[e for e in ev if e['fixture_id']==fid and e['category']=='verified_fact' and e['state']=='confirmed' and e['factor_type'] and e['factor_direction'] in side and e['corroborated_by'].strip()]
    seen=set(); cnt={'H':[],'D':[],'A':[]}
    for e in conf:
        key=(e['team'],e['factor_type'])           # one factor per cause per team
        if key in seen: continue
        seen.add(key); cnt[side[e['factor_direction']]].append(e['evidence_id'])
    if p[order[0]]-p[order[1]]<0.05 and len(cnt[sec])-len(cnt[top])>=2: return top,sec,'yes',' '.join(cnt[sec])
    return top,top,'no',''
def build_predictions(d,extra=None):
    """Assembles every method's row from the stage outputs. `extra` supplies M2/S1/Shuffle picks made by their own procedures."""
    guard_unfrozen(d,'rebuilding predictions'); M=methods(); mk=run_market(d); pr={r['fixture_id']:r for r in rd(f'{d}/probabilities.csv')}; ev=rd(f'{d}/evidence.csv'); cov=coverage(d); rows=[]; t=now()
    def add(fid,mid,pick,p=None,core='',ov='',fac=''):
        m=M[mid]; rows.append(dict(fixture_id=fid,method_id=mid,method_version=m['version'],label=m['label'],engine=m['engine'],lineage=m['lineage'],independent_source=m['independent_source'],
            p_home=p[0] if p else '',p_draw=p[1] if p else '',p_away=p[2] if p else '',core_pick=core or pick,override=ov or 'no',override_factors=fac,pick=pick,coverage=cov.get(fid,'none'),generated_at_EAT=t,row_version=1,correction_reason=''))
    for f in validate_fixtures(d):
        fid=f['fixture_id']; m=mk[fid]
        if m['complete']:
            add(fid,'M1','H' if m['favourite']=='none' else m['favourite'],m['p'])
            if m['p'][1]>=0.29: add(fid,'A','D')
            if abs(m['p'][0]-m['p'][2])<0.03: add(fid,'B','D')
        r=pr.get(fid)
        if r and r['status']=='ok':
            p=[r['p_home'],r['p_draw'],r['p_away']]; add(fid,'S2',r['most_likely'],p)
            core,pick,ov,fac=fid_select(fid,r,ev); add(fid,'FID-A',pick,p,core,ov,fac)
        for mid,picks in (extra or {}).items():
            if fid in picks: add(fid,mid,picks[fid]['pick'],picks[fid].get('p'))
    wr(f'{d}/predictions.csv',rows,PD_COLS); return rows
# ---------- 6. review, approval, freeze ----------
FREEZE_FILES=['fixtures.csv','odds_snapshots.csv','evidence.csv','possibilities.csv','model_inputs.csv','probabilities.csv','predictions.csv']
def review(d):
    fx=validate_fixtures(d); validate_evidence(d); done=validate_possibilities(d); pr=rd(f'{d}/probabilities.csv'); pd=rd(f'{d}/predictions.csv'); mk=json.load(open(f'{d}/market.json')); cov=coverage(d)
    meth={}
    for r in pd: meth.setdefault(r['method_id'],[]).append(r['fixture_id'])
    rv=dict(generated_at=now(),fixtures=len(fx),first_kickoff=min(f['kickoff_EAT'] for f in fx),market_complete=sum(m['complete'] for m in mk.values()),
        market_incomplete=[k for k,m in mk.items() if not m['complete']],possibilities_complete=len(done),
        probabilities={s:sum(1 for r in pr if r['status']==s) for s in('ok','insufficient_evidence','blocked')},coverage={c:sum(1 for v in cov.values() if v==c) for c in('high','medium','low','none')},
        methods={k:dict(fixtures=len(v),skipped=[f['fixture_id'] for f in fx if f['fixture_id'] not in v]) for k,v in meth.items()},
        hashes={f:sha(f'{d}/{f}') for f in FREEZE_FILES if os.path.exists(f'{d}/{f}')})
    json.dump(rv,open(f'{d}/pre_freeze_review.json','w'),indent=1); return rv
def freeze(d,approval_text,approved_by,lab_version,at=None):
    if frozen(d): raise LabError('already frozen')
    if not approval_text or not approved_by: raise LabError('freeze refused: explicit approval is required')
    if not os.path.exists(f'{d}/pre_freeze_review.json'): raise LabError('freeze refused: no pre-freeze review')
    rv=json.load(open(f'{d}/pre_freeze_review.json')); cur={f:sha(f'{d}/{f}') for f in rv['hashes']}
    if cur!=rv['hashes']: raise LabError('freeze refused: files changed after the review; run the review again')
    at=at or now()
    if at>=rv['first_kickoff']: raise LabError(f"freeze refused: {at} is not before first kick-off {rv['first_kickoff']}; the round is invalid")
    man=dict(frozen_at=at,lab_version=lab_version,approval=dict(text=approval_text,by=approved_by),first_kickoff=rv['first_kickoff'],files=cur)
    json.dump(man,open(f'{d}/freeze_manifest.json','w'),indent=1); return man
def verify_freeze(d):
    man=json.load(open(f'{d}/freeze_manifest.json')); bad=[f for f,h in man['files'].items() if not os.path.exists(f'{d}/{f}') or sha(f'{d}/{f}')!=h]
    if bad: raise LabError('FROZEN RECORD ALTERED: '+', '.join(bad))
    return True
def add_correction(d,fixture_id,method_id,new_pick,reason):
    if not frozen(d): raise LabError('corrections apply only after freezing')
    if not reason: raise LabError('a correction needs a reason')
    c=rd(f'{d}/corrections.csv'); c.append(dict(fixture_id=fixture_id,method_id=method_id,new_pick=new_pick,reason=reason,recorded_at_EAT=now(),version=len(c)+2))
    wr(f'{d}/corrections.csv',c,['fixture_id','method_id','new_pick','reason','recorded_at_EAT','version'])
# ---------- 7. results ----------
STATUS={'played','postponed','abandoned','void'}
def add_result(d,fixture_id,outcome,score,status,s1,s2='',treatment='',reason=''):
    if status not in STATUS: raise LabError('bad status')
    if status=='played' and outcome not in('H','D','A'): raise LabError('a played match needs outcome H, D or A')
    if status!='played' and not treatment: raise LabError('a match that was not played needs a documented settlement treatment')
    if fixture_id not in {f['fixture_id'] for f in rd(f'{d}/fixtures.csv')}: raise LabError('unknown fixture')
    rs=rd(f'{d}/results.csv'); prev=[r for r in rs if r['fixture_id']==fixture_id]
    if prev and not reason: raise LabError('a result already exists; a change needs a correction reason')
    rs.append(dict(fixture_id=fixture_id,outcome=outcome if status=='played' else '',score=score,status=status,settlement_treatment=treatment,source_1=s1,source_2=s2,recorded_at_EAT=now(),row_version=len(prev)+1,correction_reason=reason))
    wr(f'{d}/results.csv',rs,RS_COLS)
def final_results(d):
    out={}
    for r in rd(f'{d}/results.csv'):
        if r['fixture_id'] not in out or int(r['row_version'])>int(out[r['fixture_id']]['row_version']): out[r['fixture_id']]=r
    return out
# ---------- 8. scoring ----------
def wilson(h,n,z=1.96):
    if n==0: return None
    p=h/n; dn=1+z*z/n; c=p+z*z/(2*n); m=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return [round((c-m)/dn,4),round((c+m)/dn,4)]
def pb_tail(ps,k):
    dd=[1.0]
    for p in ps:
        n=[0]*(len(dd)+1)
        for i,v in enumerate(dd): n[i]+=v*(1-p); n[i+1]+=v*p
        dd=n
    return sum(dd[k:])
def score(base):
    rounds=json.load(open(f'{base}/rounds.json'))['rounds']; M=methods(); S={}; uniq=set(); rsum=[]; excl=[]; draw=[]
    def acc(): return dict(n=0,hit=0,brier=0.0,logloss=0.0,pn=0,both=0,only_method=0,only_market=0,neither=0,mn=0,by_pick={k:[0,0] for k in 'HDA'},by_league={},by_coverage={},core_n=0,core_hit=0,override_n=0,override_hit=0,override_core_hit=0,calib={})
    for r in rounds:
        d=f"{base}/{r['id']}"; valid=frozen(d)
        info=dict(id=r['id'],label=r['label'],status=r.get('status',''),frozen_valid=False,frozen_at='',lab_version='',integrity='')
        if valid:
            try: verify_freeze(d); man=json.load(open(f'{d}/freeze_manifest.json')); info.update(frozen_valid=True,frozen_at=man['frozen_at'],lab_version=man['lab_version'],integrity='hashes verified')
            except LabError as e: info.update(integrity=str(e)); valid=False
        rsum.append(info)
        if not valid: continue
        fx={f['fixture_id']:f for f in rd(f'{d}/fixtures.csv')}; res=final_results(d); mk=json.load(open(f'{d}/market.json'))
        for fid,x in res.items():
            if x['status']!='played': excl.append(dict(fixture_id=fid,status=x['status'],treatment=x['settlement_treatment']))
        for p in rd(f'{d}/predictions.csv'):
            fid=p['fixture_id']; x=res.get(fid)
            if not x or x['status']!='played': continue
            y=x['outcome']; uniq.add(fid); a=S.setdefault(p['method_id']+' '+p['method_version'],acc()); ok=p['pick']==y
            a['n']+=1; a['hit']+=ok; a['by_pick'][p['pick']][0]+=1; a['by_pick'][p['pick']][1]+=ok
            for key,val in(('by_league',fx[fid].get('league') or fx[fid].get('country','')),('by_coverage',p['coverage'])):
                b=a[key].setdefault(val,[0,0]); b[0]+=1; b[1]+=ok
            m=mk.get(fid)
            if m and m['complete']:
                fav='H' if m['favourite']=='none' else m['favourite']; fo=fav==y; a['mn']+=1
                a['both' if ok and fo else 'only_method' if ok else 'only_market' if fo else 'neither']+=1
            if p['p_home']:
                q=[float(p['p_home']),float(p['p_draw']),float(p['p_away'])]; i='HDA'.index(y); a['pn']+=1
                a['brier']+=sum((q[j]-(j==i))**2 for j in range(3)); a['logloss']+=-math.log(max(q[i],1e-9))
                for j in range(3):
                    b=a['calib'].setdefault(f'{int(q[j]*10)*10}-{int(q[j]*10)*10+10}%',[0,0,0.0]); b[0]+=1; b[1]+=(j==i); b[2]+=q[j]
            a['core_n']+=1; a['core_hit']+=p['core_pick']==y
            if p['override']=='yes': a['override_n']+=1; a['override_hit']+=ok; a['override_core_hit']+=p['core_pick']==y
        for fid in fx:
            m=mk.get(fid); x=res.get(fid)
            if m and m['complete'] and x and x['status']=='played': draw.append((m['p'][1],x['outcome']=='D'))
    out={}
    for k,a in S.items():
        mid=k.split(' ')[0]
        out[k]=dict(label=M[mid]['label'],lineage=M[mid]['lineage'],independent_source=M[mid]['independent_source'],correct=a['hit'],n=a['n'],ci=wilson(a['hit'],a['n']),
            brier=round(a['brier']/a['pn'],4) if a['pn'] else None,logloss=round(a['logloss']/a['pn'],4) if a['pn'] else None,probability_fixtures=a['pn'],
            vs_market=dict(fixtures=a['mn'],both_right=a['both'],method_only=a['only_method'],market_only=a['only_market'],both_wrong=a['neither']),
            by_pick=a['by_pick'],by_league=a['by_league'],by_coverage=a['by_coverage'],core_selection=[a['core_hit'],a['core_n']],
            overrides=dict(count=a['override_n'],override_right=a['override_hit'],core_would_have_been_right=a['override_core_hit']),
            calibration={b:dict(n=v[0],mean_predicted=round(v[2]/v[0],4),actual=round(v[1]/v[0],4)) for b,v in sorted(a['calib'].items())})
    dob=sum(y for _,y in draw)
    sb=dict(generated_at=now(),unique_fixtures_scored=len(uniq),checkpoints=[120,250,500],rounds=rsum,methods=out,excluded=excl,
        draw_hypothesis=dict(fixtures=len(draw),observed=dob,expected=round(sum(p for p,_ in draw),2),primary_test_at=120,p_value=round(pb_tail([p for p,_ in draw],dob),4) if len(draw)>=120 else None),
        note='Small samples: no verdict before the 120, 250 and 500 fixture checkpoints. Methods sharing a lineage are not independent confirmation.')
    json.dump(sb,open(f'{base}/scoreboard.json','w'),indent=1); return sb
# ---------- dashboard state ----------
def state(base):
    """One file the dashboard reads. Built only from the operational files, never typed by hand."""
    rounds=json.load(open(f'{base}/rounds.json'))['rounds']; out=[]
    for r in rounds:
        d=f"{base}/{r['id']}"; fx=rd(f'{d}/fixtures.csv'); ev=rd(f'{d}/evidence.csv'); cov=coverage(d); pr={x['fixture_id']:x for x in rd(f'{d}/probabilities.csv')}
        try: done=validate_possibilities(d)
        except LabError: done=set()
        mk=run_market(d) if os.path.exists(f'{d}/odds_snapshots.csv') else {}; res=final_results(d); pd=rd(f'{d}/predictions.csv'); rows=[]
        for f in fx:
            fid=f['fixture_id']; e=[x for x in ev if x['fixture_id']==fid]; m=mk.get(fid,{}); p=pr.get(fid,{})
            rows.append(dict(fixture_id=fid,match_no=f.get('match_no',''),home=f['home'],away=f['away'],country=f.get('country',''),league=f.get('league',''),kickoff=f['kickoff_EAT'],
                evidence={c:sum(1 for x in e if x['category']==c) for c in sorted(EV_CAT)},coverage=cov.get(fid,'none'),possibilities='complete' if fid in done else 'not done',
                model=dict(status=p.get('status','not run'),reason=p.get('reason',''),p=[p.get('p_home'),p.get('p_draw'),p.get('p_away')] if p.get('status')=='ok' else None,
                    range=[[p.get('p_home_lo'),p.get('p_home_hi')],[p.get('p_draw_lo'),p.get('p_draw_hi')],[p.get('p_away_lo'),p.get('p_away_hi')]] if p.get('status')=='ok' else None,
                    most_likely=p.get('most_likely',''),second=p.get('second_most_likely',''),scorelines=p.get('top_scorelines','')),
                market=dict(complete=m.get('complete',False),p=m.get('p'),favourite=m.get('favourite',''),snapshot=m.get('used_snapshot',''),movement=m.get('movement')),
                picks={x['method_id']:x['pick'] for x in pd if x['fixture_id']==fid},result=(res[fid]['outcome'] or res[fid]['status']) if fid in res else ''))
        man=json.load(open(f'{d}/freeze_manifest.json')) if frozen(d) else None
        out.append(dict(id=r['id'],label=r['label'],status=r.get('status',''),frozen=bool(man),frozen_at=man['frozen_at'] if man else '',lab_version=man['lab_version'] if man else '',
            review=os.path.exists(f'{d}/pre_freeze_review.json'),fixtures=rows))
    st=dict(generated_at=now(),engine='LAB-1.0',model_engine=ENGINE_VERSION,rounds=out,methods=methods())
    json.dump(st,open(f'{base}/state.json','w'),indent=1); return st
if __name__=='__main__':
    cmd,base=sys.argv[1],sys.argv[2]
    if cmd=='state': state(base); print('state written')
    elif cmd=='score': s=score(base); print('scored',s['unique_fixtures_scored'])
