/* AI Company HQ – Picking (clicks/hover) and the animation loop – must load last.
   Loaded in the order of js/manifest.json and served as one script (/ui/app.js). */
/* ================= PICKING ================= */
const ray=new THREE.Raycaster(),mouse=new THREE.Vector2();let down=null;
const meshes=[];agents.forEach(p=>p.g.traverse(o=>{if(o.isMesh)meshes.push(o)}));
const vis=o=>{while(o){if(!o.visible)return false;o=o.parent}return true};
renderer.domElement.addEventListener('pointerdown',e=>down=[e.clientX,e.clientY]);
let sendMode=null;
function pickAt(e){mouse.set(e.clientX/innerWidth*2-1,-(e.clientY/innerHeight)*2+1);ray.setFromCamera(mouse,cam);
  if(mode==='ext'&&!sendMode){const h=ray.intersectObjects(floorHits,false).filter(h=>vis(h.object))[0];return h?{floor:h.object.userData.floor}:null}
  for(const h of ray.intersectObjects([...meshes,...ROOMS.map(r=>r.carpet)],false).filter(h=>vis(h.object))){
    if(h.object.userData.person&&!sendMode)return {person:h.object.userData.person};
    if(h.object.userData.room)return {room:h.object.userData.room}}
  return null}
function sendHome(p){if(p.state==='meeting')HQ.status(p,'idle','Back at desk');HQ.desk(p)}
function sendAgent(p,roomId){if(RP.on)return toast('Replay mode','Go back to live first.','#60a5fa');const r=R[roomId];if(!r)return;
  HQ.move(p,r,{});const meet=['mr1','mr2','mr3','brd'].includes(r.id);if(meet)HQ.status(p,'meeting','In '+r.name);
  toast(`${p.name} → ${r.name}`,meet?'Sent to the meeting room.':'On their way.','#60a5fa')}
function startSendMode(){if(!selAgent)return;sendMode=selAgent;setTP(false);follow=false;setView('xray');renderer.domElement.style.cursor='crosshair';
  toast('Pick a room',`Click a room in the building, on the floor map or in the Rooms list to send ${sendMode.name}. Esc cancels.`,'#60a5fa')}
function cancelSend(){sendMode=null;renderer.domElement.style.cursor=''}
const cGoRoom=document.getElementById('cGoRoom');
cGoRoom.innerHTML='<optgroup label="Meeting rooms">'+['mr1','mr2','mr3','brd'].map(id=>`<option value="${id}">${R[id].name} · L${R[id].floor+1}</option>`).join('')+'</optgroup><optgroup label="Departments">'+TEAMROOMS.map(r=>`<option value="${r.id}">${r.name} · L${r.floor+1}</option>`).join('')+'</optgroup><optgroup label="Other"><option value="lob">Reception & Café · L1</option></optgroup>';
document.getElementById('cGoBtn').onclick=()=>{if(selAgent)sendAgent(selAgent,cGoRoom.value)};
document.getElementById('cPick').onclick=startSendMode;
renderer.domElement.addEventListener('pointerup',e=>{
  if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>5||e.button!==0)return;
  if(fp.on){fpClick(e);return}
  if(!sendMode){const rh=resHit(e);if(rh){selectResident(rh);return}const wh=wpHit(e);if(wh){selectWorkplace(wh);return}}
  if(!sendMode&&mode!=='ext'){const h=boardHit(e);if(h){enterRoom(h.room.id);fpZoomTo(h);return}}
  const pk=pickAt(e);
  if(sendMode){if(pk&&pk.room){sendAgent(sendMode,pk.room.id);cancelSend()}return}
  if(!pk)return;
  if(pk.floor!=null){follow=false;setView('one',pk.floor);return}
  if(pk.person)return focusAgent(pk.person.id);if(pk.room)return focusDept(pk.room.id)});
