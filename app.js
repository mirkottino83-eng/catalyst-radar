const state={data:null,filter:"all",deferredInstall:null,history:null,historyShown:30,favorites:[],notificationsEnabled:false,nativeAvailable:null,nativeBusy:false,nativeStatus:null};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const fmt=(v,d=2)=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
const signed=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v))?((Number(v)>0?"+":"")+Number(v).toFixed(2)+"%"):"N/D";
const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
const toast=m=>{const e=$("#toast");e.textContent=m;e.classList.add("show");setTimeout(()=>e.classList.remove("show"),2500)};


// Per-installation browser setting. This never writes a shared GitHub setting.
// Current legacy ntfy Android subscription is independent and must be muted
// in ntfy itself; a future Play Store native app will use FCM per device.
const DEVICE_NOTIFICATIONS_KEY="catalyst-radar-device-notifications-v1";
const isNativeRadar=()=>!!(window.CatalystRadarNative&&typeof window.CatalystRadarNative.postMessage==="function");
window.addEventListener("CatalystRadarNativeState",event=>{
  if(!isNativeRadar())return;
  const detail=event.detail||{};
  state.nativeAvailable=detail.available===true;
  state.nativeBusy=detail.busy===true;
  state.nativeStatus=detail.status||"ready";
  state.notificationsEnabled=detail.enabled===true;
  renderDeviceNotifications();
  if(detail.error)toast(detail.error);
});
function readDeviceNotifications(){
  try{return localStorage.getItem(DEVICE_NOTIFICATIONS_KEY)==="enabled"}
  catch(_){return false}
}
function saveDeviceNotifications(enabled){
  try{localStorage.setItem(DEVICE_NOTIFICATIONS_KEY,enabled?"enabled":"disabled");return true}
  catch(_){return false}
}
function renderDeviceNotifications(){
  const input=$("#deviceNotificationToggle"),status=$("#deviceNotificationStatus");
  const detail=$("#notificationPlatformInfo");
  if(!input||!status)return;
  if(detail){
    detail.textContent=isNativeRadar()
      ?"Versione Android: gli avvisi Firebase sono separati da ntfy. Questo interruttore controlla le notifiche di QUESTO telefono anche con l'app chiusa, dopo la configurazione Firebase e l'autorizzazione Android. La scansione del mercato continua indipendentemente."
      :"Versione web: l'interruttore controlla gli avvisi locali quando la pagina è aperta. Le notifiche dell'app esterna ntfy sono indipendenti e vanno silenziate direttamente in ntfy.";
  }
  input.checked=state.notificationsEnabled;
  if(isNativeRadar()){
    input.disabled=state.nativeBusy||state.nativeAvailable!==true;
    if(state.nativeAvailable===null){
      status.textContent="Verifica configurazione notifiche Android…";
    }else if(!state.nativeAvailable){
      status.textContent="Notifiche Android non ancora configurate con Firebase: necessaria la configurazione prima del Play Store.";
    }else if(state.nativeBusy){
      status.textContent="Aggiornamento notifiche Android in corso…";
    }else if(state.notificationsEnabled){
      status.textContent="ON: notifiche native abilitate per questo telefono, anche con l'app chiusa. Puoi disattivarle qui.";
    }else{
      status.textContent="OFF: notifiche native disabilitate soltanto su questo telefono.";
    }
    return;
  }
  input.disabled=false;
  const usable=("Notification" in window) && Notification.permission==="granted";
  if(!state.notificationsEnabled){
    status.textContent="Disattivate: nessun nuovo avviso locale da Catalyst Radar. Le notifiche ntfy esterne vanno silenziate direttamente in ntfy.";
  }else if(usable){
    status.textContent="Attive: avvisi locali per nuovi catalyst e macro quando questa app è aperta. ntfy esterna è indipendente.";
  }else{
    status.textContent="Preferenza attiva, ma le notifiche locali del browser non sono autorizzate o supportate. Controlla i permessi Android. ntfy resta indipendente.";
  }
}
async function updateDeviceNotifications(enabled){
  if(isNativeRadar()){
    if(state.nativeAvailable!==true||state.nativeBusy)return;
    state.nativeBusy=true;
    renderDeviceNotifications();
    try{
      window.CatalystRadarNative.postMessage(JSON.stringify({type:"setNotifications",enabled:!!enabled}));
    }catch(error){
      state.nativeBusy=false;
      renderDeviceNotifications();
      toast("Impossibile aggiornare le notifiche native.");
    }
    return;
  }
  if(enabled && "Notification" in window && Notification.permission==="default"){
    try{await Notification.requestPermission()}catch(e){console.warn("Notification permission:",e)}
  }
  if(!saveDeviceNotifications(enabled)){
    toast("Impossibile salvare la preferenza su questo dispositivo");
    renderDeviceNotifications();
    return;
  }
  state.notificationsEnabled=enabled;
  renderDeviceNotifications();
  if(!enabled)toast("Avvisi locali disattivati. Per silenziare ntfy usa la sua app.");
  else if(!("Notification" in window)||Notification.permission!=="granted")
    toast("Preferenza salvata: autorizza le notifiche del browser in Android.");
  else toast("Avvisi locali attivati su questo dispositivo.");
}
function isMacroFresh(snapshot){
  const macro=snapshot?.macro||{};
  if(macro.tech_bias!=="strong_positive"||Number(macro.macro_score||0)<72)return false;
  const names=["nasdaq","sox","vix","treasury_10y","wti"];
  return names.every(k=>{
    const t=Date.parse(macro.quote_times?.[k]||"");
    return Number.isFinite(t)&&Math.abs(Date.now()-t)<25*60*1000;
  });
}
function newLocalAlerts(previous,current){
  if(!previous||!current||previous.generated_at===current.generated_at)return [];
  const known=new Set((previous.catalysts||[]).map(x=>x.id||x.ticker+"|"+x.headline));
  const fresh=(current.catalysts||[]).filter(x=>
    !known.has(x.id||x.ticker+"|"+x.headline)&&
    x.verification_status==="RSS_INDICIZZATO_DA_VERIFICARE"&&
    (x.early_signal===true||Number(x.confidence_score||0)>=78));
  const result=fresh.slice(0,2).map(x=>({
    title:"Catalyst Radar · "+x.ticker,
    body:(x.headline||"Nuovo catalyst da verificare")+" · Notizia RSS non verificata."
  }));
  if(isMacroFresh(current)&&!isMacroFresh(previous)){
    result.push({title:"Catalyst Radar · Macro tech favorevole",
      body:"Contesto tech favorevole secondo gli indicatori disponibili: verifica volumi, dati e fonti."});
  }
  return result;
}
async function showDeviceAlert(title,body){
  if(isNativeRadar())return; // Native FCM service owns notifications. Never duplicate.
  if(!state.notificationsEnabled||!("Notification" in window)||Notification.permission!=="granted")return;
  try{
    if("serviceWorker" in navigator){
      const reg=await navigator.serviceWorker.getRegistration("./");
      if(reg?.showNotification){
        await reg.showNotification(title,{
          body,
          icon:"./assets/icon-192.png",
          tag:"catalyst-radar-"+title,
          renotify:false,
        });
        return;
      }
    }
    new Notification(title,{body,icon:"./assets/icon-192.png"});
  }catch(err){console.warn("Avviso locale non disponibile:",err)}
}

