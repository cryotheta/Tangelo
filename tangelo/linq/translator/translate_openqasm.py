# Copyright 2021 Good Chemistry Company.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Functions helping with quantum circuit format conversion between abstract
format and a subset of the openqasm format (the format generated by IBM openqasm
functionalities in qiskit).

In order to produce an equivalent circuit for the target backend, it is
necessary to account for:
- how the gate names differ between the source backend to the target backend.
- how the order and conventions for some of the inputs to the gate operations
    may also differ.
"""

import re
from math import pi
from tangelo.linq import Gate, Circuit


def get_openqasm_gates():
    """Map gate name of the abstract format to the equivalent gate name used in
    openqasm OpenQASM is a general format that allows users to express a quantum
    program, define conditional operations manipulating quantum and qubit
    registers, as well as defining new quantum unitaries. We however make the
    choice here to support well-known gate operations.
    """

    GATE_OPENQASM = dict()
    for name in {"H", "X", "Y", "Z", "S", "T", "RX", "RY", "RZ", "MEASURE",
                 "CZ", "CY", "CRZ", "SWAP", "CSWAP"}:
        GATE_OPENQASM[name] = name.lower()
    GATE_OPENQASM["CNOT"] = "cx"
    GATE_OPENQASM["PHASE"] = "p"
    GATE_OPENQASM["CPHASE"] = "cp"

    return GATE_OPENQASM


def translate_openqasm(source_circuit):
    """Take in an abstract circuit, return a OpenQASM 2.0 string using IBM
    Qiskit (they are the reference for OpenQASM).

    Args:
        source_circuit: quantum circuit in the abstract format.

    Returns:
        str: the corresponding OpenQASM program, as per IBM Qiskit.
    """
    from .translate_qiskit import translate_qiskit

    return translate_qiskit(source_circuit).qasm()


def _translate_openqasm2abs(openqasm_str):
    """Take an OpenQASM 2.0 string as input (as defined by IBM Qiskit), return
    the equivalent abstract circuit. Only a subset of OpenQASM supported, mostly
    to be able to go back and forth QASM and abstract representations to
    leverage tools and innovation implemented to work in the QASM format. Not
    designed to support elaborate QASM programs defining their own operations.
    Compatible with qiskit.QuantumCircuit.from_qasm method.

    Assumes single-qubit measurement instructions only. Final qubit register
    measurement is implicit.

    Args:
        openqasm_string(str): an OpenQASM program, as a string, as defined by
            IBM Qiskit.

    Returns:
        Circuit: corresponding quantum circuit in the abstract format.
    """

    # Get dictionary of gate mapping, as the reverse dictionary of abs -> openqasm translation
    GATE_OPENQASM = get_openqasm_gates()
    gate_mapping = {v: k for k, v in GATE_OPENQASM.items()}

    def parse_param(s):
        """ Parse parameter as either a float or a string if it's not a float """
        try:
            return float(s)
        except ValueError:
            return s

    # Get number of qubits, extract gate operations
    n_qubits = int(re.findall('qreg q\[(\d+)\];', openqasm_str)[0])
    openqasm_gates = openqasm_str.split(f"qreg q[{n_qubits}];\ncreg c[{n_qubits}];")[-1]
    openqasm_gates = [instruction for instruction in openqasm_gates.split("\n") if instruction]

    # Translate gates
    abs_circ = Circuit()
    for openqasm_gate in openqasm_gates:

        # Extract gate name, qubit indices and parameter value (single parameter for now)
        gate_name = re.split('\s|\(', openqasm_gate)[0]
        qubit_indices = [int(index) for index in re.findall('q\[(\d+)\]', openqasm_gate)]
        parameters = [parse_param(index) for index in re.findall('\((.*)\)', openqasm_gate)]
        # TODO: controlled operation, will need to store value in classical register
        #  bit_indices = [int(index) for index in re.findall('c\[(\d+)\]', openqasm_gate)]

        if gate_name in {"h", "x", "y", "z", "s", "t", "measure"}:
            gate = Gate(gate_mapping[gate_name], qubit_indices[0])
        elif gate_name in {"rx", "ry", "rz", "p"}:
            gate = Gate(gate_mapping[gate_name], qubit_indices[0], parameter=eval(str(parameters[0])))
        # TODO: Rethink the use of enums for gates to set the equality CX=CNOT and enable other refactoring
        elif gate_name in {"cx", "cz", "cy"}:
            gate = Gate(gate_mapping[gate_name], qubit_indices[1], control=qubit_indices[0])
        elif gate_name in {"crz", "cp"}:
            gate = Gate(gate_mapping[gate_name], qubit_indices[1], control=qubit_indices[0], parameter=eval(str(parameters[0])))
        elif gate_name in {"swap"}:
            gate = Gate(gate_mapping[gate_name], [qubit_indices[0], qubit_indices[1]])
        elif gate_name in {"cswap"}:
            gate = Gate(gate_mapping[gate_name], [qubit_indices[1], qubit_indices[2]], control=qubit_indices[0])
        else:
            raise ValueError(f"Gate '{gate_name}' not supported with openqasm translation")
        abs_circ.add_gate(gate)

    return abs_circ
