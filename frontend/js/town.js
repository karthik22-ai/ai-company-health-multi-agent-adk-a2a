/* AI Company HQ – Wattle Grove: residents, houses, daily plans, health visits, life events, person panels.
   Loaded in the order of js/manifest.json and served as one script (/ui/app.js). */
/* ================= THE TOWN: Wattle Grove, 100 residents choosing health insurance ================= */
const TX=178,TR=58,townG=new THREE.Group();scene.add(townG);
const INS_COL={aich:'#22d3ee',medibank:'#3b82f6',bupa:'#a855f7',hcf:'#ef4444',nib:'#22c55e',hbf:'#f97316',ahm:'#eab308',teachers:'#ec4899',aunity:'#94a3b8',gmhba:'#84cc16',none:'#475569'};
const insCol=k=>INS_COL[k||'none']||'#8691ab';
const TOWN={residents:[],byId:{},rel:[],events:[],campaigns:[],insurers:{},built:false,sig:0,hist:{}};
(()=>{const g=townG;
  buildCity(g);
  for(let x=-44;x<=44;x+=22)box(.6,.12,96,M(0x9aa3b5,{roughness:.9}),TX+x+11,.07,0,g,false);
  for(let z=-39;z<=39;z+=13)box(96,.13,2.4,M(0x9aa3b5,{roughness:.9}),TX,.07,z+6.5,g,false);
  const c=document.createElement('canvas');c.width=512;c.height=128;const x=c.getContext('2d');x.fillStyle='#14532d';x.fillRect(0,0,512,128);x.fillStyle='#f0fdf4';x.font='800 58px system-ui';x.textAlign='center';x.textBaseline='middle';x.fillText('WATTLE GROVE',256,66);
  const sign=new THREE.Mesh(new THREE.PlaneGeometry(10,2.5),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(c),side:THREE.DoubleSide}));sign.position.set(TX-TR+6,3.2,6);sign.rotation.y=Math.PI/2;g.add(sign);
  [-1,1].forEach(o=>cyl(.15,.15,3,M(0x5b4636),TX-TR+6,1.5,6+o*4.6,g,6));
  for(let i=0;i<22;i++){const a=i/22*6.283+.2,r=TR-6+Math.sin(i*3)*2;const t=new THREE.Group();t.position.set(TX+Math.cos(a)*r,0,Math.sin(a)*r);t.scale.setScalar(.75);g.add(t);
    cyl(.3,.42,2.2,M(0x6b4a32),0,1.1,0,t,6);const k=new THREE.Mesh(new THREE.IcosahedronGeometry(2.2,0),M(i%2?0x3e9a5a:0x4cae6a,{flatShading:true}));k.position.y=3.6;k.castShadow=true;t.add(k)}})();
const resMeshes=[];
function houseAt(i){const cols=8,c=i%cols,r=Math.floor(i/cols);return {x:TX-38.5+c*11,z:-32.5+r*13}}
const SUBURB_COL={'Harbourview':0xe2e8f0,'Riverside':0xfde68a,'Wattle Park':0xbbf7d0,'Eastgate':0xfecaca,'Banksia Hills':0xddd6fe,'Old Town':0xfed7aa,'Marina Bay':0xbae6fd,'Gumtree Flats':0xd9f99d};
/* houses: 48 lots in the town grid, then new suburbs to the north and south as families move in */
function lotPos(i){if(i<48)return houseAt(i);const j=i-48,side=j%2?1:-1,k=Math.floor(j/2);return {x:70+(k%26)*11,z:side*(104+Math.floor(k/26)*14)}}
const FAC_LOTS=[{x:-24,z:-140},{x:-24,z:140},{x:398,z:-62},{x:398,z:64},{x:430,z:2},{x:-70,z:-110},{x:-70,z:110},{x:150,z:-136}];
const FAC_COL={childcare:['#f472b6',0xfce7f3],park:['#15803d',0x86efac],gym:['#111827',0xd1d5db],aged_care:['#7c3aed',0xede9fe],bus:['#0369a1',0xbae6fd],community:['#b45309',0xfde68a],supermarket:['#16a34a',0xdcfce7],gp:['#0891b2',0xcffafe]};
TOWN.houses={};TOWN.lotN=0;TOWN.facBuilt={};
function ensureHouse(h,suburb){if(TOWN.houses[h])return TOWN.houses[h];const i=TOWN.lotN++,P=lotPos(i),col=SUBURB_COL[suburb]||0xe5e7eb;
  box(6.4,3.2,5,M(col,{roughness:.8}),P.x,1.6,P.z,townG);const roof=new THREE.Mesh(new THREE.ConeGeometry(4.9,2.4,4),M(0x7c2d12,{roughness:.7,flatShading:true}));roof.rotation.y=Math.PI/4;roof.scale.set(1,1,.78);roof.position.set(P.x,4.4,P.z);roof.castShadow=true;townG.add(roof);
  box(1.1,2,.1,M(0x5b4636),P.x,1,P.z+2.53,townG,false);box(1.3,1,.08,glowMat(0xfff2c2,.25,.9),P.x-2,2,P.z+2.53,townG,false);
  if(i>=48&&i<50)box(300,.12,7,M(0x3b4252,{roughness:.95}),200,.06,P.z<0?-96:96,townG,false);
  TOWN.houses[h]={x:P.x,z:P.z,n:0};return TOWN.houses[h]}
