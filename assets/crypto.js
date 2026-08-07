const keys=['window','venue','market','unit','refresh','total','count','poc','delta','ratio','health','coverage','breakdown','status','badge','fresh'];
const cryptoEls=Object.fromEntries(keys.map(k=>[k,document.getElementById('crypto-'+k)]));
const cryptoCanvas=document.getElementById('profile-canvas'),cryptoTip=document.getElementById('profile-tooltip');
const chartHost=document.getElementById('candle-chart');
const BINANCE_FAPI='https://fapi.binance.com';
let chart=null,candleSeries=null,volumeSeries=null,priceLines=[];
let detailData=null,rollupData=null,statusData=null,profileView=null,rangeReady=false;
const money=n=>n==null?'-':new Intl.NumberFormat('ko-KR',{notation:'compact',maximumFractionDigits:2}).format(n)+' USDT';
const price=n=>n==null?'-':new Intl.NumberFormat('ko-KR',{maximumFractionDigits:0}).format(n);
const dt=ms=>ms?new Date(ms).toLocaleString('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}):'-';
const ago=iso=>{if(!iso)return'-';const m=Math.round((Date.now()-new Date(iso).getTime())/60000);return m<1?'방금 전':m<60?`${m}분 전`:`${(m/60).toFixed(1)}시간 전`};
const cssVar=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const timeframe=()=>({15:'15m',30:'30m',60:'1h',240:'4h'})[cryptoEls.window.value];

function initChart(){
  const dark=matchMedia('(prefers-color-scheme: dark)').matches;
  chart=LightweightCharts.createChart(chartHost,{width:chartHost.clientWidth,height:chartHost.clientHeight,layout:{background:{type:'solid',color:dark?'#111827':'#ffffff'},textColor:dark?'#cbd5e1':'#52606d'},grid:{vertLines:{color:dark?'#233044':'#edf1f4'},horzLines:{color:dark?'#233044':'#edf1f4'}},rightPriceScale:{borderColor:dark?'#334155':'#d8dee4'},timeScale:{borderColor:dark?'#334155':'#d8dee4',timeVisible:true,secondsVisible:false},crosshair:{mode:LightweightCharts.CrosshairMode.Normal},handleScroll:true,handleScale:true});
  candleSeries=chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:'#16a070',downColor:'#d95757',borderVisible:false,wickUpColor:'#16a070',wickDownColor:'#d95757',priceFormat:{type:'price',precision:1,minMove:.1}});
  volumeSeries=chart.addSeries(LightweightCharts.HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:'volume',lastValueVisible:false,priceLineVisible:false});
  volumeSeries.priceScale().applyOptions({scaleMargins:{top:.82,bottom:0}});
  new ResizeObserver(()=>chart.applyOptions({width:chartHost.clientWidth,height:chartHost.clientHeight})).observe(chartHost);
  // The volume profile always tracks whatever range is currently visible -- zoom or
  // pan the candles and the profile bars recompute for exactly that window, same as
  // the built-in volume-profile tools on stock/crypto charting platforms.
  let debounceId=null;
  chart.timeScale().subscribeVisibleTimeRangeChange(range=>{
    if(!range)return;
    clearTimeout(debounceId);
    debounceId=setTimeout(()=>refreshProfileView(range.from*1000,range.to*1000),120);
  });
}

async function fetchJson(url,timeout=7000){const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(timeout)});if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()}
async function loadCandles(){
  // Binance's public futures klines endpoint is CORS-open and needs no server,
  // so the chart works the same on GitHub Pages and on localhost with no collector running.
  const rows=await fetchJson(`${BINANCE_FAPI}/fapi/v1/klines?symbol=BTCUSDT&interval=${timeframe()}&limit=300`,12000);
  const candles=rows.map(r=>({time:Math.floor(r[0]/1000),open:+r[1],high:+r[2],low:+r[3],close:+r[4],volume:+r[5]}));
  candleSeries.setData(candles.map(x=>({time:x.time,open:x.open,high:x.high,low:x.low,close:x.close})));
  volumeSeries.setData(candles.map(x=>({time:x.time,value:x.volume,color:x.close>=x.open?'rgba(22,160,112,.35)':'rgba(217,87,87,.35)'})));
  chart.timeScale().fitContent();
}

