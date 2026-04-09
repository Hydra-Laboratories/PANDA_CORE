from __future__ import annotations

import logging
import math
import sys
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, Sequence

logger = logging.getLogger(__name__)

from instruments.base_instrument import BaseInstrument
from instruments.potentiostat.exceptions import (
    PotentiostatConfigError,
    PotentiostatConnectionError,
    PotentiostatMeasurementError,
    PotentiostatPlatformError,
    PotentiostatTimeoutError,
)
from instruments.potentiostat.models import (
    ChronoAmperometryResult,
    CyclicVoltammetryResult,
    OCPResult,
    PotentiostatStatus,
)

SUPPORTED_POTENTIOSTAT_VENDORS = ("gamry", "emstat")
_DEFAULT_OCP_DURATION_S = 15.0
_DEFAULT_SAMPLE_PERIOD_S = 0.5
_DEFAULT_CA_CURRENT_SENSITIVITY_A = 1e-6


def _build_time_axis(duration_s: float, sample_period_s: float) -> tuple[float, ...]:
    sample_count = max(1, int(round(duration_s / sample_period_s))) + 1
    return tuple(round(i * sample_period_s, 10) for i in range(sample_count))


def _series_from_mapping(
    rows: Any,
    *candidate_keys: str,
) -> tuple[float, ...]:
    if rows is None:
        raise PotentiostatMeasurementError(
            "Potentiostat returned no data. The experiment may have failed to run."
        )

    if hasattr(rows, "to_dict"):
        try:
            rows = rows.to_dict(orient="records")
        except TypeError:
            rows = rows.to_dict()

    if isinstance(rows, dict):
        for key in candidate_keys:
            if key in rows:
                values = rows[key]
                return tuple(_safe_float(v, key) for v in values)
        raise PotentiostatMeasurementError(
            f"None of the expected data keys {candidate_keys!r} found in potentiostat result. "
            f"Available keys: {list(rows.keys())}"
        )

    if isinstance(rows, Iterable):
        output: list[float] = []
        for row in rows:
            if isinstance(row, dict):
                for key in candidate_keys:
                    if key in row and row[key] is not None:
                        output.append(_safe_float(row[key], key))
                        break
                else:
                    raise PotentiostatMeasurementError(
                        f"Row is missing all expected keys {candidate_keys!r}. Row: {row!r}"
                    )
        return tuple(output)

    raise PotentiostatMeasurementError(
        f"Unexpected potentiostat data format: {type(rows).__name__}"
    )


def _safe_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (ValueError, TypeError) as exc:
        raise PotentiostatMeasurementError(
            f"Could not convert potentiostat data field '{field_name}' "
            f"value {value!r} to float: {exc}"
        ) from exc


def _triangular_wave(
    phase: float,
    minimum: float,
    maximum: float,
) -> float:
    span = maximum - minimum
    if span <= 0:
        return minimum
    if phase < 0.5:
        return minimum + (phase * 2.0 * span)
    return maximum - ((phase - 0.5) * 2.0 * span)


class _PotentiostatBackend(ABC):

    def __init__(self, vendor: str) -> None:
        self.vendor = vendor

    @property
    def backend_name(self) -> str:
        return self.vendor

    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def measure_ocp(self, duration_s: float, sample_period_s: float) -> OCPResult:
        raise NotImplementedError

    @abstractmethod
    def run_chronoamperometry(
        self,
        step_potential_v: float,
        duration_s: float,
        sample_period_s: float,
        current_sensitivity_a: float,
        second_working_electrode_potential_v: float | None,
    ) -> ChronoAmperometryResult:
        raise NotImplementedError

    @abstractmethod
    def run_cyclic_voltammetry(
        self,
        initial_potential_v: float,
        vertex_potential_1_v: float,
        vertex_potential_2_v: float,
        final_potential_v: float,
        scan_rate_v_s: float,
        step_size_v: float,
        cycles: int,
        current_sensitivity_a: float,
    ) -> CyclicVoltammetryResult:
        raise NotImplementedError