function buildFacility(f){if(!f||TOWN.facBuilt[f.kind])return;const L=FAC_LOTS[f.lot%FAC_LOTS.length],[sb,c]=FAC_COL[f.kind]||['#334155',0xe5e7eb];
  if(f.kind==='park'){box(30,.08,22,M(0x4ade80,{roughness:1}),L.x,.05,L.z,townG,false);for(let i=0;i<8;i++){const t=new THREE.Group();t.position.set(L.x-12+i*3.4,0,L.z+(i%2?7:-7));t.scale.setScalar(.6);townG.add(t);cyl(.3,.42,2.2,M(0x6b4a32),0,1.1,0,t,6);const k=new THREE.Mesh(new THREE.IcosahedronGeometry(2.2,0),M(0x3e9a5a,{flatShading:true}));k.position.y=3.6;t.add(k)}
    const sg=new THREE.Mesh(new THREE.PlaneGeometry(14,3.5),new THREE.MeshBasicMaterial({map:signTex(f.name.toUpperCase().slice(0,26),sb,'#fff'),toneMapped:false,side:THREE.DoubleSide}));sg.position.set(L.x,3,L.z+11.5);townG.add(sg)}
  else building(townG,L.x,L.z,20,14,f.kind==='aged_care'?9:6,c,f.name.toUpperCase().slice(0,24),'fac_'+f.kind,sb);
  WNAME['fac_'+f.kind]=f.name;WPOS['fac_'+f.kind]={x:L.x,z:L.z};TOWN.facBuilt[f.kind]=f}
/* residents: gender, age, hair, clothes; a ring under their feet shows their insurer */
const SK=[0xf6d5b8,0xe0a97c,0xc68642,0x8d5524,0x6b4423],HRC=[0x15151a,0x3a2a1a,0x6b3f1d,0xd9b36c,0x8a5a2b],SHIRT=[0x2563eb,0xdc2626,0x16a34a,0xf59e0b,0x7c3aed,0x0891b2,0xf8fafc,0x374151,0xdb2777,0x65a30d],PANT=[0x1f2937,0x334155,0x1e3a8a,0x57534e,0x0f172a];
function resModel(r){const n=+r.id.slice(1),g=new THREE.Group(),fem=r.gender==='female',old=r.age>=65,kid=r.age<18;
  const sc=r.age<1?.32:r.age<4?.45:r.age<10?.62:r.age<15?.8:r.age<18?.92:old?.95:1;
  const skin=M(SK[n%5],{roughness:.75}),hair=M(old?0xc8c8cc:HRC[(n*3)%5],{roughness:.9}),shirt=M(SHIRT[(n*7)%SHIRT.length],{roughness:.65}),pant=M(PANT[n%5],{roughness:.8}),shoe=M(0x111827,{roughness:.5});
  const legs=[-1,1].map(sd=>{const hp=new THREE.Group();hp.position.set(sd*.17,1.05,0);g.add(hp);cyl(.13,.11,1,pant,0,-.5,0,hp,8);box(.24,.14,.4,shoe,0,-1,.08,hp,false);return hp});
  const torso=cyl(fem?.27:.31,fem?.34:.3,1.0,shirt,0,1.55,0,g,12);torso.scale.z=.7;if(fem&&!kid){const sk=cyl(.3,.42,.45,shirt,0,1.05,0,g,12);sk.scale.z=.75}
  const arms=[-1,1].map(sd=>{const sh=new THREE.Group();sh.position.set(sd*(fem?.33:.38),1.98,0);g.add(sh);cyl(.09,.08,.85,shirt,0,-.42,0,sh,8);const hd=new THREE.Mesh(new THREE.SphereGeometry(.09,8,6),skin);hd.position.y=-.88;sh.add(hd);return sh});
  cyl(.09,.1,.15,skin,0,2.12,0,g,8);const head=new THREE.Mesh(new THREE.SphereGeometry(.27,14,12),skin);head.position.y=2.42;head.scale.set(1,1.08,.98);g.add(head);
  const dark=new THREE.MeshBasicMaterial({color:0x111111});[-1,1].forEach(sd=>{const e=new THREE.Mesh(new THREE.SphereGeometry(.035,6,5),dark);e.position.set(sd*.09,2.46,.24);g.add(e)});
  box(.1,.02,.02,M(0x8a3b3b),0,2.33,.25,g,false);
  const cap=new THREE.Mesh(new THREE.SphereGeometry(.285,14,10,0,6.283,0,old&&!fem&&n%2?1.0:1.35),hair);cap.position.set(0,2.45,-.02);g.add(cap);
  if(fem&&!old&&r.age>3){if(n%3===0){const bun=new THREE.Mesh(new THREE.SphereGeometry(.13,8,6),hair);bun.position.set(0,2.62,-.2);g.add(bun)}else box(.5,.55,.16,hair,0,2.2,-.18,g,false)}
  if(!fem&&r.age>25&&n%4===0){const bd=new THREE.Mesh(new THREE.SphereGeometry(.24,10,6,0,6.283,1.9,1.0),hair);bd.position.set(0,2.36,.03);g.add(bd)}
  const ring=new THREE.Mesh(new THREE.RingGeometry(.42,.62,24),new THREE.MeshBasicMaterial({color:insCol((r.cover||{}).insurer),transparent:true,opacity:.9,side:THREE.DoubleSide}));ring.rotation.x=-Math.PI/2;ring.position.y=.06;g.add(ring);
  g.scale.setScalar(1.15*sc);g.userData={legs,arms,ring,head};return g}
function spawnResident(r){const H=ensureHouse(r.household,r.suburb),j=H.n++,g=resModel(r),n=+r.id.slice(1);g.position.set(H.x-2.4+(j%5)*1.25,0,H.z+4.4+Math.floor(j/5)*1.2);townG.add(g);
  g.traverse(o=>{if(o.isMesh){o.userData.resident=r.id;resMeshes.push(o)}});r.g=g;r.body=g.userData.ring;r.ph=n*.7;r.bubUntil=0;
  r.homePos={x:g.position.x,z:g.position.z};const W=WPOS[r.workplace];r.workPos=W?{x:W.x+((n*7)%17-8)*.9,z:W.z+(W.z<0?18:-18)+((n*3)%7-3)*.9}:null;
  r.mode=/bicycle|e-bike/.test(r.vehicle||'')?'bike':(r.vehicle&&!/walk|bus|drop|parent/.test(r.vehicle))?'car':'walk';r.loc='home';r.trip=null;
  if(r.mode==='car'&&r.age>=18){r.car=carMesh(CAR_COLS[n%CAR_COLS.length]);r.car.position.set(H.x+3.6,0,H.z+3.6+j*.15);r.car.rotation.y=Math.PI/2;townG.add(r.car);r.car.traverse(o=>{if(o.isMesh){o.userData.resident=r.id;resMeshes.push(o)}})}
  if(r.mode==='bike'){const bk=new THREE.Group();[-.5,.5].forEach(z0=>{const w=new THREE.Mesh(new THREE.TorusGeometry(.32,.05,6,14),M(0x111827));w.position.set(0,.33,z0);w.rotation.y=Math.PI/2;bk.add(w)});box(.06,.06,1,M(0x22d3ee),0,.55,0,bk,false);bk.visible=false;g.add(bk);r.bike=bk}}
