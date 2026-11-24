/* AI Company HQ – The AI Company HQ: three floors, rooms, desks, screens and boards.
   Loaded in the order of js/manifest.json and served as one script (/ui/app.js). */
/* ================= BUILDING ================= */
const FG=[0,1,2].map(f=>{const g=new THREE.Group();g.position.y=FY[f];scene.add(g);return g});
const SOLID=M(0x2b3556,{roughness:.8}),DESKT=M(0x34415f),DESKL=M(0x222b43),WOOD=M(0x4a3a2c),WHITE=M(0xe8eef8,{emissive:0xdfe6f3,emissiveIntensity:.35,roughness:.5});
const slabMats=[];
const extMat=new THREE.MeshStandardMaterial({color:0x9fc8ff,transparent:true,opacity:.3,roughness:.08,metalness:.35,depthWrite:false});
const FRAME=M(0xeef1f7,{roughness:.55}),BAND=M(0x27304a,{roughness:.45,metalness:.3}),MULL=M(0x39435f,{roughness:.5,metalness:.4}),roofMats=[];
const GH=FH-.5,GY=TOP+GH/2,GX=HW*2+1,GZ=HD*2+1;
FG.forEach((G,f)=>{const g=new THREE.Group();G.add(g);G.userData.shell=g;
  const sm=M(0xe3e7f0,{roughness:.85,transparent:true});slabMats.push(sm);
  box(GX,.5,GZ,sm,0,.25,0,g);
  box(HW*2-.4,.06,CZ*2,M(0x4a5678,{roughness:.9}),0,TOP+.03,0,g,false);
  box(HW*2-1,.07,.18,M(0xffe9a8,{emissive:0xffd77a,emissiveIntensity:.7}),0,TOP+.05,0,g,false);
  /* curtain wall: glass + mullions + spandrel band + corner columns */
  box(GX,GH,.2,extMat,0,GY,-HD-.4,g,false);box(GX,GH,.2,extMat,0,GY,HD+.4,g,false);box(.2,GH,GZ,extMat,-HW-.4,GY,0,g,false);
  box(.2,GH,HD-CZ,extMat,HW+.4,GY,-(HD+CZ)/2,g,false);box(.2,GH,HD-CZ,extMat,HW+.4,GY,(HD+CZ)/2,g,false);
  for(let x=-HW;x<=HW+.01;x+=4){box(.24,GH,.34,MULL,x,GY,-HD-.4,g,false);box(.24,GH,.34,MULL,x,GY,HD+.4,g,false)}
  for(let z=-HD;z<=HD+.01;z+=4){box(.34,GH,.24,MULL,-HW-.4,GY,z,g,false);if(Math.abs(z)>CZ+.5)box(.34,GH,.24,MULL,HW+.4,GY,z,g,false)}
  box(GX+.9,.9,.5,BAND,0,.45,-HD-.55,g);box(GX+.9,.9,.5,BAND,0,.45,HD+.55,g);box(.5,.9,GZ+.9,BAND,-HW-.55,.45,0,g);
  box(.5,.9,HD-CZ,BAND,HW+.55,.45,-(HD+CZ)/2,g);box(.5,.9,HD-CZ,BAND,HW+.55,.45,(HD+CZ)/2,g);
  [[-1,-1],[1,-1],[-1,1],[1,1]].forEach(([sx,sz])=>box(1,GH+.5,1,FRAME,sx*(HW+.45),GY-.25,sz*(HD+.45),g));
  /* lift & stair core */
  box(8,GH,HD-CZ,M(0x3c4668,{roughness:.55,metalness:.25}),0,TOP+GH/2,-(HD+CZ)/2,g);
  g.userData.liftPanel=box(3.4,3.2,.15,M(0xffd77a,{emissive:0xffd77a,emissiveIntensity:.5}),0,TOP+1.6,-CZ+.05,g,false);
  box(.12,3.2,.2,M(0x0b1020),0,TOP+1.6,-CZ+.1,g,false);
  LBL.push({el:dom('lbl','Lifts &amp; stairs','#ffd77a'),pos:new THREE.Vector3(0,FY[f]+TOP+4.6,-CZ-.5),floor:f,sub:true});
  G.userData.liftPanel=g.userData.liftPanel;
});
const floorHits=FG.map((G,f)=>{const m=new THREE.Mesh(new THREE.BoxGeometry(GX,FH,GZ),new THREE.MeshBasicMaterial({visible:false}));m.position.set(0,FH/2,0);m.userData.floor=f;G.userData.shell.add(m);return m});
/* roof */
const RG=new THREE.Group();RG.position.y=FY[2]+FH;scene.add(RG);
(()=>{const rm=M(0xcdd3e0,{roughness:.9,transparent:true});roofMats.push(rm);box(GX+.6,.5,GZ+.6,rm,0,.25,0,RG);
  [[0,-HD-.55,GX+1.2,.6],[0,HD+.55,GX+1.2,.6]].forEach(([x,z,w,d])=>box(w,1.1,d,FRAME,x,1.05,z,RG));[-1,1].forEach(sx=>box(.6,1.1,GZ+.6,FRAME,sx*(HW+.55),1.05,0,RG));
  box(8,3.6,HD-CZ,FRAME,0,.5+1.8,-(HD+CZ)/2,RG);                                   // lift penthouse
  [[-18,-10],[-12,-10],[-18,-5]].forEach(([x,z])=>{box(3,1.4,2.4,M(0xaab2c4),x,1.2,z,RG);cyl(.9,.9,.2,M(0x39435f),x,2,z,RG,16)});    // AC units
  for(let i=0;i<4;i++)for(let j=0;j<3;j++){const p=box(4.2,.12,2.4,M(0x1c3a78,{roughness:.2,metalness:.6}),14+i*5,1.2,-13+j*3.4,RG,false);p.rotation.x=-.35}  // solar panels
  const sg=new THREE.PlaneGeometry(26,5.2);
  [[1,0],[-1,Math.PI]].forEach(([d,ry])=>{const pl=new THREE.Mesh(sg,signMat());pl.position.set(0,4.2,HD-3+(d>0?.06:-.06));pl.rotation.y=ry;RG.add(pl)});
  [-10,10].forEach(x=>box(.3,3.4,.3,MULL,x,2.2,HD-3,RG));
  const core=new THREE.Mesh(new THREE.IcosahedronGeometry(2.1,1),new THREE.MeshBasicMaterial({color:0x22d3ee,wireframe:true}));core.position.set(0,9.2,-12);RG.add(core);RG.userData.core=core;
  const orb2=new THREE.Mesh(new THREE.SphereGeometry(.9,18,14),M(0xffffff,{emissive:0x8b5cf6,emissiveIntensity:1.5}));orb2.position.copy(core.position);RG.add(orb2);
  cyl(.15,.15,3.4,MULL,0,.5+3.6+.9,-12,RG,6).position.y=6.2})();
