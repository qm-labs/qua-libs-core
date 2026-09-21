"""Tests for qua_libs_core.telemetry.calibration_node."""

import functools
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Realistic mock of QualibrationNode
# ---------------------------------------------------------------------------


class MockParameters:
    """Mimics a calibration node's Parameters dataclass."""

    def __init__(self):
        self.operation = "x180"
        self.num_shots = 100
        self.timeout = 300
        self.load_data_id = None
        self.simulate = False
        # Extra params that a real node might have
        self.qubits = ["q1", "q3"]
        self.frequency_detuning_in_mhz = 5.0


class MockModes:
    external = False


class MockNode:
    """
    Mimics QualibrationNode with a realistic run_action that:
      - accepts skip_if
      - returns a decorator
      - immediately calls the function (with node as arg) if skip_if is falsy
    This matches the real ActionManager.register_action behavior.
    """

    def __init__(self, name="test_node"):
        self.name = name
        self.parameters = MockParameters()
        self.namespace = {}
        self.results = {}
        self.outcomes = {}
        self.modes = MockModes()
        self._registered_actions = {}
        self._call_log = []  # track which functions actually ran

    def run_action(self, func=None, *, skip_if=False):
        """Mirror of QualibrationNode.run_action."""
        node = self

        def decorator(fn):
            node._registered_actions[fn.__name__] = fn

            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                return fn(node, *args, **kwargs)

            if not skip_if:
                wrapper()
            return wrapper

        if func is not None:
            return decorator(func)
        return decorator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_telemetry_globals():
    """Reset the module-level globals so each test starts clean."""
    import qua_libs_core.telemetry.config as cfg

    orig = cfg._runtime
    cfg._runtime = None
    yield
    cfg._runtime = orig


