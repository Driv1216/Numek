const detail=document.querySelector('#direction-detail');
const choices=[...document.querySelectorAll('.choice')];
function choose(id){
 const c=concepts.find(c=>c.id===id)||concepts[0];
 choices.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.id===c.id)));
 detail.innerHTML=`<div class="direction-heading"><div><h2>${c.id.toUpperCase()}. ${c.title}</h2><p>${c.thesis}</p></div><div class="palette" aria-label="Proposed palette">${c.palette.map(p=>`<span class="swatch" style="background:${p}" title="${p}"></span>`).join('')}</div></div><div class="screen-labels"><span>Landing / opening composition study</span><span>Application home (top) / representative result (bottom)</span><a href="styleframe.html?direction=${c.id}" target="_blank">Enlarge study</a></div><div class="stage">${c.svg}</div><div class="type-line">Proposed typography: ${c.type}. Original static style frames; final responsive pages follow review.</div><div class="direction-copy"><div><h3>Complete landing progression</h3><p>${c.landing}</p><h3>Application home</h3><p>${c.home}</p><h3>Representative result</h3><p>${c.results}</p></div><div><h3>Observed influences</h3><p>${c.influence}</p><div class="influence-links">${c.refs.map(r=>`<a href="#ref-${r}">${r} reference</a>`).join('')}</div><h3>Motion language</h3><p>${c.motion}</p><h3>Critical tradeoff</h3><p>${c.risk}</p><details><summary>Responsive and implementation intent</summary><p>${c.mobile}</p><p>${c.build}</p></details></div></div>`;
 const url=new URL(location.href);url.searchParams.set('direction',c.id);history.replaceState(null,'',url);
}
choices.forEach(b=>b.addEventListener('click',()=>choose(b.dataset.id)));
choose(new URLSearchParams(location.search).get('direction')||'a');
const range=document.querySelector('#frame-range'),motionImage=document.querySelector('#motion-image'),frameOutput=document.querySelector('#frame-number'),play=document.querySelector('#play-frames');
let timer=null;
function frame(n){range.value=n;motionImage.src=`motion/lpas/frame-${String(n).padStart(2,'0')}.jpg`;motionImage.alt=`LPAS browser scroll sequence, frame ${Number(n)+1} of 10`;frameOutput.value=`${Number(n)+1} / 10`;}
function stop(){clearInterval(timer);timer=null;play.textContent='Play sequence';}
range.addEventListener('input',()=>{stop();frame(range.value)});
play.addEventListener('click',()=>{if(timer){stop();return}frame(0);play.textContent='Pause sequence';timer=setInterval(()=>{const n=Number(range.value)+1;if(n>9){stop();return}frame(n)},650)});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
