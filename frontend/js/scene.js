/* AI Company HQ – Renderer, camera, lights, sky and ground.
   Loaded in the order of js/manifest.json and served as one script (/ui/app.js). */
/* ================= SCENE ================= */
const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(innerWidth,innerHeight);
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.outputEncoding=THREE.sRGBEncoding;
renderer.domElement.className='main';document.body.prepend(renderer.domElement);
const scene=new THREE.Scene();
const cam=new THREE.PerspectiveCamera(42,innerWidth/innerHeight,.5,700);
const HOME={c:new THREE.Vector3(170,215,380),t:new THREE.Vector3(170,0,0)};cam.position.copy(HOME.c);
const controls=new THREE.OrbitControls(cam,renderer.domElement);
controls.target.copy(HOME.t);controls.enableDamping=true;controls.dampingFactor=.07;controls.maxPolarAngle=Math.PI*.47;controls.minDistance=8;controls.maxDistance=620;controls.autoRotate=true;controls.autoRotateSpeed=.35;
const hemi=new THREE.HemisphereLight(0xd6e6ff,0x7a6a58,1.0);scene.add(hemi);const moonL=new THREE.DirectionalLight(0x8fa8ff,0);moonL.position.set(-60,90,-40);scene.add(moonL);
const sun=new THREE.DirectionalLight(0xfff1dd,1.15);sun.position.set(60,110,70);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);
Object.assign(sun.shadow.camera,{left:-85,right:85,top:85,bottom:-85,near:10,far:300});sun.shadow.bias=-.0005;scene.add(sun);

const M=(c,o={})=>new THREE.MeshStandardMaterial(Object.assign({color:c,roughness:.7,metalness:.08},o));
function box(w,h,d,m,x,y,z,parent,shadow=true){const me=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),m);me.position.set(x,y,z);me.castShadow=shadow;me.receiveShadow=true;if(parent)parent.add(me);return me}
function cyl(rt,rb,h,m,x,y,z,parent,seg=16){const me=new THREE.Mesh(new THREE.CylinderGeometry(rt,rb,h,seg),m);me.position.set(x,y,z);me.castShadow=true;me.receiveShadow=true;parent.add(me);return me}
const labels=document.getElementById('labels'),LBL=[];
function dom(cls,html,color){const d=document.createElement('div');d.className=cls;if(color)d.style.setProperty('--c',color);d.innerHTML=html;labels.appendChild(d);return d}
const GLOW=[],CMATS=[];
const glowMat=(c,base,k)=>{const m=M(c,{emissive:c,emissiveIntensity:base,roughness:.4});GLOW.push({m,base,k});return m};
function textPanel(w,h,draw){const c=document.createElement('canvas');c.width=w;c.height=h;draw(c.getContext('2d'),w,h);const t=new THREE.CanvasTexture(c);t.encoding=THREE.sRGBEncoding;t.anisotropy=4;return {c,t}}


/* ================= ISLAND + SKY ================= */
const ISL=66,isle=new THREE.Group();scene.add(isle);
let _seed=7;const rr=()=>{_seed=(_seed*16807)%2147483647;return _seed/2147483647};
const warp=(geo,amp)=>{const p=geo.attributes.position;for(let i=0;i<p.count;i++){const x=p.getX(i),y=p.getY(i),z=p.getZ(i);
  p.setXYZ(i,x+Math.sin(y*.9+z*.5)*amp,y+Math.sin(x*.7+z*.8)*amp*.5,z+Math.sin(y*1.1+x*.5)*amp)}geo.computeVertexNormals()};
const grass=cyl(ISL,ISL-1,1.2,M(0x62ad63,{roughness:1}),0,-.6,0,isle,64);grass.castShadow=false;
cyl(ISL-1,ISL-5,3.2,M(0x7a5538,{roughness:1}),0,-3.2,0,isle,64).castShadow=false;
const rg=new THREE.CylinderGeometry(ISL-5,4,50,11,6);warp(rg,2.8);
const rock=new THREE.Mesh(rg,M(0x8a8494,{roughness:1,flatShading:true}));rock.position.y=-4.6-25;isle.add(rock);
for(let i=0;i<7;i++){const a=rr()*6.28,d=rr()*26+6,h=rr()*16+12,c=new THREE.Mesh(new THREE.ConeGeometry(rr()*4+4,h,7),M(0x7b7586,{roughness:1,flatShading:true}));
  c.rotation.x=Math.PI;c.position.set(Math.cos(a)*d,-26-h*.3,Math.sin(a)*d);isle.add(c)}