function despawnResident(r){[r.g,r.car].forEach(o=>{if(!o)return;o.traverse(x=>{const i=resMeshes.indexOf(x);if(i>=0)resMeshes.splice(i,1)});townG.remove(o)});if(r.bub)r.bub.remove()}
function buildTown(){const hh={};TOWN.residents.forEach(r=>(hh[r.household]=hh[r.household]||[]).push(r));
  Object.keys(hh).map(Number).sort((a,b)=>a-b).forEach(h=>{ensureHouse(h,hh[h][0].suburb);hh[h].forEach(spawnResident)});TOWN.built=true}
/* life events: births, deaths, move-ins, birthdays, jobs, friendships, partners, new facilities */
const LICON={birthday:'🎂',birth:'👶',death:'🕊️',move_in:'🚚',new_job:'💼',retired:'🏖️',friendship:'🤝',partner:'💕',facility:'🏗️'};
function townLife(m){const ev=m.event||{},nr=m.resident;
  if(m.facility){buildFacility(m.facility);TOWN.facilities=(TOWN.facilities||[]).concat([m.facility]);toast('🏗️ Wattle Grove is building',`${m.facility.name}: ${m.facility.reason||''}`.slice(0,140),'#ca8a04',()=>{const W=WPOS['fac_'+m.facility.kind];if(W){setView('ext');focus={t:new THREE.Vector3(W.x,2,W.z),c:new THREE.Vector3(W.x+30,40,W.z+50)}}});log(`🏗️ ${esc(ev.text||m.facility.name)}`,'#ca8a04');return}
  if(m.removed){const r=TOWN.byId[m.removed];if(r){despawnResident(r);TOWN.residents=TOWN.residents.filter(x=>x!==r);delete TOWN.byId[r.id];(TOWN.departed=TOWN.departed||[]).unshift({id:r.id,name:r.name,age:nr?nr.age:r.age,date:ev.date})}
    toast('🕊️ Passed away',ev.text||'','#94a3b8');log(`🕊️ ${esc(ev.text||'')}`,'#94a3b8');TOWN.sig++;if(selRes===m.removed){selRes=null;renderDetail()}if(ltab==='town')renderLeft(true);return}
  if(m.added&&nr&&!TOWN.byId[nr.id]){const r=Object.assign({cover_label:nr.cover?'covered with the family':'no private cover'},nr);TOWN.residents.push(r);TOWN.byId[r.id]=r;if(TOWN.built)spawnResident(r);resSay(r,ev.kind==='birth'?'👶':'👋 Hi Wattle Grove!',6000)}
  else if(nr&&TOWN.byId[nr.id]){const r=TOWN.byId[nr.id];['age','occupation','workplace','employer','income_aud','vehicle','household_kind'].forEach(k=>{if(nr[k]!==undefined)r[k]=nr[k]});
    if(nr.workplace){const W=WPOS[nr.workplace],n=+r.id.slice(1);r.workPos=W?{x:W.x+((n*7)%17-8)*.9,z:W.z+(W.z<0?18:-18)}:null}resSay(r,(LICON[ev.kind]||'')+' '+(ev.kind==='birthday'?r.age:''),5000)}
  if(m.other&&TOWN.byId[m.other])resSay(TOWN.byId[m.other],LICON[ev.kind]||'',5000);
  TOWN.events.unshift(ev);TOWN.events=TOWN.events.slice(0,200);TOWN.sig++;
  if(['birth','move_in','partner','new_job','retired'].includes(ev.kind)){toast(`${LICON[ev.kind]} Wattle Grove`,ev.text||'','#22d3ee',nr?()=>selectResident(nr.id):null)}
  log(`${LICON[ev.kind]||'•'} ${esc(ev.text||'')}`,'#22d3ee');if(ltab==='town')renderLeft(true);if(nr&&selRes===nr.id){delete TOWN.hist[nr.id];loadRes(nr.id)}}
function townSnap(m){const prev=TOWN.byId;TOWN.residents=(m.residents||[]).map(r=>Object.assign(prev[r.id]||{},r));TOWN.byId={};TOWN.residents.forEach(r=>TOWN.byId[r.id]=r);
  TOWN.rel=m.relations||[];TOWN.events=(m.events||[]).slice();TOWN.campaigns=m.campaigns||[];TOWN.insurers=m.insurers||{};TOWN.sig++;TOWN.facilities=m.facilities||[];TOWN.departed=m.departed||[];TOWN.funds_note=m.funds_note||'';
  if(!TOWN.built&&TOWN.residents.length)buildTown();else TOWN.residents.forEach(r=>{if(!r.g&&TOWN.built)spawnResident(r)});(TOWN.facilities||[]).forEach(buildFacility);TOWN.residents.forEach(r=>{if(r.body)r.body.material.color.set(insCol((r.cover||{}).insurer))});
  if(ltab==='town')renderLeft(true);if(selRes)renderDetail();if(coEl.style.display==='flex'&&BIZ.tab==='town')renderCo()}
