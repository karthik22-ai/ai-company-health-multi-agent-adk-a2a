/* AI Company HQ – Company dashboard, live department boards, work files, data access, floor map.
   Loaded in the order of js/manifest.json and served as one script (/ui/app.js). */
/* ================= COMPANY DASHBOARD (synthetic Australian health insurer) ================= */
const BIZ={day:null,inis:{},notes:[],clock:{running:false},tab:'over'};
const coEl=document.getElementById('co'),coBody=document.getElementById('coBody');
const fmtN=(v,d=0)=>v==null?'–':Number(v).toLocaleString('en-AU',{maximumFractionDigits:d,minimumFractionDigits:d});
const fmtP=(v,d=1)=>v==null?'–':(v*100).toFixed(d)+'%';
const money=v=>v==null?'–':(Math.abs(v)>=1e6?'$'+(v/1e6).toFixed(1)+'M':Math.abs(v)>=1e3?'$'+Math.round(v/1e3)+'k':'$'+Math.round(v));
function bizDay(m){
  BIZ.day=m;
  const dk=m.dept_kpis||{};for(const id in dk){if(R[id]&&R[id].team)R[id].team.kpis=dk[id]}
  const d=new Date(m.date+'T00:00:00');document.getElementById('bizdate').textContent='📅 '+d.toLocaleDateString('en-AU',{weekday:'short',day:'numeric',month:'short',year:'numeric'})+(m.last?` · ${fmtN(m.last.policies_in_force)} policies`:'');refreshSold();
  (m.alerts||[]).slice(0,0);
  if(coEl.style.display==='flex')renderCo();
  ROOMS.forEach(r=>r.board&&drawBoard(r));
  if(selDept)try{renderDetail()}catch(e){}
}
/* ---------- teams' work: files, data access, hires, meetings ---------- */
BIZ.files=[];BIZ.access={datasets:[],grants:[],pending:[]};BIZ.meetings=[];
const KIND={report:'Report',dashboard:'Dashboard',presentation:'Presentation',app:'App',minutes:'Minutes',brief:'Brief'};
const API=()=>wsUrl&&/^wss?:/.test(wsUrl)?wsUrl.replace(/^ws/,'http').replace(/\/ws(\?.*)?$/,''):'';
const aName=id=>AG[id]?AG[id].name:(id==='ceo'?'CEO (you)':id);
function bizFile(f,quiet){if(!f)return;const i=BIZ.files.findIndex(x=>x.id===f.id);if(i>=0)BIZ.files[i]=f;else BIZ.files.unshift(f);
  if(!quiet&&!RP.on){const p=AG[f.author];toast(`${f.icon} ${KIND[f.kind]||'File'} published`,`${aName(f.author)}: ${f.title}`,p?p.home.color:'#60a5fa',()=>openFile(f.id));log(`${f.icon} <b>${esc(aName(f.author))}</b> published ${KIND[f.kind]||'a file'} <b>${esc(f.title)}</b>`,p?p.home.color:'#60a5fa',p)}
  if(selDept===f.dept||(selAgent&&selAgent.id===f.author))renderDetail();if(coEl.style.display==='flex'&&BIZ.tab==='files')renderCo()}
function bizAccess(m){BIZ.access={datasets:m.datasets||[],grants:m.grants||[],pending:m.pending||[]};if(selDept==='data'||selDept==='it')renderDetail();if(coEl.style.display==='flex'&&BIZ.tab==='access')renderCo()}
function hireAgent(a,quiet){if(!a||AG[a.id])return AG[a&&a.id];const r=R[a.dept];if(!r||!r.team||r.seats.length>=8)return null;
  addSeat(r);r.team.people.push([a.name,a.role]);const p=spawnAgent(r,a.name,a.role,r.seats.length-1,a.id);
  try{p.g.traverse(o=>{if(o.isMesh)meshes.push(o)})}catch(e){}updateMonitor(p);
  if(!quiet&&!RP.on){p.sc=.001;toast('🤝 New hire',`${a.name} joined ${r.name} as ${a.role}`,r.color,()=>focusAgent(p.id));log(`🤝 <b>${esc(a.name)}</b> joined <b>${r.name}</b> as ${esc(a.role)}${a.hired_by?' · hired by '+esc(aName(a.hired_by)):''}`,r.color,p);say(p,'👋 Hi team!',4000)}
  renderLeft(true);try{renderMeet()}catch(e){}if(selDept===r.id)renderDetail();return p}
function meetingStarted(m){if(!RP.on)toast('📋 Meeting started',`${(m.attendees||[]).length} people in ${R[m.room]?R[m.room].name:m.room} · ${m.agenda}`,'#e2b714',()=>watchRoom(R[m.room]))}
function meetingDone(m){if(BIZ.meetings.some(x=>x.meeting===m.meeting))return;BIZ.meetings.unshift(m);if(m.quiet){(m.files||[]).forEach(f=>bizFile(f,true));return}(m.files||[]).forEach(f=>bizFile(f,true));const mins=(m.files||[]).find(f=>f.kind==='minutes')||(m.files||[])[0];
  toast('✅ Meeting finished',`${(m.files||[]).length} file(s): decks and minutes are ready to open and download`,'#2ee6a6',mins?()=>openFile(mins.id):null);
  log(`📋 Meeting on <b>${esc(m.agenda||'')}</b> finished · ${(m.files||[]).map(f=>f.icon+' '+esc(f.title)).join(', ')}`,'#e2b714')}