function islet(x,y,z,r){const g=new THREE.Group();g.position.set(x,y,z);isle.add(g);
  cyl(r,r*.9,1,M(0x62ad63,{roughness:1}),0,-.5,0,g,14).castShadow=false;const k=new THREE.Mesh(new THREE.ConeGeometry(r*.9,r*1.7,8),M(0x8a8494,{roughness:1,flatShading:true}));k.rotation.x=Math.PI;k.position.y=-1-r*.85;g.add(k);
  const t=new THREE.Mesh(new THREE.IcosahedronGeometry(r*.45,0),M(0x3e9a5a,{flatShading:true}));t.position.y=r*.5;t.castShadow=true;g.add(t);return g}
const islets=[];
const GROUND=new THREE.Mesh(new THREE.CircleGeometry(1600,64),M(0x6aa865,{roughness:1}));GROUND.rotation.x=-Math.PI/2;GROUND.position.y=-.03;GROUND.receiveShadow=true;scene.add(GROUND);
/* paving, paths */
box(92,.14,62,M(0xd5dae6,{roughness:.9}),0,.07,0,isle,false).castShadow=false;
box(84,.16,54,M(0xc2c9d9,{roughness:.9}),0,.08,0,isle,false).castShadow=false;
box(30,.15,CZ*2+6,M(0xd5dae6,{roughness:.9}),HW+24,.075,0,isle,false);
/* trees, hedges, lamps */
function tree(x,z,s,kind){const t=new THREE.Group();t.position.set(x,0,z);t.scale.setScalar(s);cyl(.3,.42,2.2,M(0x6b4a32),0,1.1,0,t,6);
  if(kind){const a=new THREE.Mesh(new THREE.IcosahedronGeometry(2.3,0),M(0x3e9a5a,{flatShading:true}));a.position.y=3.8;a.castShadow=true;t.add(a);
    const b=new THREE.Mesh(new THREE.IcosahedronGeometry(1.5,0),M(0x4cae6a,{flatShading:true}));b.position.set(1.1,5.2,.4);b.castShadow=true;t.add(b)}
  else{const a=new THREE.Mesh(new THREE.ConeGeometry(2.4,4.6,7),M(0x2f8a58,{flatShading:true}));a.position.y=4.2;a.castShadow=true;t.add(a);
    const b=new THREE.Mesh(new THREE.ConeGeometry(1.8,3.6,7),M(0x3b9d66,{flatShading:true}));b.position.y=6.4;b.castShadow=true;t.add(b)}isle.add(t)}
for(let i=0,n=0;n<26&&i<400;i++){const a=rr()*6.28,r=47+rr()*15,x=Math.cos(a)*r,z=Math.sin(a)*r;
  if(Math.abs(x)<48&&Math.abs(z)<33)continue;if(x>40&&Math.abs(z)<12)continue;tree(x,z,.8+rr()*.7,rr()>.45);n++}
for(let x=-40;x<=40;x+=16)[-1,1].forEach(sz=>{const z=sz*28.5;cyl(.12,.14,3.4,M(0x39435f),x,1.7,z,isle,6);
  const l=new THREE.Mesh(new THREE.SphereGeometry(.4,10,8),glowMat(0xfff2c2,.25,1.6));l.position.set(x,3.6,z);isle.add(l)});
[-1,1].forEach(sz=>{box(26,1,1.6,M(0x4a9a5c,{roughness:1}),-8*sz,.5,sz*24.5+(sz>0?0:0),isle)});
/* AI sculpture in the front plaza */
const sculpt=new THREE.Group();sculpt.position.set(0,0,29);isle.add(sculpt);
cyl(2.2,2.5,.7,M(0x39435f),0,.35,0,sculpt,24);
const ringM=M(0x22d3ee,{emissive:0x22d3ee,emissiveIntensity:1.3,roughness:.3}),ring1=new THREE.Mesh(new THREE.TorusGeometry(2.1,.2,10,40),ringM),ring2=new THREE.Mesh(new THREE.TorusGeometry(1.5,.16,10,40),M(0x8b5cf6,{emissive:0x8b5cf6,emissiveIntensity:1.3}));
ring1.position.y=3.4;ring2.position.y=3.4;sculpt.add(ring1,ring2);const orb=new THREE.Mesh(new THREE.SphereGeometry(.7,20,16),M(0xffffff,{emissive:0xbdeaff,emissiveIntensity:1.4}));orb.position.y=3.4;sculpt.add(orb);
/* entrance furniture + flags */
[-1,1].forEach(sz=>{box(1.4,.7,3.2,M(0x39435f),HW+14,.35,sz*7,isle);const pole=cyl(.1,.12,8,M(0xcfd5e2),HW+18,4,sz*10,isle,6);
  const flag=new THREE.Mesh(new THREE.PlaneGeometry(3,1.8),new THREE.MeshBasicMaterial({color:sz>0?0x22d3ee:0x8b5cf6,side:THREE.DoubleSide}));flag.position.set(HW+18,7,sz*10+1.6);flag.rotation.y=Math.PI/2;isle.add(flag)});
