"""Arithmetic machine package.

Provides a tiny virtual machine that executes a configurable assembly
language made only of arithmetic expressions (addition, subtraction,
multiplication and division)."""

from .machine import ArithmeticMachine, InstructionCall, MachineError

__all__ = [
    "ArithmeticMachine",
    "InstructionCall",
    "MachineError",
]
