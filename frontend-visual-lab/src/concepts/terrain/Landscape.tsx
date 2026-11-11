import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { grid } from '../../shared/distributions';
import { prefersReduced } from '../../shared/motion';

/*
 * The real age × hours density of all 48,842 Adult rows as a landscape: height
 * is the square root of rows per cell, lightly smoothed. Fog and a pale sky
 * keep it calm. Annotation pins sit on real cells and track the camera.
 */
export interface Pin {
  id: string;
  age: number;
  hours: number;
  title: string;
  detail: string;
  hot?: boolean;
  side?: 'l' | 'r';
}

const A = grid.counts.length;
const B = grid.counts[0].length;
const max = Math.max(...grid.counts.flat());
const W = 16;
const D = 11;
const toX = (age: number) => ((age - grid.age_edges[0]) / (grid.age_edges[A] - grid.age_edges[0]) - 0.5) * W;
const toZ = (hr: number) => -((hr - grid.hour_edges[0]) / (grid.hour_edges[B] - grid.hour_edges[0]) - 0.5) * D;

function heightAt(age: number, hr: number) {
  const fa = ((age - grid.age_edges[0]) / (grid.age_edges[A] - grid.age_edges[0])) * A - 0.5;
  const fb = ((hr - grid.hour_edges[0]) / (grid.hour_edges[B] - grid.hour_edges[0])) * B - 0.5;
  let s = 0;
  let w = 0;
  for (let i = Math.floor(fa) - 2; i <= Math.ceil(fa) + 2; i++)
    for (let j = Math.floor(fb) - 2; j <= Math.ceil(fb) + 2; j++) {
      if (i < 0 || j < 0 || i >= A || j >= B) continue;
      const d2 = (i - fa) ** 2 + (j - fb) ** 2;
      const k = Math.exp(-d2 / 0.7);
      s += Math.pow(grid.counts[i][j] / max, 0.55) * k;
      w += k;
    }
  return w ? (s / w) * 4.6 : 0;
}