function filesHtml(list,title='Work files'){return `<h3 style="margin-top:12px">${title} <span>${list.length}</span></h3>`+(list.length?list.slice(0,14).map(f=>`<div class="frow" data-file="${f.id}" title="Open ${esc(f.title)}"><i>${f.icon}</i><div><b>${esc(f.title)}</b><small>${KIND[f.kind]||f.kind} · ${esc(aName(f.author).split(' ')[0])} · ${f.sim_date}</small></div></div>`).join(''):'<div class="hint">Nothing published yet.</div>')}
const RQ_HINT={bi:'e.g. a dashboard of cancellations by reason and plan',it:'e.g. an app to track the claims backlog by state',people:'e.g. hire a fraud analytics specialist for Claims',data:'e.g. review who can see HR and claims data',exec:'e.g. a one-page view of the strategy budget'};
function deptExtras(r){let h=filesHtml(BIZ.files.filter(f=>f.dept===r.id));
  h+=`<h3 style="margin-top:12px">Ask ${esc(r.name)}</h3><div class="crow"><input type="text" id="rqIn" placeholder="${RQ_HINT[r.id]||'e.g. analyse why this week changed and what to do'}"><button class="btn pri" data-act="rq">Send</button></div>`;
  if(r.id==='data'||r.id==='it')h+=accessHtml(true);return h}
function accessHtml(compact){const A2=BIZ.access,pend=A2.pending||[];
  let h=`<h3 style="margin-top:12px">Data access ${pend.length?`<span style="color:#f5b942">${pend.length} pending</span>`:''}</h3>`;
  h+=pend.length?pend.map(q=>`<div class="frow" style="cursor:default"><i>🔑</i><div style="flex:1"><b>${esc(aName(q.requester))} → ${esc(q.dataset_label)}</b><small>${esc(q.reason)}</small></div><button class="btn sm" data-acc="${q.id}" data-ok="1">Approve</button><button class="btn sm" data-acc="${q.id}" data-ok="0">Reject</button></div>`).join(''):'<div class="hint">No pending requests.</div>';
  h+=`<table class="acc"><tr><th>Dataset</th><th>Level</th><th>Who can read</th></tr>`+(A2.datasets||[]).map(d=>{const g=(A2.grants||[]).filter(x=>x.dataset===d.dataset).map(x=>aName(x.subject).split(' ')[0]);
    return `<tr><td>${esc(d.label)}</td><td><span class="sens ${d.sensitivity}">${d.sensitivity}</span></td><td>${d.default==='all'?'Everyone':(d.default||[]).join(', ')}${g.length?' <b>+ '+esc(g.join(', '))+'</b>':''}</td></tr>`}).join('')+'</table>';
  return h}
function accessDecision(id,ok){if(!(ws&&ws.readyState===1))return toast('Backend offline','Connect the backend to decide access requests.','#8691ab');emitWS({type:'access_decision',id,approve:ok,note:ok?'Approved by the CEO':'Rejected by the CEO'})}
function sendRequest(dept){const q=document.getElementById('rqIn'),t=q?q.value.trim():'';if(!t)return;if(!(ws&&ws.readyState===1))return toast('Backend offline','Connect the backend so the team can work on it.','#8691ab');
  emitWS({type:'request_work',dept,text:t});q.value='';toast('📨 Request sent',`${R[dept].name}: ${t}`,R[dept].color);log(`📨 You asked <b>${R[dept].name}</b>: ${esc(t)}`,R[dept].color)}
const fvEl=document.getElementById('fv');
function openFile(id){const f=BIZ.files.find(x=>x.id===id)||{id,title:id,kind:'report',author:'',sim_date:'',icon:'📄'};const base=API();
  if(!base)return toast('Backend needed','Open the app from the backend link to view and download work files.','#8691ab');
  document.getElementById('fvT').textContent=`${f.icon} ${f.title}`;
  document.getElementById('fvM').textContent=`${KIND[f.kind]||f.kind} · ${aName(f.author)}${AG[f.author]?' · '+AG[f.author].role:''} · company date ${f.sim_date} · ${f.id}`;
  const fm={presentation:[['pptx','PowerPoint'],['html','HTML deck'],['md','Markdown']],dashboard:[['html','HTML'],['csv','CSV data'],['pptx','PowerPoint']],app:[['html','HTML app'],['csv','Data CSV']],
    report:[['html','HTML'],['md','Markdown'],['pptx','PowerPoint'],['csv','Chart data']],minutes:[['html','HTML'],['md','Markdown']]}[f.kind]||[['html','HTML'],['json','JSON']];
  document.getElementById('fvD').innerHTML=`<a class="btn sm pri" href="${base}/api/files/${encodeURIComponent(f.id)}/view" target="_blank" rel="noopener">↗ Open in new tab</a>`+fm.map(([x,l])=>`<a class="btn sm" href="${base}/api/files/${encodeURIComponent(f.id)}/download?fmt=${x}" download>⬇ ${l}</a>`).join('');
  const fr=document.getElementById('fvF');fr.removeAttribute('src');fr.srcdoc='<body style="background:#0b1226;color:#8a97b4;font:14px system-ui;padding:24px">Loading…</body>';fvEl.classList.add('on');
  fetch(`${base}/api/files/${encodeURIComponent(f.id)}/view`).then(r=>{if(!r.ok)throw new Error(r.status);return r.text()}).then(h=>{fr.srcdoc=h})   // sandboxed: no access to this page
    .catch(e=>{fr.srcdoc=`<body style="background:#0b1226;color:#ff8a8a;font:14px system-ui;padding:24px">Could not load the file (${e.message}).</body>`})}