class _OfflinePotentiostatBackend(_PotentiostatBackend):

    def __init__(self, vendor: str) -> None:
        super().__init__(vendor=vendor)
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def health_check(self) -> bool:
        return True

    def measure_ocp(self, duration_s: float, sample_period_s: float) -> OCPResult:
        time_s = _build_time_axis(duration_s, sample_period_s)
        vendor_offset = 0.12 if self.vendor == "emstat" else 0.1
        voltage_v = tuple(
            vendor_offset
            + 0.03 * math.exp(-t / max(duration_s, sample_period_s))
            + 0.002 * math.sin((t + 1.0) * 1.7)
            for t in time_s
        )
        return OCPResult(
            time_s=time_s,
            voltage_v=voltage_v,
            sample_period_s=sample_period_s,
            duration_s=duration_s,
            vendor=self.vendor,
        )

    def run_chronoamperometry(
        self,
        step_potential_v: float,
        duration_s: float,
        sample_period_s: float,
        current_sensitivity_a: float,
        second_working_electrode_potential_v: float | None,
    ) -> ChronoAmperometryResult:
        time_s = _build_time_axis(duration_s, sample_period_s)
        decay_scale = max(duration_s / 4.0, sample_period_s)
        current_scale = current_sensitivity_a * (0.9 if self.vendor == "emstat" else 1.0)
        current_a = tuple(
            current_scale * math.exp(-t / decay_scale) * math.copysign(1.0, step_potential_v or 1.0)
            for t in time_s
        )
        voltage_v = tuple(step_potential_v for _ in time_s)
        return ChronoAmperometryResult(
            time_s=time_s,
            current_a=current_a,
            voltage_v=voltage_v,
            sample_period_s=sample_period_s,
            duration_s=duration_s,
            step_potential_v=step_potential_v,
            vendor=self.vendor,
            metadata={
                "current_sensitivity_a": current_sensitivity_a,
                "second_working_electrode_potential_v": second_working_electrode_potential_v,
            },
        )

    def run_cyclic_voltammetry(
        self,
        initial_potential_v: float,
        vertex_potential_1_v: float,
        vertex_potential_2_v: float,
        final_potential_v: float,
        scan_rate_v_s: float,
        step_size_v: float,
        cycles: int,
        current_sensitivity_a: float,
    ) -> CyclicVoltammetryResult:
        points_per_segment = max(
            2,
            int(
                max(
                    abs(vertex_potential_1_v - initial_potential_v),
                    abs(vertex_potential_1_v - vertex_potential_2_v),
                    abs(final_potential_v - vertex_potential_2_v),
                )
                / step_size_v
            ) + 1,
        )
        time_step_s = step_size_v / scan_rate_v_s
        time_s: list[float] = []
        voltage_v: list[float] = []
        current_a: list[float] = []
        for cycle_index in range(cycles):
            for point_index in range(points_per_segment * 2):
                phase = point_index / max(1, (points_per_segment * 2) - 1)
                base_voltage = _triangular_wave(
                    phase=phase,
                    minimum=min(vertex_potential_2_v, initial_potential_v, final_potential_v),
                    maximum=max(vertex_potential_1_v, initial_potential_v, final_potential_v),
                )
                elapsed_s = (len(time_s)) * time_step_s
                capacitive_current = current_sensitivity_a * math.sin(phase * math.pi * 2.0)
                faradaic_current = (
                    current_sensitivity_a
                    * 0.3
                    * math.cos((cycle_index + 1) * base_voltage * math.pi)
                )
                time_s.append(round(elapsed_s, 10))
                voltage_v.append(base_voltage)
                current_a.append(capacitive_current + faradaic_current)
        return CyclicVoltammetryResult(
            time_s=tuple(time_s),
            voltage_v=tuple(voltage_v),
            current_a=tuple(current_a),
            scan_rate_v_s=scan_rate_v_s,
            step_size_v=step_size_v,
            cycles=cycles,
            vendor=self.vendor,
            metadata={
                "initial_potential_v": initial_potential_v,
                "vertex_potential_1_v": vertex_potential_1_v,
                "vertex_potential_2_v": vertex_potential_2_v,
                "final_potential_v": final_potential_v,
                "current_sensitivity_a": current_sensitivity_a,
            },
        )