function resSay(r,t,ms=4500){if(!r)return;if(!r.bub)r.bub=dom('bub','');r.bub.textContent=t;r.bub.style.opacity=1;r.bubUntil=performance.now()+ms}
const KICON={buy:'🛒',switch:'🔁',change_plan:'🔁',keep:'🤔',cancel:'✂️',enquiry:'☎️',message:'💬',review:'⭐',web:'🔎',health:'🩺',talk:'💬'};
function townEvent(m){const ev=m.event||{},r=TOWN.byId[ev.resident];if(!r)return;if(m.say)resSay(r,m.say);if(m.quiet)return;
  if(['buy','switch','change_plan'].includes(ev.kind)&&ev.insurer){TOWN.residents.filter(x=>x.household===r.household).forEach(x=>{x.cover=Object.assign({},x.cover||{},{insurer:ev.insurer});x.cover_label=(TOWN.insurers[ev.insurer]||ev.insurer)+' (new)';if(x.body)x.body.material.color.set(insCol(ev.insurer))})}
  if(ev.kind==='cancel')TOWN.residents.filter(x=>x.household===r.household).forEach(x=>{x.cover=null;x.cover_label='no private cover';if(x.body)x.body.material.color.set(insCol(null))});
  TOWN.events.unshift(ev);TOWN.events=TOWN.events.slice(0,200);TOWN.sig++;
  const col=insCol(ev.insurer);log(`🏘 ${KICON[ev.kind]||'•'} <b>${esc(r.name)}</b>: ${esc((ev.text||'').slice(0,180))}`,col);
  if(['buy','switch'].includes(ev.kind)&&ev.insurer==='aich'&&!RP.on)toast('🎉 New member from Wattle Grove',`${r.name}: ${(ev.text||'').split('Why:')[1]||''}`.slice(0,140),'#22d3ee',()=>selectResident(r.id));
  if(ltab==='town')renderLeft(true);if(selRes===r.id){delete TOWN.hist[r.id];loadRes(r.id)}if(coEl.style.display==='flex'&&BIZ.tab==='town')renderCo()}
function townVisit(m){const ev=m.event||{},r=TOWN.byId[ev.resident];if(!r)return;const care=m.care||'gp',lbl=`${CARE_ICON[care]||'🩺'} ${care}`;
  TOWN.visits[r.id]={place:m.facility,label:lbl+' at '+(WNAME[m.facility]||m.facility),until:performance.now()+45000};resSay(r,lbl,6000);
  TOWN.events.unshift(Object.assign({},ev,{kind:'health'}));TOWN.sig++;log(`${CARE_ICON[care]||'🩺'} ${esc(ev.text||'')}`,String(m.facility).startsWith('aich')?'#22d3ee':'#94a3b8');
  if(String(m.facility).startsWith('aich')&&!RP.on&&Math.random()<.4)toast('🏥 AI Company Health care',ev.text||'','#22d3ee',()=>selectResident(r.id));if(selRes===r.id){delete TOWN.hist[r.id];loadRes(r.id)}}
function townShoppers(m){(m.shoppers||[]).forEach(t=>resSay(TOWN.byId[t.resident],'🤔 '+t.reason,7000))}
function townCampaign(m){const c=m.campaign||{};TOWN.campaigns.unshift(c);toast('📣 Town campaign',`${c.title} · reach ${c.reach} people · ${c.offer||''}`,'#b388ff');log(`📣 Marketing launched <b>${esc(c.title)}</b> in Wattle Grove (${c.reach} people)`,'#b388ff')}
/* residents' daily life: a town day lasts 4 minutes. Home → commute → work/school → (some go to the mall) → home */
const DAY_S=240;const townClock=()=>((performance.now()/1000)/DAY_S+.30)%1;
function wantLoc(r,c){const st=(r.ph*7.3%1)*.05,ret=r.occupation==='Retired'||!r.workPos;
  if(ret){if(c>.36+st&&c<.52+st)return 'mall';return 'home'}
  if(c>.24+st&&c<.62+st)return 'work';
  if(c>=.62+st&&c<.74+st&&(r.ph*13.1%1)<.4)return 'mall';return 'home'}
TOWN.plans={};TOWN.visits={};
const CARE_ICON={gp:'🩺',dental:'🦷',optical:'👓',physio:'💪',admission:'🏥',surgery:'🏥',maternity:'👶',emergency:'🚑'};
function planNow(r,c){const P=TOWN.plans[r.id];if(!P||!P.length)return null;const h=c*24;let cur=P[0];for(const e of P){const [hh,mm]=e.t.split(':').map(Number);if(hh+mm/60<=h)cur=e}return cur}
function placePos(r,place){const n=+r.id.slice(1),j=((n*7)%9-4)*1.1;if(!place||place==='home')return r.homePos;if(place==='work')return r.workPos||r.homePos;
  if(place.startsWith('friend:')){const f=TOWN.byId[place.slice(7)];return f&&f.homePos?{x:f.homePos.x+2+j*.3,z:f.homePos.z+1.5}:r.homePos}
  const key=place==='park'?'fac_park':place==='gym'?'fac_gym':place,W=WPOS[key]||WPOS[place]||WPOS.mall;return {x:W.x+j,z:W.z+(W.z<0?16:-16)+((n*3)%5-2)}}
function locPos(r,l){if(l&&l.startsWith('@'))return placePos(r,l.slice(1));if(l==='work')return r.workPos;if(l==='mall'){const n=+r.id.slice(1);return {x:WPOS.mall.x+((n*5)%23-11)*1.2,z:WPOS.mall.z+16+((n*7)%5)}}return r.homePos}
function route(a,b){const s=a.z>48||a.z<-48?Math.sign(a.z)*0:0;return [{x:a.x,z:a.z+(Math.abs(a.z)<45?(a.z>0?2.1:-2.1):0)},{x:a.x,z:0},{x:b.x,z:0},{x:b.x,z:b.z}]}
function townMove(dt){const c=townClock();
  for(const r of TOWN.residents){if(!r.g||!r.homePos)continue;
    if(!r.trip){const vis=TOWN.visits[r.id],pn=vis&&vis.until>performance.now()?{place:vis.place,label:vis.label}:planNow(r,c);if(pn)r.now=pn;const w=pn?'@'+pn.place:wantLoc(r,c);if(w!==r.loc&&locPos(r,w)){const from=r.car&&r.mode==='car'?{x:r.car.position.x,z:r.car.position.z}:{x:r.g.position.x,z:r.g.position.z};
      r.trip={pts:route(from,locPos(r,w)),i:0,to:w};if(r.mode==='car'&&r.car)r.g.visible=false;if(r.bike)r.bike.visible=true}continue}
    const t=r.trip,obj=(r.mode==='car'&&r.car)?r.car:r.g,sp=(r.mode==='car'?17:r.mode==='bike'?8:4.6)*dt,P=t.pts[t.i],dx=P.x-obj.position.x,dz=P.z-obj.position.z,d=Math.hypot(dx,dz);
    if(d<=sp){obj.position.x=P.x;obj.position.z=P.z;t.i++;if(t.i>=t.pts.length){r.loc=t.to;r.trip=null;if(r.car&&r.mode==='car'){r.g.visible=true;r.g.position.set(obj.position.x+2.2,0,obj.position.z)}if(r.bike)r.bike.visible=false}}
    else{obj.position.x+=dx/d*sp;obj.position.z+=dz/d*sp;obj.rotation.y=Math.atan2(dx,dz)}}}
