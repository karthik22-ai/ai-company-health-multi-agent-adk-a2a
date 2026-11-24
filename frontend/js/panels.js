/* AI Company HQ – Header, panels, details, chat, meetings, task board, replay, palette, backend connection.
   Loaded in the order of js/manifest.json and served as one script (/ui/app.js). */
/* ================= PANELS: every panel is switched on/off from the header ================= */
const PANELS=[
  {k:'plist',n:'Agents',t:'Agents, departments, rooms & meetings',i:'👥',col:'l',g:()=>document.querySelector('.col.l>.panel')},
  {k:'map',n:'Map',t:'Floor map',i:'🗺️',col:'l',g:()=>document.querySelector('.mapcard')},
  {k:'floors',n:'Floors',t:'Floor & view switcher',i:'🏬',g:()=>document.getElementById('floors')},
  {k:'bar',n:'Tools',t:'View tools (labels, lighting, quality…)',i:'🛠️',g:()=>document.querySelector('.mid>.bar')},
  {k:'detail',n:'Details',t:'Selected agent or department',i:'🔎',col:'r',g:()=>document.getElementById('detail')},
  {k:'feed',n:'Activity',t:'Live activity feed',i:'📰',col:'r',g:()=>document.getElementById('feed').closest('.panel')},
  {k:'sys',n:'Systems',t:'Core systems status',i:'🖥️',col:'r',g:()=>document.getElementById('sys').closest('.panel')},
  {k:'test',n:'Test',t:'Test controls (no backend needed)',i:'🧪',col:'r',g:()=>document.getElementById('cAgent').closest('.panel')},
  {k:'api',n:'API',t:'Backend connection & API',i:'🔌',col:'r',g:()=>document.getElementById('apidoc').closest('.panel')}];
const PK=Object.fromEntries(PANELS.map(P=>[P.k,P]));
let pHide={sys:true,test:true,api:true};
try{const v=JSON.parse(localStorage.getItem('hq-panels2')||'null');if(v&&typeof v==='object')pHide=v}catch(e){}
const pnav=document.getElementById('pnav');
const usable=P=>!P.avail||P.avail();
pnav.innerHTML=PANELS.map(P=>`<button data-p="${P.k}" title="${P.i} ${P.n}|${P.t} · click to show / hide"><i>${P.i}</i><span>${P.n}</span></button>`).join('')+
  '<span class="sep"></span><button data-a="town" title="🏘 Town|Wattle Grove: 100 residents choosing their health insurance"><i>🏘</i><span>Town</span></button><button data-a="apps" title="🧩 Apps|Open the apps IT has built"><i>🧩</i><span>Apps</span></button><button data-a="docs" title="📁 Documents|Every presentation, report, dashboard, app and set of minutes the agents made: open and download"><i>📁</i><span>Documents</span></button><button data-a="profile" title="🏢 Company profile|Who we are, people, health care, plans, market position"><i>🏢</i><span>Profile</span></button><button data-a="timeline" title="🕒 Timeline|Replay the company day by day: KPIs and everything that happened"><i>🕒</i><span>Timeline</span></button><button data-a="ops" title="📈 Ops|Live AI operations: model calls, quota, cost, every agent run traced, evaluations and weekly goals"><i>📈</i><span>Ops</span></button><button data-a="tour" title="❓ Tour|A quick guided tour of the app"><i>❓</i><span>Tour</span></button><button data-a="co" title="📊 Company|KPIs, plans, decisions, team health and the strategy log"><i>📊</i><span>Company</span></button><button data-a="board" title="📋 Tasks|Task board: queued, in progress, blocked, done"><i>📋</i><span>Tasks</span></button>'+
  '<button data-a="replay" title="⏪ Replay|Rewind and replay what happened"><i>⏪</i><span>Replay</span></button><button data-a="pal" title="🔍 Search ( / )|Find agents, departments, rooms and actions"><i>🔍</i><span>Search</span></button>';
function panelApply(){
  PANELS.forEach(P=>{const el=P.g();if(!el)return;el.classList.toggle('pmin',!!pHide[P.k])});
  pnav.querySelectorAll('button[data-p]').forEach(b=>{const P=PK[b.dataset.p];b.classList.toggle('on',!pHide[P.k]&&usable(P));b.classList.toggle('off',!usable(P));
    b.dataset.tip=P.k==='chat'?(selAgent?`💬 Chat|Chat with ${selAgent.name} · click to show / hide`:'💬 Chat|Select a person first, then chat with them here'):`${P.i} ${P.n}|${P.t} · click to show / hide${pHide[P.k]?'':' (shown)'}`});
  const B=document.body.classList;
  B.toggle('lcol0',PANELS.filter(P=>P.col==='l').every(P=>pHide[P.k]));B.toggle('rcol0',PANELS.filter(P=>P.col==='r').every(P=>pHide[P.k]));
  try{localStorage.setItem('hq-panels2',JSON.stringify(pHide))}catch(e){}
}
pnav.onclick=e=>{const b=e.target.closest('button');if(!b||b.classList.contains('off'))return;
  if(b.dataset.p){const k=b.dataset.p;pHide[k]=!pHide[k];panelApply();return}
  ({co:()=>openCo(),board:()=>openBoard(),replay:()=>replayOpen(),pal:()=>palOpen(),town:()=>goTown(),apps:()=>openApps(),docs:()=>openDocs(),profile:()=>openProfile(),timeline:()=>openTimeline(),ops:()=>openOps(),tour:()=>startTour()})[b.dataset.a]()};
