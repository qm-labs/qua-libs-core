"""
hello_octave.py: template for basic usage of the Octave
"""

from qm import QuantumMachinesManager
from qm.qua import *
from qm.octave import *
from configuration import *
from qm import SimulationConfig
from qua_libs_core.telemetry import (
    start_qca_telemetry,
    trace_execute,
    trace_get_simulated_samples,
    trace_open_qm,
    trace_qmm,
    trace_simulate,
)
import time


###################################
# Open Communication with the QOP #
###################################
telemetry = start_qca_telemetry(__file__, resource_attributes={"experiment.category": "tutorial"})
qmm = trace_qmm(QuantumMachinesManager)(host=qop_ip, port=qop_port, octave=octave_config)

###################
# The QUA program #
###################
with program() as hello_octave:
    with infinite_loop_():
        play("cw" * amp(0.5), "qe1")
        play("cw" * amp(0.5), "qe2")

#######################################
# Execute or Simulate the QUA program #
#######################################
simulate = False
if simulate:
    simulation_config = SimulationConfig(duration=400)  # in clock cycles
    job_sim = trace_simulate(qmm.simulate)(config, hello_octave, simulation_config)
    trace_get_simulated_samples(job_sim.get_simulated_samples)().con1.plot()
else:
    qm = trace_open_qm(qmm.open_qm)(config)
    job = trace_execute(qm.execute)(hello_octave)
    # Execute does not block python! As this is an infinite loop, the job would run forever.
    # In this case, we've put a 10 seconds sleep and then halted the job.
    time.sleep(10)
    job.halt()

telemetry.end()
