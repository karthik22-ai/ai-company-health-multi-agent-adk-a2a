/* AI Company HQ – Employees: 3D characters, animation and commanded movement.
   Loaded in the order of js/manifest.json and served as one script (/ui/app.js). */
/* ================= CHARACTERS ================= */
const SKINS=[0xf6d5b8,0xf2c8a0,0xe0a97c,0xc68642,0xa86a3c,0x8d5524,0x6b4423,0x4a2f1b],HAIRS=[0x15151a,0x2a1b12,0x3a2a1a,0x6b3f1d,0xb5651d,0xd9b36c,0x8a8a92,0x9b2d20];
const PANTS=[0x232a3d,0x2b3350,0x3a3f4f,0x4a4538,0x1d2433],SHOES=[0x0d0f16,0xe8ecf4,0x5b4636,0x1b2a44],BLAZERS=[0x1b2540,0x2a2a33,0x40202c,0x1f3a34];
const LEADER=/head|cfo|controller|treasurer|lead|manager|chief|officer/i;
function makeChar(color,seed,leader,dept){
  const H=(k,n)=>{const v=Math.sin(seed*12.9898+k*78.233)*43758.5453;return Math.floor((v-Math.floor(v))*n)};
  const g=new THREE.Group(),skin=M(SKINS[H(1,8)],{roughness:.75}),hair=M(HAIRS[H(2,8)],{roughness:.85}),pants=M(PANTS[H(3,5)],{roughness:.8}),
    top=leader?M(BLAZERS[H(5,4)],{roughness:.55}):M(color,{roughness:.6}),shoe=M(SHOES[H(4,4)],{roughness:.4}),white=M(0xf2f4fa,{roughness:.5});
  const style=H(6,8),beard=H(7,5)===0&&[0,3,4,7].includes(style),glasses=H(8,3)===0,watch=H(12,3)!==0,hs=.95+H(9,6)*.02,build=.94+H(10,5)*.03;
  const body=new THREE.Group();body.scale.x=build;g.add(body);
  cyl(.42,.46,.36,pants,0,1.32,0,body,18).scale.z=.62;
  cyl(.5,.42,1.15,top,0,1.92,0,body,18).scale.z=.62;
  box(.98,.07,.5,M(0x151a28),0,1.5,0,body,false);
  [-1,1].forEach(s=>{const sp=new THREE.Mesh(new THREE.SphereGeometry(.17,12,10),top);sp.position.set(s*.6,2.38,0);body.add(sp)});
  if(leader){box(.3,.75,.04,white,0,1.98,.3,body,false);box(.1,.6,.05,M(color,{roughness:.5}),0,1.93,.33,body,false)}else box(.36,.1,.34,white,0,2.5,.1,body,false);
  box(.22,.28,.03,white,.2,1.78,.3,body,false);box(.22,.07,.035,M(color),.2,1.89,.3,body,false);
  cyl(.14,.15,.22,skin,0,2.55,0,body,10);
  const head=new THREE.Group();head.position.set(0,2.92,0);body.add(head);
  const hs0=new THREE.Mesh(new THREE.SphereGeometry(.4,22,16),skin);hs0.scale.set(1,1.1,.95);hs0.castShadow=true;head.add(hs0);
  const dark=new THREE.MeshBasicMaterial({color:0x15151a}),eyes=[];
  [-1,1].forEach(s=>{
    const e=new THREE.Mesh(new THREE.SphereGeometry(.07,10,8),new THREE.MeshBasicMaterial({color:0xffffff}));e.position.set(s*.14,.05,.33);e.scale.z=.5;head.add(e);eyes.push(e);
    const pu=new THREE.Mesh(new THREE.SphereGeometry(.035,8,6),dark);pu.position.set(s*.14,.05,.365);head.add(pu);eyes.push(pu);
    box(.16,.03,.03,hair,s*.14,.15,.36,head,false);
    const ear=new THREE.Mesh(new THREE.SphereGeometry(.07,8,6),skin);ear.position.set(s*.4,0,0);head.add(ear);
  });
  const nose=new THREE.Mesh(new THREE.SphereGeometry(.05,8,6),skin);nose.position.set(0,-.02,.4);head.add(nose);
  const mouth=box(.15,.025,.02,M(0x8a3b3b),0,-.14,beard?.43:.37,head,false);
  const cap=(r=.43,tl=.55)=>{const h=new THREE.Mesh(new THREE.SphereGeometry(r,20,12,0,Math.PI*2,0,Math.PI*tl),hair);h.position.set(0,.04,-.03);h.scale.set(1,1.1,1);head.add(h)};
  switch(style){
    case 0:cap();break;
    case 1:cap(.43,.6);box(.8,.9,.2,hair,0,-.3,-.3,head,false);[-1,1].forEach(s=>box(.12,.6,.3,hair,s*.4,-.15,-.1,head,false));break;
    case 2:{cap();const b=new THREE.Mesh(new THREE.SphereGeometry(.18,10,8),hair);b.position.set(0,.5,-.2);head.add(b)}break;
    case 3:cap(.42,.4);break;
    case 4:cap();box(.5,.1,.25,hair,.08,.36,.28,head,false);break;
    case 5:cap();[[-.2,-.42,.17],[-.5,-.45,.15],[-.78,-.42,.13]].forEach(([y,z,r])=>{const sp=new THREE.Mesh(new THREE.SphereGeometry(r,8,6),hair);sp.position.set(0,y,z);head.add(sp)});break;
    case 6:cap(.44,.62);for(let i=0;i<9;i++){const a=i/9*6.283,sp=new THREE.Mesh(new THREE.SphereGeometry(.17,8,6),hair);sp.position.set(Math.cos(a)*.38,.2+Math.sin(i*2)*.1,Math.sin(a)*.34-.05);head.add(sp)}break;
    default:cap(.415,.5)}
  if(beard){const bd=new THREE.Mesh(new THREE.SphereGeometry(.415,18,10,0,Math.PI*2,Math.PI*.6,Math.PI*.3),hair);bd.scale.set(1,1.1,.97);head.add(bd);box(.22,.04,.05,hair,0,-.08,.4,head,false)}
  if(glasses){[-1,1].forEach(s=>{const gl=new THREE.Mesh(new THREE.TorusGeometry(.1,.014,6,16),dark);gl.position.set(s*.14,.05,.4);head.add(gl)});box(.09,.014,.014,dark,0,.06,.41,head,false)}
  if(!leader&&(dept==='care'||dept==='sales')&&H(11,4)!==0){const hm=M(0x1b1f2a,{roughness:.45}),acc=M(0x22d3ee,{emissive:0x22d3ee,emissiveIntensity:.7});
    const band=new THREE.Mesh(new THREE.TorusGeometry(.47,.035,6,22,Math.PI),hm);band.position.y=.06;head.add(band);
    [-1,1].forEach(s=>{const cup=cyl(.13,.13,.09,hm,s*.44,.02,0,head,14);cup.rotation.z=Math.PI/2});
    const boom=box(.035,.035,.34,hm,-.41,-.14,.17,head,false);boom.rotation.y=.35;
    const mic=new THREE.Mesh(new THREE.SphereGeometry(.05,8,6),acc);mic.position.set(-.35,-.15,.33);head.add(mic)}
  [-1,1].forEach(s=>{const ck=new THREE.Mesh(new THREE.SphereGeometry(.06,8,6),M(0xe58e8e,{roughness:.9,transparent:true,opacity:.35}));ck.position.set(s*.22,-.08,.33);ck.scale.z=.3;head.add(ck)});
  const arm=s=>{const sh=new THREE.Group();sh.position.set(s*.62,2.38,0);body.add(sh);cyl(.12,.11,.55,top,0,-.275,0,sh,10);
    const el=new THREE.Group();el.position.set(0,-.55,0);sh.add(el);cyl(.105,.09,.5,top,0,-.25,0,el,10);
    const hd=new THREE.Mesh(new THREE.SphereGeometry(.11,10,8),skin);hd.position.y=-.56;hd.scale.set(.9,1.2,.75);el.add(hd);
    cyl(.095,.095,.05,skin,0,-.5,0,el,10);if(s<0&&watch){cyl(.107,.107,.07,M(0x1d222c,{roughness:.3}),0,-.45,0,el,12);const f=box(.09,.012,.09,M(0x9fd8ff,{emissive:0x9fd8ff,emissiveIntensity:.5}),0,-.45,.1,el,false);f.rotation.x=Math.PI/2}return [sh,el]};
  const leg=s=>{const hp=new THREE.Group();hp.position.set(s*.22,1.3,0);body.add(hp);cyl(.19,.16,.65,pants,0,-.325,0,hp,10);
    const kn=new THREE.Group();kn.position.set(0,-.65,0);hp.add(kn);cyl(.15,.13,.65,pants,0,-.325,0,kn,10);box(.3,.16,.56,shoe,0,-.57,.1,kn);return [hp,kn]};
  const [shL,elL]=arm(-1),[shR,elR]=arm(1),[hipL,kneeL]=leg(-1),[hipR,kneeR]=leg(1);
  g.userData={body,head,mouth,eyes,hs,shL,elL,shR,elR,hipL,kneeL,hipR,kneeR,cur:{hl:-1.5,hr:-1.5,kl:1.5,kr:1.5,sl:-.45,sr:-.45,el:-.95,er:-.95,by:-SIT_DY,hy:0,hx:0,slz:0,srz:0}};return g;
}
const agents=[],AG={};
function spawnAgent(r,name,role,i,fixedId){
  const id=fixedId||`${r.id}.${name.split(' ')[0].toLowerCase()}`,g=makeChar(new THREE.Color(r.color),agents.length+i,LEADER.test(role),r.id),s=r.seats[i];
  const hs=g.userData.hs;g.scale.setScalar(BASE*hs);g.position.set(s.x,r.y,s.z);g.rotation.y=s.ang;scene.add(g);
  const mats=new Set();g.traverse(o=>{if(o.isMesh)mats.add(o.material)});
  const p={id,name,role,home:r,g,seat:s,cur:r.id,floor:r.floor,state:'idle',text:'Idle',moving:false,dest:null,phase:rnd(0,6),ph:rnd(0,6),path:[],ang:s.ang,angT:s.ang,sc:BASE*hs,scT:BASE*hs,base:BASE*hs,gen:0,chat:[],
    ini:name.split(' ').map(w=>w[0]).join(''),bub:null,bubUntil:0,lifting:false,sit:1,sitT:1,task:null,mon:s.monitor,q:Promise.resolve(),seatInfo:null,dim:false,mats:[...mats],
    chip:dom('chip',`<i class="sd"></i><span class="r">${role}</span><span class="n">${name}</span>`,r.color)};
  g.traverse(o=>{if(o.isMesh)o.userData.person=p});agents.push(p);AG[id]=p;return p}