PANELS.forEach(P=>{const el=P.g();if(!el)return;el.setAttribute('data-hx','');const b=document.createElement('button');b.className='hx';b.textContent='–';b.title=`Hide ${P.n} (bring it back from the header)`;
  b.onclick=e=>{e.stopPropagation();pHide[P.k]=true;panelApply()};
  el.appendChild(b);new MutationObserver(()=>{if(!el.contains(b))el.appendChild(b)}).observe(el,{childList:true})});
{let sig='';setInterval(()=>{const v=PANELS.map(P=>P.avail?+P.avail():'').join()+(selAgent?selAgent.id:'');if(v!==sig){sig=v;panelApply()}},400)}
panelApply();

/* ---------- instant tooltips for everything in the header ---------- */
{const hdr=document.querySelector('header'),tip=document.createElement('div');tip.id='htip';document.body.appendChild(tip);
  const tipify=()=>hdr.querySelectorAll('[title]').forEach(el=>{el.dataset.tip=el.getAttribute('title');el.removeAttribute('title')});tipify();
  const esc2=t=>String(t).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'})[c]);
  hdr.addEventListener('mouseover',e=>{tipify();const el=e.target.closest('[data-tip]');if(!el||!hdr.contains(el)){tip.style.display='none';return}
    const [a,b]=el.dataset.tip.split('|');tip.innerHTML=b?`<b>${esc2(a)}</b><small>${esc2(b)}</small>`:esc2(a);tip.style.display='block';
    const r=el.getBoundingClientRect(),tw=tip.offsetWidth;tip.style.left=Math.max(8,Math.min(innerWidth-tw-8,r.left+r.width/2-tw/2))+'px';tip.style.top=(r.bottom+8)+'px'});
  hdr.addEventListener('mouseleave',()=>tip.style.display='none');hdr.addEventListener('mousedown',()=>tip.style.display='none')}
/* ---------- panel transparency ---------- */
{const set=v=>{document.documentElement.style.setProperty('--pa',v/100);try{localStorage.setItem('hq-opa',v)}catch(e){}};let v=55;try{v=+localStorage.getItem('hq-opa')||55}catch(e){}
  const bar=document.querySelector('.mid>.bar'),l=document.createElement('label');l.className='opq';l.title='Panel transparency';l.innerHTML=`Panels <input type="range" id="pOpa" min="10" max="95" value="${v}">`;bar.appendChild(l);
  l.querySelector('input').oninput=e=>set(+e.target.value);set(v)}

/* ---------- focus mode: hide the header and every panel; peek the header from the top edge ---------- */
function setFocusMode(on){const B=document.body.classList;B.toggle('focusmode',on);B.remove('peek');
  if(on)toast('Focus mode','Header and panels are hidden. Move the mouse to the top edge to peek, press F or Esc to exit.','#60a5fa')}
const isFocus=()=>document.body.classList.contains('focusmode');
document.getElementById('bFocus').onclick=()=>setFocusMode(true);
document.getElementById('focusExit').onclick=()=>setFocusMode(false);
document.getElementById('peekZone').onmouseenter=()=>document.body.classList.add('peek');
document.querySelector('header').addEventListener('mouseleave',()=>{if(isFocus())setTimeout(()=>{if(!document.querySelector('header:hover'))document.body.classList.remove('peek')},250)});
function layToggleAll(){setFocusMode(!isFocus())}


/* ================= PANELS ================= */
const llist=document.getElementById('llist'),q=document.getElementById('q'),detail=document.getElementById('detail');let ltab='agents',lsig='';
document.getElementById('ltabs').onclick=e=>{const b=e.target.closest('button');if(b)showLeftTab(b.dataset.t)};
function showLeftTab(t){ltab=t;[...document.getElementById('ltabs').children].forEach(x=>x.classList.toggle('on',x.dataset.t===t));renderLeft(true)}
q.oninput=()=>renderLeft(true);
const stCol=p=>STATE[effState(p)];
function renderLeft(force){
  const isMeet=ltab==='meet';meetpane.style.display=isMeet?'flex':'none';llist.style.display=isMeet?'none':'';q.style.display=isMeet?'none':'';if(isMeet){if(force)renderMeet();return}
  const term=q.value.trim().toLowerCase();let html='',sig=ltab+term+(selAgent?selAgent.id:'')+(selDept||'');
  if(ltab==='agents'){
    const list=agents.filter(p=>!term||(p.name+p.role+p.id+p.home.name).toLowerCase().includes(term));
    list.forEach(p=>sig+=p.id+effState(p)+p.cur);
    html=list.map(p=>`<div class="row${p===selAgent?' sel':''}" data-agent="${p.id}" style="--c:${p.home.color}"><div class="av">${p.ini}</div><div class="t"><b>${p.name}</b><small>${p.role}</small></div><div class="meta"><i class="sdot" style="--s:${stCol(p)}"></i><br>${p.home.name.split(' ')[0]}</div></div>`).join('')||'<div class="hint">No match.</div>';
  }else if(ltab==='town'){
    const list=TOWN.residents.filter(r=>!term||(r.name+r.suburb+r.occupation+r.cover_label).toLowerCase().includes(term));
    sig+=TOWN.sig+list.length+(selRes||'');
    html=townShareHtml()+`<button class="btn sm" data-towngo style="width:100%;margin:2px 0 8px">▶ Let a few households review their cover now</button>`+
      (list.length?list.map(r=>`<div class="row${r.id===selRes?' sel':''}" data-res="${r.id}" style="--c:${insCol((r.cover||{}).insurer)}"><i class="dot"></i><div class="t"><b>${esc(r.name)}</b><small style="display:block">${r.age} · ${esc(r.gender||'')} · ${esc(r.occupation)} · ${esc(r.suburb)}</small><small style="display:block;color:#c4cbdb">${esc(r.cover_label)}</small></div></div>`).join(''):'<div class="hint">The town appears when the backend is connected.</div>');
  }else if(ltab==='depts'){
    const list=TEAMROOMS.filter(r=>!term||r.name.toLowerCase().includes(term));
    list.forEach(r=>sig+=r.id+agents.filter(p=>p.home===r&&p.state==='working').length);
    html=list.map(r=>{const m=agents.filter(p=>p.home===r),w=m.filter(p=>p.state==='working').length;return `<div class="row${r.id===selDept?' sel':''}" data-dept="${r.id}" style="--c:${r.color}"><i class="dot"></i><div class="t"><b>${r.name}<em>L${r.floor+1}</em></b><small>${r.team.lead} · ${m.length} agents</small></div><div class="meta">${w} working</div></div>`}).join('');
  }else{
    const list=SHARED.filter(r=>!term||r.name.toLowerCase().includes(term));
    list.forEach(r=>sig+=r.id+agents.filter(p=>p.cur===r.id).length);
    html=list.map(r=>{const n=agents.filter(p=>p.cur===r.id).length;return `<div class="row${r.id===selDept?' sel':''}" data-dept="${r.id}" style="--c:${r.color}"><i class="dot"></i><div class="t"><b>${r.name}<em>L${r.floor+1}</em></b><small>${r.seats?r.seats.length+' seats':r.desc}</small></div><div class="meta">${n} inside</div></div>`}).join('');
  }
  if(!force&&sig===lsig)return;lsig=sig;llist.innerHTML=html;
}
llist.onclick=e=>{if(e.target.closest('[data-towngo]')){townNow();return}const r=e.target.closest('.row');if(!r)return;if(r.dataset.res){selectResident(r.dataset.res);return}if(sendMode&&r.dataset.dept){sendAgent(sendMode,r.dataset.dept);cancelSend();return}if(r.dataset.agent)focusAgent(r.dataset.agent);else focusDept(r.dataset.dept)};

