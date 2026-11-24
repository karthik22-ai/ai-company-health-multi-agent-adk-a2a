/* AI Company HQ – Camera views, focus, third-person and first-person room view.
   Loaded in the order of js/manifest.json and served as one script (/ui/app.js). */
/* ================= VIEW / FOCUS ================= */
let selWp=null,selRes=null,mode='ext',curFloor=1,selDept=null,selAgent=null,follow=false,focus=null,prevView=null;
const tp={on:false,yaw:0,pitch:.36,dist:11};
function setTP(on){tp.on=on;controls.enabled=!on;if(on){tp.yaw=0;tp.pitch=.36;tp.dist=11;follow=false}}
const bRot=document.getElementById('bRot'),ftabs=document.getElementById('ftabs');
const aspectK=()=>{const a=cam.aspect;return isFinite(a)&&a>0?Math.max(1,1.5/a):1};
function agentRoom(){const p=selAgent;if(!p)return null;const r=R[p.cur];return r&&r.w?r:p.home}
function applyView(){
  const ext=mode==='ext',xr=mode==='xray',dp=mode==='dept',sr=dp?(selDept?R[selDept]:agentRoom()):null;
  isle.visible=!dp;clouds.visible=!dp;if(typeof townG!=='undefined')townG.visible=!dp;
  FG.forEach((g,f)=>{g.visible=dp?!!(sr&&f===sr.floor):(ext||xr||f<=curFloor);g.userData.shell.visible=!dp});
  ROOMS.forEach(r=>{r.grp.visible=!dp||r===sr;r.plate.visible=dp&&r===sr});
  RG.visible=ext||xr;
  slabMats.forEach(m=>m.opacity=xr?.2:1);roofMats.forEach(m=>m.opacity=xr?.15:1);extMat.opacity=ext?.3:xr?.16:.1;
  ROOMS.forEach(r=>{r.carpetMat.opacity=xr?.6:1});
  [...ftabs.querySelectorAll('button')].forEach(b=>b.classList.toggle('on',mode==='xray'?b.dataset.f==='all':mode==='one'&&b.dataset.f!=='all'&&+b.dataset.f===curFloor));
  try{renderFloors()}catch(e){}
}
function viewFocus(){
  const k=aspectK();
  if(mode==='ext')focus={t:HOME.t.clone(),c:HOME.t.clone().add(HOME.c.clone().sub(HOME.t).multiplyScalar(Math.max(1,k*.9)))};
  else if(mode==='xray')focus={t:new THREE.Vector3(0,6,0),c:new THREE.Vector3(48*k,40*k,68*k)};
  else{const y=FY[curFloor]+1;focus={t:new THREE.Vector3(0,y,0),c:new THREE.Vector3(16*k,y+40*k,42*k)}}
}
function setView(m,f){if(fp.on)fpExit(true);if(tp.on)setTP(false);mode=m;if(f!=null)curFloor=f;applyView();viewFocus();controls.autoRotate=mode==='ext';bRot.classList.toggle('on',controls.autoRotate);drawMap()}
ftabs.onclick=e=>{const b=e.target.closest('button');if(!b)return;follow=false;b.dataset.f==='all'?setView('xray'):setView('one',+b.dataset.f)};
const stopRot=()=>{controls.autoRotate=false;bRot.classList.remove('on')};
bRot.onclick=()=>{controls.autoRotate=!controls.autoRotate;bRot.classList.toggle('on',controls.autoRotate)};
document.getElementById('bReset').onclick=()=>{clearFocus();setView('ext')};
document.getElementById('bClear').onclick=()=>clearFocus();
addEventListener('keydown',e=>{
  if(e.key==='k'&&(e.metaKey||e.ctrlKey)){e.preventDefault();palOpen();return}
  if(e.key==='Escape'){if(tourOn){endTour();return}for(const m of [docsM,profM,opsM,tlM])if(m.classList.contains('on')){m.classList.remove('on');if(m===tlM)tlStop();return}if(appsM.classList.contains('on')){appsM.classList.remove('on');return}if(fvEl.classList.contains('on')){closeFile();return}if(isFocus()&&!fp.on&&!document.body.classList.contains('scrfocus')){setFocusMode(false);return}if(sendMode){cancelSend();return}if(palEl.style.display==='flex')return palClose();if(coEl.style.display==='flex')return closeCo();if(boardEl.style.display==='flex')return closeBoard();if(fp.on)return fpEsc();if(RP.on)return replayExit();clearFocus();return}
  if(/input|select|textarea/i.test(document.activeElement.tagName))return;
  const k=e.key.toLowerCase();if(k==='/'){e.preventDefault();palOpen();return}
  if((k==='h'||k==='f')&&!e.metaKey&&!e.ctrlKey){layToggleAll();return}
  if(fp.on){if(k==='['||k===']'){fpCycle(k===']'?1:-1);e.preventDefault();return}if(k.length===1&&'wasd'.includes(k)||k.startsWith('arrow')){fp.keys[k]=true;e.preventDefault()}return}
  if(k==='1'||k==='2'||k==='3'){follow=false;setView('one',+k-1)}if(k==='e'){follow=false;setView('ext')}if(k==='x'){follow=false;setView('xray')}});