class _EmstatBackend(_PotentiostatBackend):

    def __init__(
        self,
        vendor: str,
        model: str,
        data_directory: str,
        verbose: int,
    ) -> None:
        super().__init__(vendor=vendor)
        self._model = model
        self._data_directory = Path(data_directory)
        self._verbose = verbose
        self._connected = False

    def connect(self) -> None:
        try:
            import hardpotato as hp  # type: ignore
        except ImportError as exc:
            raise PotentiostatConnectionError(
                "EmStat support requires the 'hardpotato' package."
            ) from exc

        setup = hp.potentiostat.Setup(
            self._model,
            None,
            str(self._data_directory),
            verbose=self._verbose,
        )
        if not setup.check_connection():
            raise PotentiostatConnectionError("Could not connect to EmStat potentiostat.")
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def health_check(self) -> bool:
        return self._connected

    def measure_ocp(self, duration_s: float, sample_period_s: float) -> OCPResult:
        self._require_connection()
        data = self._run_hardpotato_experiment(
            class_name="OCP",
            kwargs={
                "ttot": duration_s,
                "dt": sample_period_s,
                "fileName": self._file_stem("ocp"),
                "header": "OCP",
            },
        )
        time_s = _series_from_mapping(data, "t", "Time")
        voltage_v = _series_from_mapping(data, "E", "Vf", "voltage")
        return OCPResult(
            time_s=time_s,
            voltage_v=voltage_v,
            sample_period_s=sample_period_s,
            duration_s=duration_s,
            vendor=self.vendor,
        )

    def run_chronoamperometry(
        self,
        step_potential_v: float,
        duration_s: float,
        sample_period_s: float,
        current_sensitivity_a: float,
        second_working_electrode_potential_v: float | None,
    ) -> ChronoAmperometryResult:
        self._require_connection()
        data = self._run_hardpotato_experiment(
            class_name="CA",
            kwargs={
                "Estep": step_potential_v,
                "dt": sample_period_s,
                "ttot": duration_s,
                "sens": current_sensitivity_a,
                "E2": second_working_electrode_potential_v or 0.0,
                "sens2": current_sensitivity_a,
                "fileName": self._file_stem("ca"),
                "header": "CA",
            },
        )
        return ChronoAmperometryResult(
            time_s=_series_from_mapping(data, "t", "Time"),
            current_a=_series_from_mapping(data, "I", "Im", "current"),
            voltage_v=_series_from_mapping(data, "E", "Vf", "voltage"),
            sample_period_s=sample_period_s,
            duration_s=duration_s,
            step_potential_v=step_potential_v,
            vendor=self.vendor,
            metadata={
                "current_sensitivity_a": current_sensitivity_a,
                "second_working_electrode_potential_v": second_working_electrode_potential_v,
            },
        )

    def run_cyclic_voltammetry(
        self,
        initial_potential_v: float,
        vertex_potential_1_v: float,
        vertex_potential_2_v: float,
        final_potential_v: float,
        scan_rate_v_s: float,
        step_size_v: float,
        cycles: int,
        current_sensitivity_a: float,
    ) -> CyclicVoltammetryResult:
        self._require_connection()
        data = self._run_hardpotato_experiment(
            class_name="CV",
            kwargs={
                "Eini": initial_potential_v,
                "Ev1": vertex_potential_1_v,
                "Ev2": vertex_potential_2_v,
                "Efin": final_potential_v,
                "sr": scan_rate_v_s,
                "dE": step_size_v,
                "nSweeps": cycles,
                "sens": current_sensitivity_a,
                "E2": vertex_potential_2_v,
                "sens2": current_sensitivity_a,
                "fileName": self._file_stem("cv"),
                "header": "CV",
            },
        )
        return CyclicVoltammetryResult(
            time_s=_series_from_mapping(data, "t", "Time"),
            voltage_v=_series_from_mapping(data, "E", "Vf", "voltage"),
            current_a=_series_from_mapping(data, "I", "Im", "current"),
            scan_rate_v_s=scan_rate_v_s,
            step_size_v=step_size_v,
            cycles=cycles,
            vendor=self.vendor,
            metadata={
                "initial_potential_v": initial_potential_v,
                "vertex_potential_1_v": vertex_potential_1_v,
                "vertex_potential_2_v": vertex_potential_2_v,
                "final_potential_v": final_potential_v,
                "current_sensitivity_a": current_sensitivity_a,
            },
        )

    def _file_stem(self, technique: str) -> str:
        stem = f"cubos_{technique}_{uuid.uuid4().hex[:8]}"
        return str((self._data_directory / stem).with_suffix("")).rstrip(".")

    def _run_hardpotato_experiment(self, class_name: str, kwargs: dict[str, Any]) -> Any:
        try:
            import hardpotato as hp  # type: ignore
        except ImportError as exc:
            raise PotentiostatMeasurementError(
                "EmStat support requires the 'hardpotato' package."
            ) from exc

        if not hasattr(hp.potentiostat, class_name):
            raise PotentiostatMeasurementError(
                f"hardpotato does not have a '{class_name}' experiment class. "
                "Check hardpotato version compatibility."
            )
        experiment_class = getattr(hp.potentiostat, class_name)
        try:
            experiment = experiment_class(**kwargs)
            experiment.run()
        except Exception as exc:
            raise PotentiostatMeasurementError(
                f"EmStat {class_name} measurement failed: {exc}"
            ) from exc
        if not hasattr(experiment, "data"):
            raise PotentiostatMeasurementError(
                f"EmStat {class_name} experiment completed but returned no 'data' attribute."
            )
        return experiment.data

    def _require_connection(self) -> None:
        if not self._connected:
            raise PotentiostatConnectionError("EmStat potentiostat is not connected.")