function townTick(dt,T){if(!TOWN.built)return;const now=performance.now(),show=townG.visible;townMove(Math.min(dt,.1));
  for(const r of TOWN.residents){if(!r.g)continue;const u=r.g.userData,walk=r.trip&&r.mode!=='car',sw=walk?Math.sin(T*9+r.ph)*.6:0;if(u.legs){u.legs[0].rotation.x=sw;u.legs[1].rotation.x=-sw;u.arms[0].rotation.x=-sw*.8;u.arms[1].rotation.x=sw*.8;if(!walk)u.head.rotation.y=Math.sin(T*.5+r.ph)*.4}
    if(r.bub){if(!show||now>r.bubUntil){r.bub.style.opacity=0;continue}const sp=toScreen(v3.set(r.g.position.x,2.9*r.g.scale.y,r.g.position.z));if(sp){r.bub.style.display='';r.bub.style.left=sp[0]+'px';r.bub.style.top=(sp[1]-6)+'px'}else r.bub.style.display='none'}}
  if(selRes&&TOWN.byId[selRes]&&TOWN.byId[selRes].g){const R0=TOWN.byId[selRes],g=R0.g.visible||!R0.car?R0.g:R0.car;ringMesh.visible=true;ringMesh.position.set(g.position.x,.15,g.position.z)}}
function resHit(e){if(!TOWN.built||!townG.visible||fp.on)return null;mouse.set(e.clientX/innerWidth*2-1,-(e.clientY/innerHeight)*2+1);ray.setFromCamera(mouse,cam);const h=ray.intersectObjects(resMeshes,false)[0];return h?h.object.userData.resident:null}
renderer.domElement.addEventListener('pointermove',e=>{if(e.buttons||fp.on||!TOWN.built)return;const nw=performance.now();if(nw-(window._rhT||0)<90)return;window._rhT=nw;const id=resHit(e);
  if(id){const r=TOWN.byId[id];hoverTip.style.display='block';hoverTip.style.left=(e.clientX+14)+'px';hoverTip.style.top=(e.clientY+14)+'px';hoverTip.textContent=`${r.name} · ${r.age} · ${r.gender||''} · ${r.occupation}${r.employer&&r.employer!=='—'?' at '+r.employer:''} · ${r.cover_label}`;renderer.domElement.style.cursor='pointer'}
  else if(hoverTip.textContent&&hoverTip.textContent.includes(' · ')&&!hoverTip.textContent.startsWith('Level')){hoverTip.style.display='none'}});
function goTown(){clearFocus();setView('ext');stopRot();focus={t:new THREE.Vector3(TX+20,0,0),c:new THREE.Vector3(TX+80,130,210)};showLeftTab('town');if(!TOWN.built)toast('Town not loaded','Connect the backend to bring Wattle Grove to life.','#8691ab')}
function selectResident(id){const r=TOWN.byId[id];if(!r)return;if(fp.on)fpExit(true);selWp=null;selRes=id;loadPeople(id);selAgent=null;selDept=null;follow=false;setTP(false);if(mode==='dept'||mode==='one')setView('ext');stopRot();
  {const o=r.g&&r.g.visible?r.g:(r.car||r.g);if(o){const p=o.position;focus={t:new THREE.Vector3(p.x,1,p.z),c:new THREE.Vector3(p.x+22,26,p.z+38)}}}applyFocus();loadRes(id);if(ltab==='town')renderLeft(true)}
function loadRes(id){const base=API();if(!base)return;fetch(`${base}/api/town/residents/${id}`).then(r=>r.json()).then(h=>{TOWN.hist[id]=h;if(selRes===id)renderDetail()}).catch(()=>{})}
function townNow(){if(!(ws&&ws.readyState===1))return toast('Backend offline','Connect the backend to run the town.','#8691ab');emitWS({type:'town_now',limit:4});toast('🏘 Town','A few households are reviewing their health cover now.','#22d3ee')}
function townShareHtml(){const n={};TOWN.residents.forEach(r=>{const k=(r.cover||{}).insurer||'none';n[k]=(n[k]||0)+1});const tot=TOWN.residents.length||1,keys=Object.keys(n).sort((a,b)=>n[b]-n[a]);
  return `<div class="share">${keys.map(k=>`<i style="width:${n[k]/tot*100}%;background:${insCol(k)}" title="${esc(TOWN.insurers[k]||'No cover')}: ${n[k]}"></i>`).join('')}</div><div style="font-size:11px;color:var(--mute);margin-bottom:6px">${keys.map(k=>`<span style="white-space:nowrap;margin-right:8px"><i class="ins" style="background:${insCol(k)}"></i>${esc(TOWN.insurers[k]||'No cover')} ${n[k]}</span>`).join('')}</div>`}