export function Landscape({ height, pins = [], drift = 0, interactive = false }: { height: number | string; pins?: Pin[]; drift?: number; interactive?: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const pinRefs = useRef<(HTMLDivElement | null)[]>([]);
  const driftRef = useRef(drift);
  driftRef.current = drift;
  const pinsRef = useRef(pins);
  pinsRef.current = pins;

  useEffect(() => {
    const el = host.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    stage.current!.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog('#e3e9ef', 8, 24);
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);

    const SEG_X = 150;
    const SEG_Z = 100;
    const geo = new THREE.PlaneGeometry(W * 1.6, D * 1.9, SEG_X, SEG_Z);
    geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position as THREE.BufferAttribute;
    const colors = new Float32Array(pos.count * 3);
    const lo = new THREE.Color('#7f95ab');
    const hi = new THREE.Color('#ffffff');
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const z = pos.getZ(i);
      const age = (x / W + 0.5) * (grid.age_edges[A] - grid.age_edges[0]) + grid.age_edges[0];
      const hr = (-z / D + 0.5) * (grid.hour_edges[B] - grid.hour_edges[0]) + grid.hour_edges[0];
      const inside = age >= grid.age_edges[0] && age <= grid.age_edges[A] && hr >= grid.hour_edges[0] && hr <= grid.hour_edges[B];
      const h = inside ? heightAt(age, hr) : 0;
      // gentle ground noise outside the data so the horizon stays natural
      const noise = Math.sin(x * 0.9) * Math.cos(z * 1.1) * 0.06;
      pos.setY(i, h + noise);
      const c = lo.clone().lerp(hi, Math.min(1, Math.pow(h / 3.2, 0.7) + 0.08));
      colors.set([c.r, c.g, c.b], i * 3);
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geo.computeVertexNormals();
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, metalness: 0, flatShading: false }));
    scene.add(mesh);

    // Isolines of row density (marching squares over the same height field).
    const segs: number[] = [];
    const NX = 120;
    const NZ = 80;
    const hs: number[][] = [];
    for (let i = 0; i <= NX; i++) {
      hs[i] = [];
      for (let j = 0; j <= NZ; j++) {
        const age = grid.age_edges[0] + (i / NX) * (grid.age_edges[A] - grid.age_edges[0]);
        const hr = grid.hour_edges[0] + (j / NZ) * (grid.hour_edges[B] - grid.hour_edges[0]);
        hs[i][j] = heightAt(age, hr);
      }
    }
    const P = (i: number, j: number) => [((i / NX) - 0.5) * W, -((j / NZ) - 0.5) * D];
    for (let lv = 0.25; lv < 4.6; lv += 0.32) {
      for (let i = 0; i < NX; i++)
        for (let j = 0; j < NZ; j++) {
          const c = [hs[i][j], hs[i + 1][j], hs[i + 1][j + 1], hs[i][j + 1]];
          const corners = [P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1)];
          const pts: number[][] = [];
          for (let e = 0; e < 4; e++) {
            const a = c[e];
            const b = c[(e + 1) % 4];
            if ((a < lv) !== (b < lv)) {
              const t = (lv - a) / (b - a);
              const p0 = corners[e];
              const p1 = corners[(e + 1) % 4];
              pts.push([p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t]);
            }
          }
          if (pts.length >= 2) segs.push(pts[0][0], lv + 0.02, pts[0][1], pts[1][0], lv + 0.02, pts[1][1]);
          if (pts.length === 4) segs.push(pts[2][0], lv + 0.02, pts[2][1], pts[3][0], lv + 0.02, pts[3][1]);
        }
    }
    const iso = new THREE.BufferGeometry();
    iso.setAttribute('position', new THREE.Float32BufferAttribute(segs, 3));
    scene.add(new THREE.LineSegments(iso, new THREE.LineBasicMaterial({ color: '#4f6680', transparent: true, opacity: 0.35 })));

    scene.add(new THREE.HemisphereLight('#f4f8ff', '#8ea3b8', 1.6));
    const sun = new THREE.DirectionalLight('#fff6ea', 2.4);
    sun.position.set(-6, 7, 4);
    scene.add(sun);

    let Wd = 1;
    let Hd = 1;
    const resize = () => {
      Wd = el.clientWidth;
      Hd = el.clientHeight;
      renderer.setSize(Wd, Hd);
      camera.aspect = Wd / Hd;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    let drag: { x: number; a: number } | null = null;
    let yaw = 0;
    const down = (e: PointerEvent) => (drag = { x: e.clientX, a: yaw });
    const move = (e: PointerEvent) => {
      if (drag) yaw = drag.a + (e.clientX - drag.x) * 0.004;
    };
    const up = () => (drag = null);
    if (interactive) {
      el.addEventListener('pointerdown', down);
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    }

    const reduced = prefersReduced();
    let t = 0;
    let raf = 0;
    const tick = () => {
      if (!reduced) t += 0.0015;
      const d = driftRef.current;
      const ang = -1.05 + Math.sin(t) * 0.1 + yaw + d * 0.9;
      const r = 14 - d * 3;
      camera.position.set(Math.sin(ang) * r, 3.6 + d * 2.2, Math.cos(ang) * r);
      camera.lookAt(0.6, 1.4, 0.2);
      renderer.render(scene, camera);
      pinsRef.current.forEach((p, i) => {
        const node = pinRefs.current[i];
        if (!node) return;
        const v = new THREE.Vector3(toX(p.age), heightAt(p.age, p.hours) + 0.05, toZ(p.hours)).project(camera);
        node.style.transform = `translate(${(v.x * 0.5 + 0.5) * Wd}px, ${(-v.y * 0.5 + 0.5) * Hd}px)`;
        node.style.opacity = v.z < 1 ? '1' : '0';
      });
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      el.removeEventListener('pointerdown', down);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      renderer.dispose();
      geo.dispose();
      renderer.domElement.remove();
    };
  }, [interactive]);

  return (
    <div className={`tn-land${interactive ? ' is-int' : ''}`} ref={host} style={{ height }} role="img" aria-label="Landscape of Adult rows by age and hours per week">
      <div ref={stage} className="tn-stage" />
      {pins.map((p, i) => (
        <div key={p.id} className={`tn-pin${p.hot ? ' is-hot' : ''}${p.side === 'l' ? ' is-l' : ''}`} ref={(n) => { pinRefs.current[i] = n; }}>
          <i />
          <span>
            <b>{p.title}</b>
            {p.detail}
          </span>
        </div>
      ))}
    </div>
  );
}

export function peakHigh() {
  let best = { a: 0, b: 0, v: 0 };
  grid.high.forEach((row, a) => row.forEach((v, b) => v > best.v && (best = { a, b, v })));
  return {
    age: (grid.age_edges[best.a] + grid.age_edges[best.a + 1]) / 2,
    hours: (grid.hour_edges[best.b] + grid.hour_edges[best.b + 1]) / 2,
    ageLabel: `${grid.age_edges[best.a]}–${grid.age_edges[best.a + 1] - 1}`,
    hourLabel: `${grid.hour_edges[best.b]}–${grid.hour_edges[best.b + 1] - 1}`,
    count: best.v,
  };
}