async function loadData(manual=false){
  try{
    const r=await fetch("./data/latest.json?t="+Date.now(),{cache:"no-store"});
    if(!r.ok) throw new Error("HTTP "+r.status);
    const data=await r.json(), previous=state.data;
    state.data=data; render();
    if(!previous||previous.generated_at!==data.generated_at)loadHistory();
    if(state.notificationsEnabled && previous){
      newLocalAlerts(previous,data).forEach(x=>showDeviceAlert(x.title,x.body));
    }
    if(manual) toast("Dati aggiornati");
  }catch(e){console.error(e);$("#lastUpdate").textContent="Dati non disponibili";if(manual)toast("Aggiornamento non riuscito")}
}
function render(){if(!state.data)return;renderHeader();renderMacro();renderMovers();renderCatalysts();renderArchive();renderWatchlist();renderSources()}
function renderHeader(){
  const d=state.data,ts=d.generated_at?new Date(d.generated_at):null;
  $("#lastUpdate").textContent=ts?"Agg. "+ts.toLocaleString("it-IT",{hour:"2-digit",minute:"2-digit",day:"2-digit",month:"2-digit"}):"Aggiornamento —";
  const ny=new Date().toLocaleString("en-US",{timeZone:"America/New_York"}),nd=new Date(ny),h=nd.getHours(),day=nd.getDay(),mins=nd.getMinutes();
  const open=day>=1&&day<=5&&((h>9&&h<16)||(h===9&&mins>=30));
  const b=$("#marketBadge");b.textContent=open?"US MARKET OPEN":"US MARKET CLOSED";b.className="badge "+(open?"positive":"neutral");
}
function renderMacro(){
  const m=state.data.macro||{};
  const cards=[
    ["US 10Y",m.treasury_10y,m.treasury_10y_change_bp,"","%"," bp"],
    ["WTI",m.wti,m.wti_change_pct,"$","","%"],
    ["Brent",m.brent,m.brent_change_pct,"$","","%"],
    ["Nasdaq",m.nasdaq_level,m.nasdaq_change_pct,"","","%"],
    ["SOX",m.sox_level,m.sox_change_pct,"","","%"],
    ["VIX",m.vix,m.vix_change_pct,"","","%"]
  ];
  $("#macroGrid").innerHTML=cards.map(([name,value,change,prefix,suffix,changeUnit])=>
    '<div class="macro-card"><small>'+esc(name)+'</small><strong>'+prefix+fmt(value,2)+suffix+
    '</strong><span class="'+(Number(change)>0?"pos":Number(change)<0?"neg":"flat")+'">'+
    (change==null?"N/D":(Number(change)>0?"+":"")+fmt(change,2)+changeUnit)+
    '</span></div>').join("");
  const bias=(m.tech_bias||"neutral").replaceAll("_"," ").toUpperCase();
  const el=$("#macroBias");el.textContent=bias;
  el.className="badge "+(bias.includes("POSITIVE")?"positive":bias.includes("NEGATIVE")?"negative":"neutral");
  $("#macroSummary").textContent=m.summary||"Quadro macro in aggiornamento.";
  const qt=m.quote_times||{};
  const dated=Object.entries({Treasury:qt.treasury_10y,WTI:qt.wti,Brent:qt.brent,Nasdaq:qt.nasdaq,SOX:qt.sox,VIX:qt.vix})
    .map(([name,time])=>time?name+" "+new Date(time).toLocaleString("it-IT",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):name+" N/D");
  $("#macroQuoteTimes").textContent="Ora dell'ultima quotazione disponibile (non necessariamente live): "+dated.join(" · ");
  const age=Date.now()-Date.parse(state.data.generated_at);
  const readable=Number.isFinite(age)?Math.max(0,Math.floor(age/60000)):null;
  const st=$("#backendStatus");
  st.textContent="Scanner su GitHub indipendente dall'app · scansioni programmate ogni 5 min (non garantite)"+
    (readable===null?" · aggiornamento non disponibile": " · ultimo file dati "+readable+" min fa")+
    " · le fonti gratuite possono avere ritardi.";
  st.classList.toggle("data-stale",readable===null||readable>20);
}
function renderMovers(){
 const target=$("#moversList");
 if(!target)return;
 const movers=state.data?.movers||[];
 if(!movers.length){target.innerHTML='<div class="empty panel">Nessuna accelerazione con quotazioni recenti. Durante il weekend è normale.</div>';return}
 target.innerHTML=movers.map(m=>{
   const t=String(m.ticker||"").toUpperCase();
   const rv=m.relative_volume==null?"N/D":fmt(m.relative_volume,2)+"×";
   const qt=m.quote_at?new Date(m.quote_at).toLocaleString("it-IT",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"N/D";
   return `<article class="mover panel">
    <div class="mover-name"><strong>${esc(t)}</strong><small>${esc(m.company||"")}</small></div>
    <div class="mover-metrics"><span>Giorno: <b>${signed(m.current_change_pct)}</b></span>
    <span>Ultima ora: <b>${signed(m.short_term_change_pct)}</b></span><span>RVOL 1h: <b>${esc(rv)}</b></span></div>
    <div class="meta">${m.early_move?'<span class="chip early-chip">Sotto +1,5% · da verificare</span>':""}
    <span class="chip">Quotazione: ${esc(qt)}</span>
    ${m.satispay_status==="unavailable"?'<span class="chip">non su Satispay</span>':""}</div>
    <button type="button" class="mini-btn" data-mover-chart="${esc(t)}">Grafico</button>
   </article>`;
 }).join("");
}
function renderCatalysts(){
  const list=(state.data.catalysts||[]).filter(x=>{if(state.filter==="all")return true;if(state.filter==="early")return x.early_signal===true;if(state.filter==="volume")return x.quote_status==="RECENT_UNOFFICIAL"&&x.relative_volume!=null&&Number(x.relative_volume)>=1.5;if(state.filter==="critical")return x.priority==="critical"||Number(x.confidence_score)>=75;if(state.filter==="tech")return /tech|semi|ai|cloud|software|cyber/i.test(x.category||"");if(state.filter==="biotech")return /bio|pharma|health/i.test(x.category||"");if(state.filter==="personal")return state.favorites.includes(x.ticker)});
  $("#emptyState").classList.toggle("hidden",list.length>0);
  $("#catalystList").innerHTML=list.map(c=>{const move=c.current_change_pct==null?null:Number(c.current_change_pct),conf=Math.round(Number(c.confidence_score||0)),impact=c.estimated_impact_pct==null?null:Number(c.estimated_impact_pct);return `<article class="catalyst"><div class="ticker"><div class="ticker-bubble">${esc(c.ticker)}</div><div><h4>${esc(c.ticker)}</h4><small>${esc(c.company||"")}</small></div></div><div><div class="headline">${esc(c.headline||c.reason||"Catalyst rilevato")}</div><div class="reason">${esc(c.reason||"")}</div><div class="meta"><span class="chip">${esc(c.catalyst_type||"News")}</span><span class="chip">${esc(c.source||"source")}</span><span class="chip">${esc(c.age_label||"")}</span><span class="chip">RVOL 1h ${c.relative_volume==null?"N/D":fmt(c.relative_volume,2)+"×"}</span><span class="chip">${c.quote_status==="RECENT_UNOFFICIAL"?"Quotazione "+fmt(c.quote_age_minutes,0)+" min fa":"Prezzo non aggiornato"}</span>${c.early_signal?'<span class="chip early-chip">PRECOCE · DA VERIFICARE</span>':""}<span class="chip">${c.verification_status==="SEC_DOCUMENTO_UFFICIALE_EVENTO_NON_CLASSIFICATO"?"SEC: evento non valutato":c.source_verified?"✓ fonte ufficiale":"RSS: evento da verificare"}</span>${c.satispay_status==="unavailable"?'<span class="chip">non su Satispay</span>':""}</div></div><div class="scores"><div class="score"><span>MOVIMENTO</span><strong class="${move>0?"pos":move<0?"neg":"flat"}">${signed(move)}</strong></div><div class="score"><span>IMPATTO INDICATIVO</span><strong>${impact==null?"N/D":(impact>0?"+":"")+fmt(impact,1)+"%"}</strong></div><div class="score full"><span>QUALITÀ · NON PROBABILITÀ</span><strong>${conf}/100</strong><div class="bar"><i style="--w:${Math.min(100,conf)}%"></i></div></div></div><div class="catalyst-actions"><button class="mini-btn" onclick='showChart(${JSON.stringify(c.tradingview_symbol||c.ticker)},${JSON.stringify(c.ticker)})'>Grafico</button>${c.url?`<a class="mini-btn" href="${esc(c.url)}" target="_blank" rel="noopener" style="text-decoration:none">Fonte ↗</a>`:""}<button class="mini-btn" onclick='showWhy(${JSON.stringify(c.ticker)})'>Perché?</button></div></article>`}).join("");
}
window.showWhy=ticker=>{const c=(state.data?.catalysts||[]).find(x=>x.ticker===ticker);if(!c)return;const f=c.factors||{};alert(`${ticker} — scoring\n\nFonte: ${f.source_quality??"—"}/100\nCatalyst: ${f.catalyst_strength??"—"}/100\nFreschezza: ${f.freshness??"—"}/100\nVolumi: ${f.volume??"—"}/100\nMomentum: ${f.momentum??"—"}/100\nMacro: ${f.macro??"—"}/100\nPenalità estensione: ${f.extension_penalty??0}\n\n${c.risk_flags||""}`)};
const CHART_NYSE=new Set(["OXY","PFE","NKE","DELL","ORCL","TSM","SHEL","MT","E","BABA","NVO","SAP","STM","SE","RDDT","HIMS","UBER","NET","PLTR","SNOW"]);
const CHART_NASDAQ=new Set(["AMD","INTC","NBIS","GOOGL","GOOG","NVDA","QCOM","MRNA","MU","META","AVGO","ASML","SMCI","MSFT","AMZN","ENPH","CRWD","CRWV","LULU","PLUG","APP","ARM","CRDO","RKLB","SOFI","COIN","MSTR","MARA","TSLA","SHOP","DDOG","CELH","BIDU","JD","PDD","MELI"]);
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
const PERSONAL_KEY="catalyst-radar-manual-favorites-v1";
function getFavorites(){
  try{
    const items=JSON.parse(localStorage.getItem(PERSONAL_KEY)||"[]");
    return Array.isArray(items)?[...new Set(items.filter(x=>typeof x==="string"&&/^[A-Z][A-Z0-9.^-]{0,11}$/.test(x)))]:[];
  }catch(_){return []}
}
function saveFavorites(){
  try{localStorage.setItem(PERSONAL_KEY,JSON.stringify(state.favorites));return true}
  catch(_){toast("Impossibile salvare sul dispositivo");return false}
}
function renderWatchlist(){
  const box=$("#watchlist");
  if(!state.favorites.length){
    box.innerHTML='<p class="section-description">Nessun titolo personale. Inserisci un ticker per creare la tua lista.</p>';
    return;
  }
  box.innerHTML=state.favorites.map(t=>
    '<span class="watch-chip personal-chip">'+esc(t)+
    ' <button class="personal-graph" type="button" data-graph="'+esc(t)+
    '" aria-label="Grafico '+esc(t)+'">Grafico</button>'+
    ' <button class="personal-remove" type="button" data-remove="'+esc(t)+
    '" aria-label="Rimuovi '+esc(t)+'">×</button></span>').join("");
}
function handleFavoriteInput(e){
  e.preventDefault();
  const input=$("#personalTicker");
  const name=input.value.trim().toUpperCase();
  if(!/^[A-Z][A-Z0-9.^-]{0,11}$/.test(name)){toast("Inserisci un ticker valido (es. AMD)");return}
  if(state.favorites.includes(name)){toast("Ticker già presente");return}
  if(state.favorites.length>=80){toast("Massimo 80 ticker personali");return}
  state.favorites.push(name);
  saveFavorites();renderWatchlist();renderCatalysts();input.value="";
  toast(name+" aggiunto sul dispositivo");
}
function validHref(value){
  try{const u=new URL(String(value));return ["http:","https:"].includes(u.protocol)?u.href:null}
  catch(_){return null}
}
async function loadHistory(){
  try{
    const response=await fetch("./data/history.json?t="+Date.now(),{cache:"no-store"});
    if(!response.ok)throw new Error("HTTP "+response.status);
    const obj=await response.json();
    state.history=Array.isArray(obj.events)?obj.events:[];
    renderArchive();
  }catch(err){
    console.warn("Archivio non disponibile:",err);
    if(state.history===null){
      $("#archiveList").innerHTML='<div class="empty panel">Archivio momentaneamente non disponibile. Riprova con «Aggiorna dati».</div>';
      $("#archiveCount").textContent="Non disponibile";
    }
  }
}
const archiveDate=s=>{
  const d=new Date(s);
  return Number.isFinite(d.getTime())?d.toLocaleString("it-IT",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"}):"N/D";
};
function outcomeView(event,h){
  const result=event.checkpoints?.[String(h)];
  if(result&&result.return_pct!==undefined&&result.return_pct!==null){
    return '<strong class="'+(result.return_pct>0?"pos":result.return_pct<0?"neg":"flat")+'">'+
           signed(result.return_pct)+'</strong><small>Alle '+esc(archiveDate(result.quote_at))+'</small>';
  }
  const pub=Date.parse(event.published_at);
  const due=pub+h*3600000;
  return '<strong class="flat">N/D</strong><small>'+
    (Number.isFinite(pub)&&Date.now()<due?"In attesa":"Mercato chiuso / dati mancanti")+'</small>';
}
function renderArchive(){
  const target=$("#archiveList");
  if(!target)return;
  if(state.history===null){target.innerHTML='<div class="empty panel">Caricamento storico dal server…</div>';return}
  const events=state.history;
  $("#archiveCount").textContent=events.length+" eventi";
  if(!events.length){
    target.innerHTML='<div class="empty panel">Archivio vuoto: conserverà i catalyst trovati dalle prossime scansioni. Non possiamo ricostruire prezzi storici senza quotazioni osservate.</div>';
    $("#archiveMoreBtn").classList.add("hidden");return;
  }
  target.innerHTML=events.slice(0,state.historyShown).map(e=>{
    const first=e.pct_at_publication==null?"N/D":signed(e.pct_at_publication);
    const initialPrice=e.price_at_publication==null?"N/D":"$"+fmt(e.price_at_publication,3);
    const url=validHref(e.url);
    const ticker=String(e.ticker||"").toUpperCase();
    const safeTicker=/^[A-Z0-9.^:-]{1,35}$/.test(ticker)?ticker:null;
    const sourceLink=url?'<a class="mini-btn" href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">Fonte ↗</a>':"";
    const graphBtn=safeTicker?'<button class="mini-btn" type="button" data-chart="'+esc(safeTicker)+'">Grafico</button>':"";
    return '<article class="archive-item panel"><div class="archive-head"><strong>'+esc(ticker)+
      '</strong><span class="muted">'+esc(archiveDate(e.published_at))+'</span></div>'+
      '<div class="archive-title">'+esc(e.headline||"Documento rilevato")+'</div>'+
      '<div class="archive-sub">'+esc(e.source||"Sorgente non nota")+
      ' · Primo rilevamento: '+esc(archiveDate(e.first_seen_at))+'</div>'+
      '<div class="archive-stats">'+
      '<div class="archive-stat"><small>Alla notizia vs chiusura precedente</small><strong>'+first+
      '</strong><small>Prezzo alla notizia: '+initialPrice+'</small></div>'+
      '<div class="archive-stat"><small>Impatto previsto*</small><strong>'+
      (e.estimated_impact_pct==null?"N/D":signed(e.estimated_impact_pct))+
      '</strong><small>Stima euristica, non previsione garantita</small></div>'+
      [2,5,8].map(h=>'<div class="archive-stat"><small>Reale dopo '+h+'h vs prezzo notizia</small>'+
      outcomeView(e,h)+'</div>').join("")+
      '</div><div class="archive-actions">'+graphBtn+sourceLink+
      '<span class="muted">'+esc(e.verification_status||"Da verificare")+'</span></div>'+
      '</article>';
  }).join("");
  $("#archiveMoreBtn").classList.toggle("hidden",events.length<=state.historyShown);
}

function renderSources(){$("#sources").innerHTML=(state.data.sources||[]).map(s=>`<div class="source"><div class="source-state"><strong>${esc(s.name)}</strong><span class="dot ${s.limited?"limited":""}"></span></div><p>${esc(s.note||s.coverage||"")}</p></div>`).join("")}
$("#deviceNotificationToggle").addEventListener("change",e=>updateDeviceNotifications(e.target.checked));
$("#refreshBtn").addEventListener("click",()=>loadData(true));$("#filters").addEventListener("click",e=>{if(!e.target.matches(".filter"))return;$$('.filter').forEach(x=>x.classList.remove("active"));e.target.classList.add("active");state.filter=e.target.dataset.filter;renderCatalysts()});
window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();state.deferredInstall=e;$("#installBtn").classList.remove("hidden")});$("#installBtn").addEventListener("click",async()=>{if(!state.deferredInstall)return;state.deferredInstall.prompt();await state.deferredInstall.userChoice;state.deferredInstall=null;$("#installBtn").classList.add("hidden")});
state.favorites=getFavorites();
$("#personalForm").addEventListener("submit",handleFavoriteInput);
$("#watchlist").addEventListener("click",e=>{
  const graph=e.target.closest("[data-graph]");
  if(graph){window.showChart(graph.dataset.graph,graph.dataset.graph);return}
  const remove=e.target.closest("[data-remove]");
  if(!remove)return;
  state.favorites=state.favorites.filter(t=>t!==remove.dataset.remove);
  saveFavorites();renderWatchlist();renderCatalysts();
});
$("#archiveMoreBtn").addEventListener("click",()=>{state.historyShown+=30;renderArchive()});
$("#archiveList").addEventListener("click",e=>{
  const btn=e.target.closest("[data-chart]");
  if(btn)window.showChart(btn.dataset.chart,btn.dataset.chart);
});
if("serviceWorker" in navigator)window.addEventListener("load",()=>navigator.serviceWorker.register("./sw.js").catch(console.warn));
state.notificationsEnabled=readDeviceNotifications();
renderDeviceNotifications();
if(isNativeRadar()){
  state.notificationsEnabled=false; // Wait for native persisted per-phone preference.
  renderDeviceNotifications();
  window.CatalystRadarNative.postMessage(JSON.stringify({type:"getState"}));
}
loadData();
setInterval(()=>loadData(false),60*1000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)loadData(false)});
window.addEventListener("pageshow",e=>{if(e.persisted)loadData(false)});