function closeFile(){fvEl.classList.remove('on');document.getElementById('fvF').srcdoc=''}
document.getElementById('fvX').onclick=closeFile;fvEl.onclick=e=>{if(e.target===fvEl)closeFile()};
function rFiles(){const ds=[...new Set(BIZ.files.map(f=>f.dept))];
  coBody.innerHTML=`<div style="display:flex;gap:8px;margin-bottom:10px"><select id="ffD"><option value="">All teams</option>${ds.map(d=>`<option value="${d}">${R[d]?R[d].name:d}</option>`).join('')}</select><select id="ffK"><option value="">All kinds</option>${Object.entries(KIND).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></div><div id="ffL"></div>`;
  const draw=()=>{const d=document.getElementById('ffD').value,k=document.getElementById('ffK').value,L=BIZ.files.filter(f=>(!d||f.dept===d)&&(!k||f.kind===k));
    document.getElementById('ffL').innerHTML=L.length?L.map(f=>`<div class="frow" data-file="${f.id}"><i>${f.icon}</i><div style="flex:1"><b style="max-width:none">${esc(f.title)}</b><small>${KIND[f.kind]||f.kind} · ${esc(aName(f.author))} · ${R[f.dept]?R[f.dept].name:f.dept} · ${f.sim_date}${f.meeting?' · meeting '+f.meeting:''}</small></div><small>${f.id}</small></div>`).join(''):'<div class="hint">No files yet. Reporting publishes on Fridays, IT ships an app on the 2nd, and every meeting leaves decks and minutes. You can also ask any team from its department panel.</div>'};
  document.getElementById('ffD').onchange=draw;document.getElementById('ffK').onchange=draw;draw()}
function rAccess(){coBody.innerHTML=`<div class="hint" style="margin-bottom:8px">The Data &amp; Actuarial team owns data access. Agents can only query the datasets they have access to; others must request it with a business reason.</div>`+accessHtml(false)}
coBody.addEventListener('click',e=>{const fr=e.target.closest('[data-file]');if(fr){openFile(fr.dataset.file);return}const ac=e.target.closest('[data-acc]');if(ac)accessDecision(+ac.dataset.acc,ac.dataset.ok==='1')});

/* ---------- live department boards ---------- */
const BOARD_SERIES={exec:['net_adds','Net adds / day',v=>fmtN(v)],sales:['new_sales','New sales / day',v=>fmtN(v)],mkt:['new_sales','New sales / day',v=>fmtN(v)],
  data:['loss_ratio','Loss ratio',v=>fmtP(v)],claims:['claims_backlog','Claims backlog',v=>fmtN(v)],care:['avg_wait_s','Avg call wait (s)',v=>fmtN(v)],
  health:['loss_ratio','Loss ratio',v=>fmtP(v)],people:['engagement','Engagement',v=>fmtN(v)],prod:['margin','Margin',v=>fmtP(v)],risk:['net_adds','Net adds / day',v=>fmtN(v)],
  bi:['new_sales','New sales / day',v=>fmtN(v)],it:['policies_in_force','Policies in force',v=>fmtN(v)]};
function drawBoard(r){const B=r.board;if(!B||!B.c)return;const c=B.c.getContext('2d'),W=640,H=240,t=performance.now()/1000,m=BIZ.day;c.setTransform(2,0,0,2,0,0);
  const bg=c.createLinearGradient(0,0,0,H);bg.addColorStop(0,'#0f1834');bg.addColorStop(1,'#080c1a');c.fillStyle=bg;c.fillRect(0,0,W,H);
  c.fillStyle=r.color;c.fillRect(0,0,W,30);c.textBaseline='middle';c.textAlign='left';c.fillStyle='#0b1226';c.font='800 16px system-ui,sans-serif';c.fillText(r.name.toUpperCase(),12,16);
  c.textAlign='right';c.font='700 11px system-ui,sans-serif';c.fillText((m?new Date(m.date+'T00:00:00').toLocaleDateString('en-AU',{weekday:'short',day:'numeric',month:'short'})+'  ·  ':'')+(ws&&ws.readyState===1?'● LIVE':'○ OFFLINE'),W-12,16);
  (r.team.kpis||[]).slice(0,3).forEach((k,i)=>{const x=10+i*210;c.fillStyle='#ffffff0d';c.fillRect(x,38,200,52);c.fillStyle=r.color;c.fillRect(x,38,3,52);
    c.textAlign='left';c.fillStyle='#8a97b4';c.font='600 11px system-ui,sans-serif';c.fillText(k[0],x+12,51);c.fillStyle='#fff';c.font='800 24px system-ui,sans-serif';c.fillText(k[1],x+12,74)});
  // chart
  const [key,label,fmt]=BOARD_SERIES[r.id]||['net_adds','Net adds',v=>fmtN(v)],pts=(m&&m.series&&m.series[key])||[],cx=10,cy=100,cw=370,chh=130;
  c.fillStyle='#ffffff08';c.fillRect(cx,cy,cw,chh);c.textAlign='left';c.fillStyle='#aab3c8';c.font='700 11px system-ui,sans-serif';c.fillText(label+' · last 60 days',cx+8,cy+12);
  if(pts.length>1){const vs=pts.map(p=>p.value),lo=Math.min(...vs),hi=Math.max(...vs),rg=hi-lo||1,X=i=>cx+10+i*(cw-20)/(pts.length-1),Y=v=>cy+chh-12-(v-lo)/rg*(chh-40);
    c.beginPath();pts.forEach((p,i)=>i?c.lineTo(X(i),Y(p.value)):c.moveTo(X(i),Y(p.value)));c.strokeStyle=r.color;c.lineWidth=2;c.stroke();
    c.lineTo(X(pts.length-1),cy+chh-12);c.lineTo(X(0),cy+chh-12);c.closePath();const fg=c.createLinearGradient(0,cy,0,cy+chh);fg.addColorStop(0,r.color+'55');fg.addColorStop(1,r.color+'00');c.fillStyle=fg;c.fill();
    const lv=vs[vs.length-1];c.fillStyle='#fff';c.beginPath();c.arc(X(pts.length-1),Y(lv),3.5,0,7);c.fill();c.textAlign='right';c.font='800 13px system-ui,sans-serif';c.fillText(fmt(lv),cx+cw-8,cy+12);
    c.font='600 9px system-ui,sans-serif';c.fillStyle='#6b7896';c.textAlign='left';c.fillText(pts[0].date.slice(5),cx+8,cy+chh-4);c.textAlign='right';c.fillText(pts[pts.length-1].date.slice(5),cx+cw-8,cy+chh-4)}
  else{c.fillStyle='#4a5b8c';c.font='600 12px system-ui,sans-serif';c.fillText('Waiting for company data – start the backend',cx+8,cy+chh/2)}
  // team
  const tx=390,mem=agents.filter(a=>a.home===r).slice(0,5);c.fillStyle='#ffffff08';c.fillRect(tx,cy,240,chh);c.textAlign='left';c.fillStyle='#aab3c8';c.font='700 11px system-ui,sans-serif';
  const busy=mem.filter(a=>a.state==='working').length;c.fillText(`Team · ${busy}/${mem.length} working`,tx+8,cy+12);
  mem.forEach((a,i)=>{const y=cy+33+i*21,colr=STATE[a.state]||'#8691ab';c.fillStyle=colr;c.globalAlpha=a.state==='working'?.6+.4*Math.sin(t*4+i):1;c.beginPath();c.arc(tx+13,y,4,0,7);c.fill();c.globalAlpha=1;
    c.fillStyle='#e8ecf6';c.font='700 11px system-ui,sans-serif';c.fillText(a.name.split(' ')[0],tx+24,y);
    let txt=a.task?a.task.title:a.text||a.state;c.fillStyle='#8a97b4';c.font='500 10.5px system-ui,sans-serif';while(txt.length>3&&c.measureText(txt).width>160)txt=txt.slice(0,-2);if(txt!==(a.task?a.task.title:a.text||a.state))txt+='…';c.fillText(txt,tx+76,y)});
  B.t.needsUpdate=true}