controls.addEventListener('start',()=>focus=null);
controls.enablePan=true;controls.screenSpacePanning=false;controls.panSpeed=1.2;
const NAV={};addEventListener('keydown',e=>{if(fp.on||/input|select|textarea/i.test(document.activeElement.tagName)||e.metaKey||e.ctrlKey)return;const k=e.key.toLowerCase();
  if(['w','a','s','d','z','c','arrowup','arrowdown','arrowleft','arrowright'].includes(k)){NAV[k]=true;if(k.startsWith('arrow'))e.preventDefault()}});
addEventListener('keyup',e=>{delete NAV[e.key.toLowerCase()]});addEventListener('blur',()=>{for(const k in NAV)delete NAV[k]});
function mapMove(dt){if(fp.on||tp.on)return;let f=0,s2=0,rot=0;if(NAV.w||NAV.arrowup)f++;if(NAV.s||NAV.arrowdown)f--;if(NAV.d||NAV.arrowright)s2++;if(NAV.a||NAV.arrowleft)s2--;if(NAV.z)rot++;if(NAV.c)rot--;
  if(!f&&!s2&&!rot)return;focus=null;follow=false;stopRot();const off=cam.position.clone().sub(controls.target),dist=off.length(),sp=Math.max(20,dist*.9)*dt;
  const fw=new THREE.Vector3(-off.x,0,-off.z).normalize(),rt=new THREE.Vector3(-fw.z,0,fw.x),mv=fw.multiplyScalar(f*sp).add(rt.multiplyScalar(s2*sp));
  controls.target.add(mv);cam.position.add(mv);if(rot){off.applyAxisAngle(new THREE.Vector3(0,1,0),rot*dt*1.2);cam.position.copy(controls.target).add(off)}}
addEventListener('keyup',e=>{delete fp.keys[e.key.toLowerCase()]});addEventListener('blur',()=>fp.keys={});
document.getElementById('lmode').onclick=e=>{const b=e.target.closest('button');if(!b)return;document.body.dataset.labels=b.dataset.m;[...e.currentTarget.children].forEach(x=>x.classList.toggle('on',x===b))};

function setDim(p,d){if(p.dim===d)return;p.dim=d;p.mats.forEach(m=>{m.transparent=d;m.opacity=d?.2:1;m.needsUpdate=true})}
function applyFocus(){
  const fa=selAgent,fd=selDept;
  ROOMS.forEach(r=>{const hot=fd?r.id===fd:fa?r===fa.home:false;
    r.gmat.opacity=hot?(fd?.34:.26):((fa||fd)?.06:.16);r.lbl.style.opacity=(!fa&&!fd)||hot?1:.25;if(r.row)r.row.classList.toggle('sel',r.id===fd)});
  agents.forEach(p=>setDim(p,false));
  ringMesh.visible=!!fa;renderDetail();renderChat();renderLeft(true);drawMap();
}
function saveView(){if(!selDept&&!selAgent&&!prevView)prevView={mode,floor:curFloor}}
function clearFocus(){if(fp.on)fpExit(true);selRes=null;selWp=null;selDept=null;selAgent=null;follow=false;setTP(false);if(prevView){const v=prevView;prevView=null;setView(v.mode,v.floor)}applyFocus()}
function focusDept(id){if(fp.on)fpExit(true);selRes=null;selWp=null;const r=Rm(id);loadRoomLog(r.id);saveView();selDept=r.id;selAgent=null;follow=false;setTP(false);curFloor=r.floor;mode='dept';applyView();stopRot();
  const k=aspectK(),w=Math.max(r.w,18);focus={t:new THREE.Vector3(r.cx,r.y+1,r.cz),c:new THREE.Vector3(r.cx+.3*w*k,r.y+.85*w*k,r.cz+1.0*w*k)};applyFocus()}