function resDetail(r){const h=TOWN.hist[r.id]||{},rels=h.relations||[],ev=h.events||[],mo=h.money||{},col=insCol((r.cover||{}).insurer);
  const why=h.cover_reason!==undefined?h.cover_reason:r.cover_reason,$=v=>v==null?'–':'$'+Number(v).toLocaleString('en-AU');
  return `<button class="btn sm" data-act="back" style="margin-bottom:10px">← Back</button><div class="head"><div class="av" style="--c:${col}">${r.name.split(' ').map(w=>w[0]).join('')}</div><div><h2>${esc(r.name)}</h2><div class="role">${r.age} · ${esc(r.occupation)}${r.employer&&r.employer!=='—'?' at '+esc(r.employer):''}</div></div></div>
  <h3>Health insurance</h3><div class="state" style="--s:${col};margin-bottom:6px"><i class="sdot" style="--s:${col}"></i><b>${esc(r.cover_label)}</b></div>
  <div class="taskc"><b style="font-size:12px">Why</b><small style="display:block;margin-top:3px;color:${why?'#d6dbe8':'var(--mute)'}">${why?esc(why):'No reason recorded'}</small></div>
  ${talkBox(r.id,r.name)}<h3 style="margin-top:12px">Money (Australian rules)</h3><dl><dt>Income</dt><dd>${$(r.income_aud)} / yr</dd><dt>Household income</dt><dd>${$(mo.household_income_aud)} / yr</dd>
  <dt>Income tier</dt><dd>${esc(mo.income_tier||'–')}</dd><dt>Gov. rebate</dt><dd>${mo.government_rebate_pct!=null?mo.government_rebate_pct+'%':'–'}</dd>
  <dt>Medicare Levy Surcharge</dt><dd>${mo.medicare_levy_surcharge_if_no_hospital_cover_aud?$(mo.medicare_levy_surcharge_if_no_hospital_cover_aud)+' / yr without hospital cover':'none'}</dd><dt>LHC loading</dt><dd>${mo.lhc_loading_pct!=null?mo.lhc_loading_pct+'%':'–'}</dd></dl>
  <h3 style="margin-top:12px">Who they are</h3><div>${(r.traits||[]).map(t=>`<span class="tchip">${esc(t)}</span>`).join('')}${(r.hobbies||[]).map(t=>`<span class="tchip">❤ ${esc(t)}</span>`).join('')}${(r.values||[]).map(t=>`<span class="tchip">★ ${esc(t)}</span>`).join('')}</div>
  <h3 style="margin-top:12px">Home & belongings</h3><dl><dt>Home</dt><dd>${esc((r.home||{}).dwelling||'–')} · ${esc((r.home||{}).tenure||'')} · ${(r.home||{}).bedrooms||'?'} bed · ${esc((r.home||{}).value_or_rent||'')}</dd>
  <dt>Vehicle</dt><dd>${esc(r.vehicle||'–')}</dd><dt>Savings</dt><dd>${esc((r.assets||{}).savings||'–')}</dd><dt>Pets</dt><dd>${esc((r.assets||{}).pets||'none')}</dd></dl>
  <h3 style="margin-top:12px">Today</h3><div class="feed" style="max-height:170px">${(TOWN.plans[r.id]||[]).map(e=>`<div style="${r.now&&r.now.t===e.t?'background:#22d3ee22;border-radius:6px':''}"><time>${e.t}</time><div>${r.now&&r.now.t===e.t?'▶ ':''}${esc(e.label)}</div></div>`).join('')||'<div class="hint">Plans arrive when the company clock runs.</div>'}</div>
  ${r.now?`<div class="hint" style="color:#c4cbdb">Now: ${esc(r.now.label)}</div>`:''}
  <h3 style="margin-top:12px">Health care</h3><div class="feed" style="max-height:150px">${(h.health||[]).map(c=>`<div><time>${(c.date||'').slice(5)}</time><div>${CARE_ICON[c.kind]||'🩺'} ${esc(c.kind)} at ${esc(WNAME[c.facility]||c.facility)} · cost ${c.cost} · fund paid ${c.benefit} · gap ${c.gap}</div></div>`).join('')||'<div class="hint">No visits yet.</div>'}</div>
  <h3 style="margin-top:12px">Life</h3><dl><dt>Lives in</dt><dd>${esc(r.suburb)} · ${esc(r.household_kind.replace('_',' '))} (${esc(r.role_in_household)})</dd><dt>Works at</dt><dd>${esc(WNAME[r.workplace]||r.workplace||'–')}</dd>
  <dt>Gets around</dt><dd>${esc(r.vehicle||'–')}</dd><dt>Right now</dt><dd>${r.trip?'travelling to '+(r.trip.to==='work'?'work':r.trip.to):r.loc==='work'?'at work':r.loc==='mall'?'at the mall':'at home'}</dd><dt>Personality</dt><dd>${esc(r.personality)}</dd></dl>
  <div>${(r.needs||[]).map(n=>`<span class="tchip">${esc(n)}</span>`).join('')}</div>
  <h3 style="margin-top:12px">People they know</h3>${rels.length?rels.map(x=>x.employee?`<div class="row" data-agent="${x.id}" style="--c:${R[x.dept]?R[x.dept].color:'#888'}"><i class="dot"></i><div class="t"><b>${esc(x.name)}</b><small style="display:block">${esc(x.relation)} · works at AI Company: ${esc(x.role)}</small></div></div>`
    :`<div class="row" data-res="${x.id}" style="--c:#8691ab"><i class="dot"></i><div class="t"><b>${esc(x.name)}</b><small style="display:block">${esc(x.relation)} · ${esc(x.cover||'')}</small></div></div>`).join(''):'<div class="hint">Loading…</div>'}
  <h3 style="margin-top:12px">What they did</h3><div class="feed" style="max-height:200px">${ev.length?ev.map(e=>`<div><time>${e.date.slice(5)}</time><div>${KICON[e.kind]||'•'} ${esc(e.text)}</div></div>`).join(''):'<div class="hint">No decisions yet.</div>'}</div>
  ${peopleExtras(r.id)}`}
