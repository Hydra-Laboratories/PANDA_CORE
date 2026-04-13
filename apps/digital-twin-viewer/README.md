# Digital Twin Viewer

Browser viewer for CubOS protocol replay bundles exported by `python -m digital_twin`.

## Default Example

The app ships with a checked-in example bundle generated from:

- `configs/gantry/cubos.yaml`
- `configs/deck/mofcat_deck.yaml`
- `configs/board/mock_mofcat_board.yaml`
- `configs/protocol/move.yaml`

That bundle lives at `public/examples/cubos-move.json`.

## Development

Install dependencies:

```bash
npm install
```

Start the dev server:

```bash
npm run dev
```

Run the app tests:

```bash
npm test
```

Build the app:

```bash
npm run build
```

## Exporting A New Bundle

From the repo root:

```bash
PYTHONPATH=src:. python -m digital_twin \
  --gantry configs/gantry/cubos.yaml \
  --deck configs/deck/mofcat_deck.yaml \
  --board configs/board/mock_mofcat_board.yaml \
  --protocol configs/protocol/move.yaml \
  --out apps/digital-twin-viewer/public/examples/cubos-move.json
```
