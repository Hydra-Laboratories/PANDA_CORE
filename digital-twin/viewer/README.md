# Digital Twin Viewer

Browser viewer for CubOS protocol replay bundles exported by `python -m digital_twin`.

## Default Example

The app ships with a checked-in example bundle generated from:

- `../examples/configs/gantry/cubos_xl.yaml`
- `../examples/configs/deck/panda_deck.yaml`
- `../examples/configs/board/asmi_board.yaml`
- `../examples/configs/protocol/asmi_panda_deck_test.yaml`

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

From the `digital-twin/` package root:

```bash
python -m digital_twin \
  --gantry examples/configs/gantry/cubos_xl.yaml \
  --deck examples/configs/deck/panda_deck.yaml \
  --board examples/configs/board/asmi_board.yaml \
  --protocol examples/configs/protocol/asmi_panda_deck_test.yaml \
  --skip-validation \
  --out viewer/public/examples/asmi-panda-deck.json
```
