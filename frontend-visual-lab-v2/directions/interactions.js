const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const observer = new IntersectionObserver(items=>items.forEach(item=>{if(item.isIntersecting){item.target.classList.add('visible');observer.unobserve(item.target)}}),{threshold:.08});
document.querySelectorAll('.reveal').forEach(el=>observer.observe(el));
document.querySelectorAll('[data-tab-group]').forEach(group=>{
  const buttons=[...group.querySelectorAll('[role=tab]')];
  const select=button=>{
    buttons.forEach(b=>{b.setAttribute('aria-selected',String(b===button));b.tabIndex=b===button?0:-1});
    const scope=group.closest('[data-product]');
    scope.querySelectorAll('[role=tabpanel]').forEach(p=>p.hidden=p.id!==button.getAttribute('aria-controls'));
  };
  buttons.forEach((button,i)=>{
    button.addEventListener('click',()=>select(button));
    button.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;select(buttons[next]);buttons[next].focus()});
  });
});
if(new URLSearchParams(location.search).get('view')==='result')document.querySelector('[data-result]')?.click();
document.querySelectorAll('[data-focus]').forEach(button=>button.addEventListener('click',()=>{
  const stage=document.querySelector(button.dataset.focus);const active=stage.classList.toggle('focus-mode');button.setAttribute('aria-pressed',String(active));button.querySelector('[data-button-label]')?.replaceChildren(document.createTextNode(active?'Show the full picture':'Follow the finding'));
}));
document.querySelectorAll('[data-method]').forEach(button=>button.addEventListener('click',()=>document.querySelector('#method-dialog').showModal()));
document.querySelector('[data-close-dialog]')?.addEventListener('click',()=>document.querySelector('#method-dialog').close());
document.querySelectorAll('[data-inspect]').forEach(button=>button.addEventListener('click',()=>{
  const target=document.querySelector(button.dataset.inspect);const tab=target.querySelector('[role=tab][data-result]');tab?.click();target.scrollIntoView({behavior:reduce?'instant':'smooth',block:'start'});
}));
document.querySelectorAll('[data-layer-toggle]').forEach(button=>button.addEventListener('click',()=>{const stage=document.querySelector(button.dataset.layerToggle);const flat=stage.classList.toggle('flat');stage.querySelector('.c-flat-plot')?.setAttribute('aria-hidden',String(!flat));button.setAttribute('aria-pressed',String(flat));button.textContent=flat?'See the dimensional study':'Read the distribution';}));
document.querySelectorAll('[data-align]').forEach(button=>button.addEventListener('click',()=>{const active=button.closest('.a-stage').classList.toggle('aligned');button.setAttribute('aria-pressed',String(active));button.setAttribute('aria-label',active?'Separate the evidence layers':'Align the evidence layers')}));
document.querySelectorAll('[data-evidence]').forEach(button=>button.addEventListener('click',()=>{const group=button.closest('[data-evidence-group]');const choice=button.getAttribute('aria-pressed')==='true'?'default':button.dataset.evidence;group.querySelectorAll('[data-evidence]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.evidence===choice)));group.querySelectorAll('[data-excerpt]').forEach(e=>e.hidden=e.dataset.excerpt!==choice);const label=group.querySelector('[data-question-label]');if(label)label.textContent=choice==='why'?'Hide the explanation':'Why does this matter?'}));
// Direction proof: one small user-driven response, no continuous animation in the work area.
if(!reduce){document.querySelectorAll('[data-tilt]').forEach(stage=>{stage.addEventListener('pointermove',e=>{const r=stage.getBoundingClientRect();const x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;stage.style.setProperty('--rx',`${-y*3}deg`);stage.style.setProperty('--ry',`${x*3}deg`)});stage.addEventListener('pointerleave',()=>{stage.style.setProperty('--rx','0deg');stage.style.setProperty('--ry','0deg')})})}
