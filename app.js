const state={data:null,filter:"all",scanEnd:null,scanTimer:null,refreshTimer:null,deferredInstall:null};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const fmt=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
const signed=v=>Number.isFinite(Number(v))?((Number(v)>0?"+":"")+Number(v).toFixed(2)+"%"):"—";
const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
const toast=m=>{const e=$("#toast");e.textContent=m;e.classList.add("show");setTimeout(()=>e.classList.remove("show"),2500)};

async function loadData(manual=false){
  try{
    const r=await fetch("./data/latest.json?t="+Date.now(),{cache:"no-store"});
    if(!r.ok) throw new Error("HTTP "+r.status);
    const data=await r.json(), previous=state.data;
    state.data=data; render();
    if(manual) toast("Dati aggiornati");
    if(previous&&state.scanEnd) detectNewSignals(previous,data);
  }catch(e){console.error(e);$("#lastUpdate").textContent="Dati non disponibili";if(manual)toast("Aggiornamento non riuscito")}
}
function detectNewSignals(prev,next){
  const old=new Set((prev.catalysts||[]).map(x=>x.id||x.ticker+"|"+x.headline));
  const fresh=(next.catalysts||[]).filter(x=>!old.has(x.id||x.ticker+"|"+x.headline)&&Number(x.confidence_score||0)>=70);
  if(fresh.length){const top=fresh[0];notify("Catalyst Radar",`${top.ticker}: nuovo catalyst forte — confidence ${Math.round(top.confidence_score)}%`)}
}
function notify(title,body){if("Notification" in window&&Notification.permission==="granted")new Notification(title,{body,icon:"./assets/icon-192.png"});toast(body)}
function render(){if(!state.data)return;renderHeader();renderMacro();renderCatalysts();renderWatchlist();renderSources()}
function renderHeader(){
  const d=state.data,ts=d.generated_at?new Date(d.generated_at):null;
  $("#lastUpdate").textContent=ts?"Agg. "+ts.toLocaleString("it-IT",{hour:"2-digit",minute:"2-digit",day:"2-digit",month:"2-digit"}):"Aggiornamento —";
  const ny=new Date().toLocaleString("en-US",{timeZone:"America/New_York"}),nd=new Date(ny),h=nd.getHours(),day=nd.getDay(),mins=nd.getMinutes();
  const open=day>=1&&day<=5&&((h>9&&h<16)||(h===9&&mins>=30));
  const b=$("#marketBadge");b.textContent=open?"US MARKET OPEN":"US MARKET CLOSED";b.className="badge "+(open?"positive":"neutral");
}
function renderMacro(){
  const m=state.data.macro||{};
  const cards=[["US 10Y",m.treasury_10y,m.treasury_10y_change_bp,"%"," bp"],["WTI",m.wti,m.wti_change_pct,"$","%"],["Brent",m.brent,m.brent_change_pct,"$","%"],["Nasdaq",m.nasdaq_level,m.nasdaq_change_pct,"","%"],["SOX",m.sox_level,m.sox_change_pct,"","%"],["VIX",m.vix,m.vix_change_pct,"","%"]];
  $("#macroGrid").innerHTML=cards.map(([n,v,c,p,s])=>`<div class="macro-card"><small>${n}</small><strong>${p}${fmt(v,2)}</strong><span class="${Number(c)>0?"pos":Number(c)<0?"neg":"flat"}">${Number.isFinite(Number(c))?(Number(c)>0?"+":"")+fmt(c,2)+s:"—"}</span></div>`).join("");
  const bias=(m.tech_bias||"neutral").replaceAll("_"," ").toUpperCase(),el=$("#macroBias");el.textContent=bias;el.className="badge "+(bias.includes("POSITIVE")?"positive":bias.includes("NEGATIVE")?"negative":"neutral");
  $("#macroSummary").textContent=m.summary||"Quadro macro in aggiornamento.";
}
function renderCatalysts(){
  const list=(state.data.catalysts||[]).filter(x=>{if(state.filter==="all")return true;if(state.filter==="critical")return x.priority==="critical"||Number(x.confidence_score)>=75;if(state.filter==="tech")return /tech|semi|ai|cloud|software|cyber/i.test(x.category||"");if(state.filter==="biotech")return /bio|pharma|health/i.test(x.category||"")});
  $("#emptyState").classList.toggle("hidden",list.length>0);
  $("#catalystList").innerHTML=list.map(c=>{const move=Number(c.current_change_pct),conf=Math.round(Number(c.confidence_score||0)),impact=Number(c.estimated_impact_pct||0);return `<article class="catalyst"><div class="ticker"><div class="ticker-bubble">${esc(c.ticker)}</div><div><h4>${esc(c.ticker)}</h4><small>${esc(c.company||"")}</small></div></div><div><div class="headline">${esc(c.headline||c.reason||"Catalyst rilevato")}</div><div class="reason">${esc(c.reason||"")}</div><div class="meta"><span class="chip">${esc(c.catalyst_type||"News")}</span><span class="chip">${esc(c.source||"source")}</span><span class="chip">${esc(c.age_label||"")}</span><span class="chip">${c.verification_status==="SEC_DOCUMENTO_UFFICIALE_EVENTO_NON_CLASSIFICATO"?"SEC: evento non valutato":c.source_verified?"✓ fonte ufficiale":"RSS: evento da verificare"}</span>${c.satispay_status==="unavailable"?'<span class="chip">non su Satispay</span>':""}</div></div><div class="scores"><div class="score"><span>MOVIMENTO</span><strong class="${move>0?"pos":move<0?"neg":"flat"}">${signed(move)}</strong></div><div class="score"><span>IMPATTO STIMATO</span><strong>${impact>0?"+":""}${fmt(impact,1)}%</strong></div><div class="score full"><span>CONFIDENCE SCORE</span><strong>${conf}%</strong><div class="bar"><i style="--w:${Math.min(100,conf)}%"></i></div></div></div><div class="catalyst-actions"><button class="mini-btn" onclick='showChart(${JSON.stringify(c.tradingview_symbol||c.ticker)},${JSON.stringify(c.ticker)})'>Grafico</button>${c.url?`<a class="mini-btn" href="${esc(c.url)}" target="_blank" rel="noopener" style="text-decoration:none">Fonte ↗</a>`:""}<button class="mini-btn" onclick='showWhy(${JSON.stringify(c.ticker)})'>Perché?</button></div></article>`}).join("");
}
window.showWhy=ticker=>{const c=(state.data?.catalysts||[]).find(x=>x.ticker===ticker);if(!c)return;const f=c.factors||{};alert(`${ticker} — scoring\n\nFonte: ${f.source_quality??"—"}/100\nCatalyst: ${f.catalyst_strength??"—"}/100\nFreschezza: ${f.freshness??"—"}/100\nVolumi: ${f.volume??"—"}/100\nMomentum: ${f.momentum??"—"}/100\nMacro: ${f.macro??"—"}/100\nPenalità estensione: ${f.extension_penalty??0}\n\n${c.risk_flags||""}`)};
const CHART_NYSE=new Set(["OXY","PFE","NKE","DELL","ORCL","TSM","SHEL","MT","E","BABA","NVO","SAP","STM","SE","RDDT","HIMS","UBER","NET","PLTR"]);
const CHART_NASDAQ=new Set(["AMD","INTC","NBIS","GOOGL","GOOG","NVDA","QCOM","MRNA","MU","META","AVGO","ASML","SMCI","MSFT","AMZN","ENPH","CRWD","CRWV","LULU","PLUG","APP","ARM","CRDO","RKLB","SOFI","COIN","MSTR","MARA","TSLA","SHOP","SNOW","DDOG","CELH","BIDU","JD","PDD","MELI"]);
const chartState={sequence:0,symbol:null,ticker:null,timeout:null,observer:null};
function chartSymbol(raw){
  const symbol=String(raw||"").trim().toUpperCase();
  if(!/^[A-Z0-9._:-]{1,35}$/.test(symbol))return null;
  if(symbol.includes(":"))return symbol;
  if(CHART_NYSE.has(symbol))return "NYSE:"+symbol;
  if(CHART_NASDAQ.has(symbol))return "NASDAQ:"+symbol;
  return symbol; // Non assegnare NASDAQ a un titolo sconosciuto.
}
function chartFail(requestId){
  if(requestId!==chartState.sequence)return;
  clearTimeout(chartState.timeout);
  if(chartState.observer)chartState.observer.disconnect();
  $("#chartStatus").textContent="TradingView non ha risposto. Riprova oppure apri il grafico su TradingView.";
  $("#tvChart").innerHTML='<div class="chart-placeholder">Impossibile caricare il grafico incorporato. Usa «Ricarica grafico» o «Apri TradingView».</div>';
}
window.showChart=(symbol,ticker)=>{
  const normalized=chartSymbol(symbol);
  if(!normalized){toast("Simbolo grafico non valido");return}
  chartState.sequence+=1;
  const requestId=chartState.sequence;
  chartState.symbol=symbol;
  chartState.ticker=ticker||symbol;
  clearTimeout(chartState.timeout);
  if(chartState.observer)chartState.observer.disconnect();
  $("#chartTitle").textContent=chartState.ticker+" — TradingView";
  $("#openTradingView").href="https://www.tradingview.com/chart/?symbol="+encodeURIComponent(normalized);
  $("#retryChartBtn").classList.remove("hidden");
  $("#chartStatus").textContent="Caricamento grafico "+normalized+"…";
  const holder=$("#tvChart");
  holder.innerHTML='<div class="tradingview-widget-container" style="height:100%;width:100%"><div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div></div>';
  const container=holder.firstElementChild;
  // Ogni selezione è indipendente: ignora errori tardivi del grafico precedente.
  chartState.observer=new MutationObserver(()=>{
    if(requestId!==chartState.sequence)return;
    if(container.querySelector("iframe")){
      clearTimeout(chartState.timeout);
      chartState.observer.disconnect();
      $("#chartStatus").textContent="Widget aperto. Se il grafico mostra un errore, usa Ricarica o Apri TradingView.";
    }
  });
  chartState.observer.observe(container,{childList:true,subtree:true});
  const script=document.createElement("script");
  script.type="text/javascript";
  script.src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
  script.async=true;
  script.textContent=JSON.stringify({
    autosize:true,symbol:normalized,interval:"5",timezone:"exchange",
    theme:"dark",style:"1",locale:"it",allow_symbol_change:true,
    calendar:false,support_host:"https://www.tradingview.com"
  });
  script.addEventListener("error",()=>chartFail(requestId));
  chartState.timeout=setTimeout(()=>{
    if(!container.querySelector("iframe"))chartFail(requestId);
  },18000);
  container.appendChild(script);
  holder.scrollIntoView({behavior:"smooth",block:"center"});
};
$("#retryChartBtn").addEventListener("click",()=>{
  if(chartState.symbol)window.showChart(chartState.symbol,chartState.ticker);
});
function renderWatchlist(){$("#watchlist").innerHTML=(state.data.watchlist||[]).map(w=>`<span class="watch-chip ${esc(w.priority||"")} ${w.satispay_status==="unavailable"?"unavailable":""}" title="${esc(w.company||"")}">${esc(w.ticker)}</span>`).join("")}
function renderSources(){$("#sources").innerHTML=(state.data.sources||[]).map(s=>`<div class="source"><div class="source-state"><strong>${esc(s.name)}</strong><span class="dot ${s.limited?"limited":""}"></span></div><p>${esc(s.note||s.coverage||"")}</p></div>`).join("")}
function startScan(){if(state.scanEnd){stopScan();return}state.scanEnd=Date.now()+25*60*1000;$("#scanBtn").textContent="■ Ferma monitor";$("#timerState").textContent="SCANNING";if("Notification" in window&&Notification.permission==="default")Notification.requestPermission();tick();state.scanTimer=setInterval(tick,1000);loadData(true);state.refreshTimer=setInterval(()=>loadData(false),60*1000);toast("Monitor da 25 minuti avviato")}
function stopScan(done=false){state.scanEnd=null;clearInterval(state.scanTimer);clearInterval(state.refreshTimer);state.scanTimer=null;state.refreshTimer=null;$("#scanBtn").textContent="▶ Avvia monitor 25 min";$("#timer").textContent="25:00";$("#timerState").textContent=done?"COMPLETO":"PRONTO";$("#timerRing").style.setProperty("--progress","0%");if(done){loadData(true);notify("Catalyst Radar","Monitor di 25 minuti completato.")}}
function tick(){const left=Math.max(0,state.scanEnd-Date.now()),total=25*60*1000;if(left<=0){stopScan(true);return}const min=Math.floor(left/60000),sec=Math.floor((left%60000)/1000);$("#timer").textContent=`${String(min).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;$("#timerRing").style.setProperty("--progress",`${100-(left/total*100)}%`)}
$("#scanBtn").addEventListener("click",startScan);$("#refreshBtn").addEventListener("click",()=>loadData(true));$("#filters").addEventListener("click",e=>{if(!e.target.matches(".filter"))return;$$('.filter').forEach(x=>x.classList.remove("active"));e.target.classList.add("active");state.filter=e.target.dataset.filter;renderCatalysts()});
window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();state.deferredInstall=e;$("#installBtn").classList.remove("hidden")});$("#installBtn").addEventListener("click",async()=>{if(!state.deferredInstall)return;state.deferredInstall.prompt();await state.deferredInstall.userChoice;state.deferredInstall=null;$("#installBtn").classList.add("hidden")});
if("serviceWorker" in navigator)window.addEventListener("load",()=>navigator.serviceWorker.register("./sw.js").catch(console.warn));
loadData();setInterval(()=>loadData(false),5*60*1000);