// Two tiers on disk: `detail` is 1-minute rows for the last ~72h (small enough to ship
// whole), `rollup` is 1-hour rows covering the full retention window. Price-bin totals
// are exact from either -- only the time-bucket width differs -- so we use detail for
// whatever slice of the requested range it covers and rollup for the rest, never both
// for the same instant (that would double-count).
async function loadBinData(){
  const [detail,rollup,status]=await Promise.all([
    fetchJson(`data/crypto_bins_recent.json?v=${Date.now()}`,15000),
    fetchJson(`data/crypto_bins_hourly.json?v=${Date.now()}`,15000),
    fetchJson(`data/crypto_status.json?v=${Date.now()}`,7000).catch(()=>({status:[]}))
  ]);
  detailData=detail;rollupData=rollup;statusData=status;rangeReady=true;
  cryptoEls.fresh.textContent=`스냅샷 생성 ${ago(detail.generated_at)}`;
  cryptoEls.badge.textContent='데이터 로드됨';
  const range=chart.timeScale().getVisibleRange();
  if(range)refreshProfileView(range.from*1000,range.to*1000);
}

function rowsInRange(payload,startMs,endMs){
  if(!payload)return[];
  const venues=payload.venues,markets=payload.markets,out=[];
  for(const b of payload.bins){
    const t=b[0];
    if(t<startMs||t>=endMs)continue;
    out.push({venue:venues[b[1]],market:markets[b[2]],price_bin:b[3],
      buy_base:b[4],sell_base:b[5],buy_quote:b[6],sell_quote:b[7],trade_count:b[8]});
  }
  return out;
}

function computeProfile(startMs,endMs,venueFilter,marketFilter){
  const detailFrom=detailData?.covers_from??Infinity;
  let rows=[];
  if(startMs<detailFrom)rows=rows.concat(rowsInRange(rollupData,startMs,Math.min(endMs,detailFrom)));
  rows=rows.concat(rowsInRange(detailData,Math.max(startMs,detailFrom),endMs));
  if(venueFilter&&venueFilter!=='all')rows=rows.filter(r=>r.venue===venueFilter);
  if(marketFilter&&marketFilter!=='all')rows=rows.filter(r=>r.market===marketFilter);

  const byPrice=new Map(),byVenue=new Map();
  for(const r of rows){
    const p=byPrice.get(r.price_bin)||{price_bin:r.price_bin,buy_base:0,sell_base:0,buy_quote:0,sell_quote:0,trade_count:0};
    p.buy_base+=r.buy_base;p.sell_base+=r.sell_base;p.buy_quote+=r.buy_quote;p.sell_quote+=r.sell_quote;p.trade_count+=r.trade_count;
    byPrice.set(r.price_bin,p);
    const vk=`${r.venue}|${r.market}`,v=byVenue.get(vk)||{venue:r.venue,market:r.market,buy_quote:0,sell_quote:0,trade_count:0};
    v.buy_quote+=r.buy_quote;v.sell_quote+=r.sell_quote;v.trade_count+=r.trade_count;
    byVenue.set(vk,v);
  }
  const bins=[...byPrice.values()].sort((a,b)=>a.price_bin-b.price_bin);
  for(const b of bins){b.total_quote=b.buy_quote+b.sell_quote;b.delta_quote=b.buy_quote-b.sell_quote}
  const poc=bins.reduce((best,x)=>!best||x.total_quote>best.total_quote?x:best,null);
  return{
    start_ms:startMs,end_ms:endMs,
    buy_quote:bins.reduce((s,x)=>s+x.buy_quote,0),sell_quote:bins.reduce((s,x)=>s+x.sell_quote,0),
    trade_count:bins.reduce((s,x)=>s+x.trade_count,0),
    poc:poc?poc.price_bin:null,bins,breakdown:[...byVenue.values()].sort((a,b)=>a.venue.localeCompare(b.venue)||a.market.localeCompare(b.market))
  };
}