const stateText=(p,s)=>{if(p.moving)return '→ '+p.dest;const t=(p.text||'').trim();return !t||t.toLowerCase()===String(s).toLowerCase()?'':t};
const pct=v=>v==null?'':`<div class="bar2"><i style="width:${v}%"></i></div>`;
const logsFor=(f,n)=>activity.filter(f).slice(0,n).map(e=>`<div><time>${e.t.slice(0,5)}</time><div><span style="color:${e.color}">●</span> ${e.html}</div></div>`).join('')||'<div class="hint">No activity yet.</div>';
const DSCR=document.createElement('div');let lastDetail=null;
/* Build the panel off-screen and touch the real one only when something changed: rebuilding it on every event (twice a second)
   swapped the chat box and buttons under the cursor, so clicks and typing were lost. */
function renderDetail(){renderDetail0();const html=DSCR.innerHTML;if(html===lastDetail&&detail.childElementCount)return;lastDetail=html;
  const keep=['rqIn','rmIn','tkIn'].map(id=>{const q=document.getElementById(id);return q?[id,q.value,document.activeElement===q]:null}).filter(Boolean);detail.innerHTML=html;
  keep.forEach(([id,v,f])=>{const q2=document.getElementById(id);if(!q2)return;if(v)q2.value=v;if(f){q2.focus();q2.setSelectionRange(v.length,v.length)}});['convFeed','talkFeed'].forEach(id=>{const cf=document.getElementById(id);if(cf)cf.scrollTop=cf.scrollHeight})}
