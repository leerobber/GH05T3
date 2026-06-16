# GH05T3 Frontend

React 19 + Vite 8 + Tailwind 3 + Radix UI dashboard for GH05T3.

## Scripts

```bash
yarn install          # install deps
yarn start            # vite dev server on http://localhost:3000
yarn build            # production build → build/
yarn preview          # serve the production build
```

## Environment

The frontend talks to the gateway via `REACT_APP_GW3_URL`. Set it at build time:

```bash
REACT_APP_GW3_URL=http://localhost:8002 yarn build
```

> Vite reads variables prefixed with `REACT_APP_` (legacy CRA convention) for
> backwards compatibility with code that uses `process.env.REACT_APP_GW3_URL`.

## Source layout

```
frontend/
├── index.html                       Vite entry HTML
├── vite.config.js                   Build config + @/ alias
├── public/                          Static assets, manifest, service worker
└── src/
    ├── main.jsx                     React root
    ├── App.jsx                      App shell + error boundary
    ├── GH05T3Dashboard_v3.jsx       v3 dashboard layout
    ├── index.css                    Global styles (Tailwind + custom)
    ├── lib/
    │   ├── ghostApi.js              Gateway API wrappers
    │   └── useGhostWS.js            WebSocket telemetry hook
    └── components/
        └── ghost/                   All UI panels (SwarmBus, GhostEye, etc.)
```