/* main entrance on the east end of the corridor */
(()=>{const g=FG[0].userData.shell;box(7.5,.4,CZ*2+4,FRAME,HW+4,4.6,0,g);[-1,1].forEach(sz=>box(.5,4.1,.5,FRAME,HW+7.3,TOP+2.05,sz*(CZ+1.5),g));
  box(.5,.9,CZ*2,BAND,HW+.5,TOP+4.2,0,g,false);[0,1,2].forEach(i=>box(2,.18,CZ*2+3,M(0xcfd5e2),HW+1.6+i*1.5,.09+(2-i)*.0,0,g));
  const sp=new THREE.Mesh(new THREE.PlaneGeometry(6.8,1.36),signMat());sp.position.set(HW+7.57,4.6,0);sp.rotation.y=Math.PI/2;g.add(sp)})();

function wall(g,axis,a,b,fixed,r,gapAt,gapW){
  const parts=gapAt==null?[[a,b]]:[[a,gapAt-gapW/2],[gapAt+gapW/2,b]];
  parts.forEach(([p,q])=>{const len=q-p;if(len<.2)return;const c=(p+q)/2,x=axis==='x';
    box(x?len:.35,1.2,x?.35:len,SOLID,x?c:fixed,TOP+.6,x?fixed:c,g);
    box(x?len:.2,3.4,x?.2:len,r.gmat,x?c:fixed,TOP+2.9,x?fixed:c,g,false);
    box(x?len:.4,.1,x?.4:len,r.trim,x?c:fixed,TOP+4.62,x?fixed:c,g,false)});
}
const plant=(g,x,z)=>{cyl(.5,.4,.8,M(0x3a2f26),x,TOP+.4,z,g,10);const s=new THREE.Mesh(new THREE.SphereGeometry(.8,10,8),M(0x238a68));s.position.set(x,TOP+1.5,z);s.castShadow=true;g.add(s)};
const sofa=(g,x,z,w,col,rot=0)=>{const s=new THREE.Group();s.position.set(x,TOP,z);s.rotation.y=rot;box(w,.7,1.6,M(col),0,.35,0,s);box(w,1,.4,M(col),0,.9,-.7,s);g.add(s)};
const desk=(g,col,x,z,fwd)=>{const d=new THREE.Group();d.position.set(x,TOP,z);g.add(d);const c=new THREE.Color(col);
  box(3,.14,1.5,DESKT,0,1.15,0,d);box(.12,1.1,1.3,DESKL,-1.35,.6,0,d);box(.12,1.1,1.3,DESKL,1.35,.6,0,d);
  box(1.3,.8,.07,M(c,{emissive:c,emissiveIntensity:.8,roughness:.3}),0,1.75,fwd*.32,d,false);box(.14,.4,.14,DESKL,0,1.4,fwd*.32,d);box(.9,.04,.3,M(0x10141f),0,1.24,-fwd*.3,d,false);cyl(.1,.1,.18,M(0xe8eef8),-1.0,1.3,fwd*.1,d,10);box(.5,.03,.65,M(0xf2f4fa),1.0,1.23,-fwd*.1,d,false);cyl(.07,.09,.05,DESKL,-1.1,1.25,-fwd*.35,d,8);cyl(.02,.02,.5,DESKL,-1.1,1.5,-fwd*.35,d,6);{const sh=new THREE.Mesh(new THREE.SphereGeometry(.16,10,8,0,6.283,0,1.6),glowMat(0xffe9a8,.2,1.8));sh.position.set(-1.1,1.78,-fwd*.35);d.add(sh)}const pl=new THREE.Mesh(new THREE.PlaneGeometry(1.2,.7),new THREE.MeshBasicMaterial({color:0x0b1020}));pl.position.set(0,1.76,fwd*.32-fwd*.085);pl.rotation.y=fwd>0?Math.PI:0;d.add(pl);return pl};