renderer.domElement.addEventListener('dblclick',e=>{if(fp.on)return;const pk=pickAt(e);if(!pk&&(selAgent||selDept||mode==='dept'))clearFocus()});
renderer.domElement.addEventListener('pointerdown',e=>{if(tp.on&&e.button===2){setTP(false);follow=true;renderDetail()}},true);
renderer.domElement.addEventListener('contextmenu',e=>e.preventDefault());
const hoverBox=new THREE.Mesh(new THREE.BoxGeometry(GX+.8,FH-.2,GZ+.8),new THREE.MeshBasicMaterial({color:0x22d3ee,transparent:true,opacity:.16,depthWrite:false}));hoverBox.visible=false;scene.add(hoverBox);
const hoverTip=document.createElement('div');hoverTip.style.cssText='position:fixed;z-index:12;pointer-events:none;padding:4px 9px;border-radius:8px;background:#0a0e1ae6;border:1px solid #22d3ee;color:#e8ecf6;font:600 11.5px system-ui,sans-serif;display:none;white-space:nowrap';document.body.appendChild(hoverTip);
renderer.domElement.addEventListener('pointermove',e=>{
  if(mode!=='ext'&&!sendMode&&!e.buttons&&!fp.on){const nw=performance.now();if(nw-(window._bhT||0)<90)return;window._bhT=nw;renderer.domElement.style.cursor=boardHit(e)?'zoom-in':'';hoverBox.visible=false;hoverTip.style.display='none';return}
  if(mode!=='ext'||sendMode||e.buttons){hoverBox.visible=false;hoverTip.style.display='none';if(!sendMode)renderer.domElement.style.cursor='';return}
  const pk=pickAt(e);
  if(pk&&pk.floor!=null){hoverBox.visible=true;hoverBox.position.set(0,FY[pk.floor]+FH/2,0);hoverTip.style.display='block';hoverTip.style.left=(e.clientX+14)+'px';hoverTip.style.top=(e.clientY+14)+'px';hoverTip.textContent='Level '+(pk.floor+1)+' · '+FNAME[pk.floor]+' — click to open';renderer.domElement.style.cursor='pointer'}
  else{hoverBox.visible=false;hoverTip.style.display='none';renderer.domElement.style.cursor=''}});

