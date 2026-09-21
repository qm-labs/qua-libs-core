"""
basic-digital-output.py: introduction to digital output (trigger out)
Author: Gal Winer - Quantum Machines
Created: 6/1/2021
Revised by Tomer Feld
Revision date: 04/04/2022
"""

from qm import QuantumMachinesManager
from qm.qua import *
from qm import SimulationConfig
from configuration import *
from qua_libs_core.telemetry import (
    start_qca_telemetry,
    trace_get_simulated_samples,
    trace_qmm,
    trace_simulate,
)

qop_ip = None
telemetry = start_qca_telemetry(__file__, resource_attributes={"experiment.category": "tutorial"})
qmm = trace_qmm(QuantumMachinesManager)(host=qop_ip)

with program() as prog:
    play("const", "qe1")
    wait(500, "qe2")
    play("const", "qe2")
    wait(500, "qe2")
    play("const_trig", "qe2")
    wait(500, "qe2")
    play("const_stutter", "qe2")


job = trace_simulate(qmm.simulate)(config, prog, SimulationConfig(int(3000)))  # in clock cycles, 4 ns

samples = trace_get_simulated_samples(job.get_simulated_samples)()
samples.con1.plot()

telemetry.end()