let boardAcc=0;
let boardFocAcc=0;
function boardTick(dt){boardAcc+=dt;boardFocAcc+=dt;if(boardFocAcc>=.5){boardFocAcc=0;if(fp.on&&fp.zoomed&&fp.cur&&fp.room.board&&fp.cur.cv===fp.room.board.c)drawBoard(fp.room)}if(boardAcc<1.5)return;boardAcc=0;ROOMS.forEach(r=>{if(r.board&&vis(r.board.m))drawBoard(r)})}
ROOMS.forEach(r=>r.board&&drawBoard(r));
function bizIni(i){if(!i)return;BIZ.inis[i.id]=i;if(coEl.style.display==='flex'&&BIZ.tab==='dec')renderCo()}
function bizNote(n){if(!n)return;if(!BIZ.notes.find(x=>x.id===n.id&&x.id!=null))BIZ.notes.unshift(n);BIZ.notes=BIZ.notes.slice(0,80);if(coEl.style.display==='flex'&&BIZ.tab==='log')renderCo()}
function bizClock(m){BIZ.clock=m;const c=document.getElementById('clk');c.querySelector('[data-a=run]').classList.toggle('on',!!m.running);c.querySelector('[data-a=pause]').classList.toggle('on',!m.running);
  c.querySelector('[data-a=step]').disabled=!!m.running||!!m.busy;document.getElementById('bizdate').style.borderColor=m.busy?'#f5b942':'';document.getElementById('bizdate').title=m.busy?'Agents are working on this day…':'Simulated company date'}
document.getElementById('clk').onclick=e=>{const b=e.target.closest('button');if(!b)return;
  if(!(ws&&ws.readyState===1)){toast('Connect the backend','The company simulation runs in the Python backend (start it, then open the UI from http://127.0.0.1:8787).','#8691ab');return}
  const spd=+document.getElementById('clkSpd').value,ag=document.getElementById('clkAg').checked;
  emitWS(b.dataset.a==='run'?{type:'clock',action:'start',seconds_per_day:spd,agents:ag}:b.dataset.a==='pause'?{type:'clock',action:'pause'}:{type:'clock',action:'step',days:1,agents:ag})};
document.getElementById('clkSpd').onchange=()=>{if(ws&&ws.readyState===1)emitWS({type:'clock',action:'config',seconds_per_day:+document.getElementById('clkSpd').value})};
document.getElementById('clkAg').onchange=()=>{if(ws&&ws.readyState===1)emitWS({type:'clock',action:'config',agents:document.getElementById('clkAg').checked})};

function openCo(){coEl.style.display='flex';renderCo()}
function closeCo(){coEl.style.display='none'}
document.getElementById('bCo').onclick=()=>coEl.style.display==='flex'?closeCo():openCo();document.getElementById('coClose').onclick=closeCo;
document.getElementById('coTabs').onclick=e=>{const b=e.target.closest('button');if(!b)return;BIZ.tab=b.dataset.t;[...e.currentTarget.children].forEach(x=>x.classList.toggle('on',x===b));renderCo()};

