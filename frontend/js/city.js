/* AI Company HQ – The city: avenue, mall, hospital, school, towers, cafés, the company's hospital and clinic.
   Loaded in the order of js/manifest.json and served as one script (/ui/app.js). */
/* ================= THE CITY: avenue, mall, hospital, school, towers, cafés, clinic, police, depot, building site, TAFE ================= */
const WPOS={aich_hospital:{x:28,z:-86},aich_clinic:{x:28,z:86},mall:{x:112,z:-62},towers:{x:112,z:64},hospital:{x:252,z:-62},school:{x:252,z:66},cafe:{x:178,z:70},clinic:{x:178,z:-70},
  police:{x:300,z:-8},depot:{x:318,z:-58},worksite:{x:318,z:60},tafe:{x:350,z:6}};
const WNAME={aich_hospital:'AI Company Health Private Hospital',aich_clinic:'AI Company Health Clinic',mall:'Wattle Grove Mall',towers:'Riverside business towers',hospital:'Wattle Grove Hospital',school:'Wattle Grove Public School',cafe:'High Street cafés',
  clinic:'Medical & dental centre',police:'Police station',depot:'ParcelGo logistics depot',worksite:'BuildRight construction site',tafe:'TAFE & Uni campus',home:'Home'};
const wpMeshes=[];
function signTex(txt,bg,fg,w=512,h=128){const c=document.createElement('canvas');c.width=w;c.height=h;const x=c.getContext('2d');x.fillStyle=bg;x.fillRect(0,0,w,h);x.fillStyle=fg;x.font=`800 ${Math.round(h*.42)}px system-ui`;x.textAlign='center';x.textBaseline='middle';x.fillText(txt,w/2,h/2+2);const t=new THREE.CanvasTexture(c);t.encoding=THREE.sRGBEncoding;return t}
function winTex(cols,rows,lit,base){const c=document.createElement('canvas');c.width=cols*16;c.height=rows*16;const x=c.getContext('2d');x.fillStyle=typeof base==='number'?'#'+base.toString(16).padStart(6,'0'):base;x.fillRect(0,0,c.width,c.height);
  for(let i=0;i<cols;i++)for(let j=0;j<rows;j++){x.fillStyle=Math.random()<lit?'#ffe9a8':'#1b2a44';x.fillRect(i*16+3,j*16+3,10,10)}const t=new THREE.CanvasTexture(c);t.encoding=THREE.sRGBEncoding;return t}
function building(g,x,z,w,d,h,col,name,wp,signBg='#0f172a',signFg='#fff',winCols=0){
  const mat=winCols?new THREE.MeshStandardMaterial({map:winTex(winCols,Math.max(2,Math.round(h/3)),.35,col),roughness:.5}):M(col,{roughness:.75});
  const b=box(w,h,d,mat,x,h/2,z,g);b.userData.workplace=wp;wpMeshes.push(b);box(w+.6,.5,d+.6,M(0x334155),x,h+.25,z,g,false);
  const sgn=new THREE.Mesh(new THREE.PlaneGeometry(Math.min(w*.8,22),Math.min(w*.8,22)/4),new THREE.MeshBasicMaterial({map:signTex(name,signBg,signFg),toneMapped:false}));
  sgn.position.set(x,Math.min(h-1.2,7.5),z+(z<0?d/2+.06:-d/2-.06));sgn.rotation.y=z<0?0:Math.PI;g.add(sgn);sgn.userData.workplace=wp;wpMeshes.push(sgn);return b}
function parkedCar(g,x,z,rot,col){const c=carMesh(col);c.position.set(x,0,z);c.rotation.y=rot;g.add(c);return c}
const CAR_COLS=[0xdc2626,0x2563eb,0xf8fafc,0x111827,0x9ca3af,0x16a34a,0xf59e0b,0x7c3aed,0x0891b2];
function carMesh(col){const c=new THREE.Group();const b=new THREE.Mesh(new THREE.BoxGeometry(1.9,.7,3.8),M(col,{roughness:.35,metalness:.3}));b.position.y=.75;b.castShadow=true;c.add(b);
  const cab=new THREE.Mesh(new THREE.BoxGeometry(1.6,.6,2),M(0x1e293b,{roughness:.2,metalness:.4}));cab.position.set(0,1.38,-.2);c.add(cab);
  [[-.95,1.25],[.95,1.25],[-.95,-1.25],[.95,-1.25]].forEach(([wx,wz])=>{const w=new THREE.Mesh(new THREE.CylinderGeometry(.36,.36,.28,10),M(0x0b0b0f));w.rotation.z=Math.PI/2;w.position.set(wx,.36,wz);c.add(w)});
  c.scale.setScalar(1.25);return c}