const faceAng=(s,cx,cz)=>Math.atan2(cx-s.x,cz-s.z);
const SEATH=.6,BASE=.85,SIT_DY=1.3-(SEATH+.08)/BASE,CH_DARK=M(0x151a29,{roughness:.5});
function makeChair(g,s,col=0x1f2a44){
  const c=new THREE.Group();c.position.set(s.x,TOP,s.z);c.rotation.y=s.ang||0;g.add(c);const m=M(col,{roughness:.65});
  cyl(.5,.5,.06,CH_DARK,0,.09,0,c,16).castShadow=false;cyl(.07,.07,.4,CH_DARK,0,.3,0,c,8).castShadow=false;
  box(1,.16,.95,m,0,SEATH-.08,0,c,false);box(.95,.95,.14,m,0,1.2,-.5,c,false);
  [-1,1].forEach(x=>box(.1,.08,.6,CH_DARK,x*.52,.92,-.05,c,false));return c;
}

function glowDot(x,y,z,g,c=0x2ee6a6){const m=new THREE.Mesh(new THREE.SphereGeometry(.07,8,6),glowMat(c,.9,.8));m.position.set(x,y,z);g.add(m)}
function furnishTeam(r,g){
  const fd=r.fdir,far=r.far,col=new THREE.Color(r.color),ph=r.w*.4*240/640;
  const pan=textPanel(1280,480,()=>{});
  const scr=new THREE.Mesh(new THREE.PlaneGeometry(r.w*.4,ph),new THREE.MeshBasicMaterial({map:pan.t,toneMapped:false}));
  r.board={m:scr,w:r.w*.4,h:ph,c:pan.c,t:pan.t};scr.position.set(r.cx-r.w*.2,TOP+2.9,far+fd*.56);scr.rotation.y=r.north?0:Math.PI;g.add(scr);
  box(r.w*.4+.3,ph+.3,.2,M(0x151a29),r.cx-r.w*.2,TOP+2.9,far+fd*.45,g,false);
  const sx=r.cx+r.w*.24;box(r.w*.3,2.6,.7,M(0x2c3752),sx,TOP+1.3,far+fd*.5,g);
  for(let sh=0;sh<3;sh++)for(let b=0;b<12;b++){const bw=.18+((b*7+sh*3)%4)*.05,bh=.5+((b*5+sh)%3)*.12;box(bw,bh,.45,M(new THREE.Color().setHSL(((b*37+sh*91)%360)/360,.5,.5)),sx-r.w*.14+b*(r.w*.28/12)+.15,TOP+.3+sh*.85+bh/2,far+fd*.75,g,false)}
  [0,1].forEach(i=>box(.9,1.5,.8,M(0x8892a8),r.x0+3.2+i*1.0,TOP+.75,far+fd*.9,g));
  const px=r.x0+1.4,pz=far+fd*8.5;box(1.8,.9,1.1,M(0x39435f),px,TOP+.45,pz,g);box(1.3,.5,.9,M(0xdfe4ee),px,TOP+1.15,pz,g);glowDot(px+.4,TOP+1.25,pz-fd*.46,g);
  const wx=r.x1-1.3,wz=r.north?r.z1-1.6:r.z0+1.6;cyl(.45,.5,1.4,M(0xdfe4ee),wx,TOP+.7,wz,g,12);
  const bt=cyl(.38,.38,.9,new THREE.MeshStandardMaterial({color:0x7ac7ff,transparent:true,opacity:.7,roughness:.1}),wx,TOP+1.85,wz,g,12);bt.castShadow=false;
  cyl(.28,.24,.6,M(0x39435f),r.x1-1.1,TOP+.3,far+fd*2.2,g,10);
  plant(g,r.x0+1.2,far+fd*1.2);plant(g,r.x1-1.2,far+fd*1.2);
  sofa(g,r.x1-3.8,r.north?r.z1-2.2:r.z0+2.2,3.4,0x2f3b5e,0);box(3.4,.18,1.1,WOOD,r.x1-3.8,TOP+.45,r.north?r.z1-3.7:r.z0+3.7,g);
  box(r.w*.34,.04,r.d*.28,M(col.clone().multiplyScalar(.22)),r.cx,TOP+.075,r.cz+(r.north?1:-1)*r.d*.22,g,false);
}
function drawScreen(r,sl){
  const {c,t}=r.scr,x=c.getContext('2d');x.setTransform(1280/768,0,0,1280/768,0,0);const W=768,H=Math.round(768*r.scr.h/r.scr.w),lite=false,fg=lite?'#0b1226':'#fff',sub=lite?'#566079':'#8aa0c8';
  x.fillStyle=lite?'#f4f6fb':'#0b1226';x.fillRect(0,0,W,H);x.fillStyle=r.color;x.fillRect(0,0,W,12);
  if(!sl){x.fillStyle=fg;x.font='800 54px system-ui,sans-serif';x.textBaseline='middle';x.textAlign='center';x.fillText(r.name,W/2,H/2-20);x.fillStyle=sub;x.font='600 28px system-ui,sans-serif';x.fillText('AI Company · ready for presentation',W/2,H/2+34)}
  else{const k=Math.min(1,H/430),P=Math.round(30*k+6),half=!!(sl.chart&&sl.chart.series&&sl.chart.series.length),bw=half?W*.46-P:W-P*2-30;
    x.textAlign='left';x.textBaseline='top';x.fillStyle=sl.color||r.color;x.font=`700 ${Math.round(22*k+4)}px system-ui,sans-serif`;x.fillText((sl.presenter||'').toUpperCase(),P,Math.round(H*.07));
    const tf=Math.round(44*k+6);x.fillStyle=fg;x.font=`800 ${tf}px system-ui,sans-serif`;const tl=wrapText(x,sl.title||'',half?W*.5:W-P*2,H<300?1:2);tl.forEach((l,i)=>x.fillText(l,P,Math.round(H*.07)+tf*.9+i*tf*1.1));
    const top=Math.round(H*.07)+tf*.9+tl.length*tf*1.1+tf*.35;
    if(half)drawSlideChart(x,sl.chart,W*.5,Math.round(H*.07),W*.5-P*.6,H-Math.round(H*.07)-P*.6,sl.color||r.color,fg,sub);
    const bf=Math.round((half?20:28)*k+5),lh=bf*1.22;x.font=`500 ${bf}px system-ui,sans-serif`;let y=top;
    for(const b of (sl.bullets||[]).slice(0,5)){const ls=wrapText(x,b,bw,2);if(y+lh*ls.length>H-P*.4)break;x.fillStyle=sl.color||r.color;x.fillRect(P,y+bf*.32,bf*.36,bf*.36);x.fillStyle=fg;ls.forEach((l,i)=>x.fillText(l,P+bf*.8,y+i*lh));y+=lh*ls.length+bf*.35}
    if(sl.progress!=null&&!half){x.fillStyle=lite?'#d6dbe8':'#1d2740';x.fillRect(P,H-P-14,W-P*2,12);x.fillStyle=sl.color||r.color;x.fillRect(P,H-P-14,(W-P*2)*sl.progress/100,12)}}
  t.needsUpdate=true}