class _GamryBackend(_PotentiostatBackend):

    def __init__(self, vendor: str, pump_timeout_s: float) -> None:
        super().__init__(vendor=vendor)
        self._pump_timeout_s = pump_timeout_s
        self._gamry_com = None
        self._client = None
        self._pstat = None
        self._open_connection = False

    def connect(self) -> None:
        if sys.platform != "win32":
            raise PotentiostatPlatformError(
                "Gamry potentiostat support is only available on Windows."
            )
        try:
            from comtypes import client  # type: ignore
        except ImportError as exc:
            raise PotentiostatConnectionError(
                "Gamry support requires the 'comtypes' package on Windows."
            ) from exc

        try:
            self._client = client
            self._gamry_com = client.GetModule(
                ["{BD962F0D-A990-4823-9CF5-284D1CDD9C6D}", 1, 0]
            )
            self._pstat = client.CreateObject("GamryCOM.GamryPC6Pstat")
            devices = client.CreateObject("GamryCOM.GamryDeviceList")
            sections = devices.EnumSections()
            if not sections:
                raise PotentiostatConnectionError("No Gamry devices found.")
            self._pstat.Init(sections[0])
            self._pstat.Open()
        except PotentiostatConnectionError:
            raise
        except Exception as exc:
            raise PotentiostatConnectionError(
                f"Failed to connect to Gamry potentiostat: {exc}"
            ) from exc
        self._open_connection = True

    def disconnect(self) -> None:
        if self._pstat is not None:
            try:
                self._pstat.Close()
            except Exception as exc:
                logger.warning(
                    "Gamry potentiostat did not close cleanly: %s. "
                    "The device may need to be power-cycled.",
                    exc,
                )
        self._open_connection = False

    def health_check(self) -> bool:
        return self._open_connection

    def measure_ocp(self, duration_s: float, sample_period_s: float) -> OCPResult:
        acquired = self._run_signal(
            signal_name="GamrySignalConst",
            dtaq_name="GamryDtaqOcv",
            signal_args=(duration_s, sample_period_s),
        )
        time_s = tuple(float(point[0]) for point in acquired)
        voltage_v = tuple(float(point[1]) for point in acquired)
        return OCPResult(
            time_s=time_s,
            voltage_v=voltage_v,
            sample_period_s=sample_period_s,
            duration_s=duration_s,
            vendor=self.vendor,
        )

    def run_chronoamperometry(
        self,
        step_potential_v: float,
        duration_s: float,
        sample_period_s: float,
        current_sensitivity_a: float,
        second_working_electrode_potential_v: float | None,
    ) -> ChronoAmperometryResult:
        acquired = self._run_signal(
            signal_name="GamrySignalDstep",
            dtaq_name="GamryDtaqChrono",
            signal_args=(step_potential_v, duration_s, sample_period_s),
        )
        time_s = tuple(float(point[0]) for point in acquired)
        voltage_v = tuple(float(point[1]) for point in acquired)
        current_a = tuple(
            float(point[3] if len(point) > 3 else point[2]) for point in acquired
        )
        return ChronoAmperometryResult(
            time_s=time_s,
            current_a=current_a,
            voltage_v=voltage_v,
            sample_period_s=sample_period_s,
            duration_s=duration_s,
            step_potential_v=step_potential_v,
            vendor=self.vendor,
            metadata={
                "current_sensitivity_a": current_sensitivity_a,
                "second_working_electrode_potential_v": second_working_electrode_potential_v,
            },
        )

    def run_cyclic_voltammetry(
        self,
        initial_potential_v: float,
        vertex_potential_1_v: float,
        vertex_potential_2_v: float,
        final_potential_v: float,
        scan_rate_v_s: float,
        step_size_v: float,
        cycles: int,
        current_sensitivity_a: float,
    ) -> CyclicVoltammetryResult:
        acquired = self._run_signal(
            signal_name="GamrySignalRupdn",
            dtaq_name="GamryDtaqRcv",
            signal_args=(
                initial_potential_v,
                vertex_potential_1_v,
                vertex_potential_2_v,
                final_potential_v,
                scan_rate_v_s,
                step_size_v / scan_rate_v_s,
                cycles,
            ),
        )
        time_s = tuple(float(point[0]) for point in acquired)
        voltage_v = tuple(float(point[1]) for point in acquired)
        current_a = tuple(
            float(point[3] if len(point) > 3 else point[2]) for point in acquired
        )
        return CyclicVoltammetryResult(
            time_s=time_s,
            voltage_v=voltage_v,
            current_a=current_a,
            scan_rate_v_s=scan_rate_v_s,
            step_size_v=step_size_v,
            cycles=cycles,
            vendor=self.vendor,
            metadata={
                "initial_potential_v": initial_potential_v,
                "vertex_potential_1_v": vertex_potential_1_v,
                "vertex_potential_2_v": vertex_potential_2_v,
                "final_potential_v": final_potential_v,
                "current_sensitivity_a": current_sensitivity_a,
            },
        )

    def _initialize_pstat(self) -> None:
        self._pstat.SetCtrlMode(self._gamry_com.PstatMode)
        self._pstat.SetCell(self._gamry_com.CellOff)
        self._pstat.SetIEStability(self._gamry_com.StabilityNorm)
        self._pstat.SetVchRangeMode(True)
        self._pstat.SetVchRange(10.0)
        self._pstat.SetIERangeMode(True)

    def _run_signal(
        self,
        signal_name: str,
        dtaq_name: str,
        signal_args: Sequence[float],
    ) -> list[tuple[Any, ...]]:
        self._require_connection()

        class _GamryEvents:

            def __init__(self, dtaq: Any) -> None:
                self.dtaq = dtaq
                self.acquired_points: list[tuple[Any, ...]] = []
                self.active = True

            def cook(self) -> None:
                count = 1
                while count > 0:
                    count, points = self.dtaq.Cook(10)
                    self.acquired_points.extend(zip(*points))

            def _IGamryDtaqEvents_OnDataAvailable(self) -> None:
                self.cook()

            def _IGamryDtaqEvents_OnDataDone(self) -> None:
                self.cook()
                self.active = False

        try:
            signal = self._client.CreateObject(f"GamryCOM.{signal_name}")
            dtaq = self._client.CreateObject(f"GamryCOM.{dtaq_name}")
        except Exception as exc:
            raise PotentiostatMeasurementError(
                f"Failed to create Gamry signal objects: {exc}"
            ) from exc

        events = _GamryEvents(dtaq)
        connection = self._client.GetEvents(dtaq, events)
        try:
            self._initialize_pstat()
            if signal_name == "GamrySignalConst":
                signal.Init(
                    self._pstat,
                    0.0,
                    signal_args[0],
                    signal_args[1],
                    self._gamry_com.PstatMode,
                )
                dtaq.Init(self._pstat)
                self._pstat.SetSignal(signal)
                self._pstat.SetCell(self._gamry_com.CellOff)
            elif signal_name == "GamrySignalDstep":
                signal.Init(
                    self._pstat,
                    0.0,
                    0.0,
                    signal_args[0],
                    signal_args[1],
                    0.0,
                    0.0,
                    signal_args[2],
                    self._gamry_com.PstatMode,
                )
                dtaq.Init(self._pstat, self._gamry_com.ChronoAmp)
                self._pstat.SetSignal(signal)
                self._pstat.SetCell(self._gamry_com.CellOn)
            else:
                signal.Init(
                    self._pstat,
                    signal_args[0],
                    signal_args[1],
                    signal_args[2],
                    signal_args[3],
                    signal_args[4],
                    signal_args[4],
                    signal_args[4],
                    0.0,
                    0.0,
                    0.0,
                    signal_args[5],
                    signal_args[6],
                    self._gamry_com.PstatMode,
                )
                dtaq.Init(self._pstat)
                self._pstat.SetSignal(signal)
                self._pstat.SetCell(self._gamry_com.CellOn)
            dtaq.Run(True)
            self._pump_events(events)
        except PotentiostatTimeoutError:
            raise
        except Exception as exc:
            raise PotentiostatMeasurementError(
                f"Gamry measurement failed: {exc}"
            ) from exc
        finally:
            try:
                self._pstat.SetCell(self._gamry_com.CellOff)
            except Exception as exc:
                logger.error(
                    "CRITICAL: Failed to turn off Gamry cell after measurement: %s. "
                    "The electrochemical cell may still be energized — inspect hardware immediately.",
                    exc,
                )
            del connection
        if not events.acquired_points:
            raise PotentiostatMeasurementError("Gamry measurement returned no data.")
        return events.acquired_points

    def _pump_events(self, events: Any) -> None:
        start = time.time()
        while events.active:
            self._client.PumpEvents(1)
            time.sleep(0.1)
            if time.time() - start > self._pump_timeout_s:
                raise PotentiostatTimeoutError("Timed out waiting for Gamry acquisition.")

    def _require_connection(self) -> None:
        if not self._open_connection:
            raise PotentiostatConnectionError("Gamry potentiostat is not connected.")


