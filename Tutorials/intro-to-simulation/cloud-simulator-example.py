from qm import QuantumMachinesManager, SimulationConfig
from qm.qua import play, program
from qm_saas import QoPVersion, QmSaas
from qua_libs_core.telemetry import (
    start_qca_telemetry,
    trace_get_simulated_samples,
    trace_open_qm,
    trace_qmm,
    trace_simulate,
)

# for qm-saas version 1.1.1

# Define quantum machine configuration dictionary
config = {
    "version": 1,
    "controllers": {
        "con1": {
            "analog_outputs": {
                1: {"offset": +0.0},
            },
        }
    },
    "elements": {
        "qe1": {
            "singleInput": {"port": ("con1", 1)},
            "intermediate_frequency": 5e6,
            "operations": {
                "playOp": "constPulse",
            },
        },
    },
    "pulses": {
        "constPulse": {
            "operation": "control",
            "length": 1000,  # in ns
            "waveforms": {"single": "const_wf"},
        },
    },
    "waveforms": {
        "const_wf": {"type": "constant", "sample": 0.2},
    },
}

# ======================================================================================================================
# Description: Use default host and port for the QOP simulator. Email and password are mandatory.
#              Using the context manager ensures them simulator instance is closed properly.
# ======================================================================================================================

# These should be changed to your credentials.
email = "john.doe@mail.com"
password = "Password_given_by_QM"

# Initialize QOP simulator client
client = QmSaas(email=email, password=password)

# Choose your QOP version (QOP2.x.y or QOP3.x.y)
# if you choose QOP3.x.y, make sure you are using an adequate config.
version = QoPVersion.v2_2_2

with client.simulator(version=version) as instance:  # Specify the QOP version
    telemetry = start_qca_telemetry(__file__, resource_attributes={"experiment.category": "tutorial"})
    # Initialize QuantumMachinesManager with the simulation instance details
    qmm = trace_qmm(QuantumMachinesManager)(
        host=instance.host, port=instance.port, connection_headers=instance.default_connection_headers
    )

    # Define a QUA program
    with program() as prog:
        play("playOp", "qe1")

    # Open quantum machine with the provided configuration and simulate the QUA program
    qm = trace_open_qm(qmm.open_qm)(config)
    job = trace_simulate(qm.simulate)(prog, SimulationConfig(int(1000)))

    # Retrieve and handle simulated samples
    samples = trace_get_simulated_samples(job.get_simulated_samples)()
    print("Test passed")
    telemetry.end()

# analysis of simulation
# do something with samples
