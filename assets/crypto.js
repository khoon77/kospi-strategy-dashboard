const keys=['window','venue','market','unit','refresh','total','count','poc','delta','ratio','health','coverage','breakdown','status','badge','fresh'];
const cryptoEls=Object.fromEntries(keys.map(k=>[k,document.getElementById('crypto-'+k)]));
const cryptoCanvas=document.getElementById('profile-canvas'),cryptoTip=document.getElementById('profile-tooltip');
const chartHost=document.getElementById('candle-chart');
const API='http://127.0.0.1:8765';
const BINANCE_FAPI='https://fapi.binance.com';
let cryptoData=null,chart=null,candleSeries=null,volumeSeries=null,priceLines=[];
const money=n=>n==null?'-':new Intl.NumberFormat('ko-KR',{notation:'compact',maximumFractionDigits:2}).format(n)+' USDT';
const btc=n=>n==null?'-':new Intl.NumberFormat('ko-KR',{maximumFractionDigits:3}).format(n)+' BTC';
const price=n=>n==null?'-':new Intl.NumberFormat('ko-KR',{maximumFractionDigits:0}).format(n);
const dt=ms=>ms?new Date(ms).toLocaleString('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}):'-';
const cssVar=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const timeframe=()=>({15:'15m',30:'30m',60:'1h',240:'4h'})[cryptoEls.window.value];

function initChart(){
  const dark=matchMedia('(prefers-color-scheme: dark)').matches;
  chart=LightweightCharts.createChart(chartHost,{width:chartHost.clientWidth,height:chartHost.clientHeight,layout:{background:{type:'solid',color:dark?'#111827':'#ffffff'},textColor:dark?'#cbd5e1':'#52606d'},grid:{vertLines:{color:dark?'#233044':'#edf1f4'},horzLines:{color:dark?'#233044':'#edf1f4'}},rightPriceScale:{borderColor:dark?'#334155':'#d8dee4'},timeScale:{borderColor:dark?'#334155':'#d8dee4',timeVisible:true,secondsVisible:false},crosshair:{mode:LightweightCharts.CrosshairMode.Normal},handleScroll:true,handleScale:true});
  candleSeries=chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:'#16a070',downColor:'#d95757',borderVisible:false,wickUpColor:'#16a070',wickDownColor:'#d95757',priceFormat:{type:'price',precision:1,minMove:.1}});
  volumeSeries=chart.addSeries(LightweightCharts.HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:'volume',lastValueVisible:false,priceLineVisible:false});
  volumeSeries.priceScale().applyOptions({scaleMargins:{top:.82,bottom:0}});
  new ResizeObserver(()=>chart.applyOptions({width:chartHost.clientWidth,height:chartHost.clientHeight})).observe(chartHost);
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

async function loadProfile(){
  const query=new URLSearchParams({minutes:cryptoEls.window.value,venue:cryptoEls.venue.value,market:cryptoEls.market.value});
  try{cryptoData=await fetchJson(`${API}/api/profile?${query}`,3000);cryptoData.live=true}
  catch(_){const payload=await fetchJson(`data/crypto_profile.json?v=${Date.now()}`,3000),windowData=payload.profiles?.[cryptoEls.window.value],key=`${cryptoEls.venue.value}|${cryptoEls.market.value}`;cryptoData=windowData?.[key]||windowData?.['all|all']||windowData;cryptoData.live=false}
  renderCrypto();
}
async function loadAll(){cryptoEls.badge.textContent='갱신 중';const results=await Promise.allSettled([loadCandles(),loadProfile()]);if(results[0].status==='rejected')cryptoEls.fresh.textContent=`캔들 연결 실패: ${results[0].reason.message}`;if(results[1].status==='rejected')throw results[1].reason}