function renderDetail0(){
  if(selWp){DSCR.innerHTML=wpDetail(selWp);return}
  if(selRes&&TOWN.byId[selRes]){DSCR.innerHTML=resDetail(TOWN.byId[selRes]);return}
  const back='<button class="btn sm" data-act="back" style="margin-bottom:10px">← Back to building</button>';
  if(selAgent){const p=selAgent,s=effState(p),rm=R[p.cur],tk=p.task;detail.style.setProperty('--c',p.home.color);
    DSCR.innerHTML=`${back}<div class="head"><div class="av" style="--c:${p.home.color}">${p.ini}</div><div><h2>${p.name}</h2><div class="role">${p.role}</div></div></div>
    <div class="state" style="--s:${STATE[s]}"><i class="sdot" style="--s:${STATE[s]}"></i><b>${p.moving?'walking':s}</b><span>${stateText(p,s)}</span></div>${talkBox(p.id,p.name)}
    <h3>Current task</h3><div class="taskc">${tk?`<b>${tk.title}</b>${tk.note?`<small>${tk.note}</small>`:''}${tk.progress!=null?pct(tk.progress)+`<small>${Math.round(tk.progress)}% complete</small>`:''}`:'<span class="hint">No active task assigned.</span>'}</div>
    <h3>Work log</h3><div class="feed" style="max-height:170px;margin-bottom:10px">${logsFor(e=>e.agent===p.id,8)}</div>${filesHtml(BIZ.files.filter(f=>f.author===p.id),'Their work files')}${peopleExtras(p.id)}
    <dl><dt>Agent ID</dt><dd><code>${p.id}</code></dd><dt>Department</dt><dd>${p.home.name} · L${p.home.floor+1}</dd><dt>Location</dt><dd>${rm?rm.name+' · L'+(rm.floor+1):'In corridor'}</dd></dl>
    <div class="btns"><button class="btn pri" data-act="meet">Call to a meeting</button><button class="btn" data-act="fp">👁 Enter their room</button><button class="btn${tp.on?' on':''}" data-act="tp">${tp.on?'Third-person ✓':'Third-person view'}</button><button class="btn" data-act="desk">Send to desk</button><button class="btn" data-act="dept">Open department</button><button class="btn" data-act="copy">Copy ID</button></div>
    ${tp.on?'<p class="hint" style="margin-top:8px">Drag to look around · scroll to zoom.</p>':''}`;
  }else if(selDept){const r=R[selDept];detail.style.setProperty('--c',r.color);
    if(r.team){const m=agents.filter(p=>p.home===r),w=m.filter(p=>p.state==='working').length;
      DSCR.innerHTML=`${back}<div class="head"><div><h2 style="color:${r.color}">${r.name}</h2><div class="hint">Floor ${r.floor+1} · led by ${r.team.lead} · ${w}/${m.length} working</div></div></div><button class="btn pri" data-act="fp" style="margin:0 0 10px">👁 Enter room (first person)</button>
      <div class="mets">${r.team.kpis.map(k=>`<div class="met"><small>${k[0]}</small><b>${k[1]}</b></div>`).join('')}</div>
      <h3>What the team is doing</h3>
      ${m.map(p=>`<div class="row" data-agent="${p.id}" style="--c:${r.color}"><div class="av">${p.ini}</div><div class="t"><b>${p.name}</b><small style="display:block">${p.role}</small><small style="display:block;color:#c4cbdb">${p.moving?'→ '+p.dest:(p.task?p.task.title:stateText(p,p.state)||p.state)}</small>${p.task&&p.task.progress!=null?pct(p.task.progress):''}</div><i class="sdot" style="--s:${stCol(p)}"></i></div>`).join('')}
      <h3 style="margin-top:12px">Department activity</h3><div class="feed" style="max-height:170px">${logsFor(e=>e.dept===r.id,8)}</div>${deptExtras(r)}${roomTalk(r)}`}
    else{const m=agents.filter(p=>p.cur===r.id&&!p.lifting);
      DSCR.innerHTML=`${back}<div class="head"><div><h2 style="color:${r.color}">${r.name}</h2><div class="hint">Floor ${r.floor+1} · shared space${r.seats?' · '+r.seats.length+' seats':''}</div></div></div><button class="btn pri" data-act="fp" style="margin:0 0 10px">👁 Enter room (first person)</button><p class="hint">${r.desc}</p>
      ${m.length?m.map(p=>`<div class="row" data-agent="${p.id}" style="--c:${p.home.color}"><div class="av">${p.ini}</div><div class="t"><b>${p.name}</b><small>${p.role} · ${p.task?p.task.title:p.text}</small></div><i class="sdot" style="--s:${stCol(p)}"></i></div>`).join(''):'<div class="hint">Nobody inside right now.</div>'}${roomTalk(r)}${meetingResources(r)}`}
  }else DSCR.innerHTML='<div class="hint">Click a <b>department</b> to open just that department and see what its team is doing. Click an <b>agent</b> to see their task and work, and follow them in third-person view.</div>';
}
detail.onclick=e=>{const row=e.target.closest('.row[data-agent]');if(row){focusAgent(row.dataset.agent);return}
  const fr=e.target.closest('[data-file]');if(fr){openFile(fr.dataset.file);return}
  const ac=e.target.closest('[data-acc]');if(ac){accessDecision(+ac.dataset.acc,ac.dataset.ok==='1');return}
  if(e.target.closest('[data-act=rq]')){sendRequest(selDept);return}
  if(e.target.closest('[data-act=rm]')){sendRoomMsg();return}
  const hn=e.target.closest('[data-hnow]');if(hn){emitWS({type:'hand',room:selDept,agent:hn.dataset.hnow,action:'now'});return}
  const hl=e.target.closest('[data-hlow]');if(hl){emitWS({type:'hand',room:selDept,agent:hl.dataset.hlow,action:'lower'});return}
  const mn=e.target.closest('[data-mention]');if(mn){insertMention(mn.dataset.mention);return}
  const rs=e.target.closest('[data-res]');if(rs){selectResident(rs.dataset.res);return}
  const th=e.target.closest('[data-thread]');if(th){openThread(th.dataset.who,th.dataset.thread);return}
  const tk=e.target.closest('[data-act=tk]');if(tk){talkTo(tk.dataset.who);return}
  if(e.target.closest('[data-act=pref]')){const w=e.target.closest('[data-act=pref]').dataset.who;loadPeople(w,true);return}
  const b=e.target.closest('[data-act]');if(!b)return;const act=b.dataset.act;if(act==='back')return clearFocus();if(act==='fp')return enterRoom(selDept||(selAgent&&R[selAgent.cur]&&!selAgent.moving?selAgent.cur:selAgent&&selAgent.home.id));if(!selAgent)return;
  ({meet:()=>{meetSel.add(selAgent.id);showLeftTab('meet')},tp:()=>{setTP(!tp.on);if(!tp.on)follow=true;renderDetail()},desk:()=>sendHome(selAgent),dept:()=>focusDept(selAgent.home.id),copy:()=>{navigator.clipboard&&navigator.clipboard.writeText(selAgent.id);b.textContent='Copied'}})[act]()};

/* floor switcher */
const FNAME=['Claims, Care & Health','Growth, Data & Reporting','Leadership, Product, IT & Risk'],floorsEl=document.getElementById('floors');let fsig='';
function renderFloors(){
  const btn=(f,t,sm,on)=>`<button data-f="${f}" class="${on?'on':''}"><b>${t}</b><small>${sm}</small></button>`;
  const rows=[btn('ext','Exterior','Building from outside · E',mode==='ext'),btn('all','X-ray','See through every floor · X',mode==='xray')];
  [2,1,0].forEach(f=>{const here=agents.filter(p=>p.floor===f&&!p.lifting).length,w=agents.filter(p=>p.floor===f&&p.state==='working').length;
    rows.push(btn(f,`Level ${f+1} <span style="font-weight:500;opacity:.7">· open floor</span>`,`${FNAME[f]} · ${here} here${w?' · '+w+' working':''}`,mode==='one'&&curFloor===f))});
  const h=rows.join('');if(h!==fsig){fsig=h;floorsEl.innerHTML=h}
}
floorsEl.onclick=e=>{const b=e.target.closest('button');if(!b)return;follow=false;const f=b.dataset.f;f==='ext'?setView('ext'):f==='all'?setView('xray'):setView('one',+f);renderFloors()};