TEAMROOMS.forEach(r=>r.team.people.forEach(([name,role],i)=>spawnAgent(r,name,role,i)));

function wrapText(c,txt,maxW,maxLines){const words=String(txt).split(' ');const lines=[];let cur='';for(const w of words){const t=cur?cur+' '+w:w;if(c.measureText(t).width>maxW&&cur){lines.push(cur);cur=w}else cur=t}lines.push(cur);return lines.slice(0,maxLines)}
const MON_TOK=['#7dd3fc','#c4b5fd','#86efac','#fca5a5','#fcd34d','#e8ecf6'];
function updateMonitor(p){
  if(!p.mon)return;
  if(!p.cv){p.cv=document.createElement('canvas');p.cv.width=640;p.cv.height=360;p.tex=new THREE.CanvasTexture(p.cv);p.tex.encoding=THREE.sRGBEncoding;p.mon.material=new THREE.MeshBasicMaterial({map:p.tex,toneMapped:false})}
  const c=p.cv.getContext('2d'),W=320,H=180,t=performance.now()/1000,st=p.state,col=STATE[st]||'#8691ab',hc=p.home.color,fr=k=>{const v=Math.sin(k*12.9898+p.ph*78.233)*43758.5453;return v-Math.floor(v)};
  c.setTransform(2,0,0,2,0,0);
  const bg=c.createLinearGradient(0,0,0,H);bg.addColorStop(0,'#0f1834');bg.addColorStop(1,'#070b18');c.fillStyle=bg;c.fillRect(0,0,W,H);
  c.fillStyle=hc;c.fillRect(0,0,W,24);c.textBaseline='middle';c.textAlign='left';c.fillStyle='#0b1226';c.font='700 12.5px system-ui,sans-serif';
  const lbl=st.toUpperCase();c.font='800 10px system-ui,sans-serif';const lw=c.measureText(lbl).width+22;
  c.font='700 12.5px system-ui,sans-serif';let hd=p.name+' · '+p.role;while(hd.length>4&&c.measureText(hd).width>W-lw-22)hd=hd.slice(0,-2);if(hd!==p.name+' · '+p.role)hd=hd.trimEnd()+'…';c.fillText(hd,8,12.5);c.font='800 10px system-ui,sans-serif';
  c.fillStyle='#0b1226cc';c.beginPath();c.roundRect?c.roundRect(W-lw-6,5,lw,15,7):c.rect(W-lw-6,5,lw,15);c.fill();
  c.fillStyle=col;c.globalAlpha=st==='working'?.55+.45*Math.sin(t*5):1;c.beginPath();c.arc(W-lw+3,12.5,3.5,0,7);c.fill();c.globalAlpha=1;c.fillStyle='#e8ecf6';c.fillText(lbl,W-lw+10,13);
  const title=p.task?p.task.title:(st==='idle'?'No active task':p.text);c.fillStyle='#f4f6fb';c.font='700 15px system-ui,sans-serif';
  wrapText(c,title,W-20,2).forEach((l,i)=>c.fillText(l,10,40+i*18));
  const y0=72,y1=146;
  if(st==='working'){
    const scroll=Math.floor(t*1.6+p.ph*10);c.font='600 9.5px ui-monospace,Menlo,monospace';
    for(let i=0;i<6;i++){const idx=scroll+i,ind=Math.floor(fr(idx+.5)*3)*10,y=y0+6+i*12;let x=10+ind;
      c.fillStyle='#4a5b8c';c.fillText(String(100+idx%900).padStart(3,' '),4-0,y);x+=16;
      const segs=1+Math.floor(fr(idx+.2)*3);for(let k=0;k<segs;k++){const w=14+fr(idx*3+k)*46;c.fillStyle=MON_TOK[Math.floor(fr(idx*7+k)*MON_TOK.length)];c.fillRect(x,y-3,Math.min(w,200-x),5);x+=w+5;if(x>196)break}
      if(i===5&&Math.sin(t*6)>0){c.fillStyle='#f4f6fb';c.fillRect(x,y-5,5,9)}}
    c.fillStyle='#ffffff10';c.fillRect(212,y0,98,y1-y0);c.strokeStyle=hc;c.lineWidth=1.6;c.beginPath();
    for(let i=0;i<=20;i++){const v=.5+.32*Math.sin(i*.7+t*1.3+p.ph)+.12*Math.sin(i*1.9+t*.7);const x=216+i*4.5,y=y1-6-v*(y1-y0-14);i?c.lineTo(x,y):c.moveTo(x,y)}c.stroke();
    c.fillStyle='#aab3c8';c.font='600 9px system-ui,sans-serif';c.fillText('live',216,y0+8);
  }else if(st==='meeting'){c.fillStyle='#c4b5fd';c.font='800 15px system-ui,sans-serif';c.fillText('● In a meeting',12,y0+18);c.fillStyle='#aab3c8';c.font='600 12px system-ui,sans-serif';c.fillText(R[p.cur]?R[p.cur].name:'',12,y0+40);
    for(let i=0;i<12;i++){const h=6+Math.abs(Math.sin(t*4+i*.8+p.ph))*26;c.fillStyle='#c4b5fd88';c.fillRect(200+i*9,y1-6-h,5,h)}}
  else if(st==='blocked'||st==='error'){c.fillStyle=st==='error'?'#ff6b6b33':'#f5b94233';c.fillRect(8,y0,W-16,y1-y0);c.fillStyle=col;c.font='800 16px system-ui,sans-serif';c.fillText(st==='error'?'⚠ Something went wrong':'✋ Needs help',16,y0+20);
    c.fillStyle='#e8ecf6';c.font='600 11.5px system-ui,sans-serif';wrapText(c,p.text||'',W-36,3).forEach((l,i)=>c.fillText(l,16,y0+42+i*15))}
  else if(st==='done'){c.fillStyle='#2ee6a6';c.font='800 30px system-ui,sans-serif';c.fillText('✓',14,y0+30);c.font='800 15px system-ui,sans-serif';c.fillText('Task complete',48,y0+30);c.fillStyle='#aab3c8';c.font='600 11px system-ui,sans-serif';c.fillText('Ready for the next one',48,y0+48)}
  else{c.fillStyle='#4a5b8c';c.font='700 13px system-ui,sans-serif';c.fillText('Waiting for work',12,y0+20);c.font='800 30px system-ui,sans-serif';c.fillStyle='#ffffff22';
    const d=new Date();c.fillText(String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0'),12,y0+56)}
  if(p.task&&p.task.progress!=null){c.fillStyle='#1d2740';c.fillRect(10,156,W-60,9);c.fillStyle=hc;c.fillRect(10,156,(W-60)*Math.max(0,Math.min(100,p.task.progress))/100,9);
    c.fillStyle='#e8ecf6';c.font='700 11px system-ui,sans-serif';c.textAlign='right';c.fillText(Math.round(p.task.progress)+'%',W-10,161);c.textAlign='left'}
  else{c.fillStyle='#4a5b8c';c.font='600 10px system-ui,sans-serif';c.fillText(p.home.name,10,162)}
  p.tex.needsUpdate=true}
let monAcc=0,monI=0;
function monitorTick(dt){monAcc+=dt;if(monAcc<.3)return;monAcc=0;
  const L=agents.filter(p=>p.mon&&p.g.visible&&(p.state==='working'||p.state==='meeting'||p.state==='blocked'||p.state==='error'));
  const n=Math.min(L.length,4);for(let i=0;i<n;i++)updateMonitor(L[(monI+i)%L.length]);monI+=n;
  const foc=fp.on&&fp.zoomed&&fp.cur&&fp.cur.agent;if(foc&&!L.includes(foc))updateMonitor(foc)}
agents.forEach(updateMonitor);
/* ================= MOVEMENT (only runs when commanded) ================= */
const walk=(p,pts)=>new Promise(res=>{p.path=pts.map(a=>new THREE.Vector3(a[0],0,a[1]));p.done=res});
const face=(p,x,z)=>{p.angT=Math.atan2(x-p.g.position.x,z-p.g.position.z)};
const liftPulse=[0,0,0];
async function ride(p,toF,gen){
  p.lifting=true;p.scT=0;liftPulse[p.floor]=1;await sleep(380);if(gen!==p.gen)return false;
  const from=p.floor;p.floor=toF;p.g.position.set(0,FY[toF]+TOP,-CZ-.5);liftPulse[toF]=1;
  await sleep(600+Math.abs(toF-from)*500);if(gen!==p.gen)return false;p.scT=p.base;await sleep(380);if(gen!==p.gen)return false;p.lifting=false;return true;
}
async function go(p,toId,tgt){
  const gen=p.gen;if(p.sitT){p.sitT=0;await sleep(450);if(gen!==p.gen)return false}
  const A=R[p.cur],Z=R[toId];p.moving=true;p.dest=Z.name;p.cur='corridor';
  const W=async pts=>{await walk(p,pts);return gen===p.gen};
  if(A===Z){if(!await W([[tgt.x,tgt.z]]))return false}
  else if(A.floor===Z.floor){if(!await W([[A.inside.x,A.inside.z],[A.cx,0],[Z.cx,0],[Z.inside.x,Z.inside.z],[tgt.x,tgt.z]]))return false}
  else{if(!await W([[A.inside.x,A.inside.z],[A.cx,0],[0,0],[0,-CZ+.6]]))return false;if(!await ride(p,Z.floor,gen))return false;
    if(!await W([[0,-1],[0,0],[Z.cx,0],[Z.inside.x,Z.inside.z],[tgt.x,tgt.z]]))return false}
  p.cur=toId;p.moving=false;p.dest=null;return true;
}
function spotIn(r){return r.team?{x:r.cx+rnd(-r.w/2+4,r.w/2-4),z:r.inside.z+(r.north?1:-1)*rnd(-.5,2)}:{x:rnd(r.x0+3,r.x1-3),z:rnd(r.z0+3,r.z1-3)}}
function release(p){if(p.seatInfo){p.seatInfo.room.occ[p.seatInfo.idx]=null;p.seatInfo=null}}
function allocSeat(r,p){if(!r.seats||r.team)return null;const i=r.seats.findIndex((s,k)=>!r.occ[k]);if(i<0)return null;r.occ[i]=p;p.seatInfo={room:r,idx:i};return r.seats[i]}

/* ---------- state / bubbles / log ---------- */
const feed=document.getElementById('feed');
const activity=[];
function log(html,color='#8691ab',p){const t=new Date().toTimeString().slice(0,8);activity.unshift({t,html,color,agent:p&&p.id,dept:p&&p.home.id});if(activity.length>400)activity.pop();
  const d=document.createElement('div');d.innerHTML=`<time>${t}</time><div><span style="color:${color}">●</span> ${html}</div>`;feed.prepend(d);while(feed.children.length>40)feed.lastChild.remove()}
function say(p,txt,ms=3500){if(!p.bub)p.bub=dom('bub','');p.bub.textContent=txt;p.bub.style.opacity=1;p.bubUntil=performance.now()+ms}
const effState=p=>p.moving?'walking':p.state;
const emitter={};function emit(ev,d){(emitter[ev]||[]).forEach(f=>{try{f(d)}catch(e){console.error(e)}});if(ws&&ws.readyState===1&&['arrived','select','state'].includes(ev))ws.send(JSON.stringify({type:ev,...d}))}
const queue=(p,fn)=>{const g=p.gen;p.q=p.q.then(()=>g===p.gen?fn():undefined).catch(e=>console.error(e));return p.q};

/* ---------- public command API ---------- */
function A(x){if(x&&x.g)return x;const k=String(x).toLowerCase();return AG[k]||agents.find(a=>a.name.toLowerCase()===k||a.role.toLowerCase()===k)||(()=>{throw new Error('unknown agent '+x)})()}
function Rm(x){if(x&&x.cx!=null)return x;const k=String(x).toLowerCase();return R[k]||ROOMS.find(r=>r.name.toLowerCase()===k)||(()=>{throw new Error('unknown room '+x)})()}
/* ---------- feature state ---------- */
const policy={autoHuddle:false},meetings={},huddles={},tasks=[];let taskN=0,applying=false;
const RP={on:false,playing:false,speed:1,pos:0,idx:0,dur:0,pending:[]};
const rec=[],recT0=performance.now(),flyers=[],pulses=[];
function record(ev){if(applying||RP.on)return;ev.t=performance.now()-recT0;rec.push(ev);if(rec.length>4000)rec.shift()}
function emitWS(o){if(ws&&ws.readyState===1)ws.send(JSON.stringify(o))}
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function taskFor(p,title,o={}){
  let t=o.id?tasks.find(x=>x.id===o.id):tasks.find(x=>x.agent===p.id&&x.title===title&&x.status!=='done');
  if(!t){t={id:o.id||('t'+(++taskN)),agent:p.id,title,progress:null,status:o.status||'doing',note:'',created:Date.now()};tasks.push(t)}
  t.title=title;if(o.progress!=null)t.progress=o.progress;if(o.note!=null&&o.note!=='')t.note=o.note;if(o.status)t.status=o.status;t.updated=Date.now();
  if(t.progress!=null&&t.progress>=100)t.status='done';return t}
function autoSlide(p){const tk=p.task,logs=activity.filter(e=>e.agent===p.id).slice(0,3).map(e=>e.html.replace(/<[^>]+>/g,'').trim()).reverse();
  return {title:tk?tk.title:p.role+' update',bullets:[...(tk&&tk.note?[tk.note]:[]),...logs],progress:tk?tk.progress:null}}
function pushChat(p,from,text){p.chat.push({from,text,t:Date.now()});if(p===selAgent)renderChat()}
const MEETRS=['mr1','mr2','mr3'];
function freeRoom(){return MEETRS.map(id=>R[id]).find(r=>!meetings[r.id]&&!agents.some(p=>p.cur===r.id||p.dest===r.name))||R.brd}
function attendeesFace(r,on){agents.forEach(p=>{if(p.seatInfo&&p.seatInfo.room===r&&!p.moving&&p.cur===r.id){const st=r.seats[p.seatInfo.idx];p.angT=on&&r.screenPos?Math.atan2(r.screenPos.x-st.x,r.screenPos.z-st.z):st.ang}})}
function watchRoom(r){saveView();selDept=null;selAgent=null;follow=false;setTP(false);curFloor=r.floor;mode='one';applyView();stopRot();
  const k=aspectK(),w=Math.max(r.w,18);focus={t:new THREE.Vector3(r.cx,r.y+1,r.cz),c:new THREE.Vector3(r.cx+.3*w*k,r.y+.9*w*k,r.cz+1.1*w*k)};applyFocus()}
function autoHuddle(p,text){
  if(RP.on||huddles[p.id]||(p.state!=='blocked'&&p.state!=='error'))return;
  const ids=new Set([p.id]),t=String(text||''),lead=agents.find(a=>a.name===p.home.team.lead);
  if(lead&&lead!==p)ids.add(lead.id);else{const o=agents.find(a=>a.home===p.home&&a!==p);if(o)ids.add(o.id)}
  if(/secur|compli|access|polic|audit|privacy|risk|sox|breach|exception/i.test(t)||p.state==='error')ids.add('risk.isabel');
  if(/data|pipeline|warehouse|report/i.test(t))ids.add('data.arjun');
  if(/price|pricing|premium|plan/i.test(t))ids.add('prod.elena');
  if(/claim|backlog|fraud/i.test(t))ids.add('claims.helen');
  const r=freeRoom();huddles[p.id]={room:r.id};
  toast('Huddle called',[...ids].map(i=>AG[i].name.split(' ')[0]).join(', ')+' → '+r.name,'#e2b714',()=>watchRoom(r));
  log(`Huddle in <b>${r.name}</b> to resolve <b>${p.name}</b>'s issue`,'#e2b714',p);
  HQ.meeting(r,[...ids],'Huddle: '+(t||p.state),{keep:[p.id]});
}
function endHuddle(p){const h=huddles[p.id];if(!h)return;delete huddles[p.id];HQ.endMeeting(h.room);log(`Huddle ended · <b>${p.name}</b> is unblocked`,'#2ee6a6',p)}
function alertAgent(p,state,text){toast(`${p.name} is ${state}`,`${p.role}${text?' · '+text:''}`,STATE[state],()=>focusAgent(p.id));beep(state==='error'?'error':'warn')}
function localReply(p,text){
  const t=text.toLowerCase(),tk=p.task;let r;
  if(/demo|show me|present|walk me|demonstrate/.test(t)){const rm=freeRoom();HQ.chatReply(p,`Sure — I'll set up in ${rm.name} and walk you through my work.`);HQ.summon([p.id],rm.id,'Demo for you');return}
  if(/where|which room|location/.test(t)){HQ.chatReply(p,`I'm in ${R[p.cur]?R[p.cur].name:'the corridor'}.`);return}
  if(/(come|go|join|head).*(meeting|meet)|\bmeeting\b/.test(t)){const rm=freeRoom();HQ.chatReply(p,`On my way to ${rm.name}.`);HQ.meeting(rm,[p.id],'Meeting with you');watchRoom(rm);return}
  if(/desk|go back|return/.test(t)){HQ.chatReply(p,'Heading back to my desk.');HQ.desk(p);return}
  if(/block|stuck|issue|problem|help/.test(t))r=(p.state==='blocked'||p.state==='error')?`Yes — ${p.text}. A huddle should resolve it.`:'No blockers on my side right now.';
  else if(/status|doing|working|progress|update|task/.test(t))r=tk?`I'm on “${tk.title}”${tk.progress!=null?' — '+Math.round(tk.progress)+'% done':''}${tk.note?'. '+tk.note:''}.`:`Nothing assigned to me right now — I'm ${p.state}.`;
  else if(/hello|\bhi\b|hey/.test(t))r=`Hi! I'm ${p.name}, ${p.role} in ${p.home.name}. How can I help?`;
  else r=`As ${p.role}, I'd look into that. (Simulated reply — connect a backend for real answers.)`;
  HQ.chatReply(p,r)}

const HQ=window.FinanceHQ={
  agents:()=>agents.map(a=>({id:a.id,name:a.name,role:a.role,dept:a.home.id,room:a.cur,floor:a.floor+1,state:effState(a),text:a.text,task:a.task?{title:a.task.title,progress:a.task.progress,status:a.task.status}:null})),
  rooms:()=>ROOMS.map(r=>({id:r.id,name:r.name,floor:r.floor+1,kind:r.kind,seats:r.seats?r.seats.length:0})),
  move(agent,room,o={}){const p=A(agent),r=Rm(room);return queue(p,async()=>{release(p);
      let tgt,ang=null;
      if(r===p.home&&!o.spot){tgt=p.seat;ang=p.seat.ang}
      else{const st=o.seat===false?null:allocSeat(r,p);if(st){tgt=st;ang=st.ang}else tgt=spotIn(r)}
      record({k:'move',agent:p.id,room:r.id,x:tgt.x,z:tgt.z,ang});
      log(`<b>${p.name}</b> → ${r.name}${o.label?' · '+o.label:''}`,p.home.color,p);
      const ok=await go(p,r.id,tgt);if(!ok)return;
      if(ang!=null){p.angT=ang;p.sitT=1}else face(p,r.cx,r.cz);
      emit('arrived',{agent:p.id,room:r.id});if(o.text)say(p,o.text,o.ms||3500)})},
  desk(agent){const p=A(agent);return HQ.move(p,p.home,{})},
  status(agent,state,text,o={}){const p=A(agent);const apply=()=>{const prev=p.state;p.state=state;
      if(state==='working'&&text)p.task=taskFor(p,text,{status:'doing'});
      else if(state==='working'&&p.task&&p.task.status!=='done')p.task.status='doing';
      else if(state==='blocked'){if(!p.task&&text)p.task=taskFor(p,text,{status:'blocked'});if(p.task){p.task.status='blocked';if(text)p.task.note=text}}
      else if(state==='done'&&p.task){p.task.progress=100;p.task.status='done'}
      else if(state==='idle'){if(p.task&&p.task.status==='doing')p.task.status='todo';p.task=null}
      p.text=text||({idle:'Idle',working:'Working',meeting:'In a meeting',blocked:'Blocked',done:'Done',error:'Error'}[state]||state);
      record({k:'status',agent:p.id,state,text,now:!!o.now});
      log(`<b>${p.name}</b> is <b style="color:${STATE[state]}">${state}</b>${text?' · '+esc(text):''}`,STATE[state],p);emit('state',{agent:p.id,state});updateMonitor(p);if(o.say)say(p,text||state);
      if(!RP.on){if(state==='blocked'||state==='error'){alertAgent(p,state,text);if(policy.autoHuddle&&!huddles[p.id])setTimeout(()=>autoHuddle(p,text||state),1200)}
        else if(huddles[p.id]&&(prev==='blocked'||prev==='error'))endHuddle(p)}};
      return o.now?Promise.resolve(apply()):queue(p,async()=>apply())},
  say(agent,text,ms){const p=A(agent);say(p,text,ms||3500);record({k:'say',agent:p.id,text,ms});log(`<b>${p.name}</b>: “${esc(text)}”`,p.home.color,p);return Promise.resolve()},
  task(agent,title,progress,note,o={}){const p=A(agent),pr=progress==null?null:Math.max(0,Math.min(100,+progress));
    const t=taskFor(p,title,{id:o.id,progress:pr,note,status:o.status});if(o.status!=='todo')p.task=t;
    record({k:'task',agent:p.id,title,progress:pr,note,id:t.id,status:o.status});
    log(`<b>${p.name}</b> ${o.status==='todo'?'queued':'task'} · ${esc(title)}${pr!=null?' ('+Math.round(pr)+'%)':''}`,p.home.color,p);updateMonitor(p);return Promise.resolve(t)},
  meeting(room,list,topic,o={}){const r=Rm(room);meetings[r.id]={topic,members:list.map(a=>A(a).id)};log(`Meeting in <b>${r.name}</b>${topic?' · '+esc(topic):''}`,'#e2b714');
      return Promise.all(list.map(a=>{const p=A(a);HQ.move(p,r,{});return(o.keep||[]).includes(p.id)?Promise.resolve():HQ.status(p,'meeting',topic||'In a meeting')}))},
  endMeeting(room){const r=Rm(room),m=meetings[r.id];delete meetings[r.id];const ids=new Set(m?m.members:[]);agents.forEach(p=>{if(p.cur===r.id||p.dest===r.name)ids.add(p.id)});
      log(`Meeting ended in <b>${r.name}</b>`,'#e2b714');drawScreen(r,null);
      return Promise.all([...ids].map(id=>{const p=AG[id];if(!p)return;if(p.state==='meeting')HQ.status(p,'idle','Back at desk');return HQ.desk(p)}))},
  summon(ids,room,topic,o={}){const r=Rm(room),list=ids.map(a=>A(a));emitWS({type:'summon',agents:list.map(p=>p.id),room:r.id,topic:topic||'',agenda:o.agenda||''});
      HQ.meeting(r,list.map(p=>p.id),topic||'Meeting with you');if(!RP.on)watchRoom(r);toast('Meeting called',`${list.length} ${list.length===1?'person':'people'} → ${r.name}`,'#e2b714',()=>watchRoom(r));
      if(o.present===false||(ws&&ws.readyState===1))return Promise.resolve();   // with a backend connected, the agents' own slides arrive as 'present' commands
      return Promise.all(list.map(p=>p.q)).then(async()=>{for(const p of list){if(!meetings[r.id])break;await HQ.present(p,{})}})},
  present(agent,spec={}){const p=A(agent);return queue(p,async()=>{const gen=p.gen,r=R[p.cur];if(!r||!r.scr){emitWS({type:'present_done',agent:p.id});return}
      const seat=p.seatInfo?r.seats[p.seatInfo.idx]:null,sp={x:r.cx-r.w*.3,z:r.far+r.fdir*2.6},slides=spec.slides&&spec.slides.length?spec.slides:[autoSlide(p)];
      log(`<b>${p.name}</b> is presenting in <b>${r.name}</b>`,p.home.color,p);attendeesFace(r,true);
      if(!await go(p,r.id,sp))return;face(p,r.cx,r.cz);
      for(const sl0 of slides){const sl=Object.assign({presenter:p.name+' · '+p.role,color:p.home.color},sl0);drawScreen(r,sl);record({k:'screen',room:r.id,slide:sl});
        say(p,sl0.say||spec.say||sl.title,5500);await sleep(spec.ms||sl0.ms||7000);if(gen!==p.gen)return}
      drawScreen(r,null);record({k:'screen',room:r.id,slide:null});
      if(seat){if(!await go(p,r.id,seat))return;p.angT=seat.ang;p.sitT=1}
      attendeesFace(r,false);emitWS({type:'present_done',agent:p.id,room:r.id})})},
  visit(agent,target,text){const p=A(agent),t=A(target);return queue(p,async()=>{release(p);const sp={x:t.seat.x+2.4,z:t.seat.z};
      record({k:'move',agent:p.id,room:t.home.id,x:sp.x,z:sp.z,ang:null,face:{x:t.seat.x,z:t.seat.z}});
      log(`<b>${p.name}</b> visits <b>${t.name}</b>`,p.home.color,p);const ok=await go(p,t.home.id,sp);if(!ok)return;face(p,t.seat.x,t.seat.z);emit('arrived',{agent:p.id,room:t.home.id});if(text)say(p,text,4000)})},
  handoff(from,to,item,o={}){const a=A(from),b=A(to);record({k:'handoff',from:a.id,to:b.id,item});startFlyer(a,b,item,o);
      log(`<b>${a.name}</b> handed off <b>${esc(item)}</b> to <b>${b.name}</b>`,a.home.color,a);say(a,'📤 '+item,2500);return Promise.resolve()},
  chat(agent,text){const p=A(agent);if(RP.on)return Promise.resolve();pushChat(p,'you',text);record({k:'chat',agent:p.id,from:'you',text});
      if(ws&&ws.readyState===1){p.typing=true;emitWS({type:'chat',agent:p.id,text});renderChat();setTimeout(()=>{if(p.typing){p.typing=false;renderChat()}},30000)}
      else{p.typing=true;renderChat();setTimeout(()=>{p.typing=false;localReply(p,text)},700+Math.random()*700)}return Promise.resolve()},
  chatReply(agent,text){const p=A(agent);p.typing=false;pushChat(p,'agent',text);record({k:'chat',agent:p.id,from:'agent',text});say(p,text.length>90?text.slice(0,87)+'…':text,5000);log(`<b>${p.name}</b> replied to you`,p.home.color,p);return Promise.resolve()},
  system(name,state,text){const sy=SYS.find(x=>x.id===String(name).toLowerCase()||x.name.toLowerCase()===String(name).toLowerCase());if(!sy)return;sy.state=state;sy.text=text||'';record({k:'system',name:sy.id,state,text});
      log(`System <b>${sy.name}</b> is <b>${state}</b>${text?' · '+esc(text):''}`,state==='ok'?'#2ee6a6':state==='down'?'#ff6b6b':'#f5b942');renderSys();
      if(!RP.on&&state!=='ok'){toast(`${sy.name} ${state}`,text||'',state==='down'?'#ff6b6b':'#f5b942');beep(state==='down'?'error':'warn')}},
  on(ev,fn){(emitter[ev]=emitter[ev]||[]).push(fn)},
  dispatch(m){if(RP.on&&m.type!=='log'){RP.pending.push(m);return}
    try{switch(m.type){
    case'move':return HQ.move(m.agent,m.room,m);case'desk':return HQ.desk(m.agent);
    case'status':return HQ.status(m.agent,m.state,m.text,m);case'say':return HQ.say(m.agent,m.text,m.ms);
    case'task':return HQ.task(m.agent,m.title,m.progress,m.note,m);
    case'meeting':return HQ.meeting(m.room,m.agents,m.topic);case'end_meeting':return HQ.endMeeting(m.room);
    case'summon':return HQ.summon(m.agents,m.room,m.topic,m);
    case'visit':return HQ.visit(m.agent,m.target,m.text);case'system':return HQ.system(m.name,m.state,m.text);
    case'handoff':return HQ.handoff(m.from,m.to,m.item,m);case'present':return HQ.present(m.agent,m);
    case'chat_reply':return HQ.chatReply(m.agent,m.text);
    case'town':return townSnap(m);case'town_life':return townLife(m);
    case'town_plans':TOWN.plans=m.plans||{};if(selRes)renderDetail();return;
    case'town_visit':return townVisit(m);case'town_event':return townEvent(m);case'town_shoppers':return townShoppers(m);case'town_campaign':return townCampaign(m);
    case'room_log':return roomLog(m.entry);case'hand':return handEv(m);case'speaking':return speakEv(m);
    case'file':return bizFile(m.file,m.quiet);case'eval_case':return evalCase(m);case'eval_done':return evalDone(m);case'hire':return hireAgent(m.agent,m.quiet);case'access':return bizAccess(m);
    case'meeting_started':return meetingStarted(m);case'meeting_done':return meetingDone(m);
    case'biz_day':return bizDay(m);case'initiative':return bizIni(m.initiative);case'note':return bizNote(m.note);case'clock':return bizClock(m);case'resync_done':return;
    case'approval_request':return showApproval(m);case'approval_resolved':return hideApproval(m);
    case'policy':policy.autoHuddle=!!m.autoHuddle;{const c=document.getElementById('cHuddle');if(c)c.checked=policy.autoHuddle}return;
    case'log':return log(m.text);default:console.warn('unknown message',m)}}catch(e){console.warn(e.message);log('⚠ '+e.message,'#ff6b6b')}},
  connect(url){connectWS(url)},disconnect(){if(ws){ws.close();ws=null}setConn(false)}
};
addEventListener('message',e=>{if(e.data&&e.data.type)HQ.dispatch(e.data)});

/* ---------- backend connection ---------- */
let ws=null,wsUrl='',es=null;
function setConn(on,t){const c=document.getElementById('conn');c.classList.toggle('on',on);c.lastChild.textContent=t||(on?'Backend connected':'Backend offline')}
function connectWS(url){
  wsUrl=url;if(ws){ws.onclose=null;ws.close()}if(es){es.close();es=null}
  const feedMsg=d=>{try{const j=JSON.parse(d);(Array.isArray(j)?j:[j]).forEach(HQ.dispatch)}catch(e){console.warn('bad message',d)}};
  if(/^wss?:/i.test(url)){
    try{ws=new WebSocket(url)}catch(e){setConn(false,'Bad URL');return}
    ws.onopen=()=>{setConn(true);log('Backend connected','#2ee6a6');ws.send(JSON.stringify({type:'hello',agents:HQ.agents(),rooms:HQ.rooms()}))};
    ws.onmessage=e=>feedMsg(e.data);ws.onclose=()=>{setConn(false);if(wsUrl===url)setTimeout(()=>wsUrl===url&&connectWS(url),3000)};ws.onerror=()=>{};
  }else if(/^https?:/i.test(url)){
    es=new EventSource(url);es.onopen=()=>{setConn(true,'Backend connected (SSE)')};es.onmessage=e=>feedMsg(e.data);es.onerror=()=>setConn(false,'SSE reconnecting…');
  }
}

/* ---------- systems ---------- */
const SYS=[{id:'policy',name:'Policy Admin',state:'ok'},{id:'claims',name:'Claims Platform',state:'ok'},{id:'crm',name:'Contact Centre & CRM',state:'ok'},{id:'dw',name:'Data Warehouse',state:'ok'},{id:'web',name:'Web & Quote Engine',state:'ok'},{id:'pay',name:'Payments & Billing',state:'ok'}];
function renderSys(){document.getElementById('sys').innerHTML=SYS.map(s=>`<div title="${s.text||''}"><i class="sdot" style="--s:${s.state==='ok'?'#2ee6a6':s.state==='down'?'#ff6b6b':'#f5b942'}"></i>${s.name}</div>`).join('')}
renderSys();