/* ---------- people: token usage, who they talked with (switch between threads), the conversation ---------- */
const PEOPLE={};
function loadPeople(id,force){const base=API();if(!base)return;const P=PEOPLE[id]||(PEOPLE[id]={});if(P.loading&&!force)return;P.loading=true;
  Promise.all([fetch(`${base}/api/people/${id}/usage`).then(r=>r.json()),fetch(`${base}/api/people/${id}/threads`).then(r=>r.json()),
    fetch(`${base}/api/people/${id}/thread?other=ceo`).then(r=>r.json()),fetch(`${base}/api/people/${id}/memory?limit=12`).then(r=>r.json())]).then(([u,t,c,mem])=>{P.usage=u;P.threads=t;P.ceo=c;P.mem=mem;P.loading=false;
    if(P.sel)openThread(id,P.sel,true);else if((selAgent&&selAgent.id===id)||selRes===id)renderDetail()}).catch(()=>{P.loading=false})}
function openThread(who,other,quiet){const base=API();if(!base)return;const P=PEOPLE[who]||(PEOPLE[who]={});P.sel=other;
  fetch(`${base}/api/people/${who}/thread?other=${encodeURIComponent(other)}`).then(r=>r.json()).then(m=>{P.thread=m;if((selAgent&&selAgent.id===who)||selRes===who)renderDetail()}).catch(()=>{})}
const CHAN={chat:'💬 chat',a2a:'🔗 A2A',handoff:'📤 hand-off',enquiry:'☎️ enquiry',message:'✉️ message',meeting:'🗣 meeting'};
const nm=id=>id==='ceo'?'You (CEO)':AG[id]?AG[id].name:(TOWN.byId[id]?TOWN.byId[id].name:id);
const md1=t=>esc(t).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/(^|\s)\*(\S[^*]*?)\*(?=\s|$|[.,!?])/g,'$1<i>$2</i>');
function talkBox(id,name){const P=PEOPLE[id]||{},first=String(name).split(' ')[0],msgs=(P.ceo||[]).slice(-12);
  return `<h3 style="margin-top:12px">Talk to ${esc(first)}</h3><div class="feed conv" id="talkFeed" style="max-height:200px">${msgs.map(m=>`<div class="cl ${m.frm==='ceo'?'user':'speech'}"><b style="color:${m.frm==='ceo'?'#f5b942':'#22d3ee'}">${m.frm==='ceo'?'You':esc(first)}</b> <small>${(m.sim_date||'').slice(5)}</small><div>${md1(m.text)}</div></div>`).join('')||`<div class="hint">Say hello to ${esc(first)}. They remember your conversation.</div>`}${P.typing?`<div class="cl speech"><b style="color:#22d3ee">${esc(first)}</b><div>… thinking <span id="tkWait">${Math.round((Date.now()-(P.typingSince||Date.now()))/1000)}s</span></div></div>`:''}</div>
  <div class="crow"><input type="text" id="tkIn" data-who="${id}" placeholder="Talk to ${esc(first)}…"><button class="btn pri" data-act="tk" data-who="${id}">Send</button></div>`}
function talkTo(id){const q=document.getElementById('tkIn'),t=q?q.value.trim():'',base=API();if(!t)return;if(!base)return toast('Backend offline','Connect the backend to talk to people.','#8691ab');
  const P=PEOPLE[id]||(PEOPLE[id]={});P.ceo=(P.ceo||[]).concat([{frm:'ceo',text:t,sim_date:''}]);P.typing=true;P.typingSince=Date.now();q.value='';renderDetail();
  clearInterval(P.tick);P.tick=setInterval(()=>{const w=document.getElementById('tkWait');if(!P.typing){clearInterval(P.tick);return}if(w)w.textContent=Math.round((Date.now()-P.typingSince)/1000)+'s'},1000);
  fetch(`${base}/api/people/${id}/talk`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:t})}).then(r=>r.json()).then(j=>{P.typing=false;P.ceo=P.ceo.concat([{frm:id,text:j.reply||'…',sim_date:''}]);renderDetail();setTimeout(()=>loadPeople(id,true),800)})
    .catch(()=>{P.typing=false;renderDetail()})}
function peopleExtras(id){const P=PEOPLE[id]||{},u=(P.usage||{}).total,th=P.threads||[],mem=P.mem||[];
  const fmt=n=>n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e3?(n/1e3).toFixed(1)+'k':String(n||0);
  let h=`<h3 style="margin-top:12px">AI usage <button class="btn sm" data-act="pref" data-who="${id}" style="float:right;padding:1px 7px">↻</button></h3>`;
  h+=u?`<div class="mets"><div class="met"><small>Tokens</small><b>${fmt(u.tokens)}</b></div><div class="met"><small>Input</small><b>${fmt(u.prompt)}</b></div><div class="met"><small>Output</small><b>${fmt(u.output)}</b></div><div class="met"><small>Model calls</small><b>${fmt(u.calls)}</b></div></div>`:'<div class="hint">Loading…</div>';
  h+=`<h3 style="margin-top:12px">Memory <span>${mem.length}</span></h3><div class="feed" style="max-height:170px">${mem.map(m=>`<div><time>${(m.sim_date||'').slice(5)}</time><div>🧠 ${esc(m.text)}</div></div>`).join('')||'<div class="hint">Nothing remembered yet.</div>'}</div>`;
  h+=`<h3 style="margin-top:12px">Who they talked with <span>${th.length}</span></h3>`;
  h+=th.length?`<table class="acc"><tr><th>With</th><th>Channel</th><th>Msgs</th><th>Last</th></tr>${th.map(t=>`<tr data-thread="${esc(t.other)}" data-who="${id}" style="cursor:pointer;${P.sel===t.other?'background:#ffffff12':''}"><td><b>${esc(t.name||nm(t.other))}</b><div class="hint" style="font-size:10.5px">${esc(t.role||t.kind||'')}</div></td><td>${CHAN[t.channel]||t.channel}</td><td>${t.n}</td><td>${(t.last_date||'').slice(5)}</td></tr>`).join('')}</table>`:'<div class="hint">No conversations yet.</div>';
  if(P.sel&&P.thread){h+=`<h3 style="margin-top:12px">Conversation with ${esc(nm(P.sel))}</h3><div class="feed conv">${P.thread.map(m=>`<div class="cl ${m.frm===id?'speech':'user'}"><b style="color:${m.frm===id?'#22d3ee':'#f5b942'}">${esc(nm(m.frm))}</b> <small>${CHAN[m.channel]||m.channel} · ${(m.sim_date||'').slice(5)}${m.room?' · '+esc(R[m.room]?R[m.room].name:m.room):''}</small><div>${md1(m.text)}</div></div>`).join('')||'<div class="hint">Empty.</div>'}</div>`}
  return h}
