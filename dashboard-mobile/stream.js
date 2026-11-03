/* Automatically connect to the bounded public Kraken test stream while visible. */
(() => {
  'use strict';
  const endpoint='https://cin-api-milestone2-test.onrender.com/research/ccxt/public-trades-stream?symbol=';
  let symbol=document.querySelector('.hero').dataset.chartMarket||'BTC/USD';
  const button=document.getElementById('stream-toggle'), status=document.getElementById('stream-state');
  const price=document.getElementById('stream-price'), meta=document.getElementById('stream-meta'), latest=document.getElementById('flow-latest');
  let enabled=false, controller=null, retryTimer=null, watch=null, lastArrival=0, latestObservedAt=0, generation=0, failures=0, resumeAfter=0, updateTimer=null, pendingTrade=null;
  function clearVisual(message){
    if(updateTimer!==null){clearTimeout(updateTimer);updateTimer=null;}pendingTrade=null;
    lastArrival=0;latestObservedAt=0;status.textContent=message;price.textContent='—';latest.textContent=message;
    window.dispatchEvent(new CustomEvent('cin:stream-ended'));
  }
  function stop(message, detail){
    enabled=false;generation++;if(controller){controller.abort();controller=null;}
    if(retryTimer){clearTimeout(retryTimer);retryTimer=null;}if(watch){clearInterval(watch);watch=null;}
    button.textContent='Connect live stream';clearVisual(message);if(detail)meta.textContent=detail;
  }
  function retry(message,detail, failed, minimumDelay=35000){
    if(!enabled)return;if(controller){controller.abort();controller=null;}
    clearVisual(message);if(detail)meta.textContent=detail;
    if(failed) failures=Math.min(failures+1,6);
    const delay=Math.max(minimumDelay,failed?Math.min(300000,35000*Math.pow(2,failures-1)):35000);
    status.textContent=message+' · retrying in '+Math.ceil(delay/1000)+'s';
    resumeAfter=Date.now()+delay;
    retryTimer=setTimeout(()=>{retryTimer=null;if(enabled&&!document.hidden)attempt();},delay);
  }
  function parseData(data){try{const x=JSON.parse(data);return x&&typeof x==='object'&&!Array.isArray(x)?x:null;}catch{return null;}}
  function eventHandler(type,data,ctx){
    const d=parseData(data);
    if(type==='connected'){
      if(!d||d.provider!=='kraken'||d.symbol!==ctx.symbol||d.market_type!=='spot'||d.mode!=='read_only')throw Error('Unexpected stream identity');
      ctx.ready=true;status.textContent='Connected · waiting for trade';latest.textContent='Connected · waiting for trade';
      meta.textContent='Test service · Kraken '+ctx.symbol+'. Provider identity and timestamps are not independently verified.';
    } else if(type==='trade'){
      if(!ctx.ready||!d||d.provider!=='kraken'||d.symbol!==ctx.symbol||d.market_type!=='spot'||d.price_currency!=='USD'||d.quantity_currency!==ctx.symbol.split('/')[0]||
         typeof d.price!=='number'||!Number.isFinite(d.price)||d.price<=0||typeof d.quantity!=='number'||!Number.isFinite(d.quantity)||d.quantity<=0||
         !Number.isSafeInteger(d.provider_observed_at_ms)||!Number.isSafeInteger(d.received_at_ms)||d.provider_observed_at_ms<=0||d.provider_observed_at_ms>d.received_at_ms||d.received_at_ms-d.provider_observed_at_ms>30000){
        status.textContent='Invalid update ignored';return;
      }
      const deviceAge=Date.now()-d.received_at_ms;
      if(deviceAge>30000||deviceAge < -5000){status.textContent='Update delayed or phone clock differs';return;}
      if(d.provider_observed_at_ms<latestObservedAt){status.textContent='Out-of-order update ignored';return;}
      failures=0;lastArrival=Date.now();latestObservedAt=d.provider_observed_at_ms;pendingTrade={data:d,symbol:ctx.symbol};
      if(updateTimer===null)updateTimer=setTimeout(()=>{
        updateTimer=null;const pending=pendingTrade;pendingTrade=null;
        if(!pending||!enabled||pending.symbol!==symbol)return;const trade=pending.data;
        status.textContent='Receiving live trades';price.textContent='$'+trade.price.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
        const time=new Date(trade.provider_observed_at_ms).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
        latest.textContent='Kraken '+pending.symbol+' trade · '+time;
        meta.textContent='Provider time '+time+' · Quantity '+trade.quantity+' '+trade.quantity_currency+' · Test service. Identity and timestamps not independently verified.';
        window.dispatchEvent(new CustomEvent('cin:validated-trade',{detail:{provider:'kraken',symbol:pending.symbol,price:trade.price,observedAt:trade.provider_observed_at_ms}}));
      },250);
    } else if(type==='closed')ctx.end='closed';
    else if(type==='unavailable')ctx.end=d&&d.reason==='market_identity_unverified'?'unsupported':'unavailable';
  }
  async function attempt(){
    if(!enabled||document.hidden)return;const own=++generation,requestedSymbol=symbol;controller=new AbortController();const local=controller;
    status.textContent='Connecting to test service…';latest.textContent='Connecting · no trade received';
    meta.textContent='Contacting the public test stream. A sleeping free service may take a minute to respond.';
    let timedOut=false;const timer=setTimeout(()=>{timedOut=true;local.abort();},70000);
    try{
      const response=await fetch(endpoint+encodeURIComponent(requestedSymbol),{method:'GET',headers:{Accept:'text/event-stream'},credentials:'omit',cache:'no-store',signal:local.signal});clearTimeout(timer);
      if(!enabled||own!==generation)return;
      if(!response.ok){
        if(response.status===429||response.status===503){retry('Test service busy','The preview may be in its cooldown or another stream is connected.',true);return;}
        retry('Stream unavailable','Test service returned HTTP '+response.status+'. Check its branch and stream setting.',true,300000);return;
      }
      if(!response.body||!response.body.getReader||!(response.headers.get('content-type')||'').toLowerCase().includes('text/event-stream'))throw Error('Invalid event-stream response');
      const reader=response.body.getReader(),decoder=new TextDecoder(),ctx={ready:false,end:null,symbol:requestedSymbol};let buffer='',kind='',lines=[];
      while(enabled&&own===generation&&!ctx.end){
        let idleTimer;const idle=new Promise((_,reject)=>{idleTimer=setTimeout(()=>{local.abort();reject(Error('Stream idle timeout'));},40000);});
        let part;try{part=await Promise.race([reader.read(),idle]);}finally{clearTimeout(idleTimer);}
        if(part.done)break;buffer+=decoder.decode(part.value,{stream:true});if(buffer.length>65536)throw Error('Event stream exceeded buffer limit');
        let pos;while((pos=buffer.indexOf('\n'))>=0){let line=buffer.slice(0,pos);buffer=buffer.slice(pos+1);if(line.endsWith('\r'))line=line.slice(0,-1);
          if(!line){if(kind&&lines.length)eventHandler(kind,lines.join('\n'),ctx);kind='';lines=[];if(ctx.end)break;}
          else if(line.startsWith('event:'))kind=line.slice(6).trim();else if(line.startsWith('data:'))lines.push(line.slice(5).replace(/^ /,''));
        }
      }
      if(ctx.end)await reader.cancel().catch(()=>{});
      if(!enabled||own!==generation)return;
      if(ctx.end==='unsupported'){controller=null;clearVisual('Selected market unavailable');meta.textContent='Kraken did not confirm an active '+requestedSymbol+' spot market. Try another ticker.';resumeAfter=Date.now()+35000;}
      else if(ctx.end==='closed')retry('Preview session ended','Session ended normally. The app will reconnect after the server cooldown.',false);
      else retry('Stream interrupted','No current trade is displayed. The app will retry the test service.',true);
    }catch(error){clearTimeout(timer);if(!enabled||own!==generation)return;
      retry(timedOut?'Connection timed out':'Stream interrupted','Cannot read the test stream. Check internet, test service, and browser access.',true);
    }
  }
  function start(){
    if(typeof fetch!=='function'||typeof TextDecoder!=='function'){status.textContent='Browser does not support streaming';return;}
    enabled=true;failures=0;button.textContent='Stop live stream';
    watch=setInterval(()=>{if(lastArrival&&Date.now()-lastArrival>30000){clearVisual('No recent trade · flow paused');meta.textContent='No recent public trade received. The test stream may be delayed or quiet.';}},5000);
    if(document.hidden){clearVisual('Waiting for app to open');meta.textContent='The test stream starts automatically when the app is visible.';}else attempt();
  }
  window.addEventListener('cin:chart-selection',event=>{
    const next=event.detail&&event.detail.symbol;if(typeof next!=='string'||!/^[A-Z0-9]{1,10}\/USD$/.test(next)||next===symbol)return;
    symbol=next;document.getElementById('stream-market').textContent='Kraken '+symbol+' · test service';generation++;if(controller){controller.abort();controller=null;}if(retryTimer){clearTimeout(retryTimer);retryTimer=null;}
    resumeAfter=Date.now()+35000;clearVisual(enabled?'Switching market · cooling down':'Disconnected');meta.textContent=enabled?'Switching to '+symbol+'. The stream restarts automatically after the server cooldown.':'Stream is stopped.';
    if(enabled&&!document.hidden){retryTimer=setTimeout(()=>{retryTimer=null;if(enabled&&!document.hidden)attempt();},35000);}
  });
  button.addEventListener('click',()=>{if(enabled)stop('Disconnected','The public test stream is disconnected for this app session.');else start();});
  document.addEventListener('visibilitychange',()=>{
    if(!enabled)return;
    if(document.hidden){
      generation++;if(controller){controller.abort();controller=null;}if(retryTimer){clearTimeout(retryTimer);retryTimer=null;}
      resumeAfter=Math.max(resumeAfter,Date.now()+35000);clearVisual('Paused while app hidden');
      meta.textContent='The public test stream resumes automatically when the app is visible and the cooldown ends.';
    } else {
      const delay=Math.max(0,resumeAfter-Date.now());
      if(delay){status.textContent='Waiting for cooldown · '+Math.ceil(delay/1000)+'s';retryTimer=setTimeout(()=>{retryTimer=null;if(enabled&&!document.hidden)attempt();},delay);}
      else attempt();
    }
  });
  start();
})();
