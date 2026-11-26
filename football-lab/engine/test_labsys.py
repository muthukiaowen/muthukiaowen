"""End-to-end acceptance tests for LAB-1.0 on a synthetic round in a temporary folder. Run: python3 engine/test_labsys.py"""
import os, sys, json, tempfile, shutil
sys.path.insert(0,os.path.dirname(__file__)); import labsys as L
R=[]
def check(name,cond): R.append((name,bool(cond))); print(('PASS' if cond else 'FAIL'),name)
def raises(name,fn,frag=''):
    try: fn(); check(name,False)
    except L.LabError as e: check(name,frag in str(e))
base=tempfile.mkdtemp(); d=f'{base}/T1'; os.makedirs(d)
json.dump({'rounds':[{'id':'T1','label':'test round','status':'test'}]},open(f'{base}/rounds.json','w'))
fx=[dict(fixture_id=f'T1-0{i}',match_no=i,home=h,away=a,country='Testland',league='Test League',kickoff_EAT='2030-01-05 15:00') for i,(h,a) in enumerate([('Alpha','Beta'),('Gamma','Delta'),('Eps','Zeta'),('Eta','Theta'),('Iota','Kappa')],1)]
L.wr(f'{d}/fixtures.csv',fx,list(fx[0]))
od=[('T1-01',1,2.10,3.30,3.60),('T1-01',2,2.00,3.40,3.90),('T1-02',1,2.60,3.20,2.60),('T1-03',1,2.40,'',2.90),('T1-04',1,1.80,3.60,4.50),('T1-05',1,2.50,3.00,2.90)]
L.wr(f'{d}/odds_snapshots.csv',[dict(fixture_id=f,snapshot=s,capture_time_EAT='2030-01-0%d 10:00'%(2+s),source='test book',odds_home=h,odds_draw=dr,odds_away=a) for f,s,h,dr,a in od],L.OD_COLS)
# --- 1 fixtures
check('fixtures validate',len(L.validate_fixtures(d))==5)
# --- 2 evidence
def ev(i,fid,team,topic,claim,cat='verified_fact',state='confirmed',conf='high',ft='',fd='',url='https://club.example/news'):
    return dict(evidence_id=i,fixture_id=fid,team=team,player='',topic=topic,claim=claim,category=cat,source_name='Club site' if url else '',source_url=url,published_at='2030-01-03 09:00',retrieved_at='2030-01-03 12:00',confidence=conf,corroborated_by=('https://second.example/x' if ft else ''),state=state,factor_type=ft,factor_direction=fd)
E=[ev('E0001','T1-01','Alpha','team_news','Top scorer out'),ev('E0002','T1-01','Alpha','team_news','Confirmed by league',url='https://league.example/a'),
   ev('E0003','T1-01','Beta','team_news','Full squad'),ev('E0004','T1-01','Beta','team_news','Coach confirms',url='https://press.example/b'),
   ev('E0005','T1-02','Gamma','team_news','Keeper out',ft='key_absence',fd='away'),ev('E0006','T1-02','Gamma','coaching','Coach sacked this week',ft='coaching_change',fd='away'),
   ev('E0007','T1-02','Delta','team_news','Striker injured',cat='reported',state='disputed',conf='low',ft='key_absence',fd='home'),
   ev('E0008','T1-02','Gamma','team_news','Second keeper also out',ft='key_absence',fd='away')]
L.wr(f'{d}/evidence.csv',E,L.EV_COLS); check('evidence validates',len(L.validate_evidence(d))==8)
bad=E+[ev('E0009','T1-02','Delta','team_news','No source given',url='')]; L.wr(f'{d}/evidence.csv',bad,L.EV_COLS)
raises('fact without a source is rejected',lambda:L.validate_evidence(d),'needs a source'); L.wr(f'{d}/evidence.csv',E,L.EV_COLS)
def down(*a): raise L.SourceUnavailable('API timeout')
L.fetch_with(down,d,'T1-03','Eps','team_news'); u=L.rd(f'{d}/evidence.csv')[-1]
check('unavailable source is recorded as unknown, not guessed',u['category']=='unknown' and 'NOT FOUND' in u['claim'])
# --- model inputs: 02 near-level, 04 too few venue games, 05 none
mi=[dict(fixture_id='T1-01',league='Test League',lg_home_goals=150,lg_away_goals=120,lg_matches=100,h_games=6,h_gf=14,h_ga=5,a_games=6,a_gf=5,a_ga=12,source_url='https://league.example/t',retrieved_at='2030-01-03 12:00'),
    dict(fixture_id='T1-02',league='Test League',lg_home_goals=150,lg_away_goals=120,lg_matches=100,h_games=6,h_gf=5,h_ga=5,a_games=6,a_gf=7,a_ga=8,source_url='https://league.example/t',retrieved_at='2030-01-03 12:00'),
    dict(fixture_id='T1-03',league='Test League',lg_home_goals=150,lg_away_goals=120,lg_matches=100,h_games=6,h_gf=9,h_ga=7,a_games=6,a_gf=7,a_ga=8,source_url='https://league.example/t',retrieved_at='2030-01-03 12:00'),
    dict(fixture_id='T1-04',league='Test League',lg_home_goals=150,lg_away_goals=120,lg_matches=100,h_games=2,h_gf=5,h_ga=1,a_games=6,a_gf=4,a_ga=9,source_url='https://league.example/t',retrieved_at='2030-01-03 12:00')]