class Potentiostat(BaseInstrument):
    """Unified CubOS potentiostat driver for Gamry and EmStat backends."""

    def __init__(
        self,
        vendor: str,
        name: str | None = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        depth: float = 0.0,
        measurement_height: float = 0.0,
        offline: bool = False,
        emstat_model: str = "emstat4_lr",
        emstat_data_directory: str = ".",
        emstat_verbose: int = 0,
        gamry_pump_timeout_s: float = 120.0,
        **kwargs,
    ) -> None:
        super().__init__(
            name=name,
            offset_x=offset_x,
            offset_y=offset_y,
            depth=depth,
            measurement_height=measurement_height,
            offline=offline,
        )
        vendor = vendor.strip().lower()
        if vendor not in SUPPORTED_POTENTIOSTAT_VENDORS:
            raise PotentiostatConfigError(
                f"Unsupported potentiostat vendor '{vendor}'. "
                f"Supported vendors: {', '.join(SUPPORTED_POTENTIOSTAT_VENDORS)}"
            )
        self._vendor = vendor
        self._backend = self._build_backend(
            vendor=vendor,
            offline=offline,
            emstat_model=emstat_model,
            emstat_data_directory=emstat_data_directory,
            emstat_verbose=emstat_verbose,
            gamry_pump_timeout_s=gamry_pump_timeout_s,
        )

    @property
    def vendor(self) -> str:
        return self._vendor

    def connect(self) -> None:
        self._backend.connect()
        self.logger.info("Potentiostat connected (%s)", self._vendor)

    def disconnect(self) -> None:
        self._backend.disconnect()
        self.logger.info("Potentiostat disconnected (%s)", self._vendor)

    def health_check(self) -> bool:
        return self._backend.health_check()

    def get_status(self) -> PotentiostatStatus:
        return PotentiostatStatus(
            is_connected=self.health_check(),
            vendor=self._vendor,
            backend_name=self._backend.backend_name,
        )

    def measure_ocp(
        self,
        duration_s: float = _DEFAULT_OCP_DURATION_S,
        sample_period_s: float = _DEFAULT_SAMPLE_PERIOD_S,
    ) -> OCPResult:
        self._validate_duration_and_period(duration_s, sample_period_s)
        return self._backend.measure_ocp(
            duration_s=duration_s,
            sample_period_s=sample_period_s,
        )

    def run_chronoamperometry(
        self,
        step_potential_v: float,
        duration_s: float,
        sample_period_s: float = _DEFAULT_SAMPLE_PERIOD_S,
        current_sensitivity_a: float = _DEFAULT_CA_CURRENT_SENSITIVITY_A,
        second_working_electrode_potential_v: float | None = None,
    ) -> ChronoAmperometryResult:
        self._validate_duration_and_period(duration_s, sample_period_s)
        return self._backend.run_chronoamperometry(
            step_potential_v=step_potential_v,
            duration_s=duration_s,
            sample_period_s=sample_period_s,
            current_sensitivity_a=current_sensitivity_a,
            second_working_electrode_potential_v=second_working_electrode_potential_v,
        )

    def run_cyclic_voltammetry(
        self,
        initial_potential_v: float,
        vertex_potential_1_v: float,
        vertex_potential_2_v: float,
        final_potential_v: float,
        scan_rate_v_s: float,
        step_size_v: float,
        cycles: int = 1,
        current_sensitivity_a: float = _DEFAULT_CA_CURRENT_SENSITIVITY_A,
    ) -> CyclicVoltammetryResult:
        if scan_rate_v_s <= 0:
            raise PotentiostatConfigError("scan_rate_v_s must be > 0")
        if step_size_v <= 0:
            raise PotentiostatConfigError("step_size_v must be > 0")
        if cycles < 1:
            raise PotentiostatConfigError("cycles must be >= 1")
        return self._backend.run_cyclic_voltammetry(
            initial_potential_v=initial_potential_v,
            vertex_potential_1_v=vertex_potential_1_v,
            vertex_potential_2_v=vertex_potential_2_v,
            final_potential_v=final_potential_v,
            scan_rate_v_s=scan_rate_v_s,
            step_size_v=step_size_v,
            cycles=cycles,
            current_sensitivity_a=current_sensitivity_a,
        )

    def measure(
        self,
        duration_s: float = _DEFAULT_OCP_DURATION_S,
        sample_period_s: float = _DEFAULT_SAMPLE_PERIOD_S,
    ) -> OCPResult:
        """Protocol-compatible default measurement alias for OCP."""
        return self.measure_ocp(duration_s=duration_s, sample_period_s=sample_period_s)

    @staticmethod
    def _validate_duration_and_period(duration_s: float, sample_period_s: float) -> None:
        if duration_s <= 0:
            raise PotentiostatConfigError("duration_s must be > 0")
        if sample_period_s <= 0:
            raise PotentiostatConfigError("sample_period_s must be > 0")

    @staticmethod
    def _build_backend(
        vendor: str,
        offline: bool,
        emstat_model: str,
        emstat_data_directory: str,
        emstat_verbose: int,
        gamry_pump_timeout_s: float,
    ) -> _PotentiostatBackend:
        if offline:
            return _OfflinePotentiostatBackend(vendor=vendor)
        if vendor == "emstat":
            return _EmstatBackend(
                vendor=vendor,
                model=emstat_model,
                data_directory=emstat_data_directory,
                verbose=emstat_verbose,
            )
        return _GamryBackend(vendor=vendor, pump_timeout_s=gamry_pump_timeout_s)