/* clouds */
const clouds=new THREE.Group();scene.add(clouds);
function cloud(x,y,z,s){const g=new THREE.Group();g.position.set(x,y,z);const m=new THREE.MeshStandardMaterial({color:0xffffff,emissive:0xffffff,emissiveIntensity:.35,roughness:1,flatShading:true});CMATS.push(m);
  [[0,0,0,5],[5,-.8,1,4],[-5,-.6,-1,4],[2.5,1.6,0,3.6],[-2.2,1.2,1.5,3.2]].forEach(([a,b,c,r])=>{const sp=new THREE.Mesh(new THREE.IcosahedronGeometry(r,1),m);sp.position.set(a,b,c);sp.scale.y=.6;g.add(sp)});
  g.scale.setScalar(s);clouds.add(g)}
for(let i=0;i<16;i++){const a=rr()*6.28,r=105+rr()*70,y=-30+rr()*58,x=Math.cos(a)*r,z=Math.sin(a)*r;
  if(Math.hypot(x-HOME.c.x,z-HOME.c.z)<70&&y>-6)continue;cloud(x,y,z,.8+rr()*1.1)}
/* sign textures */
function signTex(text,sub,w=1200,h=240){const c=document.createElement('canvas');c.width=w;c.height=h;const x=c.getContext('2d');
  x.fillStyle='rgba(8,14,36,.94)';x.beginPath();x.roundRect?x.roundRect(0,0,w,h,36):x.rect(0,0,w,h);x.fill();
  x.strokeStyle='#22d3ee';x.lineWidth=6;x.beginPath();x.roundRect?x.roundRect(6,6,w-12,h-12,32):x.rect(6,6,w-12,h-12);x.stroke();
  const cx=h/2+24,cy=h/2;x.beginPath();for(let i=0;i<6;i++){const a=i/6*6.283-1.5708;x.lineTo(cx+Math.cos(a)*74,cy+Math.sin(a)*74)}x.closePath();
  const lg=x.createLinearGradient(0,0,w*.3,h);lg.addColorStop(0,'#22d3ee');lg.addColorStop(1,'#8b5cf6');x.fillStyle=lg;x.fill();
  x.fillStyle='#fff';x.font='800 70px system-ui,sans-serif';x.textAlign='center';x.textBaseline='middle';x.fillText('AI',cx,cy+3);
  x.textAlign='left';const tg=x.createLinearGradient(260,0,w,0);tg.addColorStop(0,'#ffffff');tg.addColorStop(1,'#a5f3fc');x.fillStyle=tg;x.font='800 112px system-ui,sans-serif';x.fillText(text,260,sub?cy-14:cy+4);
  if(sub){x.fillStyle='#7aa8ff';x.font='600 40px system-ui,sans-serif';x.fillText(sub,266,cy+68)}
  const t=new THREE.CanvasTexture(c);t.encoding=THREE.sRGBEncoding;t.anisotropy=8;return t}
const signMat=()=>new THREE.MeshBasicMaterial({map:signTex('AI COMPANY','HEALTH INSURANCE & CARE · AUSTRALIA'),transparent:true,toneMapped:false});

/* ---------- time of day ---------- */
const stars=(()=>{const g=new THREE.BufferGeometry(),a=[];for(let i=0;i<700;i++){const t=rr()*6.283,b=Math.acos(rr()*1.55-.55),r=430;a.push(Math.sin(b)*Math.cos(t)*r,Math.cos(b)*r,Math.sin(b)*Math.sin(t)*r)}
  g.setAttribute('position',new THREE.Float32BufferAttribute(a,3));const p=new THREE.Points(g,new THREE.PointsMaterial({color:0xffffff,size:2.2,sizeAttenuation:false,transparent:true,opacity:0,depthWrite:false}));scene.add(p);return p})();