function lineChart(cv,series,o={}){
  const dpr=Math.min(devicePixelRatio||1,2),W=cv.clientWidth*dpr,H=cv.clientHeight*dpr;if(!W||!H)return;cv.width=W;cv.height=H;const c=cv.getContext('2d');c.clearRect(0,0,W,H);
  const L=34*dpr,Rr=(series.some(s=>s.axis==='r')?38:8)*dpr,T=8*dpr,B=16*dpr,w=W-L-Rr,h=H-T-B;
  const ext=ax=>{const v=series.filter(s=>(s.axis||'l')===ax).flatMap(s=>s.points.map(p=>p.value));if(!v.length)return null;let a=Math.min(...v),b=Math.max(...v);if(a===b){a-=1;b+=1}const pad=(b-a)*.12;return [a-pad,b+pad]};
  const E={l:ext('l'),r:ext('r')};c.font=`${10*dpr}px system-ui`;c.fillStyle='#8691ab';c.strokeStyle='#26304a';c.lineWidth=1;
  for(let i=0;i<=3;i++){const y=T+h*i/3;c.beginPath();c.moveTo(L,y);c.lineTo(W-Rr,y);c.stroke();
    if(E.l){c.textAlign='right';c.fillText((o.fl||(v=>v.toFixed(0)))(E.l[1]-(E.l[1]-E.l[0])*i/3),L-4*dpr,y+3*dpr)}
    if(E.r){c.textAlign='left';c.fillText((o.fr||(v=>v.toFixed(0)))(E.r[1]-(E.r[1]-E.r[0])*i/3),W-Rr+4*dpr,y+3*dpr)}}
  const n=series[0]&&series[0].points.length||0;
  if(n){c.textAlign='left';c.fillText(series[0].points[0].date.slice(5),L,H-3*dpr);c.textAlign='right';c.fillText(series[0].points[n-1].date.slice(5),W-Rr,H-3*dpr)}
  series.forEach(s=>{const e=E[s.axis||'l'];if(!e)return;c.strokeStyle=s.color;c.lineWidth=1.8*dpr;c.beginPath();
    s.points.forEach((p,i)=>{const x=L+w*i/Math.max(n-1,1),y=T+h*(1-(p.value-e[0])/(e[1]-e[0]));i?c.lineTo(x,y):c.moveTo(x,y)});c.stroke();
    if(s.target!=null){const y=T+h*(1-(s.target-e[0])/(e[1]-e[0]));if(y>T&&y<T+h){c.setLineDash([4*dpr,4*dpr]);c.strokeStyle=s.color+'99';c.lineWidth=1*dpr;c.beginPath();c.moveTo(L,y);c.lineTo(W-Rr,y);c.stroke();c.setLineDash([])}}})
}
const CH=[
  {t:'Sales and cancellations / day',s:[['new_sales','Sales','#22d3ee'],['cancellations','Cancellations','#ff8a5c']],fl:v=>v.toFixed(0)},
  {t:'Loss ratio and margin',s:[['loss_ratio','Loss ratio','#f5b942','l',.87],['margin','Margin','#2ee6a6','r',.04]],fl:v=>(v*100).toFixed(0)+'%',fr:v=>(v*100).toFixed(1)+'%'},
  {t:'Claims within 5 days (%) and backlog',s:[['claims_sla_pct','SLA %','#b388ff','l',92],['claims_backlog','Backlog','#8691ab','r']],fl:v=>v.toFixed(0),fr:v=>fmtN(v/1000,1)+'k'},
  {t:'Call wait (s) and NPS',s:[['avg_wait_s','Wait','#60a5fa','l',150],['nps','NPS','#f472b6','r',28]],fl:v=>v.toFixed(0),fr:v=>v.toFixed(0)}
];
const TILES=[['policies_in_force','Policies in force',v=>fmtN(v/1000,1)+'k'],['new_sales_per_day','Sales / day',v=>fmtN(v)],['net_adds','Net adds / day',v=>(v>=0?'+':'')+fmtN(v),'net_adds'],
 ['loss_ratio','Loss ratio',v=>fmtP(v),'loss_ratio'],['margin','Margin',v=>fmtP(v),'margin'],['claims_sla_pct','Claims in SLA',v=>v.toFixed(1)+'%','claims_sla_pct'],
 ['avg_wait_s','Call wait',v=>v.toFixed(0)+'s','avg_wait_s'],['nps','NPS',v=>v.toFixed(0),'nps'],['engagement','Engagement',v=>v.toFixed(0),'engagement'],['headcount','Headcount',v=>fmtN(v)]];
