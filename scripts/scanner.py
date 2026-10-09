#!/usr/bin/env python3
import json, os, re, time, math, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

import feedparser
import requests
import yfinance as yf

ROOT=Path(__file__).resolve().parents[1]
WATCH=json.loads((ROOT/'config/watchlist.json').read_text())
DISCOVERY=json.loads((ROOT/'config/discovery.json').read_text())
UNIVERSE=WATCH+[{**d,'satispay_status':'check'} for d in DISCOVERY]
OUT=ROOT/'data/latest.json'
UA={'User-Agent':'CatalystRadar/1.0 contact: github-actions'}

MAX_NEWS_AGE_HOURS=6

POSITIVE={
 'fda_approval':(['fda approves','fda approval','approved by the fda','ema recommends approval','chmp positive'],98,8.0),
 'trial_success':(['met primary endpoint','positive phase 3','positive phase iii','topline results','trial met','statistically significant'],92,7.0),
 'ma':(['to acquire','acquisition','merger agreement','buyout','takeover','strategic acquisition'],90,6.0),
 'large_contract':(['awarded contract','wins contract','multi-year contract','supply agreement','large order','purchase agreement'],86,5.0),
 'guidance_raise':(['raises guidance','raised guidance','raises outlook','boosts forecast','increases guidance'],84,4.5),
 'earnings_beat':(['beats estimates','beats expectations','earnings beat','revenue beat','profit beat'],78,3.5),
 'partnership':(['strategic partnership','partnership with','collaboration with','joint venture'],74,3.2),
 'analyst_upgrade':(['upgraded to buy','upgrade to buy','price target raised','initiated with buy'],60,2.2),
 'buyback':(['share repurchase','stock buyback','buyback authorization'],68,2.8),
}

# Rimuove titoli non operativi: un articolo nuovo puo descrivere un evento vecchio.
# Questo filtro e volutamente conservativo e non garantisce la data dell'evento.
NON_ACTIONABLE_PATTERNS=[
    r'\b(?:sponsorship|sponsors?|sponsored|philanthrop\w*|charity|donation|donates?|scholarship)\b',
    r'\b(?:previously announced|last (?:week|month|year)|a look back|news recap|explainer|explained)\b',
    r'\b(?:should you buy|stock prediction|price prediction|what investors need to know)\b',
    r'\b(?:community event|volunteer program|opinion|editorial)\b',
]

NEGATIVE=[
 'offering','secondary offering','dilution','downgrade','cuts guidance',
 'lowered guidance','misses estimates','trial failed',
 'failed primary endpoint','investigation','subpoena','recall',
 'bankruptcy','chapter 11'
]

SOURCE_QUALITY={
 'Reuters':95,
 'Bloomberg':93,
 'Associated Press':90,
 'SEC':100,
 'FDA':100,
 'EMA':100,
 'Business Wire':88,
 'GlobeNewswire':85,
 'PR Newswire':84,
 'CNBC':82,
 'MarketWatch':78,
 'Yahoo Finance':75,
 'TheStreet':65
}

def now():
    return datetime.now(timezone.utc)

def clamp(x,a=0,b=100):
    return max(a,min(b,x))

def safe_float(x):
    try:
        if x is None or (isinstance(x,float) and math.isnan(x)):
            return None
        return float(x)
    except:
        return None

def pct(a,b):
    if a is None or b in (None,0):
        return None
    return (a/b-1)*100