/* header stats + clock */
function tick(){
  const c=s=>agents.filter(p=>!p.moving&&p.state===s).length;
  const work=agents.filter(p=>p.state==='working').length,meet=agents.filter(p=>p.state==='meeting').length,bad=agents.filter(p=>p.state==='blocked'||p.state==='error').length,ok=SYS.filter(s=>s.state==='ok').length;
  document.getElementById('stats').innerHTML=`<div class="stat"><small>Working</small><b>${work}<i> / ${agents.length}</i></b></div><div class="stat"><small>In meetings</small><b>${meet}</b></div><div class="stat" data-k="blocked" style="cursor:pointer" title="Click to jump to a blocked agent"><small>Blocked</small><b style="color:${bad?'var(--bad)':'inherit'}">${bad}</b></div><div class="stat"><small>Systems OK</small><b>${ok}<i> / ${SYS.length}</i></b></div>`;
  document.getElementById('clock').textContent=new Date().toTimeString().slice(0,5);
  ROOMS.forEach(r=>{const here=agents.filter(p=>p.cur===r.id&&!p.lifting),own=here.filter(p=>p.home===r).length,vis=here.length-own;r.small.textContent=r.team?`${own}${vis?' +'+vis:''}`:`${here.length}`});
  agents.forEach(p=>{p.chip.style.setProperty('--s',stCol(p));p.chip.classList.toggle('sel',p===selAgent);p.chip.classList.toggle('dim',p.dim);p.chip.classList.toggle('alert',p.state==='blocked'||p.state==='error')});
  renderLeft();renderFloors();if(selAgent||selDept)renderDetail();
}
setInterval(tick,500);

/* ================= FEATURES UI ================= */
const toastsEl=document.getElementById('toasts');let soundOn=false;
function toast(title,msg,color='#f5b942',onclick){const d=document.createElement('div');d.className='toast';d.style.setProperty('--c',color);d.innerHTML=`<b>${esc(title)}</b><span>${esc(msg||'')}</span>`;
  d.onclick=()=>{d.remove();onclick&&onclick()};toastsEl.prepend(d);while(toastsEl.children.length>5)toastsEl.lastChild.remove();setTimeout(()=>d.remove(),9000)}
const approvals={};
function showApproval(m){hideApproval(m);const d=document.createElement('div');d.className='toast';d.style.setProperty('--c','#22d3ee');d.style.cursor='default';
  d.innerHTML=`<b>${esc(m.title||'Approval needed')}</b><span>${esc(m.summary||'')}</span><div style="display:flex;gap:6px;margin-top:8px"><button class="btn pri sm" data-a="1">Approve</button><button class="btn sm" data-a="0">Reject</button></div>`;
  d.onclick=e=>{const b=e.target.closest('button');if(!b)return;emitWS({type:'approval',run:m.run,approved:b.dataset.a==='1'});d.remove();delete approvals[m.run]};
  approvals[m.run]=d;toastsEl.prepend(d);beep('warn')}
function hideApproval(m){const d=approvals[m.run];if(d){d.remove();delete approvals[m.run]}}
function beep(kind){if(!soundOn)return;try{const ac=beep.ac||(beep.ac=new (window.AudioContext||window.webkitAudioContext)()),o=ac.createOscillator(),g=ac.createGain();o.type='sine';o.frequency.value=kind==='error'?330:kind==='warn'?440:620;g.gain.value=.05;o.connect(g);g.connect(ac.destination);o.start();o.stop(ac.currentTime+.2)}catch(e){}}
document.getElementById('bSound').onclick=e=>{soundOn=!soundOn;e.target.textContent='🔔 '+(soundOn?'On':'Off');e.target.classList.toggle('on',soundOn);if(soundOn)beep('ok')};
let blockCycle=0;document.getElementById('stats').onclick=e=>{if(!e.target.closest('[data-k=blocked]'))return;const bad=agents.filter(p=>p.state==='blocked'||p.state==='error');if(bad.length)focusAgent(bad[blockCycle++%bad.length].id)};
function beacon(p){if(p.bc)return p.bc;const g=new THREE.Group(),m=new THREE.MeshBasicMaterial({color:0xff4d4f,transparent:true,opacity:.9,side:THREE.DoubleSide,depthWrite:false});
  const ring=new THREE.Mesh(new THREE.RingGeometry(1.1,1.4,32),m);ring.rotation.x=-Math.PI/2;ring.position.y=.06;g.add(ring);
  const orb=new THREE.Mesh(new THREE.SphereGeometry(.2,10,8),new THREE.MeshBasicMaterial({color:0xff4d4f}));orb.position.y=4;g.add(orb);p.g.add(g);p.bc={g,ring,orb,m};return p.bc}
