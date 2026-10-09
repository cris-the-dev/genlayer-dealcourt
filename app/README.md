# Demo app

A static page that talks to the contract deployed on GenLayer Testnet Bradbury (address in the page header).
Reads work without a wallet; writes go through MetaMask.

Files:
- `index.html` — the page
- `gl.js` — wallet + read/write helpers
- `app.css` — shared styles
- `check-actions.mjs` — asserts which controls each deal state shows to each role (`node app/check-actions.mjs app/index.html`, runs in CI)
- `genlayer.js` — not committed; a browser bundle of `genlayer-js@1.1.8`:

```bash
npm i genlayer-js@1.1.8 esbuild
printf 'export { createClient, createAccount } from "genlayer-js";\nexport { testnetBradbury } from "genlayer-js/chains";\n' > entry.js
npx esbuild entry.js --bundle --format=esm --minify --platform=browser --outfile=app/genlayer.js
```

Serve the folder with any static server (`python -m http.server -d app`). The page loads Switzer from `/fonts/`; without it the system font is used.