def load_market(tickers):
    data={}
    unique=list(dict.fromkeys(tickers))

    try:
        daily=yf.download(
            unique,
            period='10d',
            interval='1d',
            group_by='ticker',
            auto_adjust=False,
            progress=False,
            threads=True
        )
    except Exception as e:
        print('daily market download error',e)
        daily=None

    try:
        intra=yf.download(
            unique,
            period='2d',
            interval='5m',
            group_by='ticker',
            auto_adjust=False,
            prepost=True,
            progress=False,
            threads=True
        )
    except Exception as e:
        print('intraday market download error',e)
        intra=None

    for t in unique:
        d={}

        try:
            if daily is not None:
                df=daily[t] if len(unique)>1 and t in daily.columns.get_level_values(0) else daily
                df=df.dropna(how='all')

                if len(df):
                    close=safe_float(df['Close'].iloc[-1])
                    prev=safe_float(df['Close'].iloc[-2]) if len(df)>1 else None
                    vol=safe_float(df['Volume'].iloc[-1])
                    avg=safe_float(df['Volume'].iloc[-6:-1].mean()) if len(df)>2 else None

                    d.update(
                        price=close,
                        previous_close=prev,
                        current_change_pct=pct(close,prev),
                        volume=vol,
                        relative_volume=(vol/avg if vol and avg else None)
                    )

        except Exception as e:
            print('daily parse',t,e)

        try:
            if intra is not None:
                df=intra[t] if len(unique)>1 and t in intra.columns.get_level_values(0) else intra
                df=df.dropna(how='all')

                if len(df):
                    last=safe_float(df['Close'].iloc[-1])
                    hour=safe_float(df['Close'].iloc[-13]) if len(df)>=13 else safe_float(df['Close'].iloc[0])

                    d['last_price']=last
                    d['short_term_change_pct']=pct(last,hour)

        except Exception as e:
            print('intra parse',t,e)

        data[t]=d

    return data

def google_news(query,max_items=20):
    url='https://news.google.com/rss/search?q='+quote_plus(query)+'&hl=en-US&gl=US&ceid=US:en'

    feed=feedparser.parse(url)

    out=[]

    for e in feed.entries[:max_items]:
        published=None

        try:
            published=datetime(
                *e.published_parsed[:6],
                tzinfo=timezone.utc
            )
        except:
            pass

        src=''

        if getattr(e,'source',None):
            src=getattr(e.source,'title','') or ''

        out.append({
            'title':getattr(e,'title',''),
            'url':getattr(e,'link',''),
            'published':published,
            'source':src
        })

    return out

def classify_headline(title):
    low=title.lower()

    if any(re.search(p, low) for p in NON_ACTIONABLE_PATTERNS):
        return None

    if any(k in low for k in NEGATIVE):
        return None

    best=None

    for typ,(keys,strength,impact) in POSITIVE.items():
        if any(k in low for k in keys):
            if best is None or strength>best[1]:
                best=(typ,strength,impact)

    return best

def source_score(source,title=''):
    src=(source or '').lower()

    for k,v in SOURCE_QUALITY.items():
        if k.lower() in src:
            return v

    return 68

def match_watch(title):
    found=[]
    low=title.lower()

    for w in UNIVERSE:
        aliases=w.get('aliases') or [w['company'],w['ticker']]

        if any(
            re.search(
                r'(?<![A-Za-z0-9])'
                +re.escape(a.lower())
                +r'(?![A-Za-z0-9])',
                low
            )
            for a in aliases
            if len(a)>2
        ):
            found.append(w)

    return found

def freshness_score(dt):
    if not dt:
        return 0,9999,'time n/a'

    mins=max(
        0,
        (now()-dt).total_seconds()/60
    )

    if mins<=30:
        s=100
    elif mins<=90:
        s=90
    elif mins<=240:
        s=78
    elif mins<=720:
        s=62
    elif mins<=1440:
        s=48
    else:
        s=0

    label=(
        f'{int(mins)} min fa'
        if mins<120
        else f'{int(mins/60)} h fa'
    )

    return s,mins,label

def is_recent(dt,max_hours=MAX_NEWS_AGE_HOURS):
    if dt is None:
        return False

    age=now()-dt

    return timedelta(0) <= age <= timedelta(hours=max_hours)