/* handoff flyers */
function startFlyer(a,b,item,o){
  const p0=a.g.position.clone();p0.y+=2.4;const p1=b.g.position.clone();p1.y+=2.4,mid=p0.clone().lerp(p1,.5);mid.y+=7+p0.distanceTo(p1)*.12;
  const curve=new THREE.QuadraticBezierCurve3(p0,mid,p1),doc=new THREE.Group();
  box(.6,.05,.78,M(0xffffff,{emissive:0xffffff,emissiveIntensity:.4}),0,0,0,doc,false);box(.6,.055,.14,M(a.home.color,{emissive:a.home.color,emissiveIntensity:.6}),0,.01,-.22,doc,false);
  doc.add(new THREE.Mesh(new THREE.SphereGeometry(.55,12,10),new THREE.MeshBasicMaterial({color:a.home.color,transparent:true,opacity:.25,depthWrite:false})));
  const trail=[...Array(14)].map((_,i)=>{const m=new THREE.Mesh(new THREE.SphereGeometry(.16-i*.008,6,5),new THREE.MeshBasicMaterial({color:a.home.color,transparent:true,opacity:.5-i*.03,depthWrite:false}));scene.add(m);return m});
  const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(40)),new THREE.LineDashedMaterial({color:a.home.color,dashSize:.6,gapSize:.5,transparent:true,opacity:.7}));line.computeLineDistances();scene.add(line,doc);
  flyers.push({doc,trail,line,curve,t0:performance.now(),dur:1800+p0.distanceTo(p1)*40,a,b,item,o:o||{}});
}
function finishFlyer(f){scene.remove(f.doc,f.line);f.trail.forEach(m=>scene.remove(m));
  const pos=f.b.g.position.clone();pos.y+=2.4;const m=new THREE.Mesh(new THREE.RingGeometry(.6,.8,32),new THREE.MeshBasicMaterial({color:f.a.home.color,transparent:true,opacity:.9,side:THREE.DoubleSide,depthWrite:false}));
  m.rotation.x=-Math.PI/2;m.position.set(pos.x,pos.y-2.3,pos.z);scene.add(m);pulses.push({m,t0:performance.now()});
  say(f.b,'📥 '+f.item,3200);
  if(!RP.on&&f.o.assign!==false){const busy=f.b.task&&f.b.task.status!=='done';HQ.task(f.b,f.item,0,'From '+f.a.name,{status:busy?'todo':'doing'})}}
/* chat */
const chatEl=document.getElementById('chat'),cMsgs=document.getElementById('cMsgs'),cIn=document.getElementById('cIn'),cHead=document.getElementById('cHead');
function renderChat(){const p=selAgent;chatEl.style.display=p?'flex':'none';if(!p)return;
  cHead.innerHTML=`<div class="av" style="--c:${p.home.color}">${p.ini}</div><div><b>${p.name}</b><small>${p.role} · ${ws&&ws.readyState===1?'live via backend':'simulated replies · connect a backend for real answers'}</small></div>`;
  cMsgs.innerHTML=(p.chat.length?p.chat.map(m=>`<div class="msg ${m.from==='you'?'you':'agent'}">${esc(m.text)}</div>`).join(''):'<div class="msg sys">Say hello, ask for a status update, or call them to a meeting to see their work.</div>')+(p.typing?'<div class="msg agent">…</div>':'');cMsgs.scrollTop=cMsgs.scrollHeight}
function sendChat(){const p=selAgent,t=cIn.value.trim();if(!p||!t)return;cIn.value='';HQ.chat(p,t)}
cIn.onkeydown=e=>{if(e.key==='Enter')sendChat();e.stopPropagation()};document.getElementById('cSend').onclick=sendChat;
document.getElementById('cChips').onclick=e=>{const b=e.target.closest('button');if(!b||!selAgent)return;const p=selAgent;
  if(b.dataset.c==='status')HQ.chat(p,'Give me a status update');else if(b.dataset.c==='block')HQ.chat(p,'Any blockers?');
  else if(b.dataset.c==='desk'){pushChat(p,'you','Please go back to your desk');sendHome(p)}
  else if(b.dataset.c==='meet'){const rm=freeRoom();pushChat(p,'you','Please come to a meeting and show me your work.');HQ.chatReply(p,`On my way to ${rm.name} — I'll walk you through it.`);HQ.summon([p.id],rm.id,'Demo for you')}};
/* meet pane */
const meetpane=document.getElementById('meetpane'),mRoom=document.getElementById('mRoom'),mTopic=document.getElementById('mTopic'),mDept=document.getElementById('mDept'),mq=document.getElementById('mq'),mList=document.getElementById('mList'),mInfo=document.getElementById('mInfo');
const MEETR=['mr1','mr2','mr3','brd'],meetSel=new Set();
mRoom.innerHTML=MEETR.map(id=>`<option value="${id}">${R[id].name} · L${R[id].floor+1} · ${R[id].seats.length} seats</option>`).join('');
mDept.innerHTML='<option value="">Add a whole department…</option>'+TEAMROOMS.map(r=>`<option value="${r.id}">${r.name}</option>`).join('');
function renderMeet(){const term=mq.value.trim().toLowerCase();
  mList.innerHTML=agents.filter(p=>!term||(p.name+p.role+p.home.name).toLowerCase().includes(term)).map(p=>`<label class="row" style="--c:${p.home.color}"><input type="checkbox" data-id="${p.id}" ${meetSel.has(p.id)?'checked':''}><div class="av">${p.ini}</div><div class="t"><b>${p.name}</b><small>${p.role}</small></div></label>`).join('');meetInfo()}
