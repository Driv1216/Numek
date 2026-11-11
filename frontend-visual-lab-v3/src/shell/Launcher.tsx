const concepts = [
  { id: 'markup', no: '01', name: 'Markup', line: 'Findings are vermilion marks on a drawing of the data itself.', from: 'Heron AI · Studio Freight / Hyperbolic · Praetorian spec sheets' },
  { id: 'every-row', no: '02', name: 'Every Row', line: 'All 48,842 records stay visible and re-arrange into the evidence.', from: 'The Pudding / Hamilton · Obys arrangements · The Seventh Eye' },
  { id: 'issue', no: '03', name: 'The Issue', line: 'Each audit is published as an issue: cover, contents, chapters.', from: 'State of AI Design · Sons & Daughters · 14islands / Cartier 365' },
  { id: 'passage', no: '04', name: 'Passage', line: 'Six representations, six materials; the investigation travels sideways.', from: 'LPAS / Studio Naam · Chartogne-Taillet · Elektra index' },
  { id: 'two-readings', no: '05', name: 'Two Readings', line: 'Machine output and human evidence, one typeface morphing between them.', from: 'Made With GSAP · Riotters / Aevion · Linear · Raycast' },
  { id: 'provenance', no: '06', name: 'Provenance', line: 'One real record held still while its evidence trail is traced, step by step.', from: 'Getty / Tracing Art · Persepolis · Ottografie · Studio Null' },
  { id: 'collection', no: '07', name: 'Collection', line: 'Every column of the dataset as a sculptural object, catalogued.', from: 'Monolith NYC · Studio Null · vvisual · Pangram specimen cards' },
  { id: 'modules', no: '08', name: 'Modules', line: 'A colour mosaic of live capability tiles that expand into chapters.', from: 'Dropbox Brand · Cash App Brand · Reform / Micro · BlueYard' },
  { id: 'camera', no: '09', name: 'Product Camera', line: 'The real interface at full fidelity; the landing is a guided camera tour.', from: 'Apple MacBook Pro · Linear · Raycast · Studio Freight / Hyperbolic' },
  { id: 'lexicon', no: '10', name: 'Lexicon', line: 'One giant word per finding, with real evidence drifting past at depth.', from: 'Ottografie · Sons & Daughters · Obys · Elektra index' },
  { id: 'cutaway', no: '11', name: 'Cutaway', line: 'The dataset drawn as one isometric engineering cutaway; chapters are close-ups carrying the real finding.', from: 'Townhouse · Mind Robotics · Kriss.ai' },
  { id: 'line', no: '12', name: 'The Local Line', line: 'One line carries a file through DataTrust on this machine, drawn with exact numbers and no webfonts.', from: 'From the Grid to the Page · DeepBook · Imersion' },
  { id: 'instrument', no: '13', name: 'Instrument', line: 'One scientific instrument on screen; each section asks it a question and it answers live.', from: 'Where the Shadow Fell · Anime.js' },
  { id: 'footnote', no: '14', name: 'Footnote', line: 'One honest sentence, every claim footnoted to evidence, live data set inside the line.', from: 'Watson · Mind Robotics · The Robot and Me' },
  { id: 'cells', no: '15', name: 'Cells', line: 'A rigid cell grid that builds itself, then fills with facts; one accent for what changed the score.', from: 'Aspen Search · Grids S03 · ART+TECH Report' },
  { id: 'resolution', no: '16', name: 'Resolution', line: 'An infinite wall of every artefact from seven runs, each resolving from coarse to exact.', from: 'Phantom · GMB' },
  { id: 'relief', no: '17', name: 'Relief', line: 'A white relief cast from the data; only evidence carries colour, set into it as windows.', from: 'Immersive Garden · Seasoned' },
  { id: 'file', no: '18', name: 'The File', line: 'adult.csv staged like a flagship product, changing state with each fact.', from: 'Deferred Damage · Oryzo · Seasoned' },
  { id: 'slab', no: '19', name: 'Slab', line: 'Constructivist slabs build the wordmark, then stand as the five sub-scores against the cap.', from: 'Obys AIM · Neutomni · Siena' },
  { id: 'numek', no: '22', name: 'NUMEK blend', line: 'The current direction: Product Camera across all three products, Markup’s line language, Modules as the spine, in Deep water. Step one: the NUMEK landing.', from: 'Product Camera · Markup · Two Readings · Modules' },
  { id: 'evidence', no: '21', name: 'The Evidence Mark', line: 'Mission first. NUMEK owns one act, marking the evidence, across data, models and outputs. Landing page only, for review.', from: 'NUMEK’s own thesis · round one (Markup, Every Row, The Issue, Passage, Two Readings) · Modules' },
  { id: 'findings', no: '20', name: 'Findings First', line: 'The landing page is the product: every finding from every run, with the method beside it.', from: 'Field Rank · The Robot and Me · Awwwards jury table' },
];

const screens = [['landing', 'Landing'], ['app', 'Dashboard'], ['results', 'Results']] as const;

export function Launcher() {
  return (
    <main className="launcher">
      <header className="launcher__head">
        <p className="launcher__eyebrow">NUMEK · DataTrust · visual lab v3</p>
        <h1>Twenty studios, one company.</h1>
        <p className="launcher__lede">Twenty independent directions for NUMEK’s website and DataTrust’s application, in three rounds. Each has a landing page, an application home and an analysis result. All twenty use the same real content: the Adult audit (48,842 × 15, 69.0 Elevated after the critical-sub-score guardrail) and the same list of local runs.</p>
        <p className="launcher__links"><a href="/research/">Research board, round one →</a><a href="/research/round-two.html">Round two →</a><a href="/research/round-three/">Round three →</a><a href="/screenshots/">Screenshot sheet →</a></p>
      </header>
      {[['Current direction', concepts.filter((c) => c.id === 'numek')], ['Foundation', concepts.filter((c) => c.id === 'evidence')], ['Round one', concepts.slice(0, 5)], ['Round two', concepts.slice(5, 10)], ['Round three', concepts.slice(10).filter((c) => c.id !== 'evidence' && c.id !== 'numek')]].map(([round, list]) => (
      <section key={round as string}>
      <h2 className="launcher__round">{round as string}</h2>
      <ol className="launcher__list">
        {(list as typeof concepts).map((c) => (
          <li key={c.id} className={`lc lc--${c.id}`}>
            <a className="lc__shot" href={`#/${c.id}/landing`} aria-label={`${c.name} landing page`}>
              <img src={`/screenshots/${c.id}-landing.jpg`} alt="" loading="lazy" onError={(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')} />
            </a>
            <div className="lc__text">
              <span className="lc__no">{c.no}</span>
              <h2>{c.name}</h2>
              <p>{c.line}</p>
              <p className="lc__from">From {c.from}</p>
              <nav>
                {screens.map(([s, l]) => <a key={s} href={`#/${c.id}/${s}`}>{l}</a>)}
              </nav>
            </div>
          </li>
        ))}
      </ol>
      </section>
      ))}
      <footer className="launcher__foot">Isolated prototypes with local mock data. No production integration. In 01–20, ConfidenceGuard and HallucinationGuard appear only as research directions. In 21, at the founder’s direction, ConfidenceGuard is shown as a product in development (CG1 implemented, awaiting review); HallucinationGuard remains a research direction.</footer>
    </main>
  );
}