function focusAgent(a){selRes=null;selWp=null;const p=A(a);loadPeople(p.id);if(fp.on){if(p.cur===fp.room.id){fpSelect(p,true);return}fpExit(true)}saveView();selAgent=p;selDept=null;follow=false;curFloor=p.floor;mode='dept';applyView();stopRot();{const w=p.g.position,k=aspectK();focus={t:new THREE.Vector3(w.x,w.y+1.2,w.z),c:new THREE.Vector3(w.x+4*k,w.y+11*k,w.z+13*k)}};emit('select',{agent:p.id});applyFocus()}
const ringMesh=new THREE.Mesh(new THREE.TorusGeometry(1.1,.09,8,32),M(0xffffff,{emissive:0xffffff,emissiveIntensity:1}));ringMesh.rotation.x=Math.PI/2;ringMesh.visible=false;scene.add(ringMesh);
/* ================= FIRST-PERSON ROOM VIEW ================= */
const fp={on:false,room:null,p:{x:0,y:0,z:0,yaw:0,pitch:0,fov:62},t:{x:0,y:0,z:0,yaw:0,pitch:0,fov:62},keys:{},zoomed:false,saved:null};
const fpHud=document.getElementById('fpHud'),fpDot=document.getElementById('fpDot');
const fpEyeY=r=>FY[r.floor]+TOP+2.6;
function fpHome(){const r=fp.room,fd=r.fdir||1,far=r.far!=null?r.far:r.z0;
  const z=Math.max(r.z0+1.5,Math.min(r.z1-1.5,far+fd*(r.d-3)));
  return {x:r.cx,y:fpEyeY(r),z,yaw:fd>0?0:Math.PI,pitch:-.1,fov:62}}
function enterRoom(id){const r=R[id];if(!r)return;if(fp.on)fpExit(true);
  saveView();setTP(false);follow=false;focus=null;selAgent=null;selDept=r.id;curFloor=r.floor;mode='dept';applyView();stopRot();
  document.body.classList.add('infp');fp.on=true;fp.room=r;fp.keys={};fp.zoomed=false;controls.enabled=false;
  const h=fpHome();Object.assign(fp.p,h);Object.assign(fp.t,h);fpApply();
  document.getElementById('fpName').textContent='👁 '+r.name+' · first person';fpHud.style.display='flex';fpDot.style.display='block';
  applyFocus();renderDetail()}
function fpApply(){const p=fp.p;cam.position.set(p.x,p.y,p.z);cam.rotation.set(p.pitch,p.yaw,0,'YXZ');if(Math.abs(cam.fov-p.fov)>.01){cam.fov=p.fov;cam.updateProjectionMatrix()}}
function fpExit(silent){if(!fp.on)return;const r=fp.room;bvHide();document.body.classList.remove('infp','scrfocus');fp.on=false;fp.zoomed=false;fpHud.classList.remove('zm');fp.keys={};controls.enabled=true;cam.fov=42;cam.updateProjectionMatrix();
  fpHud.style.display='none';fpDot.style.display='none';
  controls.target.set(r.cx,r.y+1,r.cz);const d=new THREE.Vector3();cam.getWorldDirection(d);
  if(!silent){selAgent=null;focusDept(r.id)}}
