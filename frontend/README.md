# FlowLens frontend

React, TypeScript, Vite and Tailwind CSS. It talks only to the FlowLens backend through `/api`, which Vite proxies to `FLOWLENS_API_URL` (default `http://127.0.0.1:8000`); it never calls a model.

```sh
npm ci
npm run dev      # http://localhost:5173, with the backend running
npm run lint     # oxlint
npm run build    # tsc -b, then vite build
```

- `src/features/`: UI by area (landing page, launcher, run history, workers, map, browser preview, evidence, findings, activity).
- `src/lib/`: API client, types mirroring the backend contracts, and helpers that derive views from run records.
- `public/`: favicon, landing background and the demo video.

Setup for the whole project is in [docs/setup.md](../docs/setup.md).