@pytest.fixture
def node():
    return MockNode(name="11_power_rabi_test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instrument_with_disabled_uptrace(node, **kwargs):
    """Call instrument_calibration_node with uptrace.configure patched out."""
    import tempfile
    from pathlib import Path

    from qua_libs_core.telemetry.config_types import TelemetryConfig

    local_dir = Path(tempfile.mkdtemp())
    config = kwargs.pop("config", None) or TelemetryConfig(
        dsn="https://fake@localhost?grpc=4317",
        service_name="test-service",
        enabled=True,
        local_path=str(local_dir / "traces.sqlite"),
        **{k: v for k, v in kwargs.items() if k == "resource_attributes"},
    )
    remaining = {k: v for k, v in kwargs.items() if k != "resource_attributes"}

    with patch("uptrace.configure_opentelemetry"):
        from qua_libs_core.telemetry import instrument_calibration_node

        instrument_calibration_node(node, config=config, **remaining)


# ---------------------------------------------------------------------------
# 1. Basic usage
# ---------------------------------------------------------------------------


class TestBasicUsage:
    def test_basic_instrumentation_runs_all_standard_functions(self, node):
        """instrument_calibration_node(node) should work with zero extra args,
        exactly as existing _common.py files use it."""
        _instrument_with_disabled_uptrace(node)

        ran = []

        @node.run_action()
        def create_qua_program(node):
            ran.append("create_qua_program")

        @node.run_action()
        def analyse_data(node):
            ran.append("analyse_data")

        @node.run_action()
        def save_results(node):
            ran.append("save_results")

        assert ran == ["create_qua_program", "analyse_data", "save_results"]

    def test_skip_if_respected(self, node):
        """Functions with skip_if=True should NOT run."""
        _instrument_with_disabled_uptrace(node)

        ran = []

        @node.run_action(skip_if=True)
        def simulate_qua_program(node):
            ran.append("simulate_qua_program")

        @node.run_action()
        def analyse_data(node):
            ran.append("analyse_data")

        assert ran == ["analyse_data"]

    def test_non_standard_functions_pass_through(self, node):
        """Functions not in STANDARD_FUNCTIONS should work without tracing."""
        _instrument_with_disabled_uptrace(node)

        ran = []

        @node.run_action()
        def my_custom_step(node):
            ran.append("my_custom_step")

        assert ran == ["my_custom_step"]


# ---------------------------------------------------------------------------
# 2. resource_attributes — merged onto a copy of the passed config
# ---------------------------------------------------------------------------


class TestResourceAttributes:
    def test_resource_attributes_merged_into_config(self, node):
        """resource_attributes should be passed to init_telemetry via config."""
        from qua_libs_core.telemetry.config_types import TelemetryConfig

        captured_config = {}

        def capture_init(config):
            captured_config["dsn"] = config.dsn
            captured_config["resource_attributes"] = config.resource_attributes

        with patch("qua_libs_core.telemetry.calibration_node.init_telemetry", side_effect=capture_init):
            from qua_libs_core.telemetry import instrument_calibration_node

            instrument_calibration_node(
                node,
                config=TelemetryConfig(
                    dsn="https://fake@localhost?grpc=4317",
                    service_name="test",
                    resource_attributes={"base.attr": "from_config"},
                ),
                resource_attributes={
                    "experiment.category": "power_rabi",
                },
            )

        # Both base and user-provided attributes should be present
        attrs = captured_config["resource_attributes"]
        assert attrs["base.attr"] == "from_config"
        assert attrs["experiment.category"] == "power_rabi"

    def test_auto_populated_node_name_and_run_at(self, node):
        """experiment.node and experiment.run_at should be auto-populated
        from node.name and current time without user specifying them."""
        captured_config = {}

        def capture_init(config):
            captured_config["resource_attributes"] = config.resource_attributes

        with patch("qua_libs_core.telemetry.calibration_node.init_telemetry", side_effect=capture_init):
            from qua_libs_core.telemetry.config_types import TelemetryConfig
            from qua_libs_core.telemetry import instrument_calibration_node

            instrument_calibration_node(
                node,
                config=TelemetryConfig(
                    dsn="https://fake@localhost?grpc=4317",
                    service_name="test",
                ),
            )

        attrs = captured_config["resource_attributes"]
        assert attrs["experiment.node"] == "11_power_rabi_test"
        assert "experiment.run_at" in attrs
        # Should be a timestamp string like "2026-03-26 12:00:00"
        assert len(attrs["experiment.run_at"]) == 19

    def test_user_can_override_auto_attributes(self, node):
        """User-provided resource_attributes should override the auto ones."""
        captured_config = {}

        def capture_init(config):
            captured_config["resource_attributes"] = config.resource_attributes

        with patch("qua_libs_core.telemetry.calibration_node.init_telemetry", side_effect=capture_init):
            from qua_libs_core.telemetry.config_types import TelemetryConfig
            from qua_libs_core.telemetry import instrument_calibration_node

            instrument_calibration_node(
                node,
                config=TelemetryConfig(
                    dsn="https://fake@localhost?grpc=4317",
                    service_name="test",
                ),
                resource_attributes={
                    "experiment.node": "custom_override_name",
                },
            )

        attrs = captured_config["resource_attributes"]
        assert attrs["experiment.node"] == "custom_override_name"

    def test_passed_config_is_not_mutated(self):
        """Passing resource_attributes must not mutate the caller's TelemetryConfig."""
        from qua_libs_core.telemetry.config_types import TelemetryConfig

        config = TelemetryConfig(enabled=True, dsn="https://fake@localhost?grpc=4317")
        original_attrs = dict(config.resource_attributes)

        node = MockNode("mutation_test")
        with patch("qua_libs_core.telemetry.calibration_node.init_telemetry"):
            from qua_libs_core.telemetry import instrument_calibration_node

            instrument_calibration_node(
                node,
                config=config,
                resource_attributes={"should.not.leak": "true"},
            )

        assert config.resource_attributes == original_attrs
        assert "should.not.leak" not in config.resource_attributes


class TestProjectConfigReload:
    def test_instrumentation_reloads_telemetry_toml(self, monkeypatch, tmp_path):
        """instrument_calibration_node should read telemetry.toml at call time."""
        from qua_libs_core.telemetry.config_types import TelemetryConfig

        config_dir = tmp_path / ".qua-libs"
        config_dir.mkdir()
        (config_dir / "telemetry.toml").write_text(
            """
[telemetry]
enabled = true
dsn = "http://token@localhost:14318?grpc=14317"
service_name = "from-file"
""",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        captured: dict[str, TelemetryConfig] = {}

        def capture_init(config):
            captured["config"] = config

        node = MockNode("reload_test")
        with patch("qua_libs_core.telemetry.calibration_node.init_telemetry", side_effect=capture_init):
            from qua_libs_core.telemetry import instrument_calibration_node

            instrument_calibration_node(node)

        assert captured["config"].enabled is True
        assert captured["config"].dsn == "http://token@localhost:14318?grpc=14317"
        assert captured["config"].service_name == "from-file"


# ---------------------------------------------------------------------------
# 3. node.namespace["_telemetry_span"] — available during, cleaned up after
# ---------------------------------------------------------------------------


class TestNamespaceSpan:
    def test_span_available_in_namespace_during_execution(self, node):
        """node.namespace['_telemetry_span'] should be set while a traced
        function is running."""
        _instrument_with_disabled_uptrace(node)

        captured = {}

        @node.run_action()
        def analyse_data(node):
            captured["span"] = node.namespace.get("_telemetry_span")
            captured["has_key"] = "_telemetry_span" in node.namespace

        assert captured["has_key"] is True
        assert captured["span"] is not None

    def test_span_cleaned_up_after_execution(self, node):
        """_telemetry_span should be removed from namespace after the function
        completes."""
        _instrument_with_disabled_uptrace(node)

        @node.run_action()
        def analyse_data(node):
            pass

        assert "_telemetry_span" not in node.namespace

    def test_span_cleaned_up_after_exception(self, node):
        """_telemetry_span should be removed even if the function raises."""
        _instrument_with_disabled_uptrace(node)

        with pytest.raises(ValueError, match="boom"):

            @node.run_action()
            def analyse_data(node):
                raise ValueError("boom")

        assert "_telemetry_span" not in node.namespace


# ---------------------------------------------------------------------------
# 4. Exception handling — spans record errors correctly
# ---------------------------------------------------------------------------


class TestExceptionHandling:
    def test_exception_propagates(self, node):
        """Exceptions should not be swallowed by the instrumentation."""
        _instrument_with_disabled_uptrace(node)

        with pytest.raises(RuntimeError, match="hardware timeout"):

            @node.run_action()
            def execute_qua_program(node):
                raise RuntimeError("hardware timeout")

    def test_subsequent_functions_still_work_after_exception(self, node):
        """After an exception in one function, the next function should
        still get proper instrumentation."""
        _instrument_with_disabled_uptrace(node)

        ran = []

        try:

            @node.run_action()
            def execute_qua_program(node):
                raise RuntimeError("fail")

        except RuntimeError:
            pass

        @node.run_action()
        def analyse_data(node):
            ran.append("analyse_data")
            assert "_telemetry_span" in node.namespace

        assert ran == ["analyse_data"]
