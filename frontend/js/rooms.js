/* AI Company HQ – Room records, conversations with @mentions and raise-hand turns; the apps launcher.
   Loaded in the order of js/manifest.json and served as one script (/ui/app.js). */
/* ================= ROOMS: records, conversations, raise-hand turns ================= */
const ROOMLOG={},HANDS={},SPEAK={};
function loadRoomLog(room){const base=API();if(!base)return;fetch(`${base}/api/rooms/${room}/log?limit=150`).then(r=>r.json()).then(rows=>{ROOMLOG[room]=rows;if(selDept===room)renderDetail()}).catch(()=>{})}
const RICON={user:'🧑‍💼',speech:'🗣',say:'💬',chat:'💬',present:'📊',enquiry:'☎️',meeting:'📋'};
function convLine(e){const who=e.speaker==='ceo'?'You':e.speaker==='system'?'':AG[e.speaker]?AG[e.speaker].name:e.speaker,col=e.speaker==='ceo'?'#f5b942':AG[e.speaker]?AG[e.speaker].home.color:'#c4cbdb';
  return `<div class="cl ${e.kind}"><b style="color:${col}">${esc(who)}</b> <small>${RICON[e.kind]||''} ${e.sim_date?e.sim_date.slice(5):''}</small><div>${md1(e.text)}</div></div>`}
function roomLog(e){if(!e)return;const L=ROOMLOG[e.room]||(ROOMLOG[e.room]=[]);L.push(e);if(L.length>300)L.shift();
  if(selDept===e.room){const cf=document.getElementById('convFeed');if(cf){cf.insertAdjacentHTML('beforeend',convLine(e));const h=cf.querySelector('.hint');if(h)h.remove();cf.scrollTop=cf.scrollHeight}}}
function handsHtml(room){const q=HANDS[room]||[],sp=SPEAK[room];if(!q.length)return '<div class="hands" id="handsBox"><span class="hint">No hands raised. Mention someone with @Name to ask them.</span></div>';
  return `<div class="hands" id="handsBox">✋ ${q.map(a=>{const n=AG[a]?AG[a].name.split(' ')[0]:a;return sp===a?`<span class="hand on">${esc(n)} · speaking</span>`:`<span class="hand">${esc(n)}<button data-hnow="${a}" title="Let ${esc(n)} speak next">▶</button><button data-hlow="${a}" title="Lower hand">✕</button></span>`}).join('')}</div>`}
function handEv(m){HANDS[m.room]=m.queue||[];const p=AG[m.agent];if(p)p.chip.classList.toggle('hand',!!m.raised);if(selDept===m.room){const b=document.getElementById('handsBox');if(b)b.outerHTML=handsHtml(m.room)}}
function speakEv(m){SPEAK[m.room]=m.agent;if(m.queue)HANDS[m.room]=m.queue;if(selDept===m.room){const b=document.getElementById('handsBox');if(b)b.outerHTML=handsHtml(m.room)}}
function peopleFor(room){const here=agents.filter(p=>p.cur===room||p.home.id===room||(meetings[room]&&meetings[room].members.includes(p.id)));return [...here,...agents.filter(p=>!here.includes(p))]}
function roomTalk(r){const L=ROOMLOG[r.id]||[];
  return `<h3 style="margin-top:12px">${r.team?'Conversations in this room':'Meeting room activity'}</h3><div class="feed conv" id="convFeed">${L.slice(-60).map(convLine).join('')||'<div class="hint">Nothing said here yet.</div>'}</div>
  ${handsHtml(r.id)}<div class="crow"><input type="text" id="rmIn" placeholder="Say something… @Name asks someone to speak (they raise a hand)"><button class="btn pri" data-act="rm">Send</button></div><div class="mention" id="mentionBox"></div>`}
function meetingResources(r){const ms=BIZ.meetings.filter(m=>m.room===r.id);
  return `<h3 style="margin-top:12px">Resources: decks, minutes, reports</h3>`+(ms.length?ms.map(m=>`<div class="hint" style="margin:8px 0 2px;color:#c4cbdb">📋 ${esc(m.agenda||'')} · ${m.date||''}</div>`+(m.files||[]).map(f=>`<div class="frow" data-file="${f.id}"><i>${f.icon}</i><div><b>${esc(f.title)}</b><small>${KIND[f.kind]||f.kind} · ${esc(aName(f.author))}</small></div></div>`).join('')).join(''):'<div class="hint">No meetings here yet. Call one from the Meet tab with an agenda.</div>')}