function renderCo(){
  const m=BIZ.day;document.getElementById('coDate').textContent=m?`Simulated date ${m.date} · synthetic data`:'';
  if(!m){coBody.innerHTML='<div class="hint" style="padding:20px">No company data yet. Start the Python backend and open the UI from <code>http://127.0.0.1:8787</code>; it generates a year of history and then a new day of sales, claims and service data each simulated day.</div>';return}
  ({over:rOver,plans:rPlans,dec:rDec,team:rTeam,log:rLog,files:rFiles,access:rAccess,town:rTown})[BIZ.tab](m)
}
function rOver(m){
  const w=m.week||{},t=m.targets||{};
  coBody.innerHTML=`<div class="tiles">${TILES.map(([k,l,f,tk])=>{const tt=tk&&t[tk];return `<div class="tile ${tt?(tt.ok?'ok':'bad'):''}"><small>${l}</small><b>${w[k]==null?'–':f(w[k])}</b>${tt?`<em>target ${tk==='loss_ratio'||tk==='margin'?fmtP(tt.target,0):fmtN(tt.target)}</em>`:''}</div>`}).join('')}
   <div class="tile"><small>Strategy budget left</small><b>${money(m.budget.remaining)}</b><em>${m.budget.financial_year}</em></div></div>
   <div class="charts">${CH.map((c,i)=>`<div class="chart"><h4>${c.t}${c.s.map(s=>`<i style="color:${s[2]}">● ${s[1]}</i>`).join('')}</h4><canvas data-c="${i}"></canvas></div>`).join('')}</div>
   <div class="two"><div class="box"><h4>Alerts needing attention</h4>${(m.alerts||[]).length?(m.alerts).map(a=>`<div class="li"><span class="sev" style="background:${a.severity==='high'?'#ff6b6b':a.severity==='medium'?'#f5b942':'#8691ab'}"></span><b>${esc(R[a.dept]?R[a.dept].name:a.dept)}</b> · ${esc(a.message)}</div>`).join(''):'<div class="hint">All metrics are inside their thresholds.</div>'}</div>
   <div class="box"><h4>Market events and today</h4>${((m.events||[]).map(e=>`<div class="li">🌏 <b>${esc(e.name)}</b> until ${e.end}<br><span class="hint">${esc(e.desc)}</span></div>`).join(''))||'<div class="hint">No market events right now.</div>'}${(m.notes_today||[]).map(x=>`<div class="li">📅 ${esc(x)}</div>`).join('')}</div></div>`;
  requestAnimationFrame(()=>coBody.querySelectorAll('canvas[data-c]').forEach(cv=>{const c=CH[+cv.dataset.c];lineChart(cv,c.s.map(([k,n,col,ax,tg])=>({name:n,color:col,axis:ax||'l',target:tg,points:(m.series[k]||[])})),{fl:c.fl,fr:c.fr})}))
}
function rPlans(m){
  const ps=(m.products||[]).filter(p=>p.active),tot=ps.reduce((a,p)=>a+p.in_force,0)||1;
  coBody.innerHTML=`<div class="box"><h4>Plans we offer (${ps.length}) · prices are monthly for a single, before the government rebate</h4><table class="pl"><tr><th>Plan</th><th>Price</th><th>vs market</th><th>Members</th><th>Share</th><th>Sales 28d</th><th>Cancels 28d</th></tr>
   ${ps.map(p=>`<tr><td><b>${esc(p.name)}</b>${p.tier?`<span class="chipx ${p.tier}">${p.tier}</span>`:''}<span class="chipx">${p.category}</span><div class="hint" style="font-size:11px">${esc(p.target||'')}</div></td><td>$${p.monthly_price.toFixed(0)}</td><td style="color:${p.price_vs_market>1.01?'#ff6b6b':p.price_vs_market<.99?'#2ee6a6':'inherit'}">${(p.price_vs_market*100).toFixed(1)}%</td><td>${fmtN(p.in_force)}</td><td>${(p.in_force/tot*100).toFixed(1)}%</td><td>${fmtN(p.sales_28d)}</td><td>${fmtN(p.cancellations_28d)}</td></tr>`).join('')}</table></div>
   <p class="hint" style="margin-top:8px">Hospital plans use the government Gold / Silver / Bronze / Basic tiers. New plans proposed and approved by the agents appear here after their launch date.</p>`
}
const KCOLS=[['Proposed / in review',['proposed','in_review'],'#f5b942'],['Approved / running',['approved','running'],'#2ee6a6'],['Completed',['completed'],'#a3e635'],['Rejected / cancelled',['rejected','cancelled'],'#ff6b6b']];
function rDec(m){
  const all=Object.values(BIZ.inis).sort((a,b)=>(+b.id.slice(1))-(+a.id.slice(1)));
  if(!all.length){coBody.innerHTML='<div class="hint" style="padding:16px">No initiatives yet. Departments propose them in the weekly strategy cycle (Mondays); Risk &amp; Compliance and Finance challenge them and the CEO decides. Use “+1 day” on a Monday, or run the clock.</div>';return}
  coBody.innerHTML=`<div style="overflow:auto"><div class="kan">${KCOLS.map(([n,st,col])=>{const items=all.filter(i=>st.includes(i.status));
   return `<div class="kcol"><h4><span style="color:${col}">${n}</span><span>${items.length}</span></h4>${items.map(i=>{const c=i.compliance||{},own=(R[i.dept]&&R[i.dept].color)||'#8691ab',pa=AG[i.proposer];
    return `<div class="icard" data-i="${i.id}" style="--c:${own}"><b>${i.id} · ${esc(i.title)}</b><small>${esc(R[i.dept]?R[i.dept].name:i.dept)} · ${pa?esc(pa.name):esc(i.proposer)} · ${money(i.cost_est)}</small>
     <small>${c.ok===false?'⛔ breaks a rule':(c.warnings&&c.warnings.length?'⚠ '+c.warnings.length+' warning(s)':'✔ compliant')} · ${(i.reviews||[]).map(r=>({endorse:'👍',concerns:'⚠️',object:'⛔'})[r.verdict]).join(' ')}</small>
     ${i.start_date?`<small>${i.start_date}${i.end_date?' → '+i.end_date:''}</small>`:''}
     <div class="more"><div>${esc(i.headline||'')}</div><div style="margin-top:4px"><b>Why:</b> ${esc(i.rationale||'')}</div>${(i.reviews||[]).map(r=>`<div style="margin-top:4px"><b>${esc(AG[r.by]?AG[r.by].name:r.by)}</b> (${r.verdict}): ${esc(r.comments)}</div>`).join('')}
      ${(c.violations||[]).map(v=>`<div style="color:#ff6b6b;margin-top:4px">⛔ ${esc(v)}</div>`).join('')}${i.decision_note?`<div style="margin-top:4px"><b>Decision (${esc(AG[i.decided_by]?AG[i.decided_by].name:i.decided_by||'')}):</b> ${esc(i.decision_note)}</div>`:''}
      ${['proposed','in_review'].includes(i.status)?`<div class="btns" style="margin-top:6px"><button class="btn sm pri" data-bd="1" data-id="${i.id}">Board: approve</button><button class="btn sm" data-bd="0" data-id="${i.id}">Reject</button></div>`:''}</div></div>`}).join('')||'<div class="hint">—</div>'}</div>`}).join('')}</div></div>`
}
coBody.onclick=e=>{const b=e.target.closest('[data-bd]');if(b){if(!(ws&&ws.readyState===1))return;emitWS({type:'board_decision',id:b.dataset.id,approved:b.dataset.bd==='1'});return}
  const c=e.target.closest('.icard');if(c)c.classList.toggle('open')};
