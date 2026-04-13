"""Tests for Potentiostat driver: constructor, offline mode, and mocked online mode.

The online-mode tests never touch the real SquidstatPyLibrary. They replace
``_load_qt_bindings`` with a helper that returns a ``_QtBindings`` assembled
from ``MagicMock``s, so the driver's Qt plumbing can be exercised
deterministically.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from instruments.potentiostat.driver import Potentiostat, _QtBindings
from instruments.potentiostat.exceptions import (
    PotentiostatCommandError,
    PotentiostatConfigError,
    PotentiostatConnectionError,
    PotentiostatTimeoutError,
)
from instruments.potentiostat.models import (
    CAParams, CAResult,
    CPParams, CPResult,
    CVParams, CVResult,
    OCPParams, OCPResult,
)


# --- Constructor --------------------------------------------------------------


class TestConstructor:

    def test_defaults(self):
        p = Potentiostat()
        assert p.name == "Potentiostat"
        assert p._channel == 0
        assert p._port == ""
        assert p._offline is False

    def test_name_override(self):
        p = Potentiostat(name="station_a")
        assert p.name == "station_a"

    def test_offsets_propagate_to_base(self):
        p = Potentiostat(offset_x=1.5, offset_y=-2.0, depth=3.0, measurement_height=4.0)
        assert p.offset_x == 1.5
        assert p.offset_y == -2.0
        assert p.depth == 3.0
        assert p.measurement_height == 4.0

    def test_negative_channel_rejected(self):
        with pytest.raises(PotentiostatConfigError, match="channel"):
            Potentiostat(channel=-1)


# --- Offline mode -------------------------------------------------------------


class TestOfflineLifecycle:

    def test_connect_and_disconnect_are_noops(self):
        p = Potentiostat(offline=True)
        p.connect()
        p.disconnect()  # must not raise

    def test_health_check_true_in_offline(self):
        p = Potentiostat(offline=True)
        assert p.health_check() is True

    def test_run_cv_offline_returns_result_with_aligned_arrays(self):
        p = Potentiostat(offline=True)
        p.connect()
        result = p.run_cv(
            CVParams(
                start_V=0.0, vertex1_V=0.5, vertex2_V=-0.5, end_V=0.0,
                scan_rate_V_per_s=0.1, cycles=2, sampling_interval_s=0.05,
            )
        )
        assert isinstance(result, CVResult)
        n = result.potentials_V.size
        assert result.currents_A.shape == (n,)
        assert result.timestamps_s.shape == (n,)
        assert result.cycle_index.shape == (n,)
        assert set(np.unique(result.cycle_index).tolist()) == {0, 1}
        assert result.metadata["aborted"] is False
        assert result.metadata["device_id"] == "offline"

    def test_run_cv_offline_is_deterministic(self):
        p1 = Potentiostat(offline=True)
        p2 = Potentiostat(offline=True)
        params = CVParams(0.0, 0.2, -0.2, 0.0, 0.05, cycles=1, sampling_interval_s=0.1)
        r1 = p1.run_cv(params)
        r2 = p2.run_cv(params)
        np.testing.assert_allclose(r1.currents_A, r2.currents_A)

    def test_run_ocp_offline(self):
        p = Potentiostat(offline=True)
        result = p.run_ocp(OCPParams(duration_s=1.0, sampling_interval_s=0.1))
        assert isinstance(result, OCPResult)
        assert result.potentials_V.size == result.timestamps_s.size == 10
        assert result.metadata["aborted"] is False

    def test_run_ca_offline(self):
        p = Potentiostat(offline=True)
        result = p.run_ca(CAParams(potential_V=0.6, duration_s=0.5, sampling_interval_s=0.05))
        assert isinstance(result, CAResult)
        assert np.allclose(result.potentials_V, 0.6)
        assert result.currents_A.size == 10

    def test_run_cp_offline(self):
        p = Potentiostat(offline=True)
        result = p.run_cp(CPParams(current_A=1e-3, duration_s=0.5, sampling_interval_s=0.05))
        assert isinstance(result, CPResult)
        assert np.allclose(result.currents_A, 1e-3)
        assert result.potentials_V.size == 10


# --- Online mode helpers ------------------------------------------------------


def _make_qt_mock_bindings(
    *,
    schedule_device_connected: bool = True,
    schedule_experiment_stopped: bool = True,
    dc_samples: list[tuple[float, float, float]] | None = None,
    new_element_breakpoints: list[int] | None = None,
):
    """Build a ``_QtBindings`` whose QEventLoop/QTimer fire pre-scripted events.

    The "event loop" here just executes queued callbacks synchronously when
    ``exec()`` is called. ``QTimer.singleShot`` appends a callback; a test can
    pre-queue signal emissions so that when the driver calls ``loop.exec()``
    the expected sequence fires and ``loop.quit()`` is invoked.
    """
    squidstat = MagicMock()
    tracker = MagicMock()
    handler = MagicMock()
    squidstat.AisDeviceTracker.Instance.return_value = tracker
    tracker.getInstrumentHandler.return_value = handler

    # Track signal slots for both tracker and handler.
    signal_registry: dict[tuple[str, str], list] = {}

    def _register_signal(owner_name: str, signal_name: str):
        sig = MagicMock()
        key = (owner_name, signal_name)
        signal_registry[key] = []
        sig.connect.side_effect = lambda slot, k=key: signal_registry[k].append(slot)
        sig.disconnect.side_effect = lambda slot, k=key: (
            signal_registry[k].remove(slot)
            if slot in signal_registry[k] else None
        )
        return sig

    tracker.newDeviceConnected = _register_signal("tracker", "newDeviceConnected")
    handler.activeDCDataReady = _register_signal("handler", "activeDCDataReady")
    handler.experimentNewElementStarting = _register_signal(
        "handler", "experimentNewElementStarting",
    )
    handler.experimentStopped = _register_signal("handler", "experimentStopped")

    # uploadExperimentToChannel / startUploadedExperiment return falsy on success.
    handler.uploadExperimentToChannel.return_value = 0
    handler.startUploadedExperiment.return_value = 0

    # QEventLoop that runs queued callbacks until quit.
    class _Loop:
        def __init__(self):
            self._queued: list = []
            self._quit = False

        def queue(self, fn):
            self._queued.append(fn)

        def quit(self):
            self._quit = True

        def exec(self):
            # Run queued callbacks until quit flag is set or queue empty.
            while self._queued and not self._quit:
                fn = self._queued.pop(0)
                fn()

    active_loop: dict[str, _Loop] = {}

    class _QEventLoopFactory:
        def __call__(self):
            loop = _Loop()
            active_loop["loop"] = loop
            # Auto-schedule the signal emissions that each test stage needs.
            # Iteration of the slot list happens at call time inside exec(),
            # by which point the driver has already wired its slots.
            if schedule_device_connected:
                loop.queue(
                    lambda: [
                        slot("SquidStatMock")
                        for slot in list(
                            signal_registry[("tracker", "newDeviceConnected")]
                        )
                    ]
                )
            if dc_samples is not None:
                for i, (v, cur, ts) in enumerate(dc_samples):
                    def _emit(v=v, cur=cur, ts=ts, i=i):
                        if new_element_breakpoints and i in new_element_breakpoints:
                            for slot in list(
                                signal_registry[
                                    ("handler", "experimentNewElementStarting")
                                ]
                            ):
                                slot(0, MagicMock(), MagicMock())
                        sample = MagicMock()
                        sample.workingElectrodeVoltage = v
                        sample.current = cur
                        sample.timestamp = ts
                        for slot in list(
                            signal_registry[("handler", "activeDCDataReady")]
                        ):
                            slot(0, sample)
                    loop.queue(_emit)
            if schedule_experiment_stopped:
                loop.queue(
                    lambda: [
                        slot(0, "completed")
                        for slot in list(
                            signal_registry[("handler", "experimentStopped")]
                        )
                    ]
                )
            return loop

    class _QTimer:
        @staticmethod
        def singleShot(_ms: int, callback):
            # For tests that want the timeout to fire, the test will NOT
            # schedule experiment_stopped; the queued callback just runs
            # last and calls quit (simulating timeout).
            loop = active_loop.get("loop")
            if loop is not None:
                loop.queue(callback)

    QCoreApplication = MagicMock()
    QCoreApplication.instance.return_value = None  # force creation
    QCoreApplication.return_value = MagicMock(name="app")

    bindings = _QtBindings(
        squidstat=squidstat,
        QCoreApplication=QCoreApplication,
        QEventLoop=_QEventLoopFactory(),
        QTimer=_QTimer,
    )
    return bindings, tracker, handler


class TestConnectMissingDependency:

    def test_raises_connection_error_with_install_hint(self):
        # Patch the real loader: simulate ImportError on SquidstatPyLibrary.
        def _raise(*_a, **_k):
            raise PotentiostatConnectionError(
                "SquidstatPyLibrary is not installed. "
                "Install with: pip install 'cubos[potentiostat]'"
            )

        with patch(
            "instruments.potentiostat.driver._load_qt_bindings",
            side_effect=_raise,
        ):
            p = Potentiostat(port="COM3")
            with pytest.raises(PotentiostatConnectionError, match=r"\[potentiostat\]"):
                p.connect()


class TestConnectOnline:

    def test_connects_and_stores_handler(self):
        bindings, tracker, handler = _make_qt_mock_bindings()
        with patch(
            "instruments.potentiostat.driver._load_qt_bindings",
            return_value=bindings,
        ):
            p = Potentiostat(port="COM3")
            p.connect()
        assert p._handler is handler
        assert p._tracker is tracker
        assert p._device_id == "SquidStatMock"
        tracker.connectToDeviceOnComPort.assert_called_once_with("COM3")

    def test_no_device_raises_timeout_error_style(self):
        bindings, tracker, _handler = _make_qt_mock_bindings(
            schedule_device_connected=False,
        )
        with patch(
            "instruments.potentiostat.driver._load_qt_bindings",
            return_value=bindings,
        ):
            p = Potentiostat(port="COM3", command_timeout=0.01)
            with pytest.raises(PotentiostatConnectionError, match="No SquidStat device"):
                p.connect()

    def test_health_check_false_before_connect(self):
        p = Potentiostat(port="COM3")
        assert p.health_check() is False


# --- Online run_cv ------------------------------------------------------------


class TestRunCVOnline:

    def test_collects_samples_and_increments_cycle_on_new_element(self):
        samples = [
            (0.0, 1e-6, 0.00),
            (0.1, 2e-6, 0.01),
            (0.2, 3e-6, 0.02),  # new element boundary fires BEFORE this sample
            (0.3, 4e-6, 0.03),
        ]
        bindings, _tracker, handler = _make_qt_mock_bindings(
            dc_samples=samples,
            new_element_breakpoints=[2],
        )
        with patch(
            "instruments.potentiostat.driver._load_qt_bindings",
            return_value=bindings,
        ):
            p = Potentiostat(port="COM3")
            p.connect()
            result = p.run_cv(
                CVParams(0.0, 0.5, -0.5, 0.0, 0.05, cycles=2, sampling_interval_s=0.01)
            )

        assert isinstance(result, CVResult)
        np.testing.assert_allclose(result.potentials_V, [0.0, 0.1, 0.2, 0.3])
        np.testing.assert_allclose(result.currents_A, [1e-6, 2e-6, 3e-6, 4e-6])
        np.testing.assert_array_equal(result.cycle_index, [0, 0, 1, 1])
        assert result.metadata["aborted"] is False
        assert result.metadata["channel"] == 0
        handler.uploadExperimentToChannel.assert_called_once()
        handler.startUploadedExperiment.assert_called_once_with(0)

    def test_run_without_connect_raises_command_error(self):
        p = Potentiostat()
        with pytest.raises(PotentiostatCommandError, match="not connected"):
            p.run_cv(CVParams(0.0, 0.5, -0.5, 0.0, 0.05))


# --- Timeout -----------------------------------------------------------------


class TestExperimentTimeout:

    def test_timeout_raises_and_stops_experiment(self):
        # Omit experiment_stopped emission so only the QTimer fires.
        bindings, _tracker, handler = _make_qt_mock_bindings(
            schedule_experiment_stopped=False,
        )
        with patch(
            "instruments.potentiostat.driver._load_qt_bindings",
            return_value=bindings,
        ):
            p = Potentiostat(port="COM3", command_timeout=0.01)
            p.connect()
            with pytest.raises(PotentiostatTimeoutError, match="timeout"):
                p.run_ocp(OCPParams(duration_s=1.0))
        handler.stopExperiment.assert_called_once_with(0)


# --- Disconnect --------------------------------------------------------------


class TestDisconnect:

    def test_clears_state_and_calls_tracker(self):
        bindings, tracker, _handler = _make_qt_mock_bindings()
        with patch(
            "instruments.potentiostat.driver._load_qt_bindings",
            return_value=bindings,
        ):
            p = Potentiostat(port="COM3")
            p.connect()
            p.disconnect()
        tracker.disconnectFromDevice.assert_called_once_with("SquidStatMock")
        assert p._handler is None
        assert p._tracker is None
        assert p._device_id is None
