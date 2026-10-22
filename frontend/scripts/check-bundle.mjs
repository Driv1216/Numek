// Fails the build if a bundle could reach the network or (for the site) carries an API client.
// Usage: node scripts/check-bundle.mjs <dir> <site|app>
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';

const [dir, kind] = process.argv.slice(2);
// Hosts that appear only as inert strings: the SVG namespace and React's error-decoder link.
const inert = new Set(['www.w3.org', 'react.dev', 'reactjs.org']);
const problems = [];
const walk = (d) => readdirSync(d).flatMap((n) => (statSync(join(d, n)).isDirectory() ? walk(join(d, n)) : [join(d, n)]));
for (const file of walk(dir)) {
  if (!['.html', '.js', '.css', '.json', '.svg'].includes(extname(file))) continue;
  const text = readFileSync(file, 'utf8');
  for (const [, host] of text.matchAll(/(?:https?:)?\/\/([a-z0-9.-]+\.[a-z]{2,})(?=[/"'`)\s:])/gi)) if (!inert.has(host.toLowerCase())) problems.push(`${file}: external host ${host}`);
  if (kind === 'site' && /["'`]\/api\//.test(text)) problems.push(`${file}: API path in the static site`);
}
if (problems.length) { console.error([...new Set(problems)].join('\n')); process.exit(1); }
console.log(`check-bundle: ${kind} bundle in ${dir} makes no external requests${kind === 'site' ? ' and has no API client' : ''}.`);