function drawSlideChart(x,ch,x0,y0,w,h,col,fg,sub){
  const fz=Math.max(11,Math.min(18,h*.075));x.fillStyle='#ffffff0a';x.fillRect(x0,y0,w,h);x.fillStyle=sub;x.font=`700 ${fz}px system-ui,sans-serif`;x.textAlign='left';x.textBaseline='top';x.fillText((ch.title||'').slice(0,46),x0+10,y0+8);
  const S=ch.series||[],n=(ch.labels||[]).length;if(!n||!S.length)return;const all=S.flatMap(s=>s.values),lo=ch.type==='bar'?Math.min(0,...all):Math.min(...all),hi=Math.max(...all),rg=(hi-lo)||1;
  const L=x0+12,T=y0+fz*2.1,W2=w-24,H2=h-fz*4.2,Y=v=>T+H2*(1-(v-lo)/rg),cols=[col,'#f5b942','#a78bfa'];
  S.forEach((s,j)=>{x.strokeStyle=x.fillStyle=cols[j%3];if(ch.type==='bar'){const bw=W2/n/(S.length+.4);s.values.forEach((v,i)=>{const bx=L+i*W2/n+j*bw;x.fillRect(bx,Math.min(Y(v),Y(0)),bw*.9,Math.abs(Y(0)-Y(v)))})}
    else{x.lineWidth=3;x.beginPath();s.values.forEach((v,i)=>{const px=L+i*W2/Math.max(1,n-1);i?x.lineTo(px,Y(v)):x.moveTo(px,Y(v))});x.stroke()}
    x.font=`600 ${fz*.85}px system-ui,sans-serif`;x.fillText('■ '+s.name,x0+10+j*fz*9,y0+h-fz*1.5)});
  x.fillStyle=fg;x.font=`800 ${fz*1.1}px system-ui,sans-serif`;x.textAlign='right';const last=S[0].values[S[0].values.length-1];x.fillText(Math.abs(last)<1&&last!==0?(last*100).toFixed(1)+'%':Math.round(last).toLocaleString('en-AU'),x0+w-10,y0+8);
  x.fillStyle=sub;x.font=`500 ${fz*.75}px system-ui,sans-serif`;x.fillText(String(ch.labels[n-1]).slice(-10),x0+w-10,y0+h-fz*1.4);x.textAlign='left'}