function refreshProfileView(startMs,endMs){
  if(!rangeReady)return;
  profileView=computeProfile(startMs,endMs,cryptoEls.venue.value,cryptoEls.market.value);
  renderCrypto();
}

function valueArea(rows){
  if(!rows.length)return{};const target=rows.reduce((s,x)=>s+x.total_quote,0)*.7,pocIndex=rows.reduce((best,x,i)=>x.total_quote>rows[best].total_quote?i:best,0);let lo=pocIndex,hi=pocIndex,total=rows[pocIndex].total_quote;
  while(total<target&&(lo>0||hi<rows.length-1)){const below=lo>0?rows[lo-1].total_quote:-1,above=hi<rows.length-1?rows[hi+1].total_quote:-1;if(above>=below){hi++;total+=rows[hi].total_quote}else{lo--;total+=rows[lo].total_quote}}
  return{val:rows[lo].price_bin,vah:rows[hi].price_bin};
}
function setLevelLines(){
  priceLines.forEach(x=>candleSeries.removePriceLine(x));priceLines=[];if(!profileView?.bins?.length)return;const va=valueArea(profileView.bins);
  [{price:profileView.poc,title:'POC',color:'#e7a621',width:2},{price:va.vah,title:'VAH',color:'#6d5bd0',width:1},{price:va.val,title:'VAL',color:'#6d5bd0',width:1}].forEach(x=>{if(x.price!=null)priceLines.push(candleSeries.createPriceLine({price:x.price,color:x.color,lineWidth:x.width,lineStyle:LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title:x.title}))});
}
function renderCrypto(){
  const d=profileView;if(!d)return;
  const buy=d.buy_quote,sell=d.sell_quote,delta=buy-sell,total=buy+sell;
  cryptoEls.total.textContent=money(total);cryptoEls.count.textContent=`${new Intl.NumberFormat('ko-KR').format(d.trade_count||0)}건`;cryptoEls.poc.textContent=price(d.poc);cryptoEls.delta.textContent=money(delta);cryptoEls.delta.className=delta>=0?'pos':'neg';cryptoEls.ratio.textContent=total?`매수 ${(buy/total*100).toFixed(1)}% · 매도 ${(sell/total*100).toFixed(1)}%`:'체결 없음';
  const now=Date.now(),statusRows=statusData?.status||[],healthy=statusRows.filter(x=>now-(x.last_receive_ms||0)<120000).length;
  cryptoEls.health.textContent=`${healthy}/${statusRows.length||10}`;
  cryptoEls.coverage.textContent=`화면 표시 구간: ${dt(d.start_ms)} ~ ${dt(d.end_ms)}`;
  cryptoEls.breakdown.innerHTML=(d.breakdown||[]).length?d.breakdown.map(x=>`<tr><td>${x.venue}</td><td>${x.market==='spot'?'현물':'무기한선물'}</td><td>${money(x.buy_quote)}</td><td>${money(x.sell_quote)}</td><td class="${x.buy_quote-x.sell_quote>=0?'pos':'neg'}">${money(x.buy_quote-x.sell_quote)}</td><td>${new Intl.NumberFormat('ko-KR').format(x.trade_count)}</td></tr>`).join(''):'<tr><td colspan="6">이 구간·필터에 체결 데이터가 없습니다.</td></tr>';
  cryptoEls.status.innerHTML=statusRows.map(x=>{const stale=now-(x.last_receive_ms||0)>120000;return `<div class="status-item ${stale?'stale':''}"><b>${x.venue} · ${x.market==='spot'?'현물':'선물'}</b><span>${stale?'수신 지연':'정상'} · ${dt(x.last_trade_ms)}</span><span>오류 ${x.errors||0}회</span></div>`}).join('')||'<p class="muted">수집기를 실행하면 피드 상태가 표시됩니다.</p>';drawProfile();setLevelLines();
}
function profileGeom(){const r=cryptoCanvas.getBoundingClientRect(),dpr=devicePixelRatio||1,w=r.width,h=r.height;if(cryptoCanvas.width!==Math.round(w*dpr)||cryptoCanvas.height!==Math.round(h*dpr)){cryptoCanvas.width=Math.round(w*dpr);cryptoCanvas.height=Math.round(h*dpr)}const ctx=cryptoCanvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return{ctx,w,h,L:66,R:8,T:18,B:34}}
function drawProfile(){const g=profileGeom(),ctx=g.ctx,rows=profileView?.bins||[],unit=cryptoEls.unit.value;ctx.clearRect(0,0,g.w,g.h);ctx.font='11px system-ui';if(!rows.length){ctx.fillStyle=cssVar('--muted');ctx.fillText('표시할 체결 데이터가 없습니다 (줌/스크롤로 구간을 조정해보세요).',10,g.h/2);return}const max=Math.max(...rows.map(x=>unit==='quote'?x.total_quote:x.buy_base+x.sell_base)),barH=Math.max(3,Math.min(16,(g.h-g.T-g.B)/rows.length*.75)),step=(g.h-g.T-g.B)/rows.length;rows.forEach((x,i)=>{const y=g.h-g.B-(i+.5)*step,buy=unit==='quote'?x.buy_quote:x.buy_base,sell=unit==='quote'?x.sell_quote:x.sell_base,bw=(g.w-g.L-g.R)*buy/max,sw=(g.w-g.L-g.R)*sell/max;ctx.fillStyle='#2a9d71';ctx.fillRect(g.L,y-barH/2,bw,barH);ctx.fillStyle='#d7655b';ctx.fillRect(g.L+bw,y-barH/2,sw,barH);if(i%Math.max(1,Math.ceil(rows.length/14))===0||x.price_bin===profileView.poc){ctx.fillStyle=x.price_bin===profileView.poc?'#e7a621':cssVar('--muted');ctx.fillText(`${price(x.price_bin)}${x.price_bin===profileView.poc?' POC':''}`,4,y+4)}});ctx.fillStyle=cssVar('--muted');ctx.fillText(unit==='quote'?'체결대금 USDT':'체결량 BTC',g.L,g.h-8)}
cryptoCanvas.addEventListener('mousemove',e=>{if(!profileView?.bins?.length)return;const r=cryptoCanvas.getBoundingClientRect(),g=profileGeom(),i=Math.max(0,Math.min(profileView.bins.length-1,Math.floor((g.h-g.B-(e.clientY-r.top))/((g.h-g.T-g.B)/profileView.bins.length)))),x=profileView.bins[i];cryptoTip.hidden=false;cryptoTip.style.left=`${Math.min(g.w-210,e.clientX-r.left+10)}px`;cryptoTip.style.top=`${Math.max(4,e.clientY-r.top-60)}px`;cryptoTip.innerHTML=`<b>${price(x.price_bin)} USDT</b><br>매수 ${money(x.buy_quote)}<br>매도 ${money(x.sell_quote)}<br>Delta ${money(x.delta_quote)}`});
cryptoCanvas.addEventListener('mouseleave',()=>cryptoTip.hidden=true);new ResizeObserver(drawProfile).observe(cryptoCanvas);
[cryptoEls.venue,cryptoEls.market].forEach(x=>x.onchange=()=>{const r=chart.timeScale().getVisibleRange();if(r)refreshProfileView(r.from*1000,r.to*1000)});
cryptoEls.window.onchange=()=>loadCandles().catch(showError);
cryptoEls.unit.onchange=drawProfile;
cryptoEls.refresh.onclick=()=>Promise.all([loadCandles(),loadBinData()]).catch(showError);
function showError(error){cryptoEls.badge.textContent='데이터 없음';cryptoEls.fresh.textContent=error.message}
initChart();
Promise.all([loadCandles(),loadBinData()]).catch(showError);
setInterval(()=>loadBinData().catch(()=>{}),60000);
