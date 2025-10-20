import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arithmetic_machine import ArithmeticMachine, MachineError


def run_program(source: str):
    machine = ArithmeticMachine()
    machine.load_program(source)
    machine.run()
    return machine


def test_simple_arithmetic():
    program = """
.define SUM3 dst a b c => a + b + c

SET R0 3
SET R1 4
SUM3 R2 R0 R1 5
PRINT R2
HALT
"""
    machine = run_program(program)
    assert machine.output == [12.0]
    assert machine.registers["R2"] == 12.0


def test_loop_with_jump():
    program = """
.define DEC dst src => src - 1

SET R0 3
SET R1 1
loop:
PRINT R0
SUB R0 R0 R1
JNZ R0 loop
HALT
"""
    machine = run_program(program)
    assert machine.output == [3.0, 2.0, 1.0]
    assert machine.registers["R0"] == 0.0


def test_division_by_zero():
    program = """
SET R0 5
SET R1 0
DIV R2 R0 R1
HALT
"""
    machine = ArithmeticMachine()
    machine.load_program(program)
    with pytest.raises(MachineError):
        machine.run()