const tgtV=new THREE.Vector3(),desV=new THREE.Vector3();
renderer.domElement.addEventListener('pointermove',e=>{if(fp.on&&(e.buttons&1)){if(fp.zoomed)fpUnzoom();fp.t.yaw+=e.movementX*.0042;fp.t.pitch=Math.max(-1.2,Math.min(1.2,fp.t.pitch+e.movementY*.003));return}if(!tp.on||!(e.buttons&1))return;tp.yaw-=e.movementX*.006;tp.pitch=Math.max(.05,Math.min(1.25,tp.pitch+e.movementY*.004))});
renderer.domElement.addEventListener('wheel',e=>{if(fp.on){e.preventDefault();if(!fp.zoomed)fp.t.fov=Math.max(26,Math.min(80,fp.t.fov*(1+e.deltaY*.0012)));return}if(!tp.on)return;e.preventDefault();tp.dist=Math.max(3,Math.min(40,tp.dist*(1+e.deltaY*.001)))},{passive:false});
/* ================= LOOP ================= */
const clk=new THREE.Clock(),v3=new THREE.Vector3(),SP=7;
const toScreen=v=>{v3.copy(v).project(cam);return v3.z<1?[(v3.x*.5+.5)*innerWidth,(-v3.y*.5+.5)*innerHeight]:null};
const lerpA=(a,b,k)=>{const d=((b-a+Math.PI)%(Math.PI*2)+Math.PI*2)%(Math.PI*2)-Math.PI;return a+d*k};
let lastFloor=null;
function animate(){
  requestAnimationFrame(animate);
  const rawDt=clk.getDelta(),dt=Math.min(rawDt,.05),T=clk.elapsedTime,nowT=performance.now();fpsStep(rawDt);
  const shownRoom=selDept||(selAgent&&agentRoom()?agentRoom().id:null);   // the room on screen in the room view
  agents.forEach(p=>{
    const g=p.g,u=g.userData;let moving=false;
    if(p.path.length){
      const tg=p.path[0],dx=tg.x-g.position.x,dz=tg.z-g.position.z,dist=Math.hypot(dx,dz),st=SP*dt*((RP.on&&RP.playing)?RP.speed:1);
      if(dist<=st){g.position.x=tg.x;g.position.z=tg.z;p.path.shift();if(!p.path.length&&p.done){const f=p.done;p.done=null;f()}}
      else{g.position.x+=dx/dist*st;g.position.z+=dz/dist*st;p.angT=Math.atan2(dx,dz)}
      moving=true;
    }
    g.position.y=FY[p.floor]+TOP;p.sc+=(p.scT-p.sc)*Math.min(1,dt*10);g.scale.setScalar(Math.max(.001,p.sc));
    const vis0=document.body.classList.contains('scrfocus')?false:mode==='dept'?(p.cur===shownRoom&&!p.lifting):(FG[p.floor].visible&&(mode!=='one'||p.floor===curFloor));g.visible=vis0&&p.sc>.03;
    p.ang=lerpA(p.ang,p.angT,Math.min(1,dt*(moving?10:6)));g.rotation.y=p.ang;
    p.sit+=(p.sitT-p.sit)*Math.min(1,dt*6);
    const J=u.cur,sit=p.sit,talk0=!!(p.bub&&nowT<p.bubUntil);let tg;
    if(moving){p.phase+=dt*9;const s=Math.sin(p.phase);tg={hl:s*.7,hr:-s*.7,kl:Math.max(0,s)*.9,kr:Math.max(0,-s)*.9,sl:-s*.55,sr:s*.55,el:-.3,er:-.3,by:Math.abs(s)*.08,hy:Math.sin(p.phase*.5)*.05,hx:-.03,slz:0,srz:0}}
    else{
      const st=p.state,seated=sit>.5;let sl=-.1,sr=-.1,el=-.15,er=-.15,hy=0,hx=0,slz=0,srz=0;
      if(seated){sl=sr=-.45;el=er=-.95}
      if(st==='working'){
        // a work rhythm: type in bursts -> use the mouse -> read the screen -> now and then a sip of coffee
        const cyc=T*.11+p.ph,ph=cyc%1,n=Math.floor(cyc);
        if(ph<.62){const burst=Math.sin(T*.9+p.ph*3)>-.25?1:.15;
          sl=-.58+Math.sin(T*16+p.ph)*.07*burst;sr=-.58+Math.sin(T*14.5+p.ph*2)*.07*burst;el=-1.02+Math.sin(T*19+p.ph)*.12*burst;er=-1.02+Math.sin(T*17+p.ph*3)*.12*burst;
          hx=.14+Math.sin(T*1.7+p.ph)*.02;hy=Math.sin(T*.6+p.ph)*.08}
        else if(ph<.8){sl=-.5;el=-.95;sr=-.5+Math.sin(T*3+p.ph)*.04;er=-.8;srz=.3+Math.sin(T*2.3)*.04;hx=.08;hy=-.12+Math.sin(T*1.1)*.04}
        else if(ph<.92||n%3){sl=sr=-.45;el=er=-.95;hx=.04;hy=Math.sin(T*2.2+p.ph)*.22}
        else{sl=-1.3;el=-2.25;slz=.28;sr=-.5;er=-1;hx=-.14;hy=.05}
      }
      else if(st==='meeting'){sr=-.5+Math.sin(T*2.5+p.ph)*.35;er=-1.0+Math.sin(T*2.5+p.ph)*.2;sl=sit>.5?-.4:-.15;el=sit>.5?-.9:-.5;hy=Math.sin(T*1.4+p.ph)*.3;hx=Math.sin(T*.8+p.ph)*.05}
      else if(st==='blocked'||st==='error'){sl=sr=-.7;el=er=-1.9;hy=Math.sin(T*(st==='error'?9:5))*.4;hx=.18}
      else if(st==='done'){sr=-2.7;er=-.3+Math.sin(T*8)*.4;sl=.05;el=-.15;hx=-.1}
      else if(seated){
        // idle at the desk: relax and look around, stretch, check the phone, glance about
        const cyc=T*.07+p.ph*1.7,ph=cyc%1,n=Math.floor(cyc);
        if(ph<.5){sl=sr=-.35;el=er=-1.15;hy=Math.sin(T*.45+p.ph)*.35;hx=Math.sin(T*.3+p.ph)*.04}
        else if(ph<.62&&n%3===0){sl=sr=-2.85;el=er=-.25;hx=-.22}
        else if(ph<.85){sl=-1.05;el=-1.75;slz=.18;sr=-.4;er=-1.1;hx=.38;hy=.05}
        else{sl=sr=-.45;el=er=-.95;hy=Math.sin(T*1.6+p.ph)*.55}
      }
      else{sl+=Math.sin(T*1.2+p.ph)*.03;sr-=Math.sin(T*1.2+p.ph)*.03;hy=Math.sin(T*.5+p.ph)*.25}
      if(talk0&&st!=='working'&&st!=='blocked'&&st!=='error'){sr=-.6+Math.sin(T*3.2+p.ph)*.4;er=-1.1;srz=0;hx=0}
      tg={hl:-1.5*sit,hr:-1.5*sit,kl:1.5*sit,kr:1.5*sit,sl,sr,el,er,by:-SIT_DY*sit+Math.sin(T*1.4+p.ph)*.012,hy,hx,slz,srz}
    }
    const k=Math.min(1,dt*(moving?14:9));for(const key in tg)J[key]+=(tg[key]-J[key])*k;
    u.hipL.rotation.x=J.hl;u.hipR.rotation.x=J.hr;u.kneeL.rotation.x=J.kl;u.kneeR.rotation.x=J.kr;u.shL.rotation.x=J.sl;u.shR.rotation.x=J.sr;u.elL.rotation.x=J.el;u.elR.rotation.x=J.er;u.body.position.y=J.by;u.head.rotation.y=J.hy;u.mouth.scale.y=talk0?1+Math.abs(Math.sin(T*14+p.ph))*3:1;u.head.rotation.x=J.hx+(talk0?Math.sin(T*5+p.ph)*.06:0);u.shL.rotation.z=J.slz;u.shR.rotation.z=J.srz;u.mouth.scale.x=(p.state==='blocked'||p.state==='error')?.6:p.state==='done'?1.4:1;{const bl=Math.sin(T*.9+p.ph*3)>.985?.12:1;u.eyes.forEach(e=>e.scale.y=bl)}
    {const bad=p.state==='blocked'||p.state==='error';if(bad||p.bc){const b=beacon(p);b.g.visible=bad;if(bad){const sc=1+((T*1.2+p.ph)%1)*.8;b.ring.scale.setScalar(sc);b.m.opacity=Math.max(0,.9-(sc-1)*1.1);b.orb.position.y=4.0+Math.sin(T*6)*.12}}}
  });
  monitorTick(dt);boardTick(dt);townTick(dt,T);mapMove(dt);
  for(let i=flyers.length-1;i>=0;i--){const f=flyers[i],t=Math.min(1,(nowT-f.t0)/f.dur),e=t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2;
    f.curve.getPoint(e,f.doc.position);f.doc.rotation.y+=dt*6;f.trail.forEach((m,j)=>f.curve.getPoint(Math.max(0,e-j*.022),m.position));
    const sh=mode!=='dept';f.doc.visible=f.line.visible=sh;f.trail.forEach(m=>m.visible=sh);if(t>=1){finishFlyer(f);flyers.splice(i,1)}}
  for(let i=pulses.length-1;i>=0;i--){const u=pulses[i],t=(nowT-u.t0)/900;if(t>=1){scene.remove(u.m);pulses.splice(i,1);continue}u.m.scale.setScalar(1+t*3);u.m.material.opacity=.9*(1-t)}
  if(RP.on&&RP.playing){RP.pos+=rawDt*1000*RP.speed;while(RP.idx<rec.length&&rec[RP.idx].t<=RP.pos){applyEvent(rec[RP.idx],false);RP.idx++}if(RP.pos>=RP.dur){RP.pos=RP.dur;RP.playing=false}syncRP()}
  clouds.rotation.y+=dt*.004;ring1.rotation.y+=dt*.7;ring2.rotation.x+=dt*.9;RG.userData.core.rotation.y+=dt*.5;RG.userData.core.rotation.x+=dt*.2;
  for(let f=0;f<3;f++){liftPulse[f]*=.95;FG[f].userData.liftPanel.material.emissiveIntensity=.5+liftPulse[f]*2}
  if(selAgent){const w=selAgent.g.position;ringMesh.position.set(w.x,w.y+.1,w.z);ringMesh.scale.setScalar(1+Math.sin(T*4)*.06);ringMesh.visible=FG[selAgent.floor].visible;
    if(follow&&!focus){const tx=w.x-controls.target.x,ty=w.y+2-controls.target.y,tz=w.z-controls.target.z,k=Math.min(1,dt*4);
      controls.target.x+=tx*k;controls.target.y+=ty*k;controls.target.z+=tz*k;cam.position.x+=tx*k;cam.position.y+=ty*k;cam.position.z+=tz*k}
    if((follow||tp.on)&&!selAgent.lifting&&selAgent.floor!==curFloor){curFloor=selAgent.floor;applyView()}}
  if(selAgent&&tp.on){const w=selAgent.g.position,a=selAgent.ang+Math.PI+tp.yaw,cp=Math.cos(tp.pitch);
    tgtV.set(w.x,w.y+2.0,w.z);desV.set(w.x+Math.sin(a)*tp.dist*cp,w.y+2.0+tp.dist*Math.sin(tp.pitch),w.z+Math.cos(a)*tp.dist*cp);
    cam.position.lerp(desV,1-Math.exp(-dt*4.5));controls.target.lerp(tgtV,1-Math.exp(-dt*9))}
  if(focus){const fk=1-Math.exp(-dt*4);controls.target.lerp(focus.t,fk);cam.position.lerp(focus.c,fk);if(cam.position.distanceTo(focus.c)<.4)focus=null}
  if(!isFinite(cam.position.x+cam.position.y+cam.position.z+controls.target.x+controls.target.y+controls.target.z)){cam.position.copy(HOME.c);controls.target.copy(HOME.t);focus=null}
  if(fp.on)fpStep(dt);else controls.update();
  LBL.forEach(l=>{const show=mode==='ext'?false:mode==='dept'?!!(l.room&&l.room.id===selDept):mode==='one'?l.floor===curFloor:true;const s=show&&FG[l.floor].visible?toScreen(l.pos):null;
    if(s){l.el.style.display='';l.el.style.left=s[0]+'px';l.el.style.top=s[1]+'px'}else l.el.style.display='none'});
  const now=performance.now();
  agents.forEach(p=>{
    if(!p.g.visible){p.chip.style.display='none';if(p.bub)p.bub.style.opacity=0;return}
    const s=toScreen(v3.set(p.g.position.x,p.g.position.y+3.05,p.g.position.z));
    if(s){p.chip.style.display=(mode==='ext'&&p!==selAgent)?'none':'';p.chip.style.left=s[0]+'px';p.chip.style.top=s[1]+'px';
      if(p.bub){if(now>p.bubUntil)p.bub.style.opacity=0;else{p.bub.style.display='';p.bub.style.left=s[0]+'px';p.bub.style.top=(s[1]-24)+'px'}}}
    else{p.chip.style.display='none';if(p.bub)p.bub.style.display='none'}
  });
  renderer.render(scene,cam);
}
[isle,RG,...FG,...ROOMS.map(r=>r.plate)].forEach(freeze);[ring1,ring2,RG.userData.core].forEach(o=>{o.matrixAutoUpdate=true});applyTOD();
applyView();viewFocus();cam.position.copy(focus.c);controls.target.copy(focus.t);focus=null;bRot.classList.add('on');
applyFocus();tick();animate();
addEventListener('resize',()=>{if(innerWidth<10||innerHeight<10)return;cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight)});
