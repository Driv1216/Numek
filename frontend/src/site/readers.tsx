// Two Readings, rebuilt closer to the round-one original that was liked: Recursive's MONO axis is
// the voice ("Machine output," set mono, "human evidence." set sans). As you scroll, the two halves
// part and a window opens between them; the real command types itself on the machine side and the
// decision summary arrives on the human side.
import '@fontsource-variable/recursive/full.css';
import { useEffect, useState, type CSSProperties } from 'react';
import { adult, local } from './content';
import { reducedMotion, seg, useScrollProgress } from '../foundation/motion';

const axes = (mono: number, casl = 0): CSSProperties => ({ fontVariationSettings: `'MONO' ${mono.toFixed(3)}, 'CASL' ${casl.toFixed(3)}` });
const terminal = [
  { p: true, t: local.commands[0] },
  ...local.cliOutput.map((t) => ({ p: false, t })),
  { p: true, t: local.commands[1] },
  { p: false, t: 'Starting DataTrust at http://127.0.0.1:8000/' },
];

function useTyping(run: boolean) {
  const [n, setN] = useState(reducedMotion() ? terminal.length : 0);
  useEffect(() => {
    if (!run || n >= terminal.length) return;
    const t = setTimeout(() => setN(n + 1), n === 0 ? 250 : 380);
    return () => clearTimeout(t);
  }, [run, n]);
  return n;
}

export function Readers() {
  const [ref, hp] = useScrollProgress<HTMLDivElement>('pinned');
  const rm = reducedMotion();
  const open = rm ? 1 : seg(hp, 0.04, 0.62);
  const n = useTyping(hp > 0.02 || rm);
  const done = n >= terminal.length;
  const ready = open > 0.97;

  const f = adult.findings;
  return (
    <section id="dt-readers" className="nk-split" ref={ref} aria-labelledby="dt-split-h">
      <div className="nk-split__stage">
        <span className="nk-label" style={{ opacity: 1 - open * 0.6 }}>One analysis, two readers</span>
        <h2 id="dt-split-h" className="nk-split__line" aria-label="Machine output, human evidence.">
          <span className="nk-split__half" style={{ ...axes(1), transform: `translateX(${-open * 30}vw)`, opacity: 1 - seg(open, 0.5, 0.9) }}>Machine output,</span>
          <span className={`nk-split__win ${ready ? 'is-ready' : ''}`} style={{ width: `${3.6 + open * 78}vw`, height: `${5.2 + open * 58}vh` }}>
            <span className="nk-rd" aria-label="The same Adult result: the terminal session for the engineer, and the decision summary for the reviewer.">
              <span className="nk-rd__bar"><i /><i /><i /><em style={axes(1)}>~/datasets · local</em><em className="nk-rd__r" style={axes(0)}>adult.html · decision summary</em></span>
              <span className="nk-rd__body">
                <span className="nk-rd__m" style={axes(1)}>
                  <span className="nk-rd__k">The engineer reads</span>
                  {terminal.slice(0, Math.max(1, n)).map((l, i) => <span key={i} className={`nk-rd__l ${l.p ? 'is-p' : ''}`}>{l.p && <b>$ </b>}{l.t}</span>)}
                  <span className="nk-rd__caret" />
                  {done && <span className="nk-rd__files">{['adult.html', 'adult.pdf', 'adult.json'].map((x) => <i key={x}>{x}</i>)}</span>}
                </span>
                <span className={`nk-rd__h ${done ? 'is-in' : ''}`} style={axes(0, 0.12)}>
                  <span className="nk-rd__k">The reviewer reads</span>
                  <span className="nk-rd__score"><b>{adult.finalScore.toFixed(1)}</b><em>{adult.band} risk</em></span>
                  <span className="nk-rd__p">The data looks healthy on average ({adult.evidenceScore}), but one answer fills 76% of the target, so the score is held at {adult.finalScore.toFixed(1)}.</span>
                  {[f[1], f[2], f[0]].map((x) => <span key={x.code} className="nk-rd__f"><i>{x.severity}</i><span><b>{x.title}</b>{x.review.split('.')[0]}.</span></span>)}
                </span>
              </span>
            </span>
          </span>
          <span className="nk-split__half" style={{ ...axes(0, 0.2), transform: `translateX(${open * 30}vw)`, opacity: 1 - seg(open, 0.5, 0.9) }}>human evidence.</span>
        </h2>
        <p className="nk-split__sub" style={{ opacity: ready ? 1 : 1 - open * 1.8 }}>
          {ready ? <><span style={axes(1)}>Same result,</span> <span style={axes(0, 0.2)}>two readings</span>: nothing is recomputed for the reader.</> : 'Every DataTrust result is written twice: exact output an engineer can check, and evidence a reviewer can read.'}
        </p>
      </div>
    </section>
  );
}