function makeScreen(r,w,h,y){const c=document.createElement('canvas');c.width=1280;c.height=Math.round(1280*h/w);const t=new THREE.CanvasTexture(c);t.encoding=THREE.sRGBEncoding;t.anisotropy=4;
  const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:t,toneMapped:false}));m.position.set(r.cx,y,r.far+r.fdir*.66);m.rotation.y=r.north?0:Math.PI;r.grp.add(m);
  r.scr={c,t,w,h,m};r.screenPos={x:r.cx,z:r.far+r.fdir*.66};drawScreen(r,null)}
ROOMS.forEach(r=>{
  r.grp=new THREE.Group();FG[r.floor].add(r.grp);const g=r.grp,col=new THREE.Color(r.color);
  r.cx=(r.x0+r.x1)/2;r.cz=(r.z0+r.z1)/2;r.w=r.x1-r.x0;r.d=r.z1-r.z0;r.north=r.z1<0;r.y=FY[r.floor]+TOP;
  r.gmat=new THREE.MeshStandardMaterial({color:col,transparent:true,opacity:.16,roughness:.1,metalness:.2,depthWrite:false});
  r.trim=M(col,{emissive:col,emissiveIntensity:.7});
  r.carpetMat=M(col.clone().multiplyScalar(.32),{roughness:.95,transparent:true});
  r.carpet=box(r.w-.6,.06,r.d-.6,r.carpetMat,r.cx,TOP+.04,r.cz,g,false);r.carpet.userData.room=r;
  const i=.18,X0=r.x0+i,X1=r.x1-i,Z0=r.z0+i,Z1=r.z1-i;
  wall(g,'z',Z0,Z1,X0,r);wall(g,'z',Z0,Z1,X1,r);
  if(r.north){wall(g,'x',X0,X1,Z0,r);wall(g,'x',X0,X1,Z1,r,r.cx,4.6)}else{wall(g,'x',X0,X1,Z1,r);wall(g,'x',X0,X1,Z0,r,r.cx,4.6)}
  box(4.6,.07,.5,r.trim,r.cx,TOP+.05,r.north?r.z1:r.z0,g,false);
  const dz=r.north?1:-1;r.door={x:r.cx,z:r.north?r.z1:r.z0};r.inside={x:r.cx,z:r.door.z-dz*2.6};
  r.far=r.north?r.z0:r.z1;r.fdir=r.north?1:-1;
  r.plate=new THREE.Group();r.plate.visible=false;scene.add(r.plate);
  box(r.w+1.8,.5,r.d+1.8,M(0xe3e7f0,{roughness:.85}),r.cx,FY[r.floor]+.25,r.cz,r.plate);
  const pc=new THREE.Mesh(new THREE.ConeGeometry(Math.min(r.w,r.d)*.55,7,6),M(0x8a8494,{roughness:1,flatShading:true}));pc.rotation.x=Math.PI;pc.position.set(r.cx,FY[r.floor]-3.5,r.cz);r.plate.add(pc);
  r.lbl=dom('lbl',`${r.name}<small></small>`,r.color);r.small=r.lbl.querySelector('small');
  LBL.push({el:r.lbl,pos:new THREE.Vector3(r.cx,r.y+5.4,r.cz),floor:r.floor,room:r});
});
TEAMROOMS.forEach(r=>{
  const g=r.grp;r.seats=[];for(let k=0;k<r.team.people.length;k++)addSeat(r);
  furnishTeam(r,g);
});
const chair=(g,s,col=0x1b2336)=>makeChair(g,s,col);
function addSeat(r){   // desks on a fixed grid (up to 8 per room) so a new hire never moves anyone
  const k=r.seats.length,narrow=r.w<20,cols=narrow?2:3,pitch=narrow?6.5:(r.w>25?7.5:6.5),rows=Math.ceil(8/cols),dz=Math.min(5.4,(r.d-6)/Math.max(1,rows-1));
  const row=Math.floor(k/cols),c=k%cols,x=r.cx+(c-(cols-1)/2)*pitch,zd=r.far+r.fdir*(4.6+row*dz);
  const mon=desk(r.grp,r.color,x,zd,-r.fdir);const st={x,z:zd+r.fdir*1.35,ang:r.north?Math.PI:0,monitor:mon};r.seats.push(st);makeChair(r.grp,st,0x1f2a44);return st}
