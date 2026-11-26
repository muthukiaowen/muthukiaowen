"""Reproducible back-test of engine GC-1.1.  Usage: python3 engine/backtest.py <path to a clone of openfootball/football.json>
Procedure: for every season file of 8 leagues, matches are sorted by date; each match is predicted from the running
totals of matches played BEFORE it in the same season (league home/away goals, home team's home record, away team's
away record). The totals are updated only after the prediction, so no future information is used.
A match is rated only if the league has 40+ matches and each team 4+ venue games; others are skipped and counted.
No parameter is fitted: K=4, the minimums and the Poisson form were fixed before this test, so there is no
training/validation split to report. Benchmark: the league's running home/draw/away shares at that date."""
import json, glob, os, math, sys
sys.path.insert(0,os.path.dirname(__file__)); import labsys as L
LEAGUES=('en.1','en.2','de.1','es.1','it.1','fr.1','nl.1','pt.1')
def ft(m):
    s=m.get('score') if isinstance(m,dict) else None
    if isinstance(s,dict): s=s.get('ft')
    return s if isinstance(s,list) and len(s)==2 and all(isinstance(x,int) for x in s) else None
def run(root):
    def new(): return dict(n=0,hit=0,brier=0.0,logloss=0.0,base_brier=0.0,base_logloss=0.0,p=[0.0,0.0,0.0],y=[0,0,0],picks=[0,0,0])
    tot=new(); per={}; cal={}; skipped=0; files=0
    for f in sorted(glob.glob(os.path.join(root,'20[0-9][0-9]-[0-9][0-9]','*.json'))):
        lg_id=os.path.basename(f)[:-5]
        if lg_id not in LEAGUES: continue
        files+=1; d=json.load(open(f)); ms=d['matches'] if isinstance(d,dict) else d
        ms=sorted([m for m in ms if ft(m) and m.get('date')],key=lambda m:m['date']); H={};A={};lg=[0,0,0];base=[0,0,0]
        for m in ms:
            h,a=m['team1'],m['team2']; g1,g2=ft(m); y=0 if g1>g2 else 1 if g1==g2 else 2; hs=H.get(h,[0,0,0]); aw=A.get(a,[0,0,0])
            r=L.model(dict(lg_home_goals=lg[0],lg_away_goals=lg[1],lg_matches=lg[2],h_games=hs[0],h_gf=hs[1],h_ga=hs[2],a_games=aw[0],a_gf=aw[1],a_ga=aw[2]))
            if r['status']=='ok':
                p=[r['p_home'],r['p_draw'],r['p_away']]; q=[x/sum(base) for x in base]; top=max(range(3),key=lambda i:p[i])
                for T in(tot,per.setdefault(lg_id,new())):
                    T['n']+=1; T['hit']+=top==y; T['brier']+=sum((p[i]-(i==y))**2 for i in range(3)); T['logloss']+=-math.log(max(p[y],1e-9))
                    T['base_brier']+=sum((q[i]-(i==y))**2 for i in range(3)); T['base_logloss']+=-math.log(max(q[y],1e-9)); T['y'][y]+=1; T['picks'][top]+=1
                    for i in range(3): T['p'][i]+=p[i]
                for i,name in enumerate(('home','draw','away')):
                    b=cal.setdefault(name,{}).setdefault(min(int(p[i]*10)*10,80),[0,0,0.0]); b[0]+=1; b[1]+=y==i; b[2]+=p[i]
            else: skipped+=1
            H.setdefault(h,[0,0,0]); A.setdefault(a,[0,0,0]); H[h][0]+=1;H[h][1]+=g1;H[h][2]+=g2; A[a][0]+=1;A[a][1]+=g2;A[a][2]+=g1; lg[0]+=g1;lg[1]+=g2;lg[2]+=1; base[y]+=1
    def fin(T): n=T['n']; return dict(matches=n,accuracy=round(T['hit']/n,4),brier=round(T['brier']/n,4),logloss=round(T['logloss']/n,4),base_brier=round(T['base_brier']/n,4),base_logloss=round(T['base_logloss']/n,4),
        predicted_share=[round(x/n,4) for x in T['p']],actual_share=[round(x/n,4) for x in T['y']],picks_home_draw_away=T['picks'])
    return dict(engine=L.ENGINE_VERSION,source='openfootball/football.json',season_files=files,skipped_matches_insufficient_data=skipped,overall=fin(tot),by_league={k:fin(v) for k,v in sorted(per.items())},
        calibration={o:{f'{k}-{k+10}%':dict(n=v[0],mean_predicted=round(v[2]/v[0],4),actual=round(v[1]/v[0],4)) for k,v in sorted(b.items())} for o,b in cal.items()})
if __name__=='__main__':
    out=run(sys.argv[1]); json.dump(out,open(os.path.join(os.path.dirname(__file__),'backtest_gc11.json'),'w'),indent=1)
    o=out['overall']; print(out['season_files'],'files |',o['matches'],'rated |',out['skipped_matches_insufficient_data'],'skipped'); print(o)
    for k,v in out['calibration'].items(): print(k,{b:(x['n'],x['mean_predicted'],x['actual']) for b,x in v.items()})