function fpEsc(){if(fp.zoomed)return fpUnzoom();fpExit(false)}
function fpUnzoom(){bvHide();document.body.classList.remove('scrfocus');if(!fp.zoomed||!fp.saved)return;fpHud.classList.remove('zm');Object.assign(fp.t,fp.saved);fp.zoomed=false}
function fpLookAt(v,dist){const p=fp.p,dx=v.x-p.x,dz=v.z-p.z,hd=Math.hypot(dx,dz)||1;fp.t.yaw=Math.atan2(-dx,-dz);fp.t.pitch=Math.max(-1.1,Math.min(1.1,Math.atan2(v.y-p.y,hd)))}
function fpSelect(p,look){selAgent=p;emit('select',{agent:p.id});if(fp.zoomed)fpUnzoom();
  if(look){fp.t.fov=Math.min(fp.t.fov,50);fpLookAt(new THREE.Vector3(p.g.position.x,p.g.position.y+2.2,p.g.position.z))}
  ringMesh.visible=true;renderDetail();renderChat();renderLeft(true);const ci=document.getElementById('cIn');ci&&ci.focus&&setTimeout(()=>ci.focus(),50)}
function fpScreens(r=fp.room){const L=[];if(r.board)L.push({o:r.board.m,w:r.board.w,h:r.board.h,cv:r.board.c,label:r.name+' – KPI board'});if(r.scr&&r.scr.m)L.push({o:r.scr.m,w:r.scr.w,h:r.scr.h,cv:r.scr.c,label:r.name+' – wall screen'});
  agents.forEach(a=>{if(a.mon&&vis(a.mon)&&a.home===r){if(!a.cv)updateMonitor(a);L.push({o:a.mon,w:1.2,h:.7,cv:a.cv,label:a.name+"'s monitor",agent:a})}});return L}
const bview=document.getElementById('bview');
function bvSize(){const cv=bview.firstChild;if(!cv)return;const w=Math.min(innerWidth-40,(innerHeight-90)*cv.width/cv.height);cv.style.width=w+'px';cv.style.height=(w*cv.height/cv.width)+'px'}
function bvShow(cv){if(!cv)return;bview.replaceChildren(cv);bview.classList.add('on');bvSize()}
function bvHide(){bview.classList.remove('on');bview.replaceChildren()}
bview.onclick=e=>{if(e.target===bview)fpUnzoom()};addEventListener('resize',bvSize);
function fpZoomTo(item){if(!fp.zoomed)fp.saved={...fp.t};fp.cur=item;const obj=item.o;
  const wp=new THREE.Vector3(),dir=new THREE.Vector3();obj.getWorldPosition(wp);obj.getWorldDirection(dir);dir.y=0;dir.normalize();
  const fov=item.w>4?74:40,vh=Math.tan(fov*Math.PI/360),vw=vh*Math.max(.6,cam.aspect);
  const d=Math.max(item.w/2/vw,item.h/2/vh)*1.12,r=fp.room;
  const x=Math.max(r.x0+.5,Math.min(r.x1-.5,wp.x+dir.x*d)),z=Math.max(r.z0+.5,Math.min(r.z1-.5,wp.z+dir.z*d));
  const dist=Math.max(.5,Math.hypot(wp.x-x,wp.z-z)),need=2*Math.atan(Math.max(item.h/2,item.w/2/Math.max(.6,cam.aspect))*1.08/dist)*180/Math.PI;
  Object.assign(fp.t,{x,y:wp.y,z,fov:Math.max(30,Math.min(85,need)),yaw:Math.atan2(-(wp.x-x),-(wp.z-z)),pitch:0});fp.zoomed=true;document.body.classList.add('scrfocus');
  if(item.agent&&selAgent!==item.agent){selAgent=item.agent;emit('select',{agent:item.agent.id});ringMesh.visible=true;renderDetail();renderChat();renderLeft(true)}
  document.getElementById('fpScr').textContent=item.label;document.getElementById('sbName').textContent=item.label;fpHud.classList.add('zm');bvShow(item.cv);if(item.cv&&R[fp.room.id].board&&item.cv===fp.room.board.c)drawBoard(fp.room)}
