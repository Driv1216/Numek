import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { run, SUB_LABELS, SUB_ORDER } from '../../shared/engine';
import { prefersReduced } from '../../shared/motion';

/*
 * Five glass plates, one per transparent sub-score, stacked like a specimen.
 * Each plate's length is its real value; the critical plate (target balance,
 * 47.86) is visibly short and tinted. Callouts track the plates in 3D.
 */
export function GlassStack({ height = 620, labels = true, scrollSpin = 0 }: { height?: number | string; labels?: boolean; scrollSpin?: number }) {
  const host = useRef<HTMLDivElement>(null);
  const tags = useRef<(HTMLDivElement | null)[]>([]);
  const spinRef = useRef(scrollSpin);
  spinRef.current = scrollSpin;

  useEffect(() => {
    const el = host.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.prepend(renderer.domElement);
    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
    camera.position.set(4.6, 3.1, 6.4);
    camera.lookAt(0, 0.1, 0);

    const group = new THREE.Group();
    scene.add(group);
    const plates: { mesh: THREE.Mesh; anchor: THREE.Vector3 }[] = [];
    SUB_ORDER.forEach((k, i) => {
      const v = run.sub[k];
      const len = 0.6 + (v / 100) * 2.6;
      const critical = v < 50;
      const geo = new RoundedBoxGeometry(len, 0.16, 1.5, 4, 0.05);
      const mat = new THREE.MeshPhysicalMaterial({
        color: critical ? '#ffc98a' : '#d9e6ff',
        metalness: 0,
        roughness: 0.08,
        transmission: 1,
        thickness: 0.8,
        ior: 1.45,
        clearcoat: 1,
        clearcoatRoughness: 0.06,
        attenuationColor: new THREE.Color(critical ? '#ff9a3d' : '#7fa4ff'),
        attenuationDistance: 1.6,
        transparent: true,
      });
      const mesh = new THREE.Mesh(geo, mat);
      const y = 0.9 - i * 0.42;
      mesh.position.set(-1.6 + len / 2, y, 0);
      group.add(mesh);
      const edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(len, 0.16, 1.5)),
        new THREE.LineBasicMaterial({ color: critical ? '#ffb36b' : '#ffffff', transparent: true, opacity: 0.55 }),
      );
      edges.position.copy(mesh.position);
      group.add(edges);
      plates.push({ mesh, anchor: new THREE.Vector3(-1.6 + len, y, 0.75) });
    });
    // blueprint frame: the full-scale envelope a perfect score would fill
    const frame = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(3.2, 2.1, 1.5)),
      new THREE.LineDashedMaterial({ color: '#ffffff', dashSize: 0.06, gapSize: 0.05, transparent: true, opacity: 0.45 }),
    );
    frame.computeLineDistances();
    frame.position.set(0, 0.06, 0);
    group.add(frame);

    const key = new THREE.DirectionalLight('#ffffff', 2.2);
    key.position.set(3, 5, 4);
    scene.add(key);
    scene.add(new THREE.AmbientLight('#9fb8ff', 0.6));

    let W = 1;
    let H = 1;
    const resize = () => {
      W = el.clientWidth;
      H = el.clientHeight;
      renderer.setSize(W, H);
      camera.aspect = W / H;
      camera.position.setLength(W / H < 1 ? 10.5 : 8.4);
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    const reduced = prefersReduced();
    let raf = 0;
    let t = 0;
    const tick = () => {
      t += reduced ? 0 : 0.004;
      group.rotation.y = -0.35 + Math.sin(t) * 0.18 + spinRef.current;
      group.updateMatrixWorld();
      renderer.render(scene, camera);
      plates.forEach((p, i) => {
        const node = tags.current[i];
        if (!node) return;
        const v = p.anchor.clone().applyMatrix4(group.matrixWorld).project(camera);
        node.style.transform = `translate(${(v.x * 0.5 + 0.5) * W}px, ${(-v.y * 0.5 + 0.5) * H}px)`;
      });
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.dispose();
      pmrem.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return (
    <div className="as-glass" ref={host} style={{ height }} role="img" aria-label="Five glass plates sized by the Adult sub-scores">
      {labels &&
        SUB_ORDER.map((k, i) => (
          <div key={k} className={`as-glass-tag${run.sub[k] < 50 ? ' is-crit' : ''}`} ref={(n) => { tags.current[i] = n; }}>
            <i />
            <span>
              <b>{run.sub[k].toFixed(2)}</b> {SUB_LABELS[k]}
            </span>
          </div>
        ))}
    </div>
  );
}