/* shared rooms: seats list lets the backend seat people */
(()=>{const r=R.lob,g=r.grp;box(6,1.2,1.4,WOOD,r.x0+5,TOP+.6,r.z0+4,g);box(7,1.3,1.2,WOOD,r.x1-4.5,TOP+.65,r.z0+1.8,g);
  LBL.push({el:dom('lbl','Reception','#c084fc'),pos:new THREE.Vector3(r.x0+5,r.y+3,r.z0+4),floor:0,sub:true});
  [[r.cx-2.5,r.cz+2],[r.cx+3,r.cz+4]].forEach(([x,z])=>{cyl(1,1,.1,WOOD,x,TOP+1.1,z,g,18);cyl(.1,.1,1.1,DESKL,x,TOP+.55,z,g,6);[-1.5,1.5].forEach(o=>cyl(.4,.4,.5,M(0x7a5ea8),x+o,TOP+.3,z,g,10))});
  sofa(g,r.cx,r.z1-2,5,0x6d4aa0,0);box(.9,1,.7,M(0x1a1f30),r.x1-3,TOP+1.8,r.z0+1.8,g);box(.5,.3,.05,glowMat(0xffb36b,.6,.6),r.x1-3,TOP+2.0,r.z0+2.17,g,false);box(1.2,2.4,1,M(0x2b3a66),r.x0+1.4,TOP+1.2,r.z1-3,g);box(.9,1.4,.05,glowMat(0x7ac7ff,.4,.8),r.x0+1.4,TOP+1.5,r.z1-2.47,g,false);plant(g,r.x0+1.4,r.z1-1.4);plant(g,r.x1-1.4,r.z1-1.4)})();
