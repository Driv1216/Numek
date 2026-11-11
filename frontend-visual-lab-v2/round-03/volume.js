import * as THREE from './vendor/three.module.min.js';
export function mount(host,bins,reduced){
 const scene=new THREE.Scene();
 const camera=new THREE.PerspectiveCamera(33,1,.1,100);camera.position.set(10,8,15);camera.lookAt(0,.2,0);
 const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor(0xf5f6f8,0);renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.1;host.append(renderer.domElement);
 scene.add(new THREE.HemisphereLight(0xffffff,0xa6a7cc,2));
 const key=new THREE.DirectionalLight(0xfff5ed,3);key.position.set(-5,10,5);key.castShadow=false;key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-10,right:10,top:10,bottom:-10});key.shadow.bias=-.0005;key.shadow.normalBias=.02;key.shadow.radius=4;scene.add(key);
 const fill=new THREE.DirectionalLight(0xa6bdff,2.5);fill.position.set(4,2,-7);scene.add(fill);
 const rim=new THREE.DirectionalLight(0xffffff,2);rim.position.set(-6,3,-5);scene.add(rim);
 const group=new THREE.Group();group.rotation.y=-.33;group.rotation.z=.03;group.position.set(.2,0,0);scene.add(group);
 const counts=bins.map(b=>b.count);const max=Math.max(...counts);
 const N=160,M=90;
 const geometry=new THREE.PlaneGeometry(10,6,N,M);geometry.rotateX(-Math.PI/2);
 const colors=[],rest=[];const p=geometry.attributes.position;
 const c1=new THREE.Color('#fa6430'),c2=new THREE.Color('#4345d5'),c3=new THREE.Color('#aabcec');
 function height(x,z){const f=(x+5)/10*39;const i=Math.floor(f);const h=THREE.MathUtils.lerp(counts[Math.min(i,39)]||0,counts[Math.min(i+1,39)]||0,f-i)/max;return -.65+h*2.5+Math.sin(z*.65+x*.3)*(.65+h*.65)+Math.pow(z/3,2)*.8;}
 for(let i=0;i<p.count;i++){const x=p.getX(i),z=p.getZ(i);const h=height(x,z);p.setY(i,h);rest.push(x,h,z);const t=(z+3)/6;const color=c1.clone().lerp(c2,Math.pow(t,.75));color.lerp(c3,(x+5)/10*.35);colors.push(color.r,color.g,color.b);}
 geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));geometry.computeVertexNormals();
 const material=new THREE.MeshPhysicalMaterial({vertexColors:true,metalness:.18,roughness:.37,clearcoat:1,clearcoatRoughness:.3,side:THREE.DoubleSide});
 const mesh=new THREE.Mesh(geometry,material);mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);
 // Thin contours expose the actual 40 bins, with a continuous sweep through the distribution.
 const lines=[];
 for(let k=0;k<=40;k++){const x=-5+k/40*10;const points=[];for(let j=0;j<=90;j++){const z=-3+j/90*6;points.push(new THREE.Vector3(x,height(x,z)+.009,z));}const g=new THREE.BufferGeometry().setFromPoints(points);const l=new THREE.Line(g,new THREE.LineBasicMaterial({color:0x32375f,transparent:true,opacity:.42}));l.userData.rest=new Float32Array(l.geometry.attributes.position.array);group.add(l);lines.push(l);}
 for(let k=0;k<=60;k++){const z=-3+k/60*6;const points=[];for(let j=0;j<=160;j++){const x=-5+j/160*10;points.push(new THREE.Vector3(x,height(x,z)+.011,z));}const g=new THREE.BufferGeometry().setFromPoints(points);const l=new THREE.Line(g,new THREE.LineBasicMaterial({color:0xececf9,transparent:true,opacity:.24}));l.userData.rest=new Float32Array(l.geometry.attributes.position.array);group.add(l);lines.push(l);}
 // A soft receiving surface anchors the data form without introducing unrelated scenery.
 const shadowCanvas=document.createElement('canvas');shadowCanvas.width=shadowCanvas.height=256;const ctx=shadowCanvas.getContext('2d');const gradient=ctx.createRadialGradient(128,128,5,128,128,128);gradient.addColorStop(0,'rgba(42,53,90,.18)');gradient.addColorStop(.5,'rgba(42,53,90,.08)');gradient.addColorStop(1,'rgba(42,53,90,0)');ctx.fillStyle=gradient;ctx.fillRect(0,0,256,256);const shadowTexture=new THREE.CanvasTexture(shadowCanvas);const floor=new THREE.Mesh(new THREE.PlaneGeometry(17,12),new THREE.MeshBasicMaterial({map:shadowTexture,transparent:true,depthWrite:false}));floor.rotation.x=-Math.PI/2;floor.position.y=-1.75;scene.add(floor);
 let pointerX=0,pointerY=0,targetFlat=0,flat=0,visible=true,frame,lastFlat=-1,lastY=-10,lastX=-10;
 const updateSize=()=>{const r=host.getBoundingClientRect();renderer.setSize(r.width,r.height,false);camera.aspect=r.width/r.height;camera.updateProjectionMatrix();lastX=-10;};new ResizeObserver(updateSize).observe(host);updateSize();
 if(!reduced){host.addEventListener('pointermove',e=>{const r=host.getBoundingClientRect();pointerX=((e.clientX-r.left)/r.width-.5)*.14;pointerY=((e.clientY-r.top)/r.height-.5)*.08});host.addEventListener('pointerleave',()=>{pointerX=pointerY=0});}
 const toggle=document.querySelector('[data-unfold]');toggle?.addEventListener('click',()=>{targetFlat=targetFlat?0:1;toggle.setAttribute('aria-pressed',String(!!targetFlat));toggle.innerHTML=targetFlat?'<span>◫</span> Return to the data form':'<span>⊞</span> Unfold the distribution';document.querySelector('.flat-inset').hidden=!targetFlat;});
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;},{rootMargin:'100px'}).observe(host);
 function draw(){frame=requestAnimationFrame(draw);if(!visible)return;flat=reduced?targetFlat:THREE.MathUtils.lerp(flat,targetFlat,.065);group.rotation.y=reduced?-.33:THREE.MathUtils.lerp(group.rotation.y,-.33+pointerX,.045);group.rotation.x=reduced?0:THREE.MathUtils.lerp(group.rotation.x,pointerY,.045);if(Math.abs(flat-lastFlat)<.00015&&Math.abs(group.rotation.y-lastY)<.00015&&Math.abs(group.rotation.x-lastX)<.00015)return;if(Math.abs(flat-lastFlat)>.00015){for(let i=0;i<p.count;i++)p.setY(i,rest[i*3+1]*(1-flat));p.needsUpdate=true;geometry.computeVertexNormals();for(const line of lines){const a=line.geometry.attributes.position;const r=line.userData.rest;for(let i=0;i<a.count;i++)a.setY(i,r[i*3+1]*(1-flat));a.needsUpdate=true;}}group.scale.setScalar(1-flat*.12);group.position.x=.2+flat*2.7;group.position.y=-flat*.4;renderer.render(scene,camera);lastFlat=flat;lastY=group.rotation.y;lastX=group.rotation.x;}draw();
 host.dataset.rendered='true';
 window.addEventListener('pagehide',()=>{cancelAnimationFrame(frame);renderer.dispose();});
}