function rTeam(m){
  const t=m.team||{},depts=Object.keys(t);
  const bar=(v,max,col,txt)=>`<div><div class="meter"><i style="width:${Math.min(100,v/max*100)}%;background:${col}"></i></div><div class="mv">${txt}</div></div>`;
  coBody.innerHTML=`<div class="box"><h4>Workforce by department (the 3D agents lead and manage these teams)</h4><div class="bars"><div class="h">Department</div><div class="h">Headcount</div><div class="h">Utilisation</div><div class="h">Engagement</div><div class="h">Attrition (annualised)</div>
   ${depts.map(d=>{const x=t[d],col=(R[d]&&R[d].color)||'#8691ab',u=x.utilization;return `<div><b style="color:${col}">${esc(R[d]?R[d].name:d)}</b></div>
     ${bar(x.headcount,Math.max(...depts.map(k=>t[k].headcount)),col,`${fmtN(x.headcount)}${x.open_roles?` · +${x.open_roles} arriving`:''}${x.starters_ramping?` · ${x.starters_ramping} ramping`:''}`)}
     ${bar(u,1.4,u>1.05?'#ff6b6b':u>.95?'#f5b942':'#2ee6a6',(u*100).toFixed(0)+'%')}
     ${bar(x.engagement,100,x.engagement<65?'#ff6b6b':x.engagement<70?'#f5b942':'#2ee6a6',x.engagement.toFixed(0))}
     ${bar(x.attrition_annualised,.35,x.attrition_annualised>.2?'#ff6b6b':'#60a5fa',(x.attrition_annualised*100).toFixed(0)+'%')}`}).join('')}</div></div>
   <p class="hint" style="margin-top:8px">Utilisation over 100% means a team cannot keep up (queues, long waits, burnout). New starters take ~2 months to reach full productivity. People &amp; Culture proposes hiring, training and wellbeing programs; the executives decide.</p>`
}
function rLog(m){
  coBody.innerHTML=`<div class="box"><h4>Strategy log: briefs, investigations, decisions and lessons written by the agents</h4>${BIZ.notes.length?BIZ.notes.map(n=>`<div class="li"><b>${esc(n.title)}</b> <span class="chipx">${esc(n.kind)}</span><span class="hint"> · ${n.date} · ${esc(AG[n.author]?AG[n.author].name+' ('+AG[n.author].role+')':n.author)}</span><div style="color:#c4cbdb;margin-top:2px">${esc(n.body)}</div></div>`).join(''):'<div class="hint">The agents have not written anything yet.</div>'}</div>`
}
window.addEventListener('resize',()=>{if(coEl.style.display==='flex'&&BIZ.tab==='over')renderCo()});

/* ---------- test controls ---------- */
const cAgent=document.getElementById('cAgent'),cRoom=document.getElementById('cRoom');
cAgent.innerHTML=agents.map(p=>`<option value="${p.id}">${p.name} — ${p.role}</option>`).join('');
cRoom.innerHTML=ROOMS.map(r=>`<option value="${r.id}">${r.name} (L${r.floor+1})</option>`).join('');
const cur=()=>selAgent?selAgent.id:cAgent.value;
setInterval(()=>{if(selAgent&&cAgent.value!==selAgent.id&&document.activeElement!==cAgent)cAgent.value=selAgent.id},400);
document.getElementById('cMove').onclick=()=>HQ.move(cAgent.value,cRoom.value);
document.getElementById('cDesk').onclick=()=>HQ.desk(cAgent.value);
document.getElementById('cSet').onclick=()=>HQ.status(cAgent.value,document.getElementById('cState').value,document.getElementById('cText').value,{now:true});
document.getElementById('cSayB').onclick=()=>{const i=document.getElementById('cSay');if(i.value)HQ.say(cAgent.value,i.value);i.value=''};
document.getElementById('cReset').onclick=()=>{demoRun=false;agents.forEach(p=>{HQ.status(p,'idle','Idle');HQ.desk(p)})};
let demoRun=false;
document.getElementById('cDemo').onclick=async()=>{
  if(demoRun)return;demoRun=true;const w=(ms)=>sleep(ms).then(()=>{if(!demoRun)throw 0}),H=HQ;
  try{
    ['claims.helen','claims.victor','claims.tara','care.rafael','care.amira','sales.leo','sales.sara','data.arjun','data.chloe'].forEach((id,i)=>H.status(id,'working',['Clearing the claims backlog','Hospital claims review','Extras claims queue','Service-level check','Call-centre roster','Weekend sales review','Online conversion','Daily KPI pack','Pipeline health check'][i],{now:true}));
    H.task('claims.helen','Clear the claims backlog',30,'4,200 claims waiting');H.task('data.arjun','Daily KPI pack',70);H.task('sales.leo','Weekend sales review',20);H.system('claims','degraded','Slow assessment engine');await w(2500);H.say('data.arjun','Sales are +6% on forecast ✅');await w(2500);H.system('claims','ok');
    H.status('care.amira','blocked','Wait times above 8 minutes',{now:true});await w(8000);H.handoff('claims.victor','care.amira','Claims status script');await w(4500);H.handoff('data.arjun','sales.leo','Conversion by channel');await w(4500);
    H.status('care.amira','working','Roster adjusted',{now:true});
    H.meeting('mr2',['exec.priya','claims.helen','care.rafael','sales.leo','data.arjun'],'Daily trading huddle');await w(14000);H.endMeeting('mr2');await w(7000);
    ['claims.helen','care.rafael','sales.leo'].forEach(id=>H.status(id,'done','Actions agreed',{now:true,say:true}));
  }catch(e){}
  demoRun=false;
};