def macro_snapshot(market):
    def one(sym):
        return market.get(sym,{})

    tnx=one('^TNX')
    wti=one('CL=F')
    brent=one('BZ=F')
    nas=one('^IXIC')
    sox=one('^SOX')
    vix=one('^VIX')
    dxy=one('DX-Y.NYB')

    n=nas.get('current_change_pct') or 0
    s=sox.get('current_change_pct') or 0
    y=tnx.get('current_change_pct') or 0
    oil=wti.get('current_change_pct') or 0
    vv=vix.get('current_change_pct') or 0

    score=50+8*n+8*s-5*y-2*max(oil,0)-2*max(vv,0)
    score=clamp(score)

    bias=(
        'strong_positive' if score>=72
        else 'positive' if score>=58
        else 'strong_negative' if score<=28
        else 'negative' if score<=42
        else 'neutral'
    )

    summary=(
        f"Tech bias {bias.replace('_',' ')}. "
        f"Nasdaq {n:+.2f}%, "
        f"SOX {s:+.2f}%, "
        f"US10Y {tnx.get('price') or tnx.get('last_price') or 0:.2f}, "
        f"WTI {oil:+.2f}%."
    )

    return {
        'treasury_10y':tnx.get('price') or tnx.get('last_price'),
        'treasury_10y_change_bp':
            (tnx.get('current_change_pct') or 0)
            *(tnx.get('previous_close') or 0),

        'wti':wti.get('price') or wti.get('last_price'),
        'wti_change_pct':wti.get('current_change_pct'),

        'brent':brent.get('price') or brent.get('last_price'),
        'brent_change_pct':brent.get('current_change_pct'),

        'nasdaq_level':nas.get('price') or nas.get('last_price'),
        'nasdaq_change_pct':nas.get('current_change_pct'),

        'sox_level':sox.get('price') or sox.get('last_price'),
        'sox_change_pct':sox.get('current_change_pct'),

        'vix':vix.get('price') or vix.get('last_price'),
        'vix_change_pct':vix.get('current_change_pct'),

        'dollar_index':dxy.get('price') or dxy.get('last_price'),

        'macro_score':round(score,1),
        'tech_bias':bias,
        'summary':summary
    }

def sec_filings(max_age_hours=24):
    out=[]

    try:
        tickers=requests.get(
            'https://www.sec.gov/files/company_tickers.json',
            headers=UA,
            timeout=20
        ).json()

        mapc={
            v['ticker'].upper():int(v['cik_str'])
            for v in tickers.values()
        }

    except Exception as e:
        print('sec ticker map error',e)
        return out

    cutoff=now()-timedelta(hours=max_age_hours)

    for w in WATCH:
        t=w['ticker']
        cik=mapc.get(t)

        if not cik:
            continue

        try:
            j=requests.get(
                f'https://data.sec.gov/submissions/CIK{cik:010d}.json',
                headers=UA,
                timeout=20
            ).json()

            r=j.get('filings',{}).get('recent',{})

            for i,form in enumerate(r.get('form',[])[:20]):
                if form not in ('8-K','6-K','10-Q','10-K','20-F'):
                    continue

                d=datetime.fromisoformat(
                    r['filingDate'][i]+'T12:00:00+00:00'
                )

                if d<cutoff:
                    continue

                acc=r['accessionNumber'][i].replace('-','')
                primary=r['primaryDocument'][i]

                url=(
                    f'https://www.sec.gov/Archives/edgar/data/'
                    f'{cik}/{acc}/{primary}'
                )

                out.append({
                    'ticker':t,
                    'company':w['company'],
                    'title':f'{w["company"]} filed {form} with the SEC',
                    'url':url,
                    'published':d,
                    'source':'SEC',
                    'form':form
                })

            time.sleep(.12)

        except Exception as e:
            print('sec',t,e)

    return out

