# Instruments

Each subdirectory contains a self-contained instrument driver that implements `BaseInstrument`.

| Folder | Vendor | Instrument | Description |
|--------|--------|------------|-------------|
| `filmetrics/` | **KLA / Filmetrics** | F-Series (via FilmetricsTool.exe) | Thin-film thickness measurement via spectral reflectance |
| `uvvis_ccs/` | **Thorlabs** | CCS100 / CCS175 / CCS200 | Compact CCD spectrometer for UV-Vis spectroscopy (3648-pixel) |

## Structure convention

Every instrument folder follows the same layout:

```
<instrument>/
├── __init__.py       # Public exports
├── driver.py         # Real hardware driver (extends BaseInstrument)
├── mock.py           # Mock implementation for testing (extends BaseInstrument)
├── models.py         # Frozen dataclasses for measurement results
└── exceptions.py     # Instrument-specific exception hierarchy
```

## Adding a new instrument

1. Create a new folder under `src/instruments/`.
2. Subclass `BaseInstrument` and implement `connect()`, `disconnect()`, `health_check()`.
3. Add a mock that tracks `command_history` for test assertions.
4. Define a frozen dataclass in `models.py` for measurement results.
5. Create an exception hierarchy rooted in `InstrumentError`.
6. Update this README with the vendor and instrument info.
