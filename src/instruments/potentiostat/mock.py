from instruments.potentiostat.driver import Potentiostat


class MockPotentiostat(Potentiostat):
    """Convenience offline potentiostat for tests and dry runs."""

    def __init__(self, vendor: str = "emstat", **kwargs):
        super().__init__(vendor=vendor, offline=True, **kwargs)
        self.command_history: list[str] = []

    def connect(self) -> None:
        self.command_history.append("connect")
        super().connect()

    def disconnect(self) -> None:
        self.command_history.append("disconnect")
        super().disconnect()

    def measure_ocp(self, *args, **kwargs):
        self.command_history.append("measure_ocp")
        return super().measure_ocp(*args, **kwargs)

    def run_chronoamperometry(self, *args, **kwargs):
        self.command_history.append("run_chronoamperometry")
        return super().run_chronoamperometry(*args, **kwargs)

    def run_cyclic_voltammetry(self, *args, **kwargs):
        self.command_history.append("run_cyclic_voltammetry")
        return super().run_cyclic_voltammetry(*args, **kwargs)