def build_candidates(market,macro):
    items=[]

    groups=[UNIVERSE[i:i+6] for i in range(0,len(UNIVERSE),6)]
    # Ricerca mirata aggiuntiva per i titoli critici, senza abbandonare
    # la scansione estesa di tutti i settori.
    groups += [[w] for w in WATCH if w.get('priority')=='critical']

    for group in groups:

        names=' OR '.join(
            '"'+w['company']+'"'
            for w in group
        )

        q=(
            f'({names}) '
            '(contract OR partnership OR acquisition OR merger '
            'OR FDA OR trial OR guidance OR earnings '
            'OR order OR approval) when:1d'
        )

        try:
            news=google_news(q,35)

        except Exception as e:
            print('news',e)
            continue

        for n in news:

            if not is_recent(n['published']):
                continue

            cl=classify_headline(n['title'])

            if not cl:
                continue

            matches=match_watch(n['title'])

            for w in matches:
                typ,strength,impact=cl

                fresh,mins,label=freshness_score(
                    n['published']
                )

                m=market.get(
                    w['ticker'],
                    {}
                )

                srcq=source_score(
                    n['source'],
                    n['title']
                )

                rv=m.get('relative_volume') or 1

                vol_score=clamp(
                    45
                    +25*math.log(
                        max(rv,.25),
                        2
                    )
                )

                mom=m.get('short_term_change_pct') or 0

                mom_score=clamp(
                    50+12*mom
                )

                move=m.get('current_change_pct') or 0

                extension=(
                    max(
                        0,
                        (move-5)*4
                    )
                    if move>5
                    else 0
                )

                macro_score=(
                    macro['macro_score']
                    if re.search(
                        'tech|semi|ai|cloud|software|cyber',
                        w['category'],
                        re.I
                    )
                    else 50
                )

                conf=clamp(
                    .20*srcq
                    +.30*strength
                    +.15*fresh
                    +.15*vol_score
                    +.10*mom_score
                    +.10*macro_score
                    -extension
                )

                est=min(
                    7.5,
                    max(
                        .5,
                        impact*(conf/100)
                        -max(0,move)*.20
                    )
                )

                if conf<48:
                    continue

                items.append({
                    'id':hashlib.sha1(
                        (w['ticker']+n['title']).encode()
                    ).hexdigest()[:12],

                    'ticker':w['ticker'],
                    'company':w['company'],
                    'category':w['category'],
                    'priority':w.get('priority','normal'),
                    'satispay_status':w.get('satispay_status','check'),

                    'headline':n['title'],

                    'reason':
                        f"Possibile evento {typ.replace('_',' ')} indicizzato da Google News. "
                        "La data e quella della pubblicazione: verificare fonte primaria "
                        "e data dell'evento prima di considerarlo un catalyst nuovo.",

                    'source':n['source'] or 'Google News',
                    'url':n['url'],
                    'published_at':n['published'].isoformat(),
                    'age_label':label,

                    'catalyst_type':typ,
                    'current_change_pct':round(move,2),
                    'short_term_change_pct':round(mom,2),
                    'relative_volume':round(rv,2),

                    'estimated_impact_pct':round(est,1),
                    'confidence_score':round(conf,0),

                    # Fonte autorevole NON significa evento verificato:
                    # il motore ha letto un indice RSS, non il documento primario.
                    'source_verified':False,
                    'verification_status':'RSS_INDICIZZATO_DA_VERIFICARE',
                    'headline_published_at':n['published'].isoformat(),
                    'event_occurred_at':None,

                    'tradingview_symbol':w['ticker'],

                    'risk_flags':(
                        'Titolo già esteso: attenzione a inseguire il movimento.'
                        if move>8
                        else
                        'Segnale da confermare con prezzo e volumi in tempo reale.'
                    ),

                    'factors':{
                        'source_quality':round(srcq),
                        'catalyst_strength':round(strength),
                        'freshness':round(fresh),
                        'volume':round(vol_score),
                        'momentum':round(mom_score),
                        'macro':round(macro_score),
                        'extension_penalty':round(extension)
                    }
                })

    for f in sec_filings():
        w=next(
            (
                x
                for x in WATCH
                if x['ticker']==f['ticker']
            ),
            None
        )

        if not w:
            continue

        fresh,mins,label=freshness_score(
            f['published']
        )

        m=market.get(
            w['ticker'],
            {}
        )

        move=m.get('current_change_pct') or 0
        mom=m.get('short_term_change_pct') or 0
        rv=m.get('relative_volume') or 1

        strength=(
            58
            if f['form'] in ('8-K','6-K')
            else 48
        )

        srcq=100

        vol_score=clamp(
            45
            +25*math.log(
                max(rv,.25),
                2
            )
        )

        mom_score=clamp(
            50+12*mom
        )

        macro_score=macro['macro_score']

        extension=(
            max(
                0,
                (move-5)*4
            )
            if move>5
            else 0
        )

        conf=clamp(
            .20*srcq
            +.30*strength
            +.15*fresh
            +.15*vol_score
            +.10*mom_score
            +.10*macro_score
            -extension
        )

        items.append({
            'id':hashlib.sha1(
                (
                    w['ticker']
                    +f['title']
                    +f['url']
                ).encode()
            ).hexdigest()[:12],

            'ticker':w['ticker'],
            'company':w['company'],
            'category':w['category'],
            'priority':w.get('priority','normal'),
            'satispay_status':w.get('satispay_status','check'),

            'headline':f['title'],

            'reason':
                'Documento SEC ufficiale rilevato. Il modulo e la data di deposito '
                'non permettono di stabilire se sia un catalyst positivo: '
                'leggere il contenuto prima di operare.',

            'source':'SEC',
            'url':f['url'],
            'published_at':f['published'].isoformat(),
            'age_label':label,

            'catalyst_type':'SEC filing',

            'current_change_pct':round(move,2),
            'short_term_change_pct':round(mom,2),
            'relative_volume':round(rv,2),

            # Filing generici non sono segnali long: nessun rialzo stimato.
            'estimated_impact_pct':0.0,

            'confidence_score':min(45,round(conf,0)),
            'verification_status':'SEC_DOCUMENTO_UFFICIALE_EVENTO_NON_CLASSIFICATO',

            'source_verified':True,

            'tradingview_symbol':w['ticker'],

            'risk_flags':
                'Leggere il filing: un 8-K/6-K può '
                'contenere notizie positive o negative.',

            'factors':{
                'source_quality':100,
                'catalyst_strength':strength,
                'freshness':round(fresh),
                'volume':round(vol_score),
                'momentum':round(mom_score),
                'macro':round(macro_score),
                'extension_penalty':round(extension)
            }
        })

    ded={}

    for x in items:
        key=(
            x['ticker'],
            re.sub(
                r'\s+',
                ' ',
                x['headline'].lower()
            )
        )

        if (
            key not in ded
            or x['confidence_score']
            >ded[key]['confidence_score']
        ):
            ded[key]=x

    out=sorted(
        ded.values(),
        key=lambda x:(
            x['confidence_score'],
            x['priority']=='critical'
        ),
        reverse=True
    )

    return out[:30]