function buildCity(g){
  const asphalt=M(0x3b4252,{roughness:.95}),line=M(0xf8fafc,{roughness:.6}),pave=M(0xb8c0cf,{roughness:.9});
  box(300,.12,9,asphalt,ISL-4+150,.06,0,g,false);for(let x=ISL;x<ISL+300;x+=8)box(3.5,.02,.25,line,x,.13,0,g,false);           // the avenue: HQ -> town -> east end
  [[112,1],[252,1],[318,1]].forEach(([x])=>box(8,.12,150,asphalt,x,.06,0,g,false));                                                // cross streets to the north and south
  box(8,.12,150,asphalt,178,.06,0,g,false);
  box(300,.1,2.2,pave,ISL-4+150,.05,6,g,false);box(300,.1,2.2,pave,ISL-4+150,.05,-6,g,false);
  // the mall + its car park
  building(g,112,-70,46,26,11,0xe5e7eb,'WATTLE GROVE MALL','mall','#be123c');box(40,.6,.6,glowMat(0x93c5fd,.4,1),112,4,-56.7,g,false);
  box(46,.08,16,M(0x475569,{roughness:.95}),112,.05,-48,g,false);for(let i=0;i<10;i++)parkedCar(g,93+i*4.2,-48+(i%2?3:-3),0,CAR_COLS[i%CAR_COLS.length]);
  // business towers
  [[98,58,26,0x60a5fa],[112,72,38,0x94a3b8],[126,58,30,0x38bdf8]].forEach(([x,z,h,c],i)=>building(g,x,z,11,11,h,c,i===1?'RIVERSIDE TOWERS':'','towers','#0f172a','#fff',6));
  building(g,252,-68,30,22,15,0xf8fafc,'HOSPITAL','hospital','#dc2626');box(4,1.2,.2,M(0xdc2626),252,13,-56.8,g,false);box(1.2,4,.2,M(0xdc2626),252,13,-56.8,g,false);
  building(g,252,72,32,16,7,0xfcd34d,'PUBLIC SCHOOL','school','#1d4ed8');const fld=box(34,.06,18,M(0x4ade80,{roughness:1}),252,.05,52,g,false);
  ['#b91c1c','#15803d','#7c3aed','#0e7490','#c2410c'].forEach((c,i)=>{const sx=166+i*6;building(g,sx,74,5.6,8,5,new THREE.Color(c).getHex(),'','cafe');box(5.8,.2,2.2,M(new THREE.Color(c).getHex()),sx,3.4,69.4,g,false)});
  const cafeSign=new THREE.Mesh(new THREE.PlaneGeometry(22,4),new THREE.MeshBasicMaterial({map:signTex('HIGH STREET','#14532d','#f0fdf4'),toneMapped:false}));cafeSign.position.set(178,7.2,69.9);cafeSign.rotation.y=Math.PI;g.add(cafeSign);
  building(g,178,-74,24,14,8,0xe0f2fe,'MEDICAL & DENTAL','clinic','#0891b2');
  building(g,300,-16,14,9,6,0x1e3a8a,'POLICE','police','#1e3a8a');
  building(g,318,-66,30,18,9,0x9ca3af,'PARCELGO DEPOT','depot','#ea580c');for(let i=0;i<3;i++){const t=carMesh(0xf97316);t.scale.set(1.6,1.9,2);t.position.set(306+i*9,0,-50);g.add(t)}
  building(g,318,64,18,14,4,0xa8a29e,'BUILDRIGHT','worksite','#ca8a04');const crane=new THREE.Group();crane.position.set(330,0,56);g.add(crane);
  box(.8,26,.8,M(0xfacc15),0,13,0,crane);box(22,.8,.8,M(0xfacc15),6,26,0,crane);box(.2,10,.2,M(0x334155),15,21,0,crane,false);
  building(g,352,12,26,16,9,0xfde68a,'TAFE & UNI','tafe','#7c2d12');
  building(g,28,-86,34,20,13,0xecfeff,'AI COMPANY HEALTH HOSPITAL','aich_hospital','#0e7490');box(4,1.2,.2,M(0x22d3ee),28,11,-75.8,g,false);box(1.2,4,.2,M(0x22d3ee),28,11,-75.8,g,false);
  building(g,28,86,26,14,7,0xecfeff,'AI COMPANY HEALTH CLINIC','aich_clinic','#0e7490');
  box(9,.12,30,M(0x3b4252,{roughness:.95}),28,.06,-58,g,false);box(9,.12,30,M(0x3b4252,{roughness:.95}),28,.06,58,g,false);
  for(let i=0;i<40;i++){const x=ISL+10+i*7.3,z=(i%2?11:-11);const t=new THREE.Group();t.position.set(x,0,z);t.scale.setScalar(.55);g.add(t);cyl(.3,.42,2.2,M(0x6b4a32),0,1.1,0,t,6);
    const k=new THREE.Mesh(new THREE.IcosahedronGeometry(2.2,0),M(0x3e9a5a,{flatShading:true}));k.position.y=3.6;k.castShadow=true;t.add(k)}}
