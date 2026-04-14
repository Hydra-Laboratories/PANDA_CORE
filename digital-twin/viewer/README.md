# Digital Twin Viewer

Browser viewer for CubOS protocol replay bundles exported by `python -m digital_twin`.

## Default Example

The app ships with a checked-in example bundle generated from:

- `configs/gantry/cubos_xl.yaml`
- `configs/deck/panda_deck.yaml`
- `configs/board/asmi_board.yaml`
- `configs/protocol/asmi_panda_deck_test.yaml`

That bundle lives at `public/examples/asmi-panda-deck.json`.

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

From the `digital-twin/` package root, using a CubOS checkout one directory up:

```bash
python -m digital_twin \
  --gantry ../configs/gantry/cubos_xl.yaml \
  --deck ../configs/deck/panda_deck.yaml \
  --board ../configs/board/asmi_board.yaml \
  --protocol ../configs/protocol/asmi_panda_deck_test.yaml \
  --skip-validation \
  --out viewer/public/examples/asmi-panda-deck.json
```