L.wr(f'{d}/model_inputs.csv',mi,L.MI_COLS)
# --- 3 possibilities gate
out=L.run_probabilities(d); check('probabilities blocked until three-outcome assessment exists',all(r['status']=='blocked' for r in out))
def po(fid,o,sup='E0001',con='none'): return dict(fixture_id=fid,outcome=o,supporting_evidence_ids=sup,contradicting_evidence_ids=con,scenarios='s',dependencies='d',uncertainties='u',change_conditions='c',completed_at='2030-01-03 13:00')
P=[po(f,o) for f in('T1-01','T1-02','T1-04','T1-05') for o in 'HDA']+[po('T1-03','H'),po('T1-03','A')]
L.wr(f'{d}/possibilities.csv',P,L.PO_COLS); done=L.validate_possibilities(d)
check('a fixture with only two outcomes assessed is incomplete','T1-03' not in done and len(done)==4)
L.wr(f'{d}/possibilities.csv',P+[po('T1-03','D',sup='E9999')],L.PO_COLS); raises('possibility citing non-existent evidence is rejected',lambda:L.validate_possibilities(d),'does not exist')
L.wr(f'{d}/possibilities.csv',P+[po('T1-03','D')],L.PO_COLS)
# --- 4 probabilities
out={r['fixture_id']:r for r in L.run_probabilities(d)}; a=out['T1-01']
check('probabilities total 100%',abs(float(a['p_home'])+float(a['p_draw'])+float(a['p_away'])-1)<2e-4)
check('ranges contain the estimate',float(a['p_home_lo'])<=float(a['p_home'])<=float(a['p_home_hi']))
check('second outcome and three scorelines reported',a['second_most_likely'] in 'HDA' and a['top_scorelines'].count(';')==2)
check('too few venue games returns insufficient evidence',out['T1-04']['status']=='insufficient_evidence')
check('no model inputs returns insufficient evidence',out['T1-05']['status']=='insufficient_evidence')
check('worked example reproduces 49.3 / 17.9 / 32.8',[round(100*x,1) for x in L.hda(*[L.model(dict(lg_home_goals=186,lg_away_goals=119,lg_matches=90,h_games=5,h_gf=11,h_ga=8,a_games=4,a_gf=11,a_ga=13))[k] for k in('xg_home','xg_away')])]==[49.3,17.9,32.8])
# --- 5 market
mk=L.run_market(d)
check('market probabilities total 100%',abs(sum(mk['T1-01']['p'])-1)<2e-4)
check('latest snapshot used and movement recorded',mk['T1-01']['used_snapshot']=='2' and mk['T1-01']['movement'][0]>0)
check('missing price gives an incomplete market record',mk['T1-03']['complete'] is False and mk['T1-03']['p'] is None)
check('level prices give no favourite',mk['T1-02']['favourite']=='none')
# --- predictions, override, lineage
pd=L.build_predictions(d,extra={'Shuffle':{'T1-01':{'pick':'A'}}}); g=lambda f,m:next((r for r in pd if r['fixture_id']==f and r['method_id']==m),None)
check('M1 uses the declared home tie-break when level',g('T1-02','M1')['pick']=='H')
check('no M1 row where the market record is incomplete',g('T1-03','M1') is None)
check('no model row where evidence is insufficient',g('T1-04','S2') is None and g('T1-04','FID-A') is None)
f2=g('T1-02','FID-A'); s2=g('T1-02','S2')
check('override fires only on confirmed factors, counted once per cause',f2['override']=='yes' and f2['pick']!=f2['core_pick'] and len(f2['override_factors'].split())==2)
check('override never changes the probabilities',[f2['p_home'],f2['p_draw'],f2['p_away']]==[s2['p_home'],s2['p_draw'],s2['p_away']])
check('disputed report does not count as a factor','E0007' not in f2['override_factors'])
check('lineage recorded: FID is not an independent source',g('T1-01','FID-A')['independent_source'].startswith('no') and g('T1-01','M1')['independent_source'].startswith('yes'))
check('coverage: two sources per team is high',g('T1-01','S2')['coverage']=='high' and g('T1-03','S2')['coverage']=='low')
# --- 6 review and freeze
raises('freeze refused without a review',lambda:L.freeze(d,'approved','Owen',99,at='2030-01-04 16:00'),'no pre-freeze review')
rv=L.review(d); check('review lists coverage, skips and hashes',rv['fixtures']==5 and 'predictions.csv' in rv['hashes'] and 'T1-04' in rv['methods']['S2']['skipped'])
raises('freeze refused without explicit approval',lambda:L.freeze(d,'','',99,at='2030-01-04 16:00'),'explicit approval')
raises('freeze refused after kick-off',lambda:L.freeze(d,'approved','Owen',99,at='2030-01-05 15:30'),'invalid')
open(f'{d}/evidence.csv','a').write('\n'); raises('freeze refused if files changed after the review',lambda:L.freeze(d,'approved','Owen',99,at='2030-01-04 16:00'),'changed after the review')
L.wr(f'{d}/evidence.csv',L.rd(f'{d}/evidence.csv'),L.EV_COLS); L.review(d)
man=L.freeze(d,'I approve the review','Owen',99,at='2030-01-04 16:00'); check('freeze records approval, version and SHA-256 hashes',man['approval']['by']=='Owen' and len(man['files']['predictions.csv'])==64)
raises('frozen round refuses recalculation',lambda:L.run_probabilities(d),'frozen'); raises('frozen round refuses rebuilding predictions',lambda:L.build_predictions(d),'frozen')
check('untouched frozen files verify',L.verify_freeze(d))
keep=open(f'{d}/predictions.csv','rb').read(); open(f'{d}/predictions.csv','wb').write(keep.replace(b',H,',b',A,',1))
raises('tampering with a frozen prediction is detected',lambda:L.verify_freeze(d),'ALTERED')
sb=L.score(base); check('a tampered round is not scored',sb['rounds'][0]['frozen_valid'] is False and sb['unique_fixtures_scored']==0)
open(f'{d}/predictions.csv','wb').write(keep); L.add_correction(d,'T1-01','M1','D','test correction')
check('correction is a separate record; frozen file unchanged',L.verify_freeze(d) and len(L.rd(f'{d}/corrections.csv'))==1)
# --- 7 results
raises('postponed match needs a settlement treatment',lambda:L.add_result(d,'T1-03','','','postponed','https://x.example'),'settlement treatment')
L.add_result(d,'T1-01','A','0-1','played','https://a.example','https://b.example'); L.add_result(d,'T1-02','D','1-1','played','https://a.example')
L.add_result(d,'T1-03','','','postponed','https://a.example',treatment='excluded from scoring'); L.add_result(d,'T1-04','','1-0 at 60 min','abandoned','https://a.example',treatment='excluded from scoring')
raises('changing a result needs a reason',lambda:L.add_result(d,'T1-01','H','1-0','played','https://a.example'),'correction reason')
L.add_result(d,'T1-01','H','1-0','played','https://a.example','https://b.example',reason='first entry had the score reversed')
check('corrected result supersedes, original kept',L.final_results(d)['T1-01']['outcome']=='H' and len([r for r in L.rd(f'{d}/results.csv') if r['fixture_id']=='T1-01'])==2)
# --- 8 scoring
sb=L.score(base); m=sb['methods']
check('only played fixtures are scored',sb['unique_fixtures_scored']==2 and len(sb['excluded'])==2)
check('frozen pick is scored, not the correction',m['M1 M1-1.0']['correct']==1 and m['M1 M1-1.0']['n']==2)
check('four-way market comparison adds up',sum(v for k,v in m['S2 S2-1.0']['vs_market'].items() if k!='fixtures')==m['S2 S2-1.0']['vs_market']['fixtures'])
check('Brier, log loss and calibration from frozen probabilities',m['S2 S2-1.0']['brier'] is not None and m['S2 S2-1.0']['calibration'])
check('override scored against the core selection',m['FID-A FID-v1.0']['overrides']['count']==1 and m['FID-A FID-v1.0']['core_selection'][1]==2)
check('coverage and league breakdowns present','high' in m['S2 S2-1.0']['by_coverage'] and 'Test League' in m['S2 S2-1.0']['by_league'])
check('draw test withheld below 120 fixtures',sb['draw_hypothesis']['p_value'] is None)
st=L.state(base); check('dashboard state built from the operational files',st['rounds'][0]['frozen'] and st['rounds'][0]['fixtures'][0]['result']=='H')
shutil.rmtree(base); n=sum(ok for _,ok in R); print(f'\n{n} of {len(R)} tests passed'); json.dump(dict(passed=n,total=len(R),tests=[dict(name=a,passed=b) for a,b in R]),open(os.path.join(os.path.dirname(__file__),'test_results.json'),'w'),indent=1); sys.exit(0 if n==len(R) else 1)