setInterval(()=>{const id=selAgent?selAgent.id:selRes;if(id&&!(PEOPLE[id]||{}).typing&&document.activeElement.id!=='tkIn')loadPeople(id,true)},15000);
/* ---------- workplaces: click a building to see who works there ---------- */
function wpHit(e){if(fp.on||!townG.visible)return null;mouse.set(e.clientX/innerWidth*2-1,-(e.clientY/innerHeight)*2+1);ray.setFromCamera(mouse,cam);const h=ray.intersectObjects(wpMeshes,false)[0];return h?h.object.userData.workplace:null}
function selectWorkplace(wp){selWp=wp;selRes=null;selAgent=null;selDept=null;const W=WPOS[wp];if(W)focus={t:new THREE.Vector3(W.x,2,W.z),c:new THREE.Vector3(W.x+30,40,W.z+(W.z<0?55:-55))};stopRot();applyFocus()}
function wpDetail(wp){const L=TOWN.residents.filter(r=>r.workplace===wp),n={};L.forEach(r=>{const k=(r.cover||{}).insurer||'none';n[k]=(n[k]||0)+1});const now=L.filter(r=>r.loc==='work').length;
  return `<button class="btn sm" data-act="back" style="margin-bottom:10px">← Back</button><div class="head"><div><h2>${esc(WNAME[wp]||wp)}</h2><div class="hint">${L.length} residents work or study here · ${now} here right now</div></div></div>
  <h3>Their health insurance</h3><div>${Object.entries(n).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<span class="tchip"><i class="ins" style="background:${insCol(k)}"></i>${esc(TOWN.insurers[k]||'No cover')} ${v}</span>`).join('')||'<span class="hint">–</span>'}</div>
  <h3 style="margin-top:12px">People</h3>${L.map(r=>`<div class="row" data-res="${r.id}" style="--c:${insCol((r.cover||{}).insurer)}"><i class="dot"></i><div class="t"><b>${esc(r.name)}</b><small style="display:block">${esc(r.occupation)} · ${esc(r.employer||'')} · $${Number(r.income_aud||0).toLocaleString('en-AU')}/yr</small></div></div>`).join('')||'<div class="hint">Nobody yet.</div>'}`}
renderer.domElement.addEventListener('pointermove',e=>{if(e.buttons||fp.on||!TOWN.built)return;if(resHit(e))return;const wp=wpHit(e);if(wp){hoverTip.style.display='block';hoverTip.style.left=(e.clientX+14)+'px';hoverTip.style.top=(e.clientY+14)+'px';
  hoverTip.textContent=`${WNAME[wp]} · ${TOWN.residents.filter(r=>r.workplace===wp).length} people work here — click`;renderer.domElement.style.cursor='pointer'}});
function rTown(){const ev=TOWN.events.filter(e=>e.kind!=='web').slice(0,40);
  const tc=townClock()*24;coBody.innerHTML=`<div style="display:flex;gap:10px;align-items:center;margin-bottom:6px"><b>Wattle Grove · ${TOWN.residents.length} residents · town time ${String(Math.floor(tc)).padStart(2,'0')}:${String(Math.floor(tc%1*60)).padStart(2,'0')}</b><button class="btn sm pri" id="twGo">▶ Let households review their cover now</button><button class="btn sm" id="twFly">🏘 Show the town</button></div>
  ${townShareHtml()}<div class="hint" style="margin-bottom:10px">Colours show who each resident is insured with. AI Company Health is cyan. Residents decide with real company data, a comparison site (four fictional competitors), the web, their friends and family, and your staff.</div>
  <h3>Active campaigns</h3>${TOWN.campaigns.length?TOWN.campaigns.map(c=>`<div class="frow" style="cursor:default"><i>📣</i><div><b style="max-width:none">${esc(c.title)}</b><small>${esc(c.message||'')} ${c.offer?'· '+esc(c.offer):''} · until ${c.until||''}</small></div></div>`).join(''):'<div class="hint">None. Marketing reviews the town on Wednesdays.</div>'}
  <h3 style="margin-top:12px">Built by the town council</h3>${(TOWN.facilities||[]).length?(TOWN.facilities||[]).map(f=>`<div class="frow" style="cursor:default"><i>🏗️</i><div><b style="max-width:none">${esc(f.name)}</b><small>${esc(f.reason||'')} · ${f.built}</small></div></div>`).join(''):'<div class="hint">Nothing yet. The council meets on the 1st of each month.</div>'}
  ${(TOWN.departed||[]).length?`<h3 style="margin-top:12px">Remembered</h3><div class="hint" style="color:#c4cbdb">${(TOWN.departed||[]).map(d=>`🕊️ ${esc(d.name)} (${d.age})`).join(' · ')}</div>`:''}
  <h3 style="margin-top:12px">Latest decisions</h3><div class="feed" style="max-height:340px">${ev.length?ev.map(e=>{const r=TOWN.byId[e.resident]||{};return `<div><time>${(e.date||'').slice(5)}</time><div><span style="color:${insCol(e.insurer)}">●</span> ${KICON[e.kind]||'•'} ${esc(e.text||'')}</div></div>`}).join(''):'<div class="hint">No decisions yet.</div>'}</div>`;
  document.getElementById('twGo').onclick=townNow;document.getElementById('twFly').onclick=()=>{closeCo();goTown()}}
