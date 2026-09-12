import os, math, datetime, requests
from flask import Flask, jsonify, request, send_from_directory
try:
    from flask_cors import CORS
except Exception:
    CORS=lambda app: None
app=Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)
TOKEN=os.getenv('API_FOOTBALL_KEY') or os.getenv('SPORTMONKS_TOKEN','')
API='https://v3.football.api-sports.io'

def api(path):
    r=requests.get(API+'/'+path,headers={'x-apisports-key':TOKEN},timeout=20); r.raise_for_status(); return r.json()
@app.get('/api/status')
def status(): return jsonify(ok=True,service='JMK Prediction Foot',tokenConfigured=bool(TOKEN),version='1.0.0')
@app.get('/api/fixtures')
def fixtures():
    date=request.args.get('date') or datetime.date.today().isoformat()
    if not TOKEN: return jsonify(ok=False,erreur='API_FOOTBALL_KEY non configurée.'),503
    try:
        j=api(f'fixtures?date={date}&timezone=Europe/Paris'); out=[]
        for m in j.get('response',[]):
            f=m['fixture']; out.append({'fixture_id':f['id'],'date_utc':f.get('date'),'horaire':(f.get('date') or '')[11:16],'pays':m.get('league',{}).get('country'),'championnat':m.get('league',{}).get('name'),'statut':m.get('fixture',{}).get('status',{}).get('long'),'code_statut':m.get('fixture',{}).get('status',{}).get('short'),'domicile':m['teams']['home'],'exterieur':m['teams']['away']})
        return jsonify(ok=True,date=date,total=len(out),matches=out)
    except Exception as e:return jsonify(ok=False,erreur=str(e)),502

def pois(k,l): return math.exp(-l)*l**k/math.factorial(k)
@app.get('/api/analyze')
def analyze():
    fid=request.args.get('fixture','')
    if not fid.isdigit(): return jsonify(ok=False,erreur='Identifiant de match invalide.'),400
    if not TOKEN:return jsonify(ok=False,erreur='API_FOOTBALL_KEY non configurée.'),503
    try:
        m=api(f'fixtures?id={fid}').get('response',[None])[0]
        if not m:return jsonify(ok=False,erreur='Match introuvable.'),404
        home,away=m['teams']['home'],m['teams']['away']; lid=m['league']['id']; season=m['league']['season']
        # Baseline from season standings; no invented detailed statistics.
        st=api(f'standings?league={lid}&season={season}').get('response',[{}])[0].get('league',{}).get('standings',[])
        rows=sum(st,[]) if st else []
        def row(tid): return next((x for x in rows if x.get('team',{}).get('id')==tid),{})
        rh,ra=row(home['id']),row(away['id'])
        def avg(r):
            a=r.get('all',{}); p=a.get('played') or 0; return ((a.get('goals',{}) or {}).get('for',0)/p if p else 1.2)
        lh=max(.15,(avg(rh)+((ra.get('goals',{}) or {}).get('against',0)/(ra.get('all',{}).get('played') or 1)))/2)
        la=max(.15,(avg(ra)+((rh.get('goals',{}) or {}).get('against',0)/(rh.get('all',{}).get('played') or 1)))/2)
        p1=px=p2=0; scores=[]
        for h in range(8):
            for a in range(8):
                p=pois(h,lh)*pois(a,la); scores.append((p,h,a));
                if h>a:p1+=p
                elif h==a:px+=p
                else:p2+=p
        scores.sort(reverse=True); total=p1+px+p2
        return jsonify(ok=True,fixture_id=int(fid),match={'domicile':home['name'],'exterieur':away['name']},prediction=f'{home["name"]} / Nul / {away["name"]}',**{'1x2':{'domicile':round(p1/total*100,1),'nul':round(px/total*100,1),'exterieur':round(p2/total*100,1)},'exact_scores':[f'{h}-{a} ({p*100:.1f}%)' for p,h,a in scores[:5]],'classement':{'domicile':rh.get('rank'),'exterieur':ra.get('rank')},'forme':{'domicile':rh.get('form'),'exterieur':ra.get('form')},'btts':None,'over_1_5':None,'over_2_5':None,'over_3_5':None})
    except Exception as e:return jsonify(ok=False,erreur=str(e)),502
@app.get('/')
def home(): return send_from_directory('../frontend','index.html')