const sunDisc=new THREE.Mesh(new THREE.SphereGeometry(14,20,14),new THREE.MeshBasicMaterial({color:0xfff2c0})),moonDisc=new THREE.Mesh(new THREE.SphereGeometry(9,20,14),new THREE.MeshBasicMaterial({color:0xdfe8ff}));scene.add(sunDisc,moonDisc);
let todMode='auto';
const hx=h=>new THREE.Color(h),clampN=(v,a,b)=>Math.max(a,Math.min(b,v));
function setTOD(h){
  const ang=(h-6)/24*Math.PI*2,el=Math.sin(ang),dayF=clampN((el+.1)/.4,0,1),duskF=Math.max(0,1-Math.abs(el-.05)/.3),n=1-dayF,mix=(a,b,t)=>hx(a).lerp(hx(b),t);
  const top=mix('#050a1c','#3b82d4',dayF).lerp(hx('#3a3568'),duskF*.55),bot=mix('#101a3d','#d3e8ff',dayF).lerp(hx('#ff9f6b'),duskF*.7),mid=top.clone().lerp(bot,.5);
  const bg=`linear-gradient(#${top.getHexString()} 0%,#${mid.getHexString()} 50%,#${bot.getHexString()} 100%)`;document.documentElement.style.background=bg;document.body.style.background=bg;
  const dir=new THREE.Vector3(Math.cos(ang)*.9,Math.sin(ang),.55).normalize();
  sun.position.copy(dir).multiplyScalar(130);sun.intensity=1.25*clampN(el*2.2,0,1);sun.color.copy(hx(0xff9a5a).lerp(hx(0xfff1dd),clampN(el*2.5,0,1)));
  moonL.position.copy(dir).multiplyScalar(-130);moonL.intensity=.4*n;
  hemi.intensity=.32+.68*dayF;hemi.color.copy(mix('#7080c0','#d6e6ff',dayF));hemi.groundColor.copy(mix('#1a1a2a','#7a6a58',dayF));
  sunDisc.position.copy(dir).multiplyScalar(380);sunDisc.visible=el>-.08;moonDisc.position.copy(dir).multiplyScalar(-380);moonDisc.visible=n>.15;
  stars.material.opacity=n*.9;extMat.emissive.set(0xffd9a0);extMat.emissiveIntensity=n*.35;
  GLOW.forEach(g=>g.m.emissiveIntensity=g.base+n*g.k);CMATS.forEach(m=>{m.emissiveIntensity=.05+.3*dayF});
}
function applyTOD(){const d=new Date(),h=todMode==='auto'?d.getHours()+d.getMinutes()/60:todMode==='day'?13:23;setTOD(h)}
setInterval(()=>{if(todMode==='auto')applyTOD()},20000);
document.getElementById('tod').onclick=e=>{const b=e.target.closest('button');if(!b)return;todMode=b.dataset.t;[...e.currentTarget.children].forEach(x=>x.classList.toggle('on',x===b));applyTOD()};
/* ---------- quality / fps ---------- */
let QUAL=2,qualAuto=true,fpsT=0,fpsN=0,lowC=0;
function setQuality(q,manual){QUAL=q;if(manual)qualAuto=false;renderer.setPixelRatio([1,1.25,Math.min(devicePixelRatio,2)][q]);renderer.setSize(innerWidth,innerHeight);
  const sh=q>0;if(renderer.shadowMap.enabled!==sh){renderer.shadowMap.enabled=sh;scene.traverse(o=>{if(o.material)[].concat(o.material).forEach(m=>m.needsUpdate=true)})}
  const ms=[0,1024,2048][q];if(sh&&sun.shadow.mapSize.x!==ms){sun.shadow.mapSize.set(ms,ms);if(sun.shadow.map){sun.shadow.map.dispose();sun.shadow.map=null}}
  document.querySelectorAll('#qual button').forEach(b=>b.classList.toggle('on',+b.dataset.q===q))}
document.getElementById('qual').onclick=e=>{const b=e.target.closest('button');if(b)setQuality(+b.dataset.q,true)};
function fpsStep(dt){fpsT+=dt;fpsN++;if(fpsT>=1){const f=Math.round(fpsN/fpsT);document.getElementById('fps').textContent=f+' fps';if(qualAuto&&f<22&&QUAL>0){if(++lowC>=3){setQuality(QUAL-1);lowC=0}}else lowC=0;fpsT=0;fpsN=0}}
function freeze(o){o.traverse(c=>{c.matrixAutoUpdate=false;c.updateMatrix()})}