(()=>{const r=R.brd,g=r.grp;makeScreen(r,r.w*.36,3.5,TOP+2.75);const tb=cyl(1,1,.4,M(0x3a2f26,{roughness:.35}),r.cx,TOP+1.1,r.cz,g,40);tb.scale.set(7.5,1,2.6);
  box(r.w*.36+.3,3.8,.25,M(0x0b1020,{emissive:0x4a6fa5,emissiveIntensity:.5}),r.cx,TOP+2.75,r.z1-.5,g,false);
  r.seats=[...Array(12)].map((_,i)=>{const a=i/12*Math.PI*2,s={x:r.cx+Math.cos(a)*8.4,z:r.cz+Math.sin(a)*4.2};s.ang=faceAng(s,r.cx,r.cz);return s});
  r.seats.forEach(s=>chair(g,s));plant(g,r.x0+1.4,r.z1-1.4);plant(g,r.x1-1.4,r.z1-1.4)})();
['mr1','mr2','mr3'].forEach(id=>{const r=R[id],g=r.grp;makeScreen(r,r.w*.62,3.4,TOP+2.75);box(6.4,.18,2.4,DESKT,r.cx,TOP+1.1,r.cz,g);box(.2,1.1,.2,DESKL,r.cx,TOP+.55,r.cz,g);
  box(r.w*.6,2.4,.2,M(0x0b1020,{emissive:0x4a6fa5,emissiveIntensity:.5}),r.cx,TOP+2.8,r.far+r.fdir*.5,g,false);
  const P=[[-2.2,-2],[0,-2],[2.2,-2],[-2.2,2],[0,2],[2.2,2],[-4,0],[4,0]];
  r.seats=P.map(([dx,dz])=>({x:r.cx+dx,z:r.cz+dz}));r.seats.forEach(s=>{s.ang=faceAng(s,r.cx,r.cz);chair(g,s,0x8a7410)});plant(g,r.x0+1.2,r.far+r.fdir*1.2)});
