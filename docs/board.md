# Board

The board defines which instruments are mounted on the gantry head, their type, and their XYZ offsets from the head reference point.

## Config

Representative example:

```yaml
instruments:
  asmi:
    type: asmi
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
    measurement_height: 0.0
    force_threshold: -50
    sensor_channels: [1]
```

Use this file when:

- a different instrument is mounted
- offsets or reach depths change
- instrument-specific connection settings change

## Supported Instruments

All instruments have real drivers and mock variants for offline testing.

| Instrument | Type Key | Vendor | Description |
|------------|----------|--------|-------------|
| Thorlabs CCS UV-Vis Spectrometer | `uvvis_ccs` | thorlabs | UV-Vis spectroscopy |
| Opentrons Pipette | `pipette` | opentrons | Liquid handling |
| ASMI Force Sensor | `asmi` | vernier | Force measurement |
| Filmetrics | `filmetrics` | kla | Thin-film thickness measurement |
| Excelitas OmniCure | `uv_curing` | excelitas | UV curing |
