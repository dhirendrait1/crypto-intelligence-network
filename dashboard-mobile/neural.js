/* Neural light paths pulse only for validated public trade events. */
(() => {
  'use strict';
  const names = {'Market candles':'Market','Technical analysis':'Analysis','Screening':'Screen','News':'News','Derivatives':'Derivatives'};
  const chips = new Map([...document.querySelectorAll('[data-flow-source]')].map(node => [node.dataset.flowSource,node]));
  const paths = [...document.querySelectorAll('[data-live-flow]')];
  let lastPulse = 0, timer;
  window.addEventListener('cin:source-status', event => {
    const d=event.detail||{};if(!Object.hasOwn(names,d.name))return;
    const chip=chips.get(d.name);if(!chip)return;chip.dataset.state=d.state;
    const mode=d.state==='Available'&&(d.dataMode==='cache'||d.dataMode==='stale_cache')?' · cached':'';
    chip.textContent=names[d.name]+' · '+(d.state==='Available'?'received':d.state==='Loading'?'checking':'unavailable')+mode;
  });
  window.addEventListener('cin:validated-trade', () => {
    const now=Date.now();if(now-lastPulse<750)return;lastPulse=now;
    clearTimeout(timer);for(const path of paths){path.classList.remove('active');void path.getBoundingClientRect();path.classList.add('active');}
    timer=setTimeout(()=>{for(const path of paths)path.classList.remove('active');},2400);
  });
  window.addEventListener('cin:stream-ended', () => {clearTimeout(timer);for(const path of paths)path.classList.remove('active');});
})();
