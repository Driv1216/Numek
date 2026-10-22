# NUMEK frontend

One Vite + React project with two independent builds, both from the approved concept 22 design.

| Build | Command | Output | Served by |
|---|---|---|---|
| Marketing site (`/`, `/datatrust/`) | `npm run build:site` | `dist/site/` (not committed) | any static host |
| Local DataTrust app (`/app/`) | `npm run build:app` | `../src/datatrust/static/app/` (committed, shipped as package data) | `datatrust ui` |

- `src/foundation/`: tokens, base styles, line kit and motion helpers, shared by both builds.
- `src/products.ts`: the product registry.
- `src/site/`: the marketing pages. `content/` holds validation-derived figures; every number traces to repository evidence.
- `src/app/`: the local app.

Each build ends with `scripts/check-bundle.mjs`. It fails if a bundle references an external host, or if the site bundle contains an API path. Fonts are self-hosted.