def notify_if_needed(catalysts):
    topic=os.getenv(
        'NTFY_TOPIC',
        ''
    ).strip()

    if not topic:
        return

    strong=[
        x
        for x in catalysts
        if x['confidence_score']>=80
        and (x.get('current_change_pct') or 0)<10
        and (x.get('short_term_change_pct') or 0)>=1.5
    ]

    if not strong:
        return

    x=strong[0]

    try:
        requests.post(
            'https://ntfy.sh/'+topic,

            data=(
                f"{x['ticker']} — "
                f"{x['headline']} | "
                f"confidence {x['confidence_score']:.0f}% | "
                f"move {x['current_change_pct']:+.2f}%"
            ).encode(),

            headers={
                'Title':'Catalyst Radar',
                'Priority':'high',
                'Tags':'chart_with_upwards_trend'
            },

            timeout=15
        )

    except Exception as e:
        print('ntfy',e)

def geopolitical_snapshot():
    try:
        rows=google_news(
            '(Iran OR "Strait of Hormuz" OR ceasefire OR shipping) '
            '(oil OR tanker OR sanctions OR conflict) when:1d',
            8
        )

    except Exception as e:
        print('geopolitics',e)
        rows=[]

    risk=35

    escal=[
        'attack',
        'strike',
        'closed',
        'closure',
        'blockade',
        'seized',
        'war',
        'missile',
        'sanction'
    ]

    ease=[
        'ceasefire',
        'talks',
        'negotiation',
        'deal',
        'reopen',
        'de-escalation',
        'mediation'
    ]

    headlines=[]
    # Evita articoli didattici e analisi storiche come breaking news.
    reliable=('reuters','associated press','bloomberg','cnbc','bbc',
              'financial times','wall street journal','ap news','axios')
    live_verbs=('attack','strike','hit','closed','closure','blockade',
                'seized','missile','sanction','ceasefire','talks','negotiat',
                'reopen','deploy','target','warn','threat')

    for r in rows:
        if len(headlines)>=5:
            break
        if not any(s in (r.get('source') or '').lower() for s in reliable):
            continue
        if not any(v in r['title'].lower() for v in live_verbs):
            continue

        if not is_recent(r['published']):
            continue

        t=r['title']
        low=t.lower()

        risk += (
            9*sum(k in low for k in escal)
            -7*sum(k in low for k in ease)
        )

        headlines.append({
            'title':t,
            'source':r.get('source',''),
            'url':r.get('url','')
        })

    return {
        'risk_score':round(clamp(risk),0),
        'headlines':headlines
    }