function meetInfo(){const r=R[mRoom.value];mInfo.textContent=`${meetSel.size} selected${meetSel.size>r.seats.length?' · room has '+r.seats.length+' seats, the rest will stand':''}`}
mList.onchange=e=>{const id=e.target.dataset.id;if(!id)return;e.target.checked?meetSel.add(id):meetSel.delete(id);meetInfo()};
mq.oninput=renderMeet;mRoom.onchange=meetInfo;
mDept.onchange=()=>{const d=mDept.value;if(d)agents.filter(p=>p.home.id===d).forEach(p=>meetSel.add(p.id));mDept.value='';renderMeet()};
document.getElementById('mClear').onclick=()=>{meetSel.clear();renderMeet()};
document.getElementById('mGo').onclick=()=>{if(RP.on)return toast('Replay mode','Go back to live first.','#60a5fa');if(!meetSel.size)return toast('Pick who to call','Select at least one agent.','#8691ab');
  const ag=document.getElementById('mAgenda').value.trim();HQ.summon([...meetSel],mRoom.value,mTopic.value.trim()||ag.slice(0,60)||'Meeting with you',{present:document.getElementById('mPresent').checked,agenda:ag});
  if(ag&&ws&&ws.readyState===1)toast('Meeting with an agenda','Each attendee prepares a deck from the live data, then presents on the room screen. Minutes follow.','#e2b714')};
document.getElementById('mEnd').onclick=()=>HQ.endMeeting(mRoom.value);
/* task board */
const boardEl=document.getElementById('board'),bCols=document.getElementById('bCols'),bDept=document.getElementById('bDept');let boardTimer=null;
bDept.innerHTML='<option value="">All departments</option>'+TEAMROOMS.map(r=>`<option value="${r.id}">${r.name}</option>`).join('');
const BCOLS=[['todo','Queued','#8691ab'],['doing','In progress','#2ee6a6'],['blocked','Blocked','#ff6b6b'],['done','Done','#a3e635']];
function renderBoard(){const d=bDept.value,list=tasks.filter(t=>!d||AG[t.agent].home.id===d);
  bCols.innerHTML=BCOLS.map(([k,n,c])=>{const items=list.filter(t=>t.status===k).sort((a,b)=>b.updated-a.updated);
    return `<div class="bcol"><h4><span style="color:${c}">${n}</span><span>${items.length}</span></h4><div class="bcards">${items.map(t=>{const p=AG[t.agent];return `<div class="bcard" data-a="${p.id}" style="--c:${p.home.color}"><b>${esc(t.title)}</b><small>${p.name} · ${p.role}</small>${t.note?`<small>${esc(t.note)}</small>`:''}${t.progress!=null?pct(t.progress):''}</div>`}).join('')||'<div class="hint">—</div>'}</div></div>`}).join('')}
function openBoard(){boardEl.style.display='flex';renderBoard();clearInterval(boardTimer);boardTimer=setInterval(renderBoard,1000)}
function closeBoard(){boardEl.style.display='none';clearInterval(boardTimer)}
document.getElementById('bBoard').onclick=()=>boardEl.style.display==='flex'?closeBoard():openBoard();
document.getElementById('bClose').onclick=closeBoard;bDept.onchange=renderBoard;
bCols.onclick=e=>{const c=e.target.closest('.bcard');if(c){closeBoard();focusAgent(c.dataset.a)}};
/* replay */
const replayPanel=document.getElementById('replay'),rpSeek=document.getElementById('rpSeek'),rpT=document.getElementById('rpT'),rpPlay=document.getElementById('rpPlay');
const fmt=ms=>{const t=Math.floor(ms/1000);return String(Math.floor(t/60)).padStart(2,'0')+':'+String(t%60).padStart(2,'0')};
function syncRP(){rpSeek.max=RP.dur;rpSeek.value=Math.min(RP.pos,RP.dur);rpT.textContent=fmt(RP.pos)+' / '+fmt(RP.dur);rpPlay.textContent=RP.playing?'⏸':'▶'}
function resetWorld(){
  agents.forEach(p=>{p.gen++;p.q=Promise.resolve();p.path=[];if(p.done){const f=p.done;p.done=null;f()}p.moving=false;p.dest=null;p.lifting=false;release(p);
    p.cur=p.home.id;p.floor=p.home.floor;p.g.position.set(p.seat.x,FY[p.floor]+TOP,p.seat.z);p.ang=p.angT=p.seat.ang;p.sit=p.sitT=1;p.sc=p.scT=p.base;
    p.state='idle';p.text='Idle';p.task=null;p.chat=[];p.typing=false;p.bubUntil=0;if(p.bub)p.bub.style.opacity=0;updateMonitor(p)});
  ROOMS.forEach(r=>{r.occ=[];if(r.scr)drawScreen(r,null)});tasks.length=0;SYS.forEach(sy=>{sy.state='ok';sy.text=''});renderSys();
  for(const k in meetings)delete meetings[k];for(const k in huddles)delete huddles[k];
  flyers.splice(0).forEach(f=>{scene.remove(f.doc,f.line);f.trail.forEach(m=>scene.remove(m))});renderChat()}
function applyEvent(ev,instant){
  const p=ev.agent?AG[ev.agent]:null;
  switch(ev.k){
    case'move':{if(!p)return;const r=R[ev.room];
      if(instant){p.cur=r.id;p.floor=r.floor;p.g.position.set(ev.x,FY[r.floor]+TOP,ev.z);p.path=[];p.moving=false;
        if(ev.ang!=null){p.ang=p.angT=ev.ang;p.sit=p.sitT=1}else{p.sit=p.sitT=0;p.ang=p.angT=ev.face?Math.atan2(ev.face.x-ev.x,ev.face.z-ev.z):Math.atan2(r.cx-ev.x,r.cz-ev.z)}}
      else queue(p,async()=>{const ok=await go(p,r.id,{x:ev.x,z:ev.z});if(!ok)return;if(ev.ang!=null){p.angT=ev.ang;p.sitT=1}else if(ev.face)face(p,ev.face.x,ev.face.z);else face(p,r.cx,r.cz)})}break;
    case'status':HQ.status(p,ev.state,ev.text,{now:instant||ev.now});break;
    case'task':HQ.task(p,ev.title,ev.progress,ev.note,{id:ev.id,status:ev.status});break;
    case'say':if(!instant)say(p,ev.text,ev.ms||3500);break;
    case'system':HQ.system(ev.name,ev.state,ev.text);break;
    case'handoff':if(!instant)startFlyer(A(ev.from),A(ev.to),ev.item,{replay:true,assign:false});break;
    case'screen':{const r=R[ev.room];if(r&&r.scr)drawScreen(r,ev.slide)}break;
    case'chat':pushChat(p,ev.from,ev.text);break}}