function valueArea(rows){
  if(!rows.length)return{};const target=rows.reduce((s,x)=>s+x.total_quote,0)*.7,pocIndex=rows.reduce((best,x,i)=>x.total_quote>rows[best].total_quote?i:best,0);let lo=pocIndex,hi=pocIndex,total=rows[pocIndex].total_quote;
  while(total<target&&(lo>0||hi<rows.length-1)){const below=lo>0?rows[lo-1].total_quote:-1,above=hi<rows.length-1?rows[hi+1].total_quote:-1;if(above>=below){hi++;total+=rows[hi].total_quote}else{lo--;total+=rows[lo].total_quote}}
  return{val:rows[lo].price_bin,vah:rows[hi].price_bin};
}
function setLevelLines(){
  priceLines.forEach(x=>candleSeries.removePriceLine(x));priceLines=[];if(!cryptoData?.bins?.length)return;const va=valueArea(cryptoData.bins);
  [{price:cryptoData.poc,title:'POC',color:'#e7a621',width:2},{price:va.vah,title:'VAH',color:'#6d5bd0',width:1},{price:va.val,title:'VAL',color:'#6d5bd0',width:1}].forEach(x=>{if(x.price!=null)priceLines.push(candleSeries.createPriceLine({price:x.price,color:x.color,lineWidth:x.width,lineStyle:LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title:x.title}))});
}
function renderCrypto(){
  const d=cryptoData,buy=d.buy_quote??d.bins.reduce((s,x)=>s+x.buy_quote,0),sell=d.sell_quote??d.bins.reduce((s,x)=>s+x.sell_quote,0),delta=buy-sell,total=buy+sell;
  cryptoEls.total.textContent=money(total);cryptoEls.count.textContent=`${new Intl.NumberFormat('ko-KR').format(d.trade_count||0)}건`;cryptoEls.poc.textContent=price(d.poc);cryptoEls.delta.textContent=money(delta);cryptoEls.delta.className=delta>=0?'pos':'neg';cryptoEls.ratio.textContent=total?`매수 ${(buy/total*100).toFixed(1)}% · 매도 ${(sell/total*100).toFixed(1)}%`:'체결 없음';
  const now=Date.now(),healthy=(d.status||[]).filter(x=>now-(x.last_receive_ms||0)<120000).length;cryptoEls.health.textContent=`${healthy}/${(d.status||[]).length||10}`;cryptoEls.coverage.textContent=d.live?'로컬 실시간 수집':'최근 스냅샷';cryptoEls.badge.textContent=d.live?'실시간 연결':'최근 스냅샷';cryptoEls.fresh.textContent=new Date(d.generated_at||Date.now()).toLocaleString('ko-KR');
  cryptoEls.breakdown.innerHTML=(d.breakdown||[]).length?d.breakdown.map(x=>`<tr><td>${x.venue}</td><td>${x.market==='spot'?'현물':'무기한선물'}</td><td>${money(x.buy_quote)}</td><td>${money(x.sell_quote)}</td><td class="${x.buy_quote-x.sell_quote>=0?'pos':'neg'}">${money(x.buy_quote-x.sell_quote)}</td><td>${new Intl.NumberFormat('ko-KR').format(x.trade_count)}</td><td>${dt(x.first_minute)}~${dt(x.last_minute)}</td></tr>`).join(''):'<tr><td colspan="7">이 필터에 체결 데이터가 없습니다.</td></tr>';
  cryptoEls.status.innerHTML=(d.status||[]).map(x=>{const stale=now-(x.last_receive_ms||0)>120000;return `<div class="status-item ${stale?'stale':''}"><b>${x.venue} · ${x.market==='spot'?'현물':'선물'}</b><span>${stale?'수신 지연':'정상'} · ${dt(x.last_trade_ms)}</span><span>오류 ${x.errors||0}회</span></div>`}).join('')||'<p class="muted">수집기를 실행하면 피드 상태가 표시됩니다.</p>';drawProfile();setLevelLines();
}
function profileGeom(){const r=cryptoCanvas.getBoundingClientRect(),dpr=devicePixelRatio||1,w=r.width,h=r.height;if(cryptoCanvas.width!==Math.round(w*dpr)||cryptoCanvas.height!==Math.round(h*dpr)){cryptoCanvas.width=Math.round(w*dpr);cryptoCanvas.height=Math.round(h*dpr)}const ctx=cryptoCanvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return{ctx,w,h,L:66,R:8,T:18,B:34}}
function drawProfile(){const g=profileGeom(),ctx=g.ctx,rows=cryptoData?.bins||[],unit=cryptoEls.unit.value;ctx.clearRect(0,0,g.w,g.h);ctx.font='11px system-ui';if(!rows.length){ctx.fillStyle=cssVar('--muted');ctx.fillText('표시할 체결 데이터가 없습니다.',10,g.h/2);return}const max=Math.max(...rows.map(x=>unit==='quote'?x.total_quote:x.buy_base+x.sell_base)),barH=Math.max(3,Math.min(16,(g.h-g.T-g.B)/rows.length*.75)),step=(g.h-g.T-g.B)/rows.length;rows.forEach((x,i)=>{const y=g.h-g.B-(i+.5)*step,buy=unit==='quote'?x.buy_quote:x.buy_base,sell=unit==='quote'?x.sell_quote:x.sell_base,bw=(g.w-g.L-g.R)*buy/max,sw=(g.w-g.L-g.R)*sell/max;ctx.fillStyle='#2a9d71';ctx.fillRect(g.L,y-barH/2,bw,barH);ctx.fillStyle='#d7655b';ctx.fillRect(g.L+bw,y-barH/2,sw,barH);if(i%Math.max(1,Math.ceil(rows.length/14))===0||x.price_bin===cryptoData.poc){ctx.fillStyle=x.price_bin===cryptoData.poc?'#e7a621':cssVar('--muted');ctx.fillText(`${price(x.price_bin)}${x.price_bin===cryptoData.poc?' POC':''}`,4,y+4)}});ctx.fillStyle=cssVar('--muted');ctx.fillText(unit==='quote'?'체결대금 USDT':'체결량 BTC',g.L,g.h-8)}
cryptoCanvas.addEventListener('mousemove',e=>{if(!cryptoData?.bins?.length)return;const r=cryptoCanvas.getBoundingClientRect(),g=profileGeom(),i=Math.max(0,Math.min(cryptoData.bins.length-1,Math.floor((g.h-g.B-(e.clientY-r.top))/((g.h-g.T-g.B)/cryptoData.bins.length)))),x=cryptoData.bins[i];cryptoTip.hidden=false;cryptoTip.style.left=`${Math.min(g.w-210,e.clientX-r.left+10)}px`;cryptoTip.style.top=`${Math.max(4,e.clientY-r.top-60)}px`;cryptoTip.innerHTML=`<b>${price(x.price_bin)} USDT</b><br>매수 ${money(x.buy_quote)}<br>매도 ${money(x.sell_quote)}<br>Delta ${money(x.delta_quote)}`});
cryptoCanvas.addEventListener('mouseleave',()=>cryptoTip.hidden=true);new ResizeObserver(drawProfile).observe(cryptoCanvas);
[cryptoEls.venue,cryptoEls.market].forEach(x=>x.onchange=()=>loadProfile().catch(showError));cryptoEls.window.onchange=()=>loadAll().catch(showError);cryptoEls.unit.onchange=drawProfile;cryptoEls.refresh.onclick=()=>loadAll().catch(showError);
function showError(error){cryptoEls.badge.textContent='데이터 없음';cryptoEls.fresh.textContent=error.message;if(!cryptoData){cryptoData={bins:[],breakdown:[],status:[]};renderCrypto()}}
initChart();loadAll().catch(showError);setInterval(()=>loadAll().catch(()=>{}),30000);