def main():
    all_tickers=[
        w['ticker']
        for w in UNIVERSE
    ]+[
        '^TNX',
        'CL=F',
        'BZ=F',
        '^IXIC',
        '^SOX',
        '^VIX',
        'DX-Y.NYB'
    ]

    market=load_market(all_tickers)

    macro=macro_snapshot(market)

    geo=geopolitical_snapshot()

    macro['geopolitical_risk_score']=geo['risk_score']
    macro['geopolitical_headlines']=geo['headlines']

    if geo['headlines']:
        macro['summary'] += (
            ' Geopolitica: '
            +geo['headlines'][0]['title']
        )

    catalysts=build_candidates(
        market,
        macro
    )

    sources=[
        {
            'name':'SEC EDGAR',
            'note':'Filings societari ufficiali USA: 8-K, 6-K, 10-Q, 10-K, 20-F.',
            'limited':False
        },
        {
            'name':'FDA / EMA',
            'note':'Catalyst biotech/regolatori tramite fonti ufficiali e indicizzazione news.',
            'limited':False
        },
        {
            'name':'Google News RSS',
            'note':'Discovery gratuita di Reuters, media finanziari, IR e comunicati quando indicizzati.',
            'limited':False
        },
        {
            'name':'Reuters',
            'note':'Non è incluso un feed Reuters completo/licenziato; headline Reuters solo quando pubblicamente indicizzati.',
            'limited':True
        },
        {
            'name':'Yahoo Finance / yfinance',
            'note':'Prezzi/volumi/pre-post market quando disponibili; feed non ufficiale, possibile ritardo.',
            'limited':True
        },
        {
            'name':'TradingView',
            'note':'Grafico incorporato nell’app per verifica manuale del titolo trovato.',
            'limited':False
        }
    ]

    result={
        'generated_at':now().isoformat(),
        'status':'ok',
        'macro':macro,
        'catalysts':catalysts,
        'watchlist':WATCH,
        'sources':sources
    }

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUT.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding='utf-8'
    )

    notify_if_needed(catalysts)

    print(
        f'wrote {OUT} '
        f'with {len(catalysts)} catalysts'
    )

if __name__=='__main__':
    main()
