const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const usd=n=>n==null?'n/a':'$'+(n>=1?n.toLocaleString(undefined,{maximumFractionDigits:2}):n.toPrecision(3));
const big=n=>n==null?'n/a':'$'+Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:2}).format(n);
const pct=n=>n==null?'n/a':(n>=0?'▲ +':'▼ ')+n.toFixed(2)+'%';
let coins=[],view='all',sortKey='market_cap',sortDir=-1,sel=null,days=30,chart=null,hist=null,show7=true,show30=true,meta={};
let watch=new Set(); try{watch=new Set(JSON.parse(localStorage.getItem('watch')||'[]'))}catch(e){}
const cols=[['★',null],['Name','name'],['Symbol','symbol'],['Price','price'],['24h %','change_24h'],['24h volume','volume_24h'],['Market cap','market_cap']];
$('#head').innerHTML=cols.map(([l,k])=>k?`<th scope="col"><button data-k="${k}">${l}</button></th>`:`<th scope="col">${l}</th>`).join('');
$('#head').onclick=e=>{const k=e.target.dataset.k;if(!k)return;sortDir=sortKey===k?-sortDir:-1;sortKey=k;render()};
async function api(path){let r;try{r=await fetch(path)}catch(e){throw new Error('Cannot reach the server')}
 const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||'Request failed ('+r.status+')');return j}
function banner(j,err){const b=$('#status');b.hidden=true;b.className='banner';
 if(err){b.hidden=false;b.classList.add('err');b.textContent='Market data unavailable: '+err+'. No prices are shown.';return}
 const m=[];if(j.source==='mock')m.push('MOCK MODE: synthetic data, not real market prices.');if(j.warning)m.push(j.warning);else if(j.stale)m.push('Data may be stale.');
 if(m.length){b.hidden=false;b.classList.add('warn');b.textContent=m.join(' ')}}
async function load(){$('#stamp').textContent='Loading…';
 try{const j=await api('/api/markets');coins=j.data;meta=j;banner(j);
  $('#stamp').textContent=`Source: ${j.source}. Fetched ${new Date(j.fetched_at).toLocaleString()}${j.stale?' (STALE)':''}.`;render();signals()}
 catch(e){coins=[];banner(null,e.message);$('#stamp').textContent='No data.';render()}}
function render(){let l=coins.filter(c=>{const q=$('#q').value.trim().toLowerCase();return !q||c.name.toLowerCase().includes(q)||c.symbol.toLowerCase().includes(q)});
 if(view==='watch')l=l.filter(c=>watch.has(c.id));if(view==='gain')l=l.filter(c=>c.change_24h>0);if(view==='lose')l=l.filter(c=>c.change_24h<0);
 l.sort((a,b)=>{const x=a[sortKey],y=b[sortKey];if(x==null)return 1;if(y==null)return -1;return(typeof x==='string'?x.localeCompare(y):x-y)*sortDir});
 $('#rows').innerHTML=l.map(c=>`<tr data-id="${esc(c.id)}" class="${c.id===sel?'sel':''}"><td><button class="star" data-w="${esc(c.id)}" aria-pressed="${watch.has(c.id)}" aria-label="Toggle watchlist for ${esc(c.name)}">${watch.has(c.id)?'★':'☆'}</button></td><td>${esc(c.name)}</td><td>${esc(c.symbol)}</td><td>${usd(c.price)}</td><td>${pct(c.change_24h)}</td><td>${big(c.volume_24h)}</td><td>${big(c.market_cap)}</td></tr>`).join('');
 const e=$('#empty');e.hidden=l.length>0;e.textContent=coins.length?'No coins match the current search or filter.':'No market data to display.'}
$('#rows').onclick=e=>{const w=e.target.dataset.w;if(w){watch.has(w)?watch.delete(w):watch.add(w);try{localStorage.setItem('watch',JSON.stringify([...watch]))}catch(_){}render();return}
 const tr=e.target.closest('tr');if(tr){sel=tr.dataset.id;render();loadChart()}};