function sendRoomMsg(){const q=document.getElementById('rmIn'),t=q?q.value.trim():'';if(!t||!selDept)return;if(!(ws&&ws.readyState===1))return toast('Backend offline','Connect the backend so people can answer.','#8691ab');emitWS({type:'room_message',room:selDept,text:t});q.value='';document.getElementById('mentionBox').innerHTML=''}
function insertMention(name){const q=document.getElementById('rmIn');if(!q)return;q.value=q.value.replace(/@[\w.'-]*$/,'@'+name+' ');q.focus();document.getElementById('mentionBox').innerHTML=''}
detail.addEventListener('input',e=>{if(e.target.id!=='rmIn')return;const m=e.target.value.match(/@([\w'-]*)$/),box=document.getElementById('mentionBox');if(!box)return;if(!m){box.innerHTML='';return}
  const t=m[1].toLowerCase(),L=peopleFor(selDept).filter(p=>p.name.toLowerCase().includes(t)).slice(0,8);box.innerHTML=L.map(p=>`<button data-mention="${esc(p.name)}" style="border-color:${p.home.color}">@${esc(p.name)}</button>`).join('')});
detail.addEventListener('keydown',e=>{if(e.target.id==='tkIn'&&e.key==='Enter'){e.preventDefault();talkTo(e.target.dataset.who)}if(e.target.id==='rmIn'&&e.key==='Enter'){e.preventDefault();sendRoomMsg()}if(e.target.id==='rqIn'&&e.key==='Enter'){e.preventDefault();sendRequest(selDept)}});

/* ================= DOCUMENTS: every file the agents made, open + download ================= */
const docsM=document.getElementById('docsM');let docKind='',docDept='';
const DL={presentation:[['pptx','PowerPoint'],['html','HTML'],['md','Markdown']],dashboard:[['html','HTML'],['csv','CSV'],['pptx','PowerPoint']],report:[['html','HTML'],['md','Markdown'],['pptx','PowerPoint'],['csv','Data']],
  minutes:[['html','HTML'],['md','Markdown']],app:[['html','HTML'],['csv','Data']]};
function openDocs(){const base=API();docsM.classList.add('on');if(base)fetch(`${base}/api/files?limit=300`).then(r=>r.json()).then(L=>{L.forEach(f=>bizFile(f,true));drawDocs()}).catch(()=>{});
  const ks=[['','All'],['presentation','🎞️ Presentations'],['report','📄 Reports'],['dashboard','📊 Dashboards'],['minutes','📝 Minutes'],['app','🧩 Apps']];
  document.getElementById('docK').innerHTML=ks.map(([k,l])=>`<button data-k="${k}" class="${k===docKind?'on':''}">${l}</button>`).join('');
  const ds=[...new Set(BIZ.files.map(f=>f.dept))];document.getElementById('docD').innerHTML='<option value="">All teams</option>'+ds.map(d=>`<option value="${d}" ${d===docDept?'selected':''}>${R[d]?R[d].name:d}</option>`).join('');
  document.getElementById('askD').innerHTML=TEAMROOMS.map(r=>`<option value="${r.id}" ${r.id==='bi'?'selected':''}>${r.name}</option>`).join('');drawDocs()}
function drawDocs(){const q=(document.getElementById('docQ').value||'').toLowerCase(),base=API();
  const L=BIZ.files.filter(f=>(!docKind||f.kind===docKind)&&(!docDept||f.dept===docDept)&&(!q||(f.title+' '+aName(f.author)+' '+(R[f.dept]?R[f.dept].name:'')).toLowerCase().includes(q)));
  document.getElementById('docN').textContent=`${L.length} of ${BIZ.files.length} documents`;
  document.getElementById('docL').innerHTML=L.length?L.map(f=>`<div class="drow"><i>${f.icon}</i><div><b>${esc(f.title)}${f.check&&!f.check.ok?' <span class="badge bad" title="Fact-check|Numbers in this document do not match the company data">⚠ numbers differ from data</span>':f.check&&f.check.checked?' <span class="badge ok" title="Fact-check|Every number checked matches the company data">✅ verified</span>':''}</b><small>${KIND[f.kind]||f.kind} · ${esc(aName(f.author))}${AG[f.author]?', '+esc(AG[f.author].role):''} · ${R[f.dept]?R[f.dept].name:f.dept} · ${f.sim_date}${f.meeting?' · meeting':''}</small></div>
    <div class="acts"><button class="btn sm pri" data-open="${f.id}">Open</button>${base?(DL[f.kind]||[['html','HTML']]).map(([x,l])=>`<a class="btn sm" href="${base}/api/files/${encodeURIComponent(f.id)}/download?fmt=${x}" download>⬇ ${l}</a>`).join(''):''}</div></div>`).join('')
    :`<div class="hint" style="padding:14px 4px">No documents yet. Agents make them as the company runs: decks and minutes in every meeting (👥 → Meet, with an agenda), dashboards and the weekly report from Reporting on Fridays, an app from IT on the 2nd, daily briefs. Or ask a team below.</div>`}
document.getElementById('docK').onclick=e=>{const b=e.target.closest('button');if(!b)return;docKind=b.dataset.k;[...e.currentTarget.children].forEach(x=>x.classList.toggle('on',x===b));drawDocs()};
document.getElementById('docD').onchange=e=>{docDept=e.target.value;drawDocs()};document.getElementById('docQ').oninput=drawDocs;
document.getElementById('docL').onclick=e=>{const b=e.target.closest('[data-open]');if(b){docsM.classList.remove('on');openFile(b.dataset.open)}};
document.getElementById('docsX').onclick=()=>docsM.classList.remove('on');docsM.onclick=e=>{if(e.target===docsM)docsM.classList.remove('on')};
document.getElementById('askGo').onclick=()=>{const d=document.getElementById('askD').value,t=document.getElementById('askT').value.trim();if(!t)return;
  if(!(ws&&ws.readyState===1))return toast('Backend offline','Connect the backend so the team can work on it.','#8691ab');emitWS({type:'request_work',dept:d,text:t});document.getElementById('askT').value='';
  toast('📨 Requested',`${R[d].name}: ${t}`,R[d].color);log(`📨 You asked <b>${R[d].name}</b>: ${esc(t)}`,R[d].color)};
/* ================= MEMBERSHIPS SOLD ================= */
const soldChip=document.getElementById('soldChip');let soldT=0;
function refreshSold(){const base=API();if(!base||Date.now()-soldT<5000)return;soldT=Date.now();
  fetch(`${base}/api/company/sales?recent=1`).then(r=>r.json()).then(s=>{soldChip.style.display='';soldChip.innerHTML=`🧾<span class="sx"> Sold</span> <b>${s.sold.all_time}</b><span class="sx"> · today ${s.sold.today} · 28d ${s.sold['28d']}${s.lost['28d']?` · lost ${s.lost['28d']}`:''}</span>`}).catch(()=>{})}
soldChip.onclick=()=>openProfile(true);
function salesHtml(s){const row=x=>`<tr><td>${x.date.slice(5)}</td><td><span data-res="${x.resident}" style="cursor:pointer;text-decoration:underline dotted">${esc(x.name)}</span></td><td>${esc(x.from||'')} → ${esc(x.to)}</td><td>${esc(x.plan||'')}</td><td>${x.price_month!=null?'$'+Math.round(x.price_month):''}</td><td class="hint" style="color:#c4cbdb">${esc(x.why)}</td></tr>`;
  return `<h3 id="profSales">🧾 Memberships sold</h3><div class="pgrid"><div class="met"><small>Today</small><b>${s.sold.today}</b></div><div class="met"><small>Last 7 days</small><b>${s.sold['7d']}</b></div>
    <div class="met"><small>Last 28 days</small><b>${s.sold['28d']}</b></div><div class="met"><small>All time</small><b>${s.sold.all_time}</b></div><div class="met"><small>Lost (28d · all)</small><b>${s.lost['28d']} · ${s.lost.all_time}</b></div><div class="met"><small>People covered now</small><b>${s.members_now}</b></div></div>
    <table class="acc"><tr><th>Date</th><th>Who</th><th>From → to</th><th>Plan</th><th>$/mo</th><th>Why</th></tr>${(s.recent_sales||[]).map(row).join('')||'<tr><td colspan="6" class="hint">No sales yet.</td></tr>'}</table>
    ${(s.recent_losses||[]).length?`<h3 style="margin-top:10px">Members we lost</h3><table class="acc"><tr><th>Date</th><th>Who</th><th>From → to</th><th>Plan</th><th>$/mo</th><th>Why</th></tr>${s.recent_losses.map(row).join('')}</table>`:''}`}
/* ================= COMPANY PROFILE ================= */
const profM=document.getElementById('profM');
function openProfile(toSales){profM.classList.add('on');const base=API();if(!base){document.getElementById('profB').innerHTML='<div class="hint">Connect the backend to see the company.</div>';return}
  fetch(`${base}/api/company/profile`).then(r=>r.json()).then(p=>{const k=p.kpis_28d||{},f=v=>v==null?'–':Number(v).toLocaleString('en-AU',{maximumFractionDigits:2}),o=p.offers_and_perks||{};
    document.getElementById('profB').innerHTML=`<p style="color:#d6dbe8;line-height:1.5">${esc(p.about)}</p>${p.sales?salesHtml(p.sales):''}
    <div class="pgrid"><div class="met"><small>Members</small><b>${p.members} / ${p.town_population}</b></div><div class="met"><small>Market share · rank</small><b>${(p.market_share*100).toFixed(0)}% · #${p.market_rank||'–'}</b></div>
      <div class="met"><small>Premium / day</small><b>$${f(k.premium_revenue_per_day)}</b></div><div class="met"><small>Loss ratio · margin</small><b>${k.loss_ratio!=null?(k.loss_ratio*100).toFixed(0)+'%':'–'} · ${k.margin!=null?(k.margin*100).toFixed(0)+'%':'–'}</b></div>
      <div class="met"><small>Claims in SLA · wait</small><b>${f(k.claims_sla_pct)}% · ${f(k.avg_wait_s)}s</b></div><div class="met"><small>Strategy budget left</small><b>$${f((p.budget||{}).remaining)}</b></div></div>
    <h3>Market (people covered)</h3><div>${(p.market||[]).map(m=>`<span class="tchip"><i class="ins" style="background:${insCol(m.id)}"></i>${esc(m.fund)} ${m.people}</span>`).join('')}</div><div class="hint" style="margin-top:4px">${esc(p.market_note||'')}</div>
    <h3 style="margin-top:12px">Our health care</h3><div>${(p.health_care||[]).map(h=>`<span class="tchip">🏥 ${esc(h)}</span>`).join('')} <span class="hint">members pay no gap</span></div>
    <h3 style="margin-top:12px">Offers & perks live</h3><div class="hint" style="color:#c4cbdb">${o.new_member_discount?`${(o.new_member_discount*100).toFixed(0)}% off for new members · `:''}${(o.perks||[]).map(esc).join(' · ')||'No offers running yet.'}</div>
    <h3 style="margin-top:12px">Plans & prices (single, before rebate)</h3><table class="acc"><tr><th>Plan</th><th>Type</th><th>$/month</th><th>Members</th></tr>${(p.plans||[]).map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.category)}${x.tier?' · '+x.tier:''}</td><td>${f(x.monthly_price)}</td><td>${f(x.in_force)}</td></tr>`).join('')}</table>
    <h3 style="margin-top:12px">Leadership</h3><div>${(p.leadership||[]).map(l=>`<span class="tchip" data-who="${l.id}" style="cursor:pointer">${esc(l.name)} · ${esc(l.role)}</span>`).join('')}</div>
    <h3 style="margin-top:12px">Departments</h3><table class="acc"><tr><th>Team</th><th>Head</th><th>Agents</th><th>Mission</th></tr>${(p.departments||[]).map(d=>`<tr><td>${esc(d.name)}</td><td>${esc(d.head)}</td><td>${d.agents}</td><td>${esc(d.mission)}</td></tr>`).join('')}</table>
    <h3 style="margin-top:12px">Initiatives live</h3><div class="hint" style="color:#c4cbdb">${(p.initiatives_live||[]).map(i=>esc(i.id+' '+i.title)).join(' · ')||'None yet.'}</div>`;
    if(toSales===true){const el=document.getElementById('profSales');if(el)el.scrollIntoView({block:'start'})}}).catch(()=>{document.getElementById('profB').innerHTML='<div class="hint">Could not load.</div>'})}
document.getElementById('profX').onclick=()=>profM.classList.remove('on');profM.onclick=e=>{if(e.target===profM){profM.classList.remove('on');return}const t=e.target.closest('[data-who]');if(t){profM.classList.remove('on');focusAgent(t.dataset.who);return}const u=e.target.closest('[data-res]');if(u&&typeof selectResident==='function'){profM.classList.remove('on');selectResident(u.dataset.res)}};

/* ================= OPS: live AI operations, traces, evaluations, goals ================= */
const opsM=document.getElementById('opsM'),opsB=document.getElementById('opsB');let opsTab='live',evalLive=[];
const nf=v=>v==null?'–':Number(v).toLocaleString('en-AU',{maximumFractionDigits:1});
function openOps(tab){opsM.classList.add('on');if(tab)opsTab=tab;[...document.getElementById('opsTabs').children].forEach(b=>b.classList.toggle('on',b.dataset.t===opsTab));drawOps()}
function opsGet(p){const base=API();return base?fetch(base+p).then(r=>r.json()):Promise.reject('offline')}
function drawOps(){if(!API()){opsB.innerHTML='<div class="hint">Connect the backend to see live operations.</div>';return}
  ({live:opsLive,traces:opsTraces,evals:opsEvals,goals:opsGoals})[opsTab]()}
function opsLive(){opsGet('/api/ops').then(o=>{const g=o.gate,a=o.last_10min,h=o.last_60min,t=o.today;document.getElementById('opsSub').textContent=o.llm||'';
  const kinds=Object.entries(h.by_kind||{}).sort((x,y)=>y[1].tokens-x[1].tokens);
  opsB.innerHTML=`<div class="pgrid"><div class="met"><small>Model calls / min (10 min)</small><b>${nf(a.calls_per_min)}</b></div><div class="met"><small>Quota errors (10 · 60 min)</small><b class="${g.quota_errors_10min?'fail':''}">${g.quota_errors_10min} · ${g.quota_errors_60min}</b></div>
    <div class="met"><small>Queue · free slots</small><b>${g.waiting} · ${g.free}/${g.max_parallel}</b></div><div class="met"><small>Avg chat reply</small><b>${a.chat_avg_s!=null?a.chat_avg_s+'s':h.chat_avg_s!=null?h.chat_avg_s+'s':'–'}</b></div>
    <div class="met"><small>Tokens today</small><b>${nf((t.prompt_tokens+t.output_tokens)/1000)}k</b></div><div class="met"><small>Cost today (estimate)</small><b>$${nf(t.cost_usd_estimate)}</b></div>
    <div class="met"><small>Runs · errors (60 min)</small><b>${h.runs} · <span class="${h.errors?'fail':''}">${h.errors}</span></b></div><div class="met"><small>Background pace</small><b>${g.background_rpm}/min${g.cooldown_s?` · cooling ${g.cooldown_s}s`:''}</b></div></div>
    <h3>Work in the last hour</h3><table class="acc"><tr><th>Kind</th><th>Runs</th><th>Errors</th><th>Model calls</th><th>Tokens</th></tr>${kinds.map(([k,v])=>`<tr><td>${esc(k)}</td><td>${v.runs}</td><td class="${v.errors?'fail':''}">${v.errors}</td><td>${v.model_calls}</td><td>${nf(v.tokens/1000)}k</td></tr>`).join('')||'<tr><td colspan=5 class="hint">No agent runs yet.</td></tr>'}</table>
    <h3 style="margin-top:10px">Biggest token users (60 min)</h3><div>${(h.top_agents||[]).map(([w,n])=>`<span class="tchip">${esc(aName(w))} ${nf(n/1000)}k</span>`).join('')||'<span class="hint">–</span>'}</div>
    <h3 style="margin-top:10px">Workflows</h3><div class="hint" style="color:#c4cbdb">${(o.workflows||[]).slice().reverse().map(w=>`${esc(w.name)} <span class="${w.status==='failed'?'fail':w.status==='completed'?'pass':''}">${w.status}</span>`).join(' · ')||'None yet.'}</div>
    <div class="hint" style="margin-top:8px">Costs are estimates at $${t.prices_per_m[0]} / $${t.prices_per_m[1]} per million input / output tokens (set HQ_PRICE_IN_PER_M and HQ_PRICE_OUT_PER_M to your Vertex AI prices).</div>`}).catch(()=>opsB.innerHTML='<div class="hint">Could not load.</div>')}
function opsTraces(){opsGet('/api/traces?limit=150').then(L=>{opsB.innerHTML=`<div class="hint" style="margin-bottom:6px">Every agent run: who, what for, the tools it used, tokens and time. Click one to see the prompt, each tool call with its result, and the reply.</div>`+
  (L.map(t=>`<div class="trow" data-tr="${t.id}"><small>${new Date(t.ts*1000).toTimeString().slice(0,5)}</small><div><b>${esc(aName(t.agent))}</b> <small>${esc(t.kind)}${t.foreground?' · you':''}</small><br><small>${t.tools.length?esc(t.tools.join(' → ')):'no tools'}</small>${t.error?`<br><small class="err">${esc(t.error)}</small>`:''}</div><small>${t.model_calls} calls · ${nf((t.prompt_tokens+t.output_tokens)/1000)}k tok · ${t.seconds}s ${t.status==='ok'?'✓':'<span class="err">✗</span>'}</small></div>`).join('')||'<div class="hint">No runs yet.</div>')}).catch(()=>{})}
function opsTrace(id){opsGet('/api/traces/'+id).then(t=>{const steps=(t.steps||[]).map(s=>s.tool?`[${s.t}s] → ${s.tool}(${s.args})`:`[${s.t}s] ← ${s.result_of}: ${s.result}`).join('\n');
  opsB.innerHTML=`<button class="btn sm" data-back="1">← All runs</button><h3 style="margin-top:8px">${esc(aName(t.agent))} · ${esc(t.kind)} · ${t.sim_date}</h3>
  <div class="hint">${t.model_calls} model calls · ${nf(t.prompt_tokens)} in / ${nf(t.output_tokens)} out tokens · ${t.seconds}s · ${t.status}${t.error?' · '+esc(t.error):''}</div>
  <h3 style="margin-top:8px">Prompt</h3><div class="tsteps">${esc(t.prompt)}</div><h3 style="margin-top:8px">Tool calls</h3><div class="tsteps">${esc(steps||'none')}</div><h3 style="margin-top:8px">Reply</h3><div class="tsteps">${esc(t.reply||'')}</div>`})}
function opsEvals(){opsGet('/api/evals').then(e=>{const last=e.runs[0];
  opsB.innerHTML=`<div class="crow" style="margin-bottom:8px"><button class="btn pri" id="evalGo" ${e.running?'disabled':''}>${e.running?'Running…':'▶ Run evaluation'}</button><span class="hint">${e.cases.length} questions with answers known from the data: numbers, memory, compliance. Takes a minute or two.</span></div>
  ${evalLive.length&&e.running?`<h3>Running</h3>${evalLive.map(evalRow).join('')}`:''}
  ${last?`<h3>Last run · ${last.sim_date} · <span class="${last.score>=.8?'pass':last.score<.5?'fail':''}">${last.passed}/${last.total} passed</span></h3>${last.results.map(evalRow).join('')}`:'<div class="hint">No evaluation yet.</div>'}
  ${e.runs.length>1?`<h3 style="margin-top:10px">History</h3><div>${e.runs.map(r=>`<span class="tchip">${r.sim_date}: ${r.passed}/${r.total}</span>`).join('')}</div>`:''}`;
  const b=document.getElementById('evalGo');if(b)b.onclick=()=>{evalLive=[];fetch(API()+'/api/evals/run',{method:'POST'}).then(()=>{toast('🧪 Evaluation started','Agents are answering the questions…','#a78bfa');opsEvals()})}})}
const evalRow=r=>`<div class="tlev"><b class="${r.pass?'pass':'fail'}">${r.pass?'✓':'✗'}</b> <b>${esc(r.id)}</b> · ${esc(aName(r.agent))} <span class="hint">${r.seconds}s</span><br><span class="hint">Q: ${esc(r.question)}</span><br>${esc((r.reply||'').slice(0,260))}<br><span class="hint">expected: ${esc(JSON.stringify(r.expected))}${r.found?' · found: '+esc(JSON.stringify(r.found)):''}</span></div>`;
function evalCase(m){evalLive.push(m.result);if(opsM.classList.contains('on')&&opsTab==='evals')opsEvals()}
function evalDone(m){toast('🧪 Evaluation finished',`${m.passed}/${m.total} passed`,m.score>=.8?'#4ade80':'#f59e0b',()=>openOps('evals'));if(opsM.classList.contains('on')&&opsTab==='evals')opsEvals()}
function opsGoals(){opsGet('/api/goals').then(g=>{const row=x=>`<tr><td>${esc(x.label)}</td><td>${nf(x.target)}</td><td>${nf(x.actual_so_far)}</td><td>${x.on_track==null?'–':x.on_track?'<span class="pass">on track</span>':'<span class="fail">behind</span>'}</td><td>${esc(aName(x.owner))}</td><td class="hint">${esc(x.why||'')}</td></tr>`;
  opsB.innerHTML=`<div class="hint" style="margin-bottom:6px">Plan → act → reflect: every Monday the CEO reviews last week's goals (lessons go into the leaders' memories) and sets new ones.</div>
  <h3>This week</h3><table class="acc"><tr><th>Goal</th><th>Target</th><th>So far</th><th>Status</th><th>Owner</th><th>Why</th></tr>${g.this_week.map(row).join('')||'<tr><td colspan=6 class="hint">No goals yet: they are set on Mondays.</td></tr>'}</table>
  <h3 style="margin-top:10px">Past weeks</h3>${g.reviews.map(r=>`<div class="tlev"><b>${r.week}</b> · ${r.met}/${r.goals.length} met<br>${r.goals.map(x=>`<span class="${x.met?'pass':'fail'}">${esc(x.label)} ${nf(x.actual)} / ${nf(x.target)}</span>`).join(' · ')}<br><span class="hint">Tried: ${esc((r.initiatives.concat(r.campaigns)).join(', ')||'nothing new')}</span></div>`).join('')||'<div class="hint">No reviews yet.</div>'}`})}
document.getElementById('opsTabs').onclick=e=>{const b=e.target.closest('button');if(!b)return;opsTab=b.dataset.t;[...e.currentTarget.children].forEach(x=>x.classList.toggle('on',x===b));drawOps()};
opsB.onclick=e=>{const t=e.target.closest('[data-tr]');if(t)return opsTrace(t.dataset.tr);if(e.target.closest('[data-back]'))opsTraces()};
document.getElementById('opsR').onclick=drawOps;document.getElementById('opsX').onclick=()=>opsM.classList.remove('on');opsM.onclick=e=>{if(e.target===opsM)opsM.classList.remove('on')};

/* ================= TIMELINE: replay the company day by day ================= */
const tlM=document.getElementById('tlM'),tlR=document.getElementById('tlR');let TL={days:[]},tlT=null;
function openTimeline(){tlM.classList.add('on');const base=API();if(!base){document.getElementById('tlB').innerHTML='<div class="hint">Connect the backend to replay the company.</div>';return}
  fetch(`${base}/api/timeline?days=${document.getElementById('tlDays').value}`).then(r=>r.json()).then(t=>{TL=t;tlR.max=Math.max(0,t.days.length-1);tlR.value=tlR.max;
    document.getElementById('tlSub').textContent=t.days.length?`${t.from} → ${t.to}`:'';drawTL()})}
function drawTL(){const D=TL.days,i=+tlR.value,d=D[i];const B=document.getElementById('tlB'),S=document.getElementById('tlSpark');
  if(!d){B.innerHTML='<div class="hint">No days recorded yet.</div>';S.innerHTML='';return}
  const v=D.map(x=>x.kpi.policies_in_force),lo=Math.min(...v),hi=Math.max(...v),X=j=>D.length>1?j*600/(D.length-1):300,Y=y=>62-(hi>lo?(y-lo)/(hi-lo):.5)*54;
  S.innerHTML=`<polyline fill="none" stroke="#f5b942" stroke-width="2" points="${v.map((y,j)=>X(j)+','+Y(y)).join(' ')}"/>`+D.map((x,j)=>x.kpi.new_sales?`<circle cx="${X(j)}" cy="${Y(v[j])}" r="3" fill="#4ade80"/>`:'').join('')+`<line x1="${X(i)}" x2="${X(i)}" y1="0" y2="70" stroke="#ffffff70"/><text x="6" y="12" fill="#8691ab" font-size="10">policies ${lo}–${hi}</text>`;
  const k=d.kpi,dt=new Date(d.date+'T00:00:00');
  B.innerHTML=`<h3>${dt.toLocaleDateString('en-AU',{weekday:'long',day:'numeric',month:'long',year:'numeric'})}</h3>
  <div class="pgrid"><div class="met"><small>Policies</small><b>${nf(k.policies_in_force)}</b></div><div class="met"><small>Sold · lost</small><b>${k.new_sales} · ${k.cancellations}</b></div><div class="met"><small>Premium · claims</small><b>$${nf(k.premium_revenue)} · $${nf(k.claims_incurred)}</b></div>
  <div class="met"><small>Loss ratio (28d)</small><b>${(k.loss_ratio*100).toFixed(0)}%</b></div><div class="met"><small>Claims SLA · NPS</small><b>${nf(k.claims_sla_pct)}% · ${nf(k.nps)}</b></div><div class="met"><small>Awareness</small><b>${nf(k.brand_awareness)}%</b></div></div>
  <h3>What happened</h3>${d.events.map(e=>`<div class="tlev ${e.tone||''}">${e.icon} ${e.file?`<a data-f="${e.file}">${esc(e.text)}</a>`:esc(e.text)}</div>`).join('')||'<div class="hint">A quiet day.</div>'}`}
function tlStop(){clearInterval(tlT);tlT=null;document.getElementById('tlPlay').textContent='▶ Play'}
document.getElementById('tlPlay').onclick=()=>{if(tlT)return tlStop();if(+tlR.value>=+tlR.max)tlR.value=0;drawTL();document.getElementById('tlPlay').textContent='⏸ Pause';
  const ms=Math.max(700,Math.min(2200,60000/Math.max(1,TL.days.length)));tlT=setInterval(()=>{if(+tlR.value>=+tlR.max)return tlStop();tlR.value=+tlR.value+1;drawTL()},ms)};
tlR.oninput=()=>{tlStop();drawTL()};document.getElementById('tlDays').onchange=()=>{tlStop();openTimeline()};
document.getElementById('tlB').onclick=e=>{const a=e.target.closest('[data-f]');if(a){tlStop();tlM.classList.remove('on');openFile(a.dataset.f)}};
document.getElementById('tlX').onclick=()=>{tlStop();tlM.classList.remove('on')};tlM.onclick=e=>{if(e.target===tlM){tlStop();tlM.classList.remove('on')}};

/* ================= GUIDED TOUR ================= */
const TOUR=[
  ['[data-a="town"]','Wattle Grove','A town of 100+ AI residents with jobs, homes, families and memories. They choose their health insurance themselves, and every company number comes only from their decisions.'],
  ['.col.l','Your AI employees','51 AI agents in 12 departments. Click anyone to see their work, memory and token use, and to talk to them. They remember your conversation.'],
  ['#clk','Run the company','Start the clock: each simulated day the agents run workflows (daily ops, reporting, meetings, strategy) on their own.'],
  ['#soldChip','Memberships sold','Live sales. Click for who bought, from which fund, which plan and why.'],
  ['[data-a="docs"]','Documents','Every presentation, report, dashboard and app the agents made. Numbers are fact-checked against the data; download as PowerPoint, HTML, Markdown or CSV.'],
  ['[data-a="timeline"]','Timeline','Replay the company day by day: KPIs and everything that happened.'],
  ['[data-a="ops"]','AI operations','Model calls, quota, cost, every agent run traced (prompt, tools, reply), evaluations and the weekly goals.'],
  ['[data-a="profile"]','Company profile','Who we are, our hospital and clinic, plans, market position and sales.'],
];
let tourOn=false,tourI=0;const tourO=document.getElementById('tourO');
function startTour(){tourOn=true;tourI=0;tourO.classList.add('on');showTour()}
function endTour(){tourOn=false;tourO.classList.remove('on');try{localStorage.setItem('hqTourDone','1')}catch(e){}}
function showTour(){const steps=TOUR.filter(s=>{const el=document.querySelector(s[0]);return el&&el.offsetParent!==null});if(tourI>=steps.length)return endTour();
  const [sel,t,p]=steps[tourI],el=document.querySelector(sel);el.scrollIntoView({block:'nearest',inline:'nearest'});const r=el.getBoundingClientRect(),H=document.getElementById('tourHole'),C=document.getElementById('tourCard');
  Object.assign(H.style,{left:r.left-6+'px',top:r.top-6+'px',width:r.width+12+'px',height:r.height+12+'px'});
  document.getElementById('tourN').textContent=`${tourI+1} / ${steps.length}`;document.getElementById('tourT').textContent=t;document.getElementById('tourP').textContent=p;
  document.getElementById('tourNext').textContent=tourI===steps.length-1?'Done':'Next';document.getElementById('tourBack').style.visibility=tourI?'visible':'hidden';
  const cw=Math.min(340,innerWidth*.92),below=r.bottom+14+200<innerHeight;C.style.left=Math.max(8,Math.min(innerWidth-cw-8,r.left))+'px';C.style.top=(below?r.bottom+14:Math.max(8,r.top-214))+'px'}
document.getElementById('tourNext').onclick=()=>{tourI++;showTour()};document.getElementById('tourBack').onclick=()=>{tourI=Math.max(0,tourI-1);showTour()};document.getElementById('tourSkip').onclick=endTour;
addEventListener('resize',()=>{if(tourOn)showTour()});
setTimeout(()=>{let done=true;try{done=localStorage.getItem('hqTourDone')==='1'}catch(e){}if(!done&&!document.body.classList.contains('infp'))startTour()},5000);

/* ================= APPS ================= */
const appsM=document.getElementById('appsM');
function openApps(){const L=BIZ.files.filter(f=>f.kind==='app');document.getElementById('appsL').innerHTML=L.length?L.map(f=>`<div class="frow" data-app="${f.id}"><i>🧩</i><div style="flex:1"><b style="max-width:none">${esc(f.title)}</b><small>${esc(f.summary||'')} · ${esc(aName(f.author))} · ${f.sim_date}</small></div><span class="btn sm">Open</span></div>`).join(''):'<div class="hint">No apps yet. IT ships one on the 2nd of each month, or ask IT &amp; Apps from its department panel.</div>';appsM.classList.add('on')}
document.getElementById('appsX').onclick=()=>appsM.classList.remove('on');appsM.onclick=e=>{if(e.target===appsM){appsM.classList.remove('on');return}const a=e.target.closest('[data-app]');if(a){appsM.classList.remove('on');openFile(a.dataset.app)}};
