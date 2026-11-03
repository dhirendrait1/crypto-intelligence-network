(() => {
  'use strict';
  const API = 'https://cin-api-oohr.onrender.com';
  const $ = id => document.getElementById(id);
  const windows = {'1h':['5m',12], '6h':['15m',24], '24h':['1h',24], '7d':['4h',42]};
  const statuses = new Map(); let generation = 0; let selected = '24h'; let selectedCoin = 'BTC'; let chartSnapshot = null; let liveTrade = null; let chartController = null; let controller = null; let lastRefresh = 0; let renderTimer = null;
  const CHART_CACHE_KEY='cin.chart.latest.v1', CHART_CACHE_TTL=900000, JOB_RETAIN_MS=600000;
  const jobMemory=new Map();
  const num = value => typeof value === 'number' && Number.isFinite(value) ? value : typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
  const money = v => { const n = num(v); return n === null ? '—' : '$' + n.toLocaleString('en-US', {minimumFractionDigits:n < 1 ? 4 : 2, maximumFractionDigits:n < 1 ? 6 : 2}); };
  const stamp = value => { const n = typeof value === 'number' ? value : Date.parse(value || ''); const date = new Date(n); return Number.isFinite(date.getTime()) ? date.toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : 'Time unavailable'; };
  const percent = value => { const n = num(value); return n === null ? '—' : (n > 0 ? '+' : '') + n.toFixed(2) + '%'; };
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const svgEl = (tag, attrs) => {const node = document.createElementNS('http://www.w3.org/2000/svg',tag);for (const [k,v] of Object.entries(attrs)) node.setAttribute(k,v);return node;};
  function showStatus(name, state, detail, metadata = {}) {
    statuses.set(name, {state,detail}); const box=$('endpoint-list'); box.replaceChildren();
    window.dispatchEvent(new CustomEvent('cin:source-status', {detail:{name,state,provider:metadata.provider||null,dataMode:metadata.dataMode||null,receivedAt:state==='Available'?Date.now():null}}));
    for (const [key,val] of statuses) { const row=el('div',undefined,'endpoint-row'); row.append(el('span',key),el('strong',val.state + (val.detail ? ' · '+val.detail : ''))); box.append(row); }
    const vals=[...statuses.values()]; const ok=vals.filter(v=>v.state==='Available').length; const loading=vals.some(v=>v.state==='Loading');
    $('api-summary').textContent = loading ? `Checking · ${ok} available` : `${ok} of 5 sources responding`;
    $('connection').textContent = loading ? 'API checking' : ok===5 ? 'API connected' : ok ? 'API partial' : 'API offline';
    document.querySelector('.live-pill').classList.toggle('offline', !loading && ok===0);
  }
  async function get(path, signal) {
    const timeout = new AbortController(); const timer = setTimeout(()=>timeout.abort(),65000);
    const abort=()=>timeout.abort(); signal.addEventListener('abort',abort,{once:true}); if(signal.aborted)timeout.abort();
    try { const response=await fetch(API+path,{signal:timeout.signal,cache:'no-store',credentials:'omit',redirect:'error',headers:{Accept:'application/json'}}); if(!response.ok) throw new Error('HTTP '+response.status); const result=await response.json(); if(!result || typeof result!=='object' || Array.isArray(result)) throw new Error('Invalid response'); return result; }
    finally {clearTimeout(timer);signal.removeEventListener('abort',abort);}
  }
  function chartMessage(text) { const svg=$('chart');svg.replaceChildren();svg.append(svgEl('text',{x:340,y:110,'text-anchor':'middle',fill:'#8fa6b7','font-size':14}));svg.lastChild.textContent=text; }
  function drawChart(candles, live) {
    const svg=$('chart'); svg.replaceChildren(); const values=candles.map(c=>num(c.close));if(live)values.push(live.price);
    const lo=Math.min(...values),hi=Math.max(...values),span=hi-lo || Math.max(hi*.01,.0001);
    const coords=values.map((v,i)=>[10+i*660/(values.length-1),190-(v-lo)/span*160]);
    for(const y of [30,80,130,180])svg.append(svgEl('line',{x1:0,x2:680,y1:y,y2:y,stroke:'#345063','stroke-opacity':'.38','stroke-width':1}));
    const defs=svgEl('defs',{}),grad=svgEl('linearGradient',{id:'chart-fill',x1:0,x2:0,y1:0,y2:1});grad.append(svgEl('stop',{offset:'0%','stop-color':'#56e7c8','stop-opacity':'.28'}),svgEl('stop',{offset:'100%','stop-color':'#56e7c8','stop-opacity':'0'}));defs.append(grad);svg.append(defs);
    const history=live?coords.slice(0,-1):coords;const line=history.map(([x,y],i)=>(i?'L':'M')+x.toFixed(2)+','+y.toFixed(2)).join(' ');
    svg.append(svgEl('path',{d:line+' L'+history.at(-1)[0]+',205 L10,205 Z',fill:'url(#chart-fill)'}));svg.append(svgEl('path',{d:line,fill:'none',stroke:'#6cebd0','stroke-width':'3','stroke-linejoin':'round','stroke-linecap':'round'}));
    const last=coords.at(-1);if(live){const prior=history.at(-1);svg.append(svgEl('line',{x1:prior[0],y1:prior[1],x2:last[0],y2:last[1],stroke:'#ffd787','stroke-width':'3','stroke-dasharray':'6 5'}));}
    svg.append(svgEl('circle',{cx:last[0],cy:last[1],r:4,fill:live?'#ffd787':'#a8ffe9'}));
  }
  function clearMarket(message, resetLive=true) {chartSnapshot=null;if(resetLive)liveTrade=null;$('btc-price').textContent='—';$('price-sub').textContent=message;$('chart-status').textContent='Unavailable';$('chart-status').classList.remove('chart-status-live');$('market-source').textContent='Market data unavailable for '+selectedCoin+'/USD.';$('chart-start').textContent='—';$('chart-end').textContent='—';$('change').textContent='—';$('change').className='change neutral';chartMessage(message);}
  function saveChart(snapshot){
    try{const data={version:1,coin:snapshot.coin,window:snapshot.window,interval:snapshot.interval,source:snapshot.source,sourceId:snapshot.sourceId,ageSeconds:snapshot.ageSeconds,warnings:snapshot.warnings,fetchedAt:snapshot.fetchedAt,items:snapshot.items.map(c=>({open_time:c.open_time,close_time:c.close_time,open:c.open,close:c.close,is_closed:true}))};localStorage.setItem(CHART_CACHE_KEY,JSON.stringify(data));}catch(_){}
  }
  function restoreChart(coin,windowName){
    try{const c=JSON.parse(localStorage.getItem(CHART_CACHE_KEY)||'null'),delta=c&&Date.now()-c.fetchedAt;
      if(!c||c.version!==1||c.coin!==coin||c.window!==windowName||c.interval!==windows[windowName][0]||!Number.isFinite(delta)||delta<0||delta>CHART_CACHE_TTL||typeof c.source!=='string'||c.source.length>256||!['kraken_public','coinbase_public','binance_public'].includes(c.sourceId)||!(c.ageSeconds===null||typeof c.ageSeconds==='number'&&Number.isFinite(c.ageSeconds)&&c.ageSeconds>=0)||!Array.isArray(c.warnings)||c.warnings.length>10||c.warnings.some(x=>typeof x!=='string'||x.length>500)||!Array.isArray(c.items)||c.items.length<2||c.items.length>windows[windowName][1])return null;
      if(c.items.some((v,i)=>!v||v.is_closed!==true||!Number.isSafeInteger(v.open_time)||!Number.isSafeInteger(v.close_time)||v.close_time<v.open_time||v.close_time>Date.now()||num(v.open)===null||num(v.open)<=0||num(v.close)===null||num(v.close)<=0||(i&&v.open_time<=c.items[i-1].open_time)))return null;
      return {...c,fromCache:true,refreshing:true,refreshFailed:false};
    }catch(_){return null;}
  }
  function showLiveWithoutChart(message){
    if(!liveTrade||liveTrade.symbol!==selectedCoin+'/USD')return;
    $('btc-price').textContent=money(liveTrade.price);$('price-sub').textContent='Latest Kraken public trade · '+stamp(liveTrade.observedAt);$('chart-status').textContent='LIVE TRADE';$('chart-status').classList.toggle('chart-status-live',true);$('market-source').textContent=message+' Live trade is shown separately until a matching chart is available.';
  }
  function renderMarket() {
    if(!chartSnapshot){showLiveWithoutChart('Historical chart unavailable or loading.');return;}
    const {items,source,interval,ageSeconds}=chartSnapshot;const last=items.at(-1),first=items[0],warnings=[...chartSnapshot.warnings];
    const delta=Date.now()-chartSnapshot.fetchedAt,elapsed=Math.max(0,delta/1000),ageNow=ageSeconds===null?null:ageSeconds+elapsed,barSeconds={'5m':300,'15m':900,'1h':3600,'4h':14400}[interval];
    if(delta<0)warnings.push('device clock changed');
    if(ageNow!==null&&ageNow>barSeconds*2&&!warnings.includes('closed candle is stale'))warnings.push('closed candle is stale');
    if(chartSnapshot.fromCache)warnings.push('saved locally; awaiting source verification');if(chartSnapshot.refreshFailed)warnings.push('refresh failed; showing last known data');
    const live=liveTrade&&liveTrade.symbol===selectedCoin+'/USD'&&liveTrade.observedAt>last.close_time?liveTrade:null;
    const plottedLive=live&&!warnings.length&&!chartSnapshot.fromCache&&chartSnapshot.sourceId==='kraken_public'?live:null;
    $('btc-price').textContent=money(live?live.price:last.close);$('price-sub').textContent=(live?'Latest Kraken public trade · ':'Last closed candle · ')+stamp(live?live.observedAt:last.close_time);
    drawChart(items,plottedLive);$('chart-start').textContent=stamp(first.open_time);$('chart-end').textContent=stamp(plottedLive?plottedLive.observedAt:last.close_time);
    $('chart-status').textContent=live?(plottedLive?'LIVE TRADE':'LIVE · separate'):chartSnapshot.refreshing?(chartSnapshot.fromCache?'Cached · updating':'Updating'):chartSnapshot.refreshFailed?'Last known':warnings.length?'Check data':'Closed candles';$('chart-status').classList.toggle('chart-status-live',!!live);
    const move=(num(last.close)/num(first.open)-1)*100;if(!warnings.length&&Number.isFinite(move)){$('change').textContent=percent(move)+' · '+chartSnapshot.window.toUpperCase()+' CLOSED';$('change').className='change '+(move>0?'up':move<0?'down':'neutral');}else{$('change').textContent='Data limited';$('change').className='change neutral';}
    $('market-source').textContent=`${source} · ${interval} · ${items.length} closed candles · age ${ageNow===null?'unknown':Math.round(ageNow)+'s'}${chartSnapshot.refreshing?' · refreshing in background':''}${warnings.length?' · '+warnings.join(' · '):''}${plottedLive?' · Gold dotted segment: Kraken test-stream trade':live?' · Kraken live price shown above; not plotted on this chart':''}`;
  }
  function scheduleMarketRender(){if(renderTimer!==null)return;renderTimer=setTimeout(()=>{renderTimer=null;renderMarket();},250);}
  async function loadMarket(run) {
    if(chartController)chartController.abort();const own=new AbortController();chartController=own;const w=selected,coin=selectedCoin,symbol=coin+'USD';const [interval,count]=windows[w];showStatus('Market candles','Loading','');
    if(!chartSnapshot||chartSnapshot.coin!==coin||chartSnapshot.window!==w){chartSnapshot=restoreChart(coin,w);if(!chartSnapshot)clearMarket('Loading '+coin+'/USD candles…',false);}
    if(chartSnapshot){chartSnapshot.refreshing=true;chartSnapshot.refreshFailed=false;renderMarket();}else{$('chart-status').textContent='Loading';showLiveWithoutChart('Historical chart loading.');}
    try {const d=await get(`/market-candles?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${count+2}`,own.signal);if(own.signal.aborted||run!==generation||w!==selected||coin!==selectedCoin)return;
      if(d.symbol!==symbol||d.timeframe!==interval||!Array.isArray(d.data)||typeof d.source!=='string'||d.quote_currency!=='USD')throw Error('Unexpected market identity');
      const items=d.data.filter(c=>c&&c.is_closed===true&&num(c.close)!==null&&num(c.close)>0&&num(c.open)!==null&&num(c.open)>0&&Number.isSafeInteger(c.open_time)&&Number.isSafeInteger(c.close_time)&&c.close_time>=c.open_time).sort((a,b)=>a.open_time-b.open_time).slice(-count);
      if(items.length<2||items.some((x,i)=>i&&x.open_time<=items[i-1].open_time))throw Error('Insufficient closed candles');
      const first=items[0],warnings=[];if(items.length<count)warnings.push(`partial window ${items.length}/${count}`);if(items.some((c,i)=>i>0&&c.open_time!==items[i-1].close_time+1))warnings.push('candle gaps detected');if(d.stale_data_warning)warnings.push(String(d.stale_data_warning).slice(0,500));if(d.pair_metadata_status!=='identified')warnings.push('pair identity unverified');
      const age=num(d.latest_closed_candle_age_seconds),ageSeconds=age!==null&&age>=0?age:null;if(ageSeconds===null)warnings.push('freshness unknown');
      chartSnapshot={coin,window:w,items,source:d.source,sourceId:d.source_id,interval,ageSeconds,warnings,fetchedAt:Date.now(),fromCache:false,refreshing:false,refreshFailed:false};saveChart(chartSnapshot);$('chart-start').textContent=stamp(first.open_time);$('source-short').textContent=String(d.source).slice(0,90);$('chart').setAttribute('aria-label',coin+'/USD closed candle chart; live trade shown separately when available');renderMarket();showStatus('Market candles','Available',warnings.length?'limitations reported':'closed candles',{provider:d.source});
    }catch(e){if(own.signal.aborted||run!==generation)return;if(chartSnapshot&&chartSnapshot.coin===coin&&chartSnapshot.window===w){chartSnapshot.refreshing=false;chartSnapshot.refreshFailed=true;renderMarket();}else{clearMarket('No chart data for '+coin+'/USD',false);showLiveWithoutChart('Historical chart unavailable.');}$('source-short').textContent='Unavailable';showStatus('Market candles','Unavailable',e.name==='AbortError'?'Timed out':e.message);}
  }
  function selectCoin(value){
    const coin=String(value||'').trim().toUpperCase();if(!/^[A-Z0-9]{1,10}$/.test(coin)){$('coin-help').textContent='Enter a ticker using 1–10 letters or digits.';return;}
    const changed=coin!==selectedCoin;selectedCoin=coin;$('coin-input').value=coin;$('coin-help').textContent='USD spot · exchange availability and token identity are not guaranteed.';
    $('chart-coin-name').textContent=coin==='BTC'?'Bitcoin':coin;$('chart-coin-icon').textContent=coin==='BTC'?'₿':coin.slice(0,2);$('chart-market-label').textContent=coin+' / USD · SPOT';document.querySelector('.hero').dataset.chartMarket=coin+'/USD';
    if(changed){liveTrade=null;window.dispatchEvent(new CustomEvent('cin:chart-selection',{detail:{symbol:coin+'/USD'}}));}loadMarket(generation);
  }
  $('coin-form').addEventListener('submit',event=>{event.preventDefault();selectCoin($('coin-input').value);});
  window.addEventListener('cin:validated-trade',event=>{const d=event.detail||{};if(d.provider!=='kraken'||d.symbol!==selectedCoin+'/USD'||typeof d.price!=='number'||!Number.isFinite(d.price)||d.price<=0||!Number.isSafeInteger(d.observedAt))return;liveTrade={symbol:d.symbol,price:d.price,observedAt:d.observedAt};scheduleMarketRender();});
  window.addEventListener('cin:stream-ended',()=>{if(liveTrade){liveTrade=null;if(renderTimer!==null){clearTimeout(renderTimer);renderTimer=null;}if(chartSnapshot)renderMarket();else clearMarket('No current market data');}});
  function loadScreen(d) {
    if(!Array.isArray(d.data)||!Number.isInteger(d.count)||typeof d.source!=='string')throw Error('Invalid screening data');const box=$('screen-list');box.replaceChildren();const rows=d.data.slice(0,5);
    if(!rows.length)box.append(el('div','No assets returned by the screening provider.','empty'));
    for(const a of rows){const row=el('button',undefined,'screen-row'), asset=el('div',undefined,'screen-asset'), icon=el('div',String(a.symbol||'?').slice(0,2).toUpperCase(),'asset-avatar'), names=el('div',undefined,'asset-text');names.append(el('b',String(a.symbol||'Unknown').toUpperCase()),el('small',a.name||'Name unavailable'));asset.append(icon,names);const price=el('div',undefined,'screen-price'),move=num(a.price_change_percentage_24h);price.append(el('b',money(a.price)),el('small',percent(move),move===null?'':move>0?'up':move<0?'down':''));const score=el('div',num(a.screen_score)===null?'—':String(a.screen_score),'score');row.type='button';const ticker=String(a.symbol||'').toUpperCase();if(/^[A-Z0-9]{1,10}$/.test(ticker)){row.addEventListener('click',()=>{selectCoin(ticker);document.getElementById('overview').scrollIntoView({behavior:'smooth'});});row.setAttribute('aria-label','Show '+ticker+'/USD chart');}else row.disabled=true;row.append(asset,price,score);box.append(row);}
    const warning=d.stale_data_warning ? ' · '+d.stale_data_warning : '';const cache=d.data_mode?` · ${d.data_mode}${num(d.cache_age_seconds)!==null?' ('+d.cache_age_seconds+'s old)':''}`:'';$('screen-meta').textContent=`${d.source}${cache}${warning} · Preliminary screening score; not a ranked forecast.`;$('screen-source').textContent=d.source+(d.data_mode?' · '+d.data_mode:'');
  }
  function safeUrl(s){try{const u=new URL(s);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null;}catch{return null;}}
  function loadNews(d) {
    if(!Array.isArray(d.articles)||!Number.isInteger(d.count)||typeof d.source!=='string')throw Error('Invalid news data');const box=$('news-list');box.replaceChildren();const rows=d.articles.slice(0,5);$('news-count').textContent=rows.length+' HEADLINES';
    if(!rows.length)box.append(el('div','No headlines returned. Try refreshing later.','empty'));
    for(const a of rows){const link=safeUrl(a.url),node=el(link?'a':'article',undefined,'news-item');if(link){node.href=link;node.target='_blank';node.rel='noopener noreferrer';}node.append(el('h3',typeof a.title==='string'&&a.title.trim()?a.title:'Headline unavailable'));const domain=typeof a.domain==='string'&&a.domain?a.domain:'Source via feed';const time=a.provider_seen_at_utc||a.published_at_utc;node.append(el('small',domain+' · '+(time?stamp(time):'Time unavailable')+' · provider-reported'));box.append(node);}
    $('news-meta').textContent=d.source+' · Headlines and times are provider-reported. Headline sentiment is not social or market-wide sentiment.';
  }
  function loadTech(d) {if(!d.input||!d.indicators)throw Error('Invalid technical data');const value=num(d.indicators.rsi_14);$('rsi').textContent=value===null?'—':value.toFixed(2);$('rsi-meta').textContent='RSI (14) · BTC/USDT';}
  function loadDerivatives(d){if(d.symbol!=='BTCUSD'||!d.data||!d.data_quality)throw Error('Invalid derivatives data');$('mark').textContent=money(d.data.mark_price);$('deriv-note').textContent='Mark price · freshness '+(d.data_quality.freshness_status||'unknown');}
  const jobs=[{name:'Technical analysis',path:'/technical-analysis/market?symbol=BTCUSDT&interval=1h&limit=100',render:loadTech,clear:()=>$('rsi').textContent='—'},{name:'Screening',path:'/coin-screening?vs_currency=usd&per_page=5&min_score=0&asset_type=growth',render:loadScreen,clear:()=>{$('screen-list').replaceChildren(el('div','Screening unavailable. Try refreshing.','empty'));$('screen-meta').textContent='No screening data available.';$('screen-source').textContent='Unavailable';}},{name:'News',path:'/news-sentiment?query=cryptocurrency&max_records=5',render:loadNews,clear:()=>{$('news-list').replaceChildren(el('div','News unavailable. Try refreshing.','empty'));$('news-count').textContent='UNAVAILABLE';$('news-meta').textContent='No headlines available from the configured provider.';}},{name:'Derivatives',path:'/derivatives/kraken-market-snapshot',render:loadDerivatives,clear:()=>{$('mark').textContent='—';$('deriv-note').textContent='Unavailable';}}];
  const noteIds={'Technical analysis':'rsi-meta','Screening':'screen-meta','News':'news-meta','Derivatives':'deriv-note'};
  function previousJob(job){const previous=jobMemory.get(job.name);if(!previous)return null;const age=Date.now()-previous.receivedAt;return age>=0&&age<=JOB_RETAIN_MS?previous:null;}
  function showPrevious(job,previous,state){const note=$(noteIds[job.name]);if(note)note.textContent=previous.note+' · '+state+' · last received '+stamp(previous.receivedAt);}
  function prepareJob(job){
    const previous=previousJob(job);if(previous){showPrevious(job,previous,'updating');return;}
    jobMemory.delete(job.name);job.clear();
    if(job.name==='Technical analysis')$('rsi-meta').textContent='RSI (14) · loading';
    if(job.name==='Screening'){$('screen-list').replaceChildren(el('div','Loading screening data…','empty'));$('screen-meta').textContent='Waiting for screening provider.';$('screen-source').textContent='Loading';}
    if(job.name==='News'){$('news-list').replaceChildren(el('div','Loading headlines…','empty'));$('news-count').textContent='LOADING';$('news-meta').textContent='Waiting for news provider.';}
    if(job.name==='Derivatives')$('deriv-note').textContent='Mark price · loading';
  }
  async function runJob(job,run,signal){showStatus(job.name,'Loading','');prepareJob(job);try{const data=await get(job.path,signal);if(signal.aborted||run!==generation)return;job.render(data);const note=$(noteIds[job.name]);jobMemory.set(job.name,{receivedAt:Date.now(),note:note?note.textContent:''});showStatus(job.name,'Available','response received',{provider:data.source||(data.input&&data.input.source),dataMode:data.data_mode});}catch(e){if(signal.aborted||run!==generation)return;const previous=previousJob(job);if(previous)showPrevious(job,previous,'last known; refresh failed');else{job.clear();if(job.name==='Technical analysis')$('rsi-meta').textContent='RSI (14) · unavailable';}showStatus(job.name,'Unavailable',e.name==='AbortError'?'Timed out':e.message);}}
  function refresh(){lastRefresh=Date.now();generation++;if(controller)controller.abort();if(chartController)chartController.abort();controller=new AbortController();const run=generation;statuses.clear();for(const n of ['Market candles','Technical analysis','Screening','News','Derivatives'])showStatus(n,'Loading','');loadMarket(run);for(const job of jobs)runJob(job,run,controller.signal);}
  $('refresh').addEventListener('click',refresh);$('flow-refresh').addEventListener('click',refresh);document.querySelectorAll('[data-window]').forEach(button=>button.addEventListener('click',()=>{selected=button.dataset.window;document.querySelectorAll('[data-window]').forEach(b=>{const active=b===button;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active));});loadMarket(generation);}));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&Date.now()-lastRefresh>=300000)refresh();});
  setInterval(()=>{if(document.hidden)return;if(chartSnapshot)renderMarket();if(Date.now()-lastRefresh>=300000)refresh();},30000);
  if('serviceWorker' in navigator&&window.isSecureContext)window.addEventListener('load',()=>navigator.serviceWorker.register('./sw.js').catch(()=>{}));
  refresh();
})();