$('#q').oninput=render;
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{view=b.dataset.view;document.querySelectorAll('.tabs button').forEach(x=>x.setAttribute('aria-pressed',x===b));render()});
document.querySelectorAll('#periods [data-d]').forEach(b=>b.onclick=()=>{days=+b.dataset.d;document.querySelectorAll('#periods [data-d]').forEach(x=>x.setAttribute('aria-pressed',x===b));if(sel)loadChart()});
for(const[id,k]of[['#t7','7'],['#t30','30']])$(id).onclick=e=>{const on=e.target.getAttribute('aria-pressed')!=='true';e.target.setAttribute('aria-pressed',on);if(k==='7')show7=on;else show30=on;drawChart()};
async function loadChart(){const c=coins.find(x=>x.id===sel);$('#coinname').textContent=c?c.name:sel;$('#chartnote').textContent='Loading history…';
 try{const j=await api(`/api/history/${encodeURIComponent(sel)}?days=${days}`);hist=j;drawChart();
  $('#chartnote').textContent=`${j.source==='mock'?'MOCK data. ':''}${j.data.points} daily points, last ${new Date(j.data.last_point_ts).toLocaleDateString()}. Volatility (daily returns): ${j.data.volatility_pct==null?'n/a':j.data.volatility_pct.toFixed(2)+'%'}.${j.stale?' STALE: '+(j.warning||'older than expected.'):''}`}
 catch(e){if(chart){chart.destroy();chart=null}hist=null;$('#chartnote').textContent='Chart unavailable: '+e.message}}
function drawChart(){if(!hist)return;const d=hist.data,L=d.t.map(t=>new Date(t).toLocaleDateString());if(chart)chart.destroy();
 const ds=[{label:'Price (USD)',data:d.price,borderColor:'#0b7285',pointRadius:0,borderWidth:2,yAxisID:'y',order:1}];
 if(show7)ds.push({label:'SMA 7',data:d.sma7,borderColor:'#b8860b',borderDash:[6,3],pointRadius:0,borderWidth:1.5,yAxisID:'y',order:1});
 if(show30)ds.push({label:'SMA 30',data:d.sma30,borderColor:'#7b3fa0',borderDash:[2,3],pointRadius:0,borderWidth:1.5,yAxisID:'y',order:1});
 ds.push({type:'bar',label:'Volume',data:d.volume,backgroundColor:'rgba(120,130,140,.35)',yAxisID:'v',order:2});
 chart=new Chart($('#chart'),{type:'line',data:{labels:L,datasets:ds},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},scales:{y:{position:'left',title:{display:true,text:'Price (USD)'}},v:{position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'Volume (USD)'},ticks:{callback:v=>big(v)}},x:{ticks:{maxTicksLimit:8}}}}})}
async function signals(){try{const a=await api('/api/active');$('#activerule').textContent=a.rule;
  $('#active').innerHTML=a.data.map(c=>`<li>${esc(c.name)} (${esc(c.symbol)}): 24h volume ${big(c.volume_24h)}</li>`).join('')||'<li>No data</li>'}catch(e){$('#active').innerHTML='<li>Unavailable: '+esc(e.message)+'</li>'}runScreen()}
async function runScreen(){const q=new URLSearchParams({min_change_24h:$('#p1').value,min_turnover:$('#p2').value,min_market_cap:$('#p3').value});
 try{const s=await api('/api/screen?'+q);$('#screenrule').textContent='Rule: '+s.rule;
  $('#screen').innerHTML=s.data.map(c=>`<tr><td>${esc(c.name)} (${esc(c.symbol)})</td><td>${pct(c.change_24h)}</td><td>${c.turnover.toFixed(3)}</td><td>${big(c.market_cap)}</td></tr>`).join('')||'<tr><td colspan="4">No coins meet this rule right now.</td></tr>'}
 catch(e){$('#screenrule').textContent='Screen unavailable: '+e.message;$('#screen').innerHTML=''}}
$('#run').onclick=runScreen;
$('#agent').onclick=async()=>{const o=$('#agentout');o.textContent='Agent running…';
 try{const a=(await api('/api/agent')).data;
  o.innerHTML='<ol>'+a.steps.map(s=>`<li>${esc(s)}</li>`).join('')+'</ol>'+a.report.map(r=>r.error?`<p><b>${esc(r.name)}</b>: ${esc(r.error)}</p>`:`<p><b>${esc(r.name)}</b> (${esc(r.symbol)}): last ${usd(r.last_price)}. Backtest error for ${r.horizon}-day-ahead over ${r.n_backtest} windows: naive ${r.mape.naive.toFixed(1)}%, 7-day average ${r.mape.ma.toFixed(1)}%, trend ${r.mape.trend.toFixed(1)}%. ${esc(r.verdict)}${r.forecast?` Forecast: ${usd(r.forecast.point)}, likely range ${usd(r.forecast.low)} to ${usd(r.forecast.high)} (from past errors; real prices can fall outside it).`:''}</p>`).join('')+`<p class="muted">${esc(a.disclaimer)}</p>`}
 catch(e){o.textContent='Agent unavailable: '+e.message}};load();setInterval(load,60000);
