import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { checks, CHECK_LABELS } from '../../shared/engine';
import { prefersReduced } from '../../shared/motion';

/*
 * The audit engine as an exploded line drawing: one layer per real check, in
 * execution order. Layers whose checks produced Adult's findings are drawn in
 * the signal colour. `explode` (0 to 1) separates them; labels track each layer.
 */
export const FINDING_CHECKS = new Set(['label_conflicts', 'classification_target', 'numeric_outliers', 'target_leakage']);

export function Exploded({
  explode,
  height,
  labels = true,
  spin = true,
  focus,
}: {
  explode: number;
  height: number | string;
  labels?: boolean;
  spin?: boolean;
  focus?: string | null;
}) {
  const host = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const tagRefs = useRef<(HTMLDivElement | null)[]>([]);
  const ex = useRef(explode);
  ex.current = explode;
  const fo = useRef(focus);
  fo.current = focus;

  useEffect(() => {
    const el = host.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    stage.current!.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-5, 5, 5, -5, 0.1, 100);
    camera.position.set(7, 6.5, 7);
    camera.lookAt(0, 0, 0);
    const group = new THREE.Group();
    group.rotation.z = labels ? -0.12 : -0.5;
    scene.add(group);

    const bone = new THREE.Color('#e9e6e0');
    const red = new THREE.Color('#ff4b3e');
    const layers: { g: THREE.Group; mats: THREE.LineBasicMaterial[]; r: number; id: string }[] = [];
    checks.forEach((c, i) => {
      const g = new THREE.Group();
      const hot = FINDING_CHECKS.has(c.id);
      const r = 1.05 + Math.abs(Math.sin(i * 1.7)) * 0.65 + (i % 3 === 0 ? 0.25 : 0);
      const mat = new THREE.LineBasicMaterial({ color: hot ? red : bone, transparent: true, opacity: hot ? 1 : 0.75 });
      const mat2 = new THREE.LineBasicMaterial({ color: hot ? red : bone, transparent: true, opacity: hot ? 0.55 : 0.32 });
      // rims (top and bottom), inner ring and radial ticks
      const ring = (rad: number, y: number, m: THREE.LineBasicMaterial) => {
        const pts: THREE.Vector3[] = [];
        for (let k = 0; k <= 96; k++) {
          const a = (k / 96) * Math.PI * 2;
          pts.push(new THREE.Vector3(Math.cos(a) * rad, y, Math.sin(a) * rad));
        }
        g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), m));
      };
      const h = 0.12 + (i % 4) * 0.04;
      ring(r, 0, mat);
      ring(r, h, mat);
      ring(r * 0.62, h, mat2);
      if (i % 2 === 0) ring(r * 0.35, h, mat2);
      const ticks: THREE.Vector3[] = [];
      const n = 24 + (i % 3) * 12;
      for (let k = 0; k < n; k++) {
        const a = (k / n) * Math.PI * 2;
        ticks.push(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r), new THREE.Vector3(Math.cos(a) * r, h, Math.sin(a) * r));
        if (k % 3 === 0) ticks.push(new THREE.Vector3(Math.cos(a) * r * 0.62, h, Math.sin(a) * r * 0.62), new THREE.Vector3(Math.cos(a) * r * 0.92, h, Math.sin(a) * r * 0.92));
      }
      g.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(ticks), mat2));
      group.add(g);
      layers.push({ g, mats: [mat, mat2], r, id: c.id });
    });
    // central spindle
    const spindle = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, -6, 0), new THREE.Vector3(0, 6, 0)]),
      new THREE.LineDashedMaterial({ color: '#8d8a84', dashSize: 0.12, gapSize: 0.08 }),
    );
    spindle.computeLineDistances();
    group.add(spindle);

    let W = 1;
    let H = 1;
    const resize = () => {
      W = el.clientWidth;
      H = el.clientHeight;
      renderer.setSize(W, H);
      const aspect = W / H;
      const s = 4.6;
      camera.left = -s * aspect;
      camera.right = s * aspect;
      camera.top = s;
      camera.bottom = -s;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    const reduced = prefersReduced();
    let cur = ex.current;
    let raf = 0;
    const tick = () => {
      cur += (ex.current - cur) * 0.08;
      if (spin && !reduced) group.rotation.y += 0.0025;
      const gap = 0.22 + cur * 0.5;
      const n = layers.length;
      layers.forEach((l, i) => {
        l.g.position.y = (i - (n - 1) / 2) * gap;
        const dim = fo.current && fo.current !== l.id;
        l.mats[0].opacity = dim ? 0.18 : FINDING_CHECKS.has(l.id) ? 1 : 0.75;
        l.mats[1].opacity = dim ? 0.08 : FINDING_CHECKS.has(l.id) ? 0.55 : 0.32;
      });
      group.updateMatrixWorld();
      renderer.render(scene, camera);
      if (labels && svg.current) {
        const lines = svg.current.querySelectorAll('line');
        layers.forEach((l, i) => {
          const left = i % 2 === 0;
          const p = new THREE.Vector3(left ? -l.r : l.r, 0.08, 0).applyMatrix4(l.g.matrixWorld).project(camera);
          const x = (p.x * 0.5 + 0.5) * W;
          const y = (-p.y * 0.5 + 0.5) * H;
          const tag = tagRefs.current[i];
          if (!tag) return;
          const rank = Math.floor((layers.length - 1 - i) / 2);
          const ty = 70 + rank * ((H - 120) / 6) + (left ? 22 : 0);
          const tx = left ? 16 : W - 16;
          tag.style.transform = `translate(${left ? tx : tx - tag.offsetWidth}px, ${ty - 9}px)`;
          const ln = lines[i];
          ln.setAttribute('x1', String(left ? tx + tag.offsetWidth + 6 : tx - tag.offsetWidth - 6));
          ln.setAttribute('y1', String(ty));
          ln.setAttribute('x2', String(x));
          ln.setAttribute('y2', String(y));
          ln.style.opacity = String(Math.min(1, cur * 1.6) * (fo.current && fo.current !== l.id ? 0.2 : 1));
          tag.style.opacity = String(Math.min(1, cur * 1.6) * (fo.current && fo.current !== l.id ? 0.35 : 1));
        });
      }
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [labels, spin]);

  return (
    <div className="en-exploded" ref={host} style={{ height }} role="img" aria-label="The twelve DataTrust checks as layers of an exploded drawing">
      <div ref={stage} className="en-stage" />
      {labels && (
        <>
          <svg ref={svg} className="en-leaders" aria-hidden="true">
            {checks.map((c) => (
              <line key={c.id} className={FINDING_CHECKS.has(c.id) ? 'hot' : ''} />
            ))}
          </svg>
          {checks.map((c, i) => (
            <div key={c.id} className={`en-tag${FINDING_CHECKS.has(c.id) ? ' is-hot' : ''}`} ref={(n) => { tagRefs.current[i] = n; }}>
              <b>{CHECK_LABELS[c.id].toLowerCase()}</b>
              <span>{c.method}</span>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