/* handoff + huddle controls */
const cTo=document.getElementById('cTo');cTo.innerHTML=agents.map(p=>`<option value="${p.id}">to ${p.name}</option>`).join('');
document.getElementById('cHand').onclick=()=>{if(cAgent.value!==cTo.value)HQ.handoff(cAgent.value,cTo.value,'Handoff pack')};
document.getElementById('cHuddle').onchange=e=>{policy.autoHuddle=e.target.checked};
/* API help */
document.getElementById('apidoc').textContent=`Agents stay still until commanded.
Send JSON over WebSocket (or SSE / postMessage / FinanceHQ.dispatch):

{"type":"move","agent":"sales.leo","room":"mr2","text":"Heading to review"}
{"type":"desk","agent":"sales.leo"}
{"type":"status","agent":"sales.leo","state":"working","text":"Weekend sales review"}
   state: idle | working | meeting | blocked | done | error
{"type":"say","agent":"sales.leo","text":"Sales review ready","ms":3500}
{"type":"task","agent":"sales.leo","title":"Weekend sales review","progress":40,"note":"Online conversion"}
{"type":"meeting","room":"mr1","agents":["claims.helen","mkt.grace"],"topic":"Daily trading huddle"}
{"type":"end_meeting","room":"mr1"}
{"type":"visit","agent":"sales.leo","target":"data.arjun","text":"Got a minute?"}
{"type":"handoff","from":"claims.helen","to":"mkt.grace","item":"Claims status script"}
{"type":"present","agent":"sales.leo","slides":[{"title":"Weekend sales","bullets":["Sales +6% vs forecast","Online conversion up"],"progress":60}]}
{"type":"summon","agents":["sales.leo","mkt.grace"],"room":"mr2","topic":"Demo for the CEO"}
{"type":"chat_reply","agent":"sales.leo","text":"The sales review is 60% done."}
{"type":"policy","autoHuddle":true}
task also accepts "id" and "status": todo | doing | blocked | done
{"type":"system","name":"erp","state":"ok|degraded|down","text":"…"}

Commands per agent run in order (queued).
Rooms: lob mr1 mr2 mr3 war brd + acct tre tax aud fpa rep data cfo ir sec
Agent IDs are <dept>.<firstname>, e.g. exec.priya, data.arjun.
Browser calls: FinanceHQ.move('sales.leo','mr2'), FinanceHQ.agents(), FinanceHQ.rooms()
UI → backend (when connected): hello, arrived, select, state, chat {agent,text}, summon {agents,room,topic}`;
document.getElementById('wsgo').onclick=()=>{const u=document.getElementById('wsurl').value.trim();if(u)connectWS(u)};
const qp=new URLSearchParams(location.search).get('ws');if(qp){document.getElementById('wsurl').value=qp;connectWS(qp)}

/* ================= FLOOR MAP ================= */
const mapC=document.getElementById('map'),mx=mapC.getContext('2d'),S=4.2,PAD=7;
const mxp=x=>(x+HW)*S+PAD,mzp=z=>(z+HD)*S+PAD;
function drawMap(){
  const f=curFloor,W=mapC.width,H=mapC.height;mx.clearRect(0,0,W,H);
  mx.fillStyle='#10172a';mx.fillRect(mxp(-HW),mzp(-HD),HW*2*S,HD*2*S);mx.strokeStyle='#7aa8ff';mx.lineWidth=1.5;mx.strokeRect(mxp(-HW),mzp(-HD),HW*2*S,HD*2*S);
  mx.fillStyle='#232d4a';mx.fillRect(mxp(-HW),mzp(-CZ),HW*2*S,CZ*2*S);mx.fillStyle='#1c2845';mx.fillRect(mxp(-4),mzp(-HD),8*S,(HD-CZ)*S);
  mx.fillStyle='#ffd77a';mx.font='bold 7px sans-serif';mx.textAlign='center';mx.fillText('LIFTS',mxp(0),mzp(-12));
  mx.fillStyle='#7aa8ff';mx.fillRect(mxp(HW)-2,mzp(-CZ),4,CZ*2*S);
  ROOMS.filter(r=>r.floor===f).forEach(r=>{
    const x=mxp(r.x0)+1,y=mzp(r.z0)+1,w=r.w*S-2,h=r.d*S-2,on=r.id===selDept||(selAgent&&selAgent.home===r);
    mx.fillStyle=r.color+(on?'66':'26');mx.fillRect(x,y,w,h);mx.strokeStyle=r.color;mx.lineWidth=on?2:1;mx.strokeRect(x,y,w,h);
    mx.fillStyle='#e8ecf6';mx.font='600 8px sans-serif';mx.textAlign='center';const nm=r.name.replace('Meeting Room','Meet');mx.fillText(nm.length>16?nm.split(' ')[0]:nm,x+w/2,r.north?y+11:y+h-5);
    const dx=mxp(r.cx),dy=r.north?mzp(r.z1):mzp(r.z0);mx.fillStyle=r.color;mx.fillRect(dx-6,dy-1.5,12,3)});
  agents.forEach(p=>{if(p.floor!==f||p.sc<.2)return;const x=mxp(p.g.position.x),y=mzp(p.g.position.z),sel=p===selAgent;
    mx.beginPath();mx.arc(x,y,sel?5:3.2,0,7);mx.fillStyle=p.home.color;mx.fill();mx.lineWidth=sel?2:1.4;mx.strokeStyle=sel?'#fff':stCol(p);mx.stroke()});
  const ang=Math.atan2(cam.position.x-controls.target.x,cam.position.z-controls.target.z),cx=mxp(Math.max(-HW,Math.min(HW,controls.target.x))),cy=mzp(Math.max(-HD,Math.min(HD,controls.target.z)));
  mx.save();mx.translate(cx,cy);mx.rotate(-ang+Math.PI);mx.fillStyle='#ffffff2a';mx.strokeStyle='#fff';mx.lineWidth=1;mx.beginPath();mx.moveTo(0,0);mx.lineTo(-14,-24);mx.lineTo(14,-24);mx.closePath();mx.fill();mx.stroke();mx.restore();
  mx.fillStyle='#f5b942';mx.font='bold 10px sans-serif';mx.textAlign='left';mx.fillText('Level '+(f+1),8,12);
}
setInterval(drawMap,120);
mapC.addEventListener('click',e=>{const b=mapC.getBoundingClientRect(),x=(e.clientX-b.left)/b.width*mapC.width,y=(e.clientY-b.top)/b.height*mapC.height,wx=(x-PAD)/S-HW,wz=(y-PAD)/S-HD;
  const rr0=ROOMS.find(r=>r.floor===curFloor&&wx>=r.x0&&wx<=r.x1&&wz>=r.z0&&wz<=r.z1);if(sendMode){if(rr0){sendAgent(sendMode,rr0.id);cancelSend()}return}
  const near=agents.filter(p=>p.floor===curFloor&&p.sc>.2).find(p=>Math.hypot(p.g.position.x-wx,p.g.position.z-wz)<1.5);if(near)return focusAgent(near.id);
  const r=ROOMS.find(r=>r.floor===curFloor&&wx>=r.x0&&wx<=r.x1&&wz>=r.z0&&wz<=r.z1);if(r)focusDept(r.id)});
