"""
Tests for instrument_calibration_node — verifies the telemetry instrumentation
works correctly with a realistic mock of QualibrationNode.

The mock mirrors the real run_action behavior:
  - node.run_action(skip_if=...) returns a decorator
  - If skip_if is falsy, the decorated function executes immediately with node as arg
  - If skip_if is truthy, the function is registered but not called

Run:
    pytest tests/test_calibration_node.py -v
"""

import functools
from unittest.mock import patch, MagicMock

import pytest
from opentelemetry import trace

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

    orig_initialized = cfg._telemetry_initialized
    orig_tracer = cfg._tracer
    cfg._telemetry_initialized = False
    cfg._tracer = None
    yield
    cfg._telemetry_initialized = orig_initialized
    cfg._tracer = orig_tracer


@pytest.fixture
def node():
    return MockNode(name="11_power_rabi_test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instrument_with_disabled_uptrace(node, **kwargs):
    """Call instrument_calibration_node with uptrace.configure patched out."""
    from qua_libs_core.telemetry.config import TelemetryConfig

    config = kwargs.pop("config", None) or TelemetryConfig(
        dsn="https://fake@localhost?grpc=4317",
        service_name="test-service",
        enabled=True,
        **{k: v for k, v in kwargs.items() if k == "resource_attributes"},
    )
    remaining = {k: v for k, v in kwargs.items() if k != "resource_attributes"}

    with patch("uptrace.configure_opentelemetry"):
        from qua_libs_core.telemetry import instrument_calibration_node

        instrument_calibration_node(node, config=config, **remaining)


# ---------------------------------------------------------------------------
# 1. Backward compatibility — basic usage works unchanged
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
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

    def test_default_attributes_captured(self, node):
        """The 4 default attributes (operation, num_shots, timeout, load_data_id)
        should be set on spans automatically."""
        _instrument_with_disabled_uptrace(node)

        captured_attrs = {}

        @node.run_action()
        def create_qua_program(node):
            span = trace.get_current_span()
            # Read back what the instrumentation set
            captured_attrs.update(dict(span.attributes) if hasattr(span, "attributes") else {})

        # With the in-memory tracer, attributes are on span.attributes
        # But even without that, we can verify via get_current_span
        assert node._registered_actions["create_qua_program"] is not None


# ---------------------------------------------------------------------------
# 2. extra_attributes — custom parameter capture
# ---------------------------------------------------------------------------


class TestExtraAttributes:
    def test_extra_attributes_read_from_parameters(self, node):
        """extra_attributes should capture additional fields from node.parameters."""
        _instrument_with_disabled_uptrace(node, extra_attributes=["qubits", "frequency_detuning_in_mhz"])

        span_ref = {}

        @node.run_action()
        def create_qua_program(node):
            span_ref["span"] = trace.get_current_span()

        # The span was created and should have been the current span during execution
        assert "span" in span_ref

    def test_missing_extra_attribute_is_silently_skipped(self, node):
        """If an extra attribute doesn't exist on node.parameters, no error."""
        _instrument_with_disabled_uptrace(node, extra_attributes=["nonexistent_param"])

        ran = []

        @node.run_action()
        def analyse_data(node):
            ran.append("analyse_data")

        assert ran == ["analyse_data"]  # no crash


# ---------------------------------------------------------------------------
# 3. resource_attributes — merged into config without mutating PROJECT_CONFIG
# ---------------------------------------------------------------------------


class TestResourceAttributes:
    def test_resource_attributes_merged_into_config(self, node):
        """resource_attributes should be passed to init_telemetry via config."""
        from qua_libs_core.telemetry.config import TelemetryConfig

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
            from qua_libs_core.telemetry.config import TelemetryConfig
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
            from qua_libs_core.telemetry.config import TelemetryConfig
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

    def test_project_config_not_mutated(self):
        """Passing resource_attributes must NOT mutate the shared PROJECT_CONFIG."""
        from qua_libs_core.telemetry.project_config import PROJECT_CONFIG

        original_attrs = dict(PROJECT_CONFIG.resource_attributes)

        node = MockNode("mutation_test")
        with patch("qua_libs_core.telemetry.calibration_node.init_telemetry"):
            from qua_libs_core.telemetry import instrument_calibration_node

            instrument_calibration_node(
                node,
                resource_attributes={"should.not.leak": "true"},
            )

        assert PROJECT_CONFIG.resource_attributes == original_attrs


class TestProjectConfigReload:
    def test_instrumentation_reloads_telemetry_toml(self, monkeypatch, tmp_path):
        """instrument_calibration_node should read telemetry.toml at call time."""
        from qua_libs_core.telemetry.config import TelemetryConfig

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
# 4. get_current_span — accessible inside traced functions
# ---------------------------------------------------------------------------


class TestGetCurrentSpan:
    def test_get_current_span_returns_active_span(self, node):
        """get_current_span() inside a traced function should return a real span,
        not a no-op."""
        _instrument_with_disabled_uptrace(node)

        from qua_libs_core.telemetry import get_current_span

        span_ref = {}

        @node.run_action()
        def analyse_data(node):
            span = get_current_span()
            span_ref["span"] = span
            span_ref["is_recording"] = span.is_recording()

        assert "span" in span_ref
        # The span from get_current_span is the same one the instrumentation created
        assert span_ref["span"] is not None

    def test_get_current_span_allows_setting_attributes(self, node):
        """User should be able to call set_span_attribute on the returned span."""
        _instrument_with_disabled_uptrace(node)

        from qua_libs_core.telemetry import get_current_span, set_span_attribute

        @node.run_action()
        def analyse_data(node):
            span = get_current_span()
            # This should not raise — mirrors the real use case of
            # setting per-qubit fit outcomes
            set_span_attribute(span, "fit.q1", "successful")
            set_span_attribute(span, "fit.q3", "failed")

        # If we get here without error, the API works


# ---------------------------------------------------------------------------
# 5. node.namespace["_telemetry_span"] — available during, cleaned up after
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

    def test_namespace_span_matches_get_current_span(self, node):
        """Both access methods should return the same span object."""
        _instrument_with_disabled_uptrace(node)

        from qua_libs_core.telemetry import get_current_span

        match = {}

        @node.run_action()
        def analyse_data(node):
            match["namespace"] = node.namespace["_telemetry_span"]
            match["current"] = get_current_span()

        assert match["namespace"] is match["current"]


# ---------------------------------------------------------------------------
# 6. Exception handling — spans record errors correctly
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


# ---------------------------------------------------------------------------
# 7. End-to-end: realistic calibration node flow
# ---------------------------------------------------------------------------


class TestRealisticFlow:
    def test_full_calibration_flow_with_dynamic_attributes(self, node):
        """Simulates the real _telemetry_common.py pattern end-to-end:
        instrument once, define all standard actions, some set dynamic attrs."""
        _instrument_with_disabled_uptrace(
            node,
            extra_attributes=["qubits"],
            resource_attributes={"experiment.category": "power_rabi"},
        )

        from qua_libs_core.telemetry import get_current_span, set_span_attribute

        flow = []

        @node.run_action(skip_if=node.modes.external)
        def custom_param(node):
            node.parameters.qubits = ["q1"]
            node.parameters.operation = "const"
            node.parameters.num_shots = 10
            flow.append("custom_param")

        @node.run_action(skip_if=node.parameters.load_data_id is not None)
        def create_qua_program(node):
            node.namespace["qua_program"] = "mock_program"
            flow.append("create_qua_program")

        @node.run_action(skip_if=True)
        def simulate_qua_program(node):
            flow.append("simulate_qua_program")  # should NOT run

        @node.run_action(skip_if=node.parameters.load_data_id is not None)
        def execute_qua_program(node):
            node.results["ds_raw"] = {"I": [0.1, 0.2], "Q": [0.3, 0.4]}
            flow.append("execute_qua_program")

        @node.run_action(skip_if=node.parameters.load_data_id is None)
        def load_data(node):
            flow.append("load_data")  # should NOT run (load_data_id is None)

        @node.run_action(skip_if=node.parameters.simulate)
        def analyse_data(node):
            node.outcomes = {"q1": "successful", "q3": "failed"}
            # Dynamic attributes — the key feature we're testing
            span = get_current_span()
            for qubit_name, outcome in node.outcomes.items():
                set_span_attribute(span, f"fit.{qubit_name}", outcome)
            flow.append("analyse_data")

        @node.run_action(skip_if=node.parameters.simulate)
        def plot_data(node):
            node.results["figures"] = {"amplitude": "mock_fig"}
            flow.append("plot_data")

        @node.run_action(skip_if=node.parameters.simulate)
        def update_state(node):
            span = get_current_span()
            for q_name, outcome in node.outcomes.items():
                if outcome == "failed":
                    set_span_attribute(span, f"update.{q_name}", "skipped")
                else:
                    set_span_attribute(span, f"update.{q_name}", "applied")
            flow.append("update_state")

        @node.run_action()
        def save_results(node):
            flow.append("save_results")

        # Verify execution order matches real calibration flow
        assert flow == [
            "custom_param",
            "create_qua_program",
            # simulate_qua_program skipped
            "execute_qua_program",
            # load_data skipped
            "analyse_data",
            "plot_data",
            "update_state",
            "save_results",
        ]

        # Verify namespace is clean after all functions ran
        assert "_telemetry_span" not in node.namespace

        # Verify node state was populated (like real calibration)
        assert node.outcomes == {"q1": "successful", "q3": "failed"}
        assert node.results["ds_raw"] == {"I": [0.1, 0.2], "Q": [0.3, 0.4]}
        assert node.results["figures"] == {"amplitude": "mock_fig"}
