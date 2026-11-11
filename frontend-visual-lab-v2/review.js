const el = (tag, attrs = {}, children = []) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'text') node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const child of children) node.append(child);
  return node;
};
const p = (value, attrs = {}) => el('p', { ...attrs, text: value });
const link = (label, href, attrs = {}) => el('a', { href, text: label, ...attrs });
if (new URLSearchParams(location.search).has('overview')) document.body.classList.add('compact');

try {
  const [directions, research, drawings] = await Promise.all([
    fetch('research/directions.json').then(r => { if (!r.ok) throw Error('Directions could not load'); return r.json(); }),
    fetch('research/research.json').then(r => { if (!r.ok) throw Error('Research could not load'); return r.json(); }),
    fetch('research/studies.json').then(r => { if (!r.ok) throw Error('Studies could not load'); return r.json(); })
  ]);
  const study = (key, description) => {
    const svg = new DOMParser().parseFromString(drawings[key], 'image/svg+xml').documentElement;
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', description);
    return svg;
  };
  const refs = new Map(research.references.map(ref => [ref.id, ref]));
  const overview = document.querySelector('#overview');
  overview.replaceChildren();
  for (const d of directions) {
    const card = el('a', { class: 'overview-card', href: `#direction-${d.id}` });
    card.append(study(`${d.id}-landing`, `${d.title} — original landing composition study`));
    card.append(el('div', { class: 'overview-label' }, [el('span', { text: d.id }), el('div', {}, [el('h2', { text: d.title }), p(d.short)])]));
    overview.append(card);

    const title = el('div', { class: 'direction-title' }, [el('span', { class: 'direction-number', style: `background:${d.color}`, text: d.id }), el('div', {}, [el('h3', { text: d.title }), p(d.signature)])]);
    const images = el('div', { class: 'study-stack' });
    for (const [screen, label] of [['landing', 'Landing composition'], ['home', 'Application home'], ['results', 'Analysis results']]) {
      const path = `research/studies/${d.id}-${screen}.svg`;
      images.append(el('a', { href: path, target: '_blank', rel: 'noopener', 'aria-label': `Open full-size ${d.title} ${label}` }, [
        study(`${d.id}-${screen}`, `${d.title}: ${label}, static direction study`),
        el('div', { class: 'study-caption' }, [el('span', { text: label }), el('span', { text: 'Static study / enlarge' })])
      ]));
    }
    const palette = el('div', { class: 'palette', 'aria-label': 'Proposed colors' });
    for (const [name, color] of d.palette) palette.append(el('span', { class: 'swatch', title: `${name} ${color}`, style: `background:${color}` }));
    const descriptions = el('dl');
    for (const [key, label] of [['landing', 'Landing story'], ['home', 'Application home'], ['results', 'Results'], ['motion', 'Proposed motion']]) descriptions.append(el('dt', { text: label }), el('dd', { text: d[key] }));
    const type = el('details', {}, [el('summary', { text: 'Typography and practical risk' }), p(d.type), p(d.risk)]);
    const influences = el('div', { class: 'source-links' }, [el('span', { text: 'Inspected influences: ' })]);
    for (const id of d.influences) influences.append(link(refs.get(id).title, `#ref-${id}`));
    const copy = el('div', { class: 'direction-copy' }, [p(d.premise), palette, p(d.palette.map(([name, color]) => `${name} ${color}`).join(' / '), { class: 'palette-label' }), descriptions, type, influences]);
    document.querySelector('#direction-list').append(el('article', { class: 'direction', id: `direction-${d.id}` }, [title, el('div', { class: 'direction-body' }, [images, copy])]));
    document.querySelector('#compare-body').append(el('tr', {}, [el('td', {}, [link(`${d.id} / ${d.short}`, `#direction-${d.id}`)]), el('td', { text: d.strength }), el('td', { text: d.risk })]));
  }
  overview.append(el('div', { class: 'overview-explainer' }, [p('The same product. Five different ways of seeing it.'), el('span', { text: 'Original composition proposals, not final prototypes. Each direction includes a landing, home and result study. Review all five before implementation.' })]));

  for (const ref of research.references) {
    const image = el('img', { src: `research/screenshots/${ref.image}`, alt: `${ref.title}: genuine opening viewport captured in browser`, width: 1280, height: 720, loading: 'lazy' });
    const label = el('span', { class: 'state-label', text: 'Captured state 1' });
    const actions = el('div', { class: 'reference-actions' }, [link('Original site', ref.url, { target: '_blank', rel: 'noopener' })]);
    if (ref.caseStudy) actions.append(link('Creator / award page', ref.caseStudy, { target: '_blank', rel: 'noopener' }));
    if (ref.after) {
      const toggle = el('button', { class: 'state-toggle', type: 'button', text: 'Show second state', 'aria-label': `Show second captured state for ${ref.title}`, 'aria-pressed': 'false' });
      let second = false;
      toggle.addEventListener('click', () => {
        second = !second;
        image.src = `research/screenshots/${second ? ref.after : ref.image}`;
        image.alt = `${ref.title}: genuine ${second ? 'second' : 'opening'} browser state`;
        label.textContent = second ? ref.action : 'Captured state 1';
        toggle.textContent = second ? 'Show first state' : 'Show second state';
        toggle.setAttribute('aria-pressed', String(second));
      });
      actions.append(toggle);
    }
    const observation = p(ref.observation);
    const more = el('details', {}, [el('summary', { text: 'Motion, transfer and inspected scope' }), p(`Motion: ${ref.motion}`), p(`For NUMEK: ${ref.transfer}`), p(`Scope: ${ref.status}`)]);
    document.querySelector('#reference-list').append(el('article', { class: 'reference', id: `ref-${ref.id}` }, [el('div', { class: 'frame' }, [image, label]), el('div', { class: 'reference-content' }, [el('h3', { text: ref.title }), p(ref.creator, { class: 'creator' }), observation, more, actions])]));
  }
  for (const note of research.accessNotes) document.querySelector('#access-notes').append(el('li', { text: note }));
} catch (error) {
  document.querySelector('#overview').replaceChildren(p(`${error.message}. Serve this folder over HTTP using the README instructions.`, { class: 'error', role: 'alert' }));
}
