import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import cloudAsset from '../../shared/adult-cloud.json';
import { useReducedMotion } from '../../shared/hooks';

/*
 * The Adult dataset plotted as it is: every one of 48,842 rows is a point at
 * (age, hours_per_week, education_years). Discrete values stack into strands,
 * which is why the cloud reads as a crystal rather than a blur.
 */

export interface Row {
  age: number;
  hours: number;
  edu: number;
  label: 0 | 1;
}

let decoded: Row[] | null = null;
export function adultRows(): Row[] {
  if (decoded) return decoded;
  const bin = atob((cloudAsset as { data: string }).data);
  const rows: Row[] = [];
  for (let i = 0; i < bin.length; i += 4) {
    rows.push({ age: bin.charCodeAt(i), hours: bin.charCodeAt(i + 1), edu: bin.charCodeAt(i + 2), label: bin.charCodeAt(i + 3) as 0 | 1 });
  }
  decoded = rows;
  return rows;
}

export const toSpace = (age: number, hours: number, edu: number) =>
  new THREE.Vector3(((age - 17) / 73 - 0.5) * 2.6, ((hours - 1) / 98 - 0.5) * 2, ((edu - 1) / 15 - 0.5) * 1.6);

export interface Track {
  id: string;
  label: string;
  detail: string;
  /** a single point, or the corners of a region */
  at: THREE.Vector3 | THREE.Box3;
  tone?: 'ink' | 'blue';
}

export function Cloud({
  tracks,
  height,
  focus,
  spin = true,
}: {
  tracks: Track[];
  height: number | string;
  /** dims every point outside the predicate */
  focus?: (r: Row) => boolean;
  spin?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const boxes = useRef<Record<string, HTMLDivElement | null>>({});
  const reduced = useReducedMotion();
  const tracksRef = useRef(tracks);
  tracksRef.current = tracks;

  useEffect(() => {
    const el = host.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.prepend(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50);
    camera.position.set(0, 0.3, 5.1);
    camera.lookAt(0, 0, 0);
    const group = new THREE.Group();
    scene.add(group);

    const rows = adultRows();
    const pos = new Float32Array(rows.length * 3);
    const col = new Float32Array(rows.length * 3);
    let seed = 11;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647 - 0.5);
    const ink = new THREE.Color('#141414');
    const blue = new THREE.Color('#2433ff');
    const faint = new THREE.Color('#d7d7d3');
    rows.forEach((r, i) => {
      const v = toSpace(r.age + rnd() * 0.55, r.hours + rnd() * 0.55, r.edu + rnd() * 0.3);
      pos.set([v.x, v.y, v.z], i * 3);
      const c = focus && !focus(r) ? faint : r.label ? blue : ink;
      col.set([c.r, c.g, c.b], i * 3);
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
    const mat = new THREE.PointsMaterial({ size: 0.016, vertexColors: true, transparent: true, opacity: 0.8, sizeAttenuation: true });
    group.add(new THREE.Points(geo, mat));

    // Axis hairlines give the cloud a measured frame.
    const axisMat = new THREE.LineBasicMaterial({ color: '#9a9a96', transparent: true, opacity: 0.6 });
    const lo = toSpace(17, 1, 1);
    const hi = toSpace(90, 99, 16);
    const axes = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(lo.x, lo.y, lo.z), new THREE.Vector3(hi.x, lo.y, lo.z),
      new THREE.Vector3(lo.x, lo.y, lo.z), new THREE.Vector3(lo.x, hi.y, lo.z),
      new THREE.Vector3(lo.x, lo.y, lo.z), new THREE.Vector3(lo.x, lo.y, hi.z),
    ]);
    group.add(new THREE.LineSegments(axes, axisMat));

    group.rotation.set(0.12, -0.55, 0);
    let drag: { x: number; ry: number } | null = null;
    const down = (e: PointerEvent) => (drag = { x: e.clientX, ry: group.rotation.y });
    const move = (e: PointerEvent) => {
      if (drag) group.rotation.y = drag.ry + (e.clientX - drag.x) * 0.006;
    };
    const up = () => (drag = null);
    el.addEventListener('pointerdown', down);
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);

    let W = 1;
    let H = 1;
    const resize = () => {
      W = el.clientWidth;
      H = el.clientHeight;
      renderer.setSize(W, H);
      camera.aspect = W / H;
      // Pull back on tall viewports so the whole cloud stays in frame.
      camera.position.z = camera.aspect < 1.1 ? 5.1 * Math.min(2.2, 1.25 / camera.aspect) : 5.1;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    const project = (v: THREE.Vector3) => {
      const p = v.clone().applyMatrix4(group.matrixWorld).project(camera);
      return { x: (p.x * 0.5 + 0.5) * W, y: (-p.y * 0.5 + 0.5) * H };
    };

    let raf = 0;
    const tick = () => {
      if (spin && !reduced && !drag) group.rotation.y += 0.0011;
      group.updateMatrixWorld();
      renderer.render(scene, camera);
      for (const t of tracksRef.current) {
        const node = boxes.current[t.id];
        if (!node) continue;
        let x0: number, y0: number, x1: number, y1: number;
        if (t.at instanceof THREE.Box3) {
          const { min, max } = t.at;
          const pts = [0, 1, 2, 3, 4, 5, 6, 7].map((i) =>
            project(new THREE.Vector3(i & 1 ? max.x : min.x, i & 2 ? max.y : min.y, i & 4 ? max.z : min.z)),
          );
          x0 = Math.min(...pts.map((p) => p.x));
          x1 = Math.max(...pts.map((p) => p.x));
          y0 = Math.min(...pts.map((p) => p.y));
          y1 = Math.max(...pts.map((p) => p.y));
        } else {
          const p = project(t.at);
          x0 = p.x - 15;
          x1 = p.x + 15;
          y0 = p.y - 15;
          y1 = p.y + 15;
        }
        node.style.transform = `translate(${x0}px, ${y0}px)`;
        node.style.width = `${x1 - x0}px`;
        node.style.height = `${y1 - y0}px`;
      }
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
  }, [focus, spin, reduced]);

  return (
    <div className="tr-cloud" ref={host} style={{ height }}>
      {tracks.map((t) => (
        <div key={t.id} className={`tr-track is-${t.tone ?? 'blue'}`} ref={(n) => { boxes.current[t.id] = n; }}>
          <span className="tr-track-tag">
            <b>{t.label}</b>
            <span>{t.detail}</span>
          </span>
        </div>
      ))}
    </div>
  );
}