function fpCycle(dir){const L=fpScreens();if(!L.length)return;let i=fp.zoomed&&fp.cur?L.findIndex(x=>x.o===fp.cur.o):-1;i=(i+dir+L.length)%L.length;fpZoomTo(L[i])}
function screenHit(e,r){cam.updateMatrixWorld(true);mouse.set(e.clientX/innerWidth*2-1,-(e.clientY/innerHeight)*2+1);ray.setFromCamera(mouse,cam);
  const L=fpScreens(r),h=ray.intersectObjects(L.map(x=>x.o),false).filter(h=>vis(h.object))[0];return h?L.find(x=>x.o===h.object):null}
function boardHit(e){cam.updateMatrixWorld(true);mouse.set(e.clientX/innerWidth*2-1,-(e.clientY/innerHeight)*2+1);ray.setFromCamera(mouse,cam);
  const L=[];ROOMS.forEach(r=>fpScreens(r).forEach(x=>{if(!x.agent){x.room=r;L.push(x)}}));
  const hb=ray.intersectObjects(L.map(x=>x.o),false).filter(h=>vis(h.object))[0];if(!hb)return null;
  const hp=ray.intersectObjects(meshes,false).filter(h=>vis(h.object))[0];if(hp&&hp.distance<hb.distance)return null;
  return L.find(x=>x.o===hb.object)}
function fpClick(e){cam.updateMatrixWorld(true);mouse.set(e.clientX/innerWidth*2-1,-(e.clientY/innerHeight)*2+1);ray.setFromCamera(mouse,cam);
  const mons=agents.map(a=>{if(a.mon)a.mon.userData.fpAgent=a;return a.mon}).filter(Boolean);if(fp.room.scr&&fp.room.scr.m)mons.push(fp.room.scr.m);
  const hit=ray.intersectObjects([...meshes,...mons],false).filter(h=>vis(h.object))[0];
  if(!hit){if(fp.zoomed)fpUnzoom();return}
  const o=hit.object;
  if(o.userData.person){fpSelect(o.userData.person,true);return}
  const it=fpScreens().find(x=>x.o===o);if(it)fpZoomTo(it)}
function fpStep(dt){const k=fp.keys,t=fp.t,r=fp.room;let f=0,s=0;
  if(k.w||k.arrowup)f++;if(k.s||k.arrowdown)f--;if(k.d)s++;if(k.a)s--;if(k.arrowright)t.yaw-=dt*1.6;if(k.arrowleft)t.yaw+=dt*1.6;
  if((f||s)&&fp.zoomed)fpUnzoom();
  if(f||s){const sp=9*dt,y=fp.p.yaw;t.x+=(-Math.sin(y)*f+Math.cos(y)*s)*sp;t.z+=(-Math.cos(y)*f-Math.sin(y)*s)*sp;
    t.x=Math.max(r.x0+1.2,Math.min(r.x1-1.2,t.x));t.z=Math.max(r.z0+1.2,Math.min(r.z1-1.2,t.z))}
  const p=fp.p,kp=1-Math.exp(-dt*7),kl=1-Math.exp(-dt*14);
  p.x+=(t.x-p.x)*kp;p.y+=(t.y-p.y)*kp;p.z+=(t.z-p.z)*kp;p.fov+=(t.fov-p.fov)*kp;p.yaw=lerpA(p.yaw,t.yaw,kl);p.pitch+=(t.pitch-p.pitch)*kl;fpApply();
  fpDot.style.display=fp.zoomed?'none':'block'}
document.getElementById('sbPrev').onclick=()=>fpCycle(-1);document.getElementById('sbNext').onclick=()=>fpCycle(1);document.getElementById('sbClose').onclick=fpUnzoom;
document.getElementById('fpPrev').onclick=()=>fpCycle(-1);document.getElementById('fpNext').onclick=()=>fpCycle(1);document.getElementById('fpScreens').onclick=()=>fpCycle(1);document.getElementById('fpBack').onclick=fpUnzoom;
document.getElementById('fpExit').onclick=()=>fpExit(false);
document.getElementById('fpReset').onclick=()=>{fp.zoomed=false;const h=fpHome();Object.assign(fp.t,h)};
document.getElementById('bFP').onclick=()=>{const id=selDept||(selAgent&&(R[selAgent.cur]&&!selAgent.moving?selAgent.cur:selAgent.home.id));
  if(id)enterRoom(id);else toast('Pick a room first','Click a department or an agent, then press Room view.','#60a5fa')};
