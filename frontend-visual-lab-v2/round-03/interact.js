import {rows,bins} from './fixture.js';
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const app=document.querySelector('.workspace');
const screen=name=>{app.querySelectorAll('[data-panel]').forEach(p=>p.hidden=p.dataset.panel!==name);app.querySelectorAll('[data-screen]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.screen===name)))};
app.querySelectorAll('[data-screen]').forEach(b=>b.addEventListener('click',()=>screen(b.dataset.screen)));
app.querySelector('[data-open-finding]')?.addEventListener('click',()=>screen('finding'));
if(new URLSearchParams(location.search).get('view')==='finding')screen('finding');
document.querySelectorAll('[data-method]').forEach(b=>b.addEventListener('click',()=>document.querySelector('#methods').showModal()));
document.querySelector('[data-close]')?.addEventListener('click',()=>document.querySelector('#methods').close());
let traceRow=0;
document.querySelector('[data-next-row]')?.addEventListener('click',()=>{traceRow=(traceRow+1)%rows.length;const [r,a,b,t]=rows[traceRow];for(const [key,value] of [['a',a],['b',b],['total',t],['row',r],['equation',`${a} + ${b} = ${t}`]])document.querySelector(`[data-trace-${key}]`).textContent=value;const scene=document.querySelector('.trace-scene');if(!reduced)scene.animate([{opacity:.5,transform:'translateY(8px)'},{opacity:1,transform:'none'}],{duration:550,easing:'cubic-bezier(.2,.8,.2,1)'});});
let kineticRow=0;
document.querySelector('[data-next-kinetic]')?.addEventListener('click',()=>{kineticRow=(kineticRow+1)%rows.length;const [r,a,b,t]=rows[kineticRow];for(const [key,value] of [['a',a],['b',b],['total',t]]){const el=document.querySelector(`[data-kinetic-${key}]`);el.textContent=value;if(!reduced)el.animate([{transform:'translateY(40px)',opacity:0},{transform:'none',opacity:1}],{duration:600,easing:'cubic-bezier(.2,.8,.2,1)'});}document.querySelector('[data-kinetic-row]').textContent=`Parsed row ${r} / Bike Sharing`;});
let lensRow=0;
const lens=document.querySelector('[data-lens]');
document.querySelector('[data-lens-next]')?.addEventListener('click',()=>{lensRow=(lensRow+1)%rows.length;const [r,a,b,t]=rows[lensRow];lens.querySelector('.lens-kicker').textContent=`Source evidence / row ${r}`;lens.querySelector('strong').innerHTML=`${a} + ${b}<br><i>= ${t}</i>`;if(!reduced)lens.animate([{filter:'blur(4px)',transform:'rotate(-8deg) scale(.96)'},{filter:'blur(0px)',transform:'rotate(-13deg) scale(1)'}],{duration:700,easing:'cubic-bezier(.2,.8,.2,1)'});});
if(lens&&!reduced){const region=document.querySelector('.evidence-landscape');region.addEventListener('pointermove',e=>{if(e.pointerType==='touch')return;const r=region.getBoundingClientRect();const x=((e.clientX-r.left)/r.width-.5)*65;const y=((e.clientY-r.top)/r.height-.5)*30;lens.style.transform=`translate(${x}px,${y}px) rotate(-13deg)`});region.addEventListener('pointerleave',()=>lens.style.transform='rotate(-13deg)');}
document.querySelector('[data-atlas-flat]')?.addEventListener('click',e=>{const button=e.currentTarget;const active=document.querySelector('[data-atlas]').classList.toggle('aligned');button.setAttribute('aria-pressed',String(active));button.innerHTML=active?'Explore the panorama <span>◫</span>':'Bring it into focus <span>⊞</span>';});
const scene=document.querySelector('[data-three]');
if(scene){import('./volume.js').then(m=>m.mount(scene,bins,reduced)).catch(err=>{scene.innerHTML='<div class="volume-fallback">'+document.querySelector('.flat-inset').innerHTML+'</div>';console.error('Data form unavailable:',err);});}
