// A WebGL unit field: one square mark per record. Marks move between layouts with a
// staggered ease; the field only renders while a transition runs.
import { reducedMotion } from '../../shell/motion';

export interface Layout {
  pos: Float32Array; // x, y in CSS pixels (top-left origin)
  color: Float32Array; // r, g, b, a (0–1)
  size: Float32Array; // CSS pixels
  labels: Label[];
}
export interface Label { x: number; y: number; text: string; sub?: string; align?: 'left' | 'center' | 'right'; tone?: string }

const VS = `#version 300 es
in vec2 aFrom; in vec2 aTo; in vec4 cFrom; in vec4 cTo; in float sFrom; in float sTo; in float aDelay;
uniform float uT; uniform vec2 uRes; uniform float uDpr;
out vec4 vColor;
void main() {
  float t = clamp((uT - aDelay * 0.42) / 0.58, 0.0, 1.0);
  t = t < 0.5 ? 4.0 * t * t * t : 1.0 - pow(-2.0 * t + 2.0, 3.0) / 2.0;
  vec2 p = mix(aFrom, aTo, t);
  vColor = mix(cFrom, cTo, t);
  gl_PointSize = max(1.0, mix(sFrom, sTo, t) * uDpr);
  gl_Position = vec4(p.x / uRes.x * 2.0 - 1.0, 1.0 - p.y / uRes.y * 2.0, 0.0, 1.0);
}`;
const FS = `#version 300 es
precision mediump float;
in vec4 vColor; out vec4 o;
void main() { o = vec4(vColor.rgb * vColor.a, vColor.a); }`;

export class UnitField {
  private gl: WebGL2RenderingContext;
  private prog: WebGLProgram;
  private bufs: Record<string, WebGLBuffer> = {};
  private cur: Layout | null = null;
  private raf = 0;
  private t = 1;
  private w = 1; private h = 1; private dpr = 1;
  readonly n: number;
  ok = true;

  constructor(private canvas: HTMLCanvasElement, n: number, delay: Float32Array) {
    this.n = n;
    const gl = canvas.getContext('webgl2', { antialias: false, premultipliedAlpha: true, alpha: true });
    if (!gl) { this.ok = false; this.gl = null as unknown as WebGL2RenderingContext; this.prog = null as unknown as WebGLProgram; return; }
    this.gl = gl;
    const sh = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const p = gl.createProgram()!;
    gl.attachShader(p, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(p);
    this.prog = p;
    gl.useProgram(p);
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    const vao = gl.createVertexArray(); gl.bindVertexArray(vao);
    for (const [name, size] of [['aFrom', 2], ['aTo', 2], ['cFrom', 4], ['cTo', 4], ['sFrom', 1], ['sTo', 1], ['aDelay', 1]] as const) {
      const b = gl.createBuffer()!; this.bufs[name] = b;
      const loc = gl.getAttribLocation(p, name);
      gl.bindBuffer(gl.ARRAY_BUFFER, b);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(n * size), gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
    }
    this.upload('aDelay', delay);
  }

  private upload(name: string, data: Float32Array) {
    const gl = this.gl; gl.bindBuffer(gl.ARRAY_BUFFER, this.bufs[name]); gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW);
  }

  resize() {
    const r = this.canvas.getBoundingClientRect();
    this.dpr = Math.min(2, devicePixelRatio || 1);
    this.w = Math.max(1, r.width); this.h = Math.max(1, r.height);
    this.canvas.width = Math.round(this.w * this.dpr); this.canvas.height = Math.round(this.h * this.dpr);
    return { w: this.w, h: this.h };
  }

  /** Move to a layout. Pass animate=false to snap (first paint, resize, reduced motion). */
  set(next: Layout, animate = true) {
    if (!this.ok) return;
    const prev = this.cur;
    this.upload('aTo', next.pos); this.upload('cTo', next.color); this.upload('sTo', next.size);
    if (prev && animate && !reducedMotion()) {
      this.upload('aFrom', prev.pos); this.upload('cFrom', prev.color); this.upload('sFrom', prev.size);
      this.t = 0;
    } else {
      this.upload('aFrom', next.pos); this.upload('cFrom', next.color); this.upload('sFrom', next.size);
      this.t = 1;
    }
    this.cur = next;
    cancelAnimationFrame(this.raf);
    const t0 = performance.now();
    const dur = 1500;
    const loop = (now: number) => {
      if (this.t < 1) this.t = Math.min(1, (now - t0) / dur);
      this.draw();
      if (this.t < 1) this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  }

  draw() {
    const gl = this.gl;
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.uniform1f(gl.getUniformLocation(this.prog, 'uT'), this.t);
    gl.uniform2f(gl.getUniformLocation(this.prog, 'uRes'), this.w, this.h);
    gl.uniform1f(gl.getUniformLocation(this.prog, 'uDpr'), this.dpr);
    gl.drawArrays(gl.POINTS, 0, this.n);
  }

  /** Nearest visible mark to a point, using the target layout. */
  pick(x: number, y: number, radius = 6) {
    const L = this.cur; if (!L) return -1;
    let best = -1, bd = radius * radius;
    for (let i = 0; i < this.n; i++) {
      if (L.color[i * 4 + 3] < 0.3) continue;
      const dx = L.pos[i * 2] - x, dy = L.pos[i * 2 + 1] - y, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  }

  // The context is reused if the canvas remounts (StrictMode), so it is never force-lost here.
  dispose() { cancelAnimationFrame(this.raf); }
}