function replaySeek(t){applying=true;resetWorld();RP.idx=0;while(RP.idx<rec.length&&rec[RP.idx].t<=t){applyEvent(rec[RP.idx],true);RP.idx++}applying=false;RP.pos=Math.min(t,RP.dur);syncRP()}
function replayOpen(){if(!rec.length)return toast('Nothing to replay yet','Replay records everything that happens after the page loads.','#8691ab');
  RP.on=true;RP.playing=false;RP.pending=[];RP.dur=rec[rec.length-1].t+1500;replaySeek(0);replayPanel.style.display='flex';syncRP();toast('Replay mode','Live commands are paused and applied when you go back to live.','#60a5fa')}
function replayExit(){if(!RP.on)return;replaySeek(Infinity);RP.on=false;RP.playing=false;replayPanel.style.display='none';const pend=RP.pending;RP.pending=[];pend.forEach(m=>HQ.dispatch(m))}
rpPlay.onclick=()=>{if(RP.pos>=RP.dur)replaySeek(0);RP.playing=!RP.playing;syncRP()};
rpSeek.oninput=()=>replaySeek(+rpSeek.value);document.getElementById('rpLive').onclick=replayExit;
document.getElementById('rpSpd').onclick=e=>{const b=e.target.closest('button');if(!b)return;RP.speed=+b.dataset.s;[...e.currentTarget.children].forEach(x=>x.classList.toggle('on',x===b))};
document.getElementById('bReplay').onclick=()=>RP.on?replayExit():replayOpen();
/* command palette */
const palEl=document.getElementById('pal'),palIn=document.getElementById('palIn'),palList=document.getElementById('palList');let palAll=[],palCur=[],palSel=0;
function palItems(){const it=[];
  agents.forEach(p=>it.push({k:'Agent',label:p.name,sub:p.role+' · '+p.home.name,color:p.home.color,run:()=>focusAgent(p.id)}));
  TEAMROOMS.forEach(r=>it.push({k:'Department',label:r.name,sub:'Level '+(r.floor+1)+' · '+r.team.lead,color:r.color,run:()=>focusDept(r.id)}));
  SHARED.forEach(r=>it.push({k:'Room',label:r.name,sub:'Level '+(r.floor+1),color:r.color,run:()=>focusDept(r.id)}));
  TEAMROOMS.concat(SHARED).forEach(r=>it.push({k:'Room view',label:r.name+' – first person',sub:'Stand inside the room, talk to people, focus on screens',color:r.color,run:()=>enterRoom(r.id)}));
  [['Exterior view','Show the building from outside',()=>setView('ext')],['X-ray view','See through every floor',()=>setView('xray')],['Open Level 1','Accounting & Treasury',()=>setView('one',0)],['Open Level 2','Planning & Data',()=>setView('one',1)],['Open Level 3','Executive & Security',()=>setView('one',2)],
   ['Company dashboard','KPIs, plans, decisions, team',openCo],['Task board','Queued, in progress, blocked, done',openBoard],['Replay','Rewind and replay what happened',replayOpen],['Call a meeting','Summon agents to a meeting room',()=>showLeftTab('meet')],
   ['Night mode','Lighting',()=>document.querySelector('#tod [data-t=night]').click()],['Day mode','Lighting',()=>document.querySelector('#tod [data-t=day]').click()],['Auto time of day','Follow local time',()=>document.querySelector('#tod [data-t=auto]').click()],['Clear focus','Back to the previous view',clearFocus]]
   .forEach(([l,sb,run])=>it.push({k:'Action',label:l,sub:sb,color:'#f5b942',run}));return it}
function palRender(){const q=palIn.value.trim().toLowerCase().split(/\s+/).filter(Boolean);palCur=palAll.filter(i=>q.every(w=>(i.label+' '+i.sub+' '+i.k).toLowerCase().includes(w))).slice(0,14);palSel=Math.min(palSel,Math.max(0,palCur.length-1));
  palList.innerHTML=palCur.map((i,n)=>`<div class="row${n===palSel?' on':''}" data-n="${n}" style="--c:${i.color||'#8691ab'}"><i class="dot"></i><div class="t"><b>${esc(i.label)}</b><small>${esc(i.sub||'')}</small></div><span class="k">${i.k}</span></div>`).join('')||'<div class="hint" style="padding:8px">No results.</div>'}
function palOpen(){palEl.style.display='flex';palIn.value='';palSel=0;palAll=palItems();palRender();palIn.focus()}
function palClose(){palEl.style.display='none'}
palIn.oninput=()=>{palSel=0;palRender()};
palIn.onkeydown=e=>{if(e.key==='ArrowDown'){palSel=Math.min(palCur.length-1,palSel+1);palRender();e.preventDefault()}else if(e.key==='ArrowUp'){palSel=Math.max(0,palSel-1);palRender();e.preventDefault()}
  else if(e.key==='Enter'){const i=palCur[palSel];if(i){palClose();i.run()}}else if(e.key==='Escape')palClose();e.stopPropagation()};
palList.onclick=e=>{const r=e.target.closest('.row');if(r){const i=palCur[+r.dataset.n];palClose();i&&i.run()}};palEl.onclick=e=>{if(e.target===palEl)palClose()};
document.getElementById('bPal').onclick=palOpen;
