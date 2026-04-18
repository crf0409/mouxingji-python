"""Core implementation of the arithmetic based model machine.

The machine executes a small assembly language consisting of arithmetic
expressions and a couple of control-flow instructions.  Users can define
new instructions either programmatically or directly inside an assembly
program using the ``.define`` directive.  All arithmetic is performed
using Python's ``+``, ``-``, ``*`` and ``/`` operators.
"""
from __future__ import annotations

from dataclasses import dataclass
import ast
from typing import Callable, Dict, Iterator, List, Optional, Sequence


class MachineError(RuntimeError):
    """Raised when the machine encounters an execution error."""


@dataclass
class InstructionCall:
    """Container describing a single instruction invocation."""

    name: str
    args: List[str]
    line_number: int


class _BaseInstruction:
    """Base class for all instruction specifications."""

    name: str

    def execute(self, machine: "ArithmeticMachine", call: InstructionCall) -> Optional[int]:
        """Execute the instruction.

        Parameters
        ----------
        machine:
            The machine executing the instruction.
        call:
            Metadata about the current invocation.

        Returns
        -------
        Optional[int]
            ``None`` to advance to the next instruction, or a program
            counter value to jump to.
        """

        raise NotImplementedError


class _ExpressionInstruction(_BaseInstruction):
    """Instruction defined by a pure arithmetic expression."""

    def __init__(self, name: str, arg_names: Sequence[str], expression: str, description: str = "") -> None:
        if not arg_names:
            raise ValueError("Arithmetic instructions require at least a destination argument.")
        self.name = name
        self.arg_names = list(arg_names)
        self.expression = expression
        self.description = description

    def execute(self, machine: "ArithmeticMachine", call: InstructionCall) -> Optional[int]:
        if len(call.args) != len(self.arg_names):
            raise MachineError(
                f"Instruction '{self.name}' expects {len(self.arg_names)} arguments but got {len(call.args)} "
                f"on line {call.line_number}."
            )
        env = {}
        for arg_name, token in zip(self.arg_names[1:], call.args[1:]):
            env[arg_name] = machine._resolve_value(token, call)
        result = machine._evaluate_expression(self.expression, env, call)
        machine._write_register(call.args[0], result, call)
        return None


class _HaltInstruction(_BaseInstruction):
    name = "HALT"

    def execute(self, machine: "ArithmeticMachine", call: InstructionCall) -> Optional[int]:
        machine.halted = True
        return None


class _JumpInstruction(_BaseInstruction):
    def __init__(self, name: str, condition: Callable[["ArithmeticMachine", InstructionCall], bool], doc: str = "") -> None:
        self.name = name
        self._condition = condition
        self.description = doc

    def execute(self, machine: "ArithmeticMachine", call: InstructionCall) -> Optional[int]:
        if len(call.args) != 1 and len(call.args) != 2:
            raise MachineError(
                f"Instruction '{self.name}' expects a label or a register and a label on line {call.line_number}."
            )
        if len(call.args) == 1:
            label = call.args[0]
            return machine._resolve_label(label, call)
        if self._condition(machine, call):
            label = call.args[1]
            return machine._resolve_label(label, call)
        return None


class _PrintInstruction(_BaseInstruction):
    name = "PRINT"

    def execute(self, machine: "ArithmeticMachine", call: InstructionCall) -> Optional[int]:
        if len(call.args) != 1:
            raise MachineError(f"PRINT expects a single argument on line {call.line_number}.")
        value = machine._resolve_value(call.args[0], call)
        machine.output.append(value)
        if machine.echo:
            print(value)
        return None


class ArithmeticMachine:
    """A simple arithmetic virtual machine with a customizable ISA."""

    def __init__(self, register_count: int = 8, echo: bool = False) -> None:
        self.registers: Dict[str, float] = {f"R{i}": 0.0 for i in range(register_count)}
        self.instructions: Dict[str, _BaseInstruction] = {}
        self.program: List[InstructionCall] = []
        self.labels: Dict[str, int] = {}
        self.pc: int = 0
        self.halted: bool = False
        self.output: List[float] = []
        self.echo = echo
        self._install_default_instructions()

    # ------------------------------------------------------------------
    # Instruction registration
    def _install_default_instructions(self) -> None:
        self.define_instruction("SET", ["dst", "value"], "value", "Assign a constant or register value.")
        self.define_instruction("ADD", ["dst", "lhs", "rhs"], "lhs + rhs", "Add two values.")
        self.define_instruction("SUB", ["dst", "lhs", "rhs"], "lhs - rhs", "Subtract rhs from lhs.")
        self.define_instruction("MUL", ["dst", "lhs", "rhs"], "lhs * rhs", "Multiply two values.")
        self.define_instruction("DIV", ["dst", "lhs", "rhs"], "lhs / rhs", "Divide lhs by rhs.")
        self.instructions[_HaltInstruction.name] = _HaltInstruction()
        self.instructions[_PrintInstruction.name] = _PrintInstruction()
        self.instructions["JMP"] = _JumpInstruction(
            "JMP",
            lambda machine, call: True,
            doc="Unconditional jump to a label.",
        )
        self.instructions["JZ"] = _JumpInstruction(
            "JZ",
            lambda machine, call: machine._resolve_value(call.args[0], call) == 0,
            doc="Jump when the provided value is zero.",
        )
        self.instructions["JNZ"] = _JumpInstruction(
            "JNZ",
            lambda machine, call: machine._resolve_value(call.args[0], call) != 0,
            doc="Jump when the provided value is non-zero.",
        )

    def define_instruction(
        self, name: str, arg_names: Sequence[str], expression: str, description: str = ""
    ) -> None:
        """Register a new arithmetic instruction.

        Parameters
        ----------
        name:
            Name of the instruction in assembly programs.
        arg_names:
            Ordered argument names; the first one is treated as the
            destination register.
        expression:
            Expression evaluated using only addition, subtraction,
            multiplication and division.  It can reference any argument
            after the destination.
        description:
            Optional help text.
        """

        normalized = name.upper()
        if normalized in self.instructions:
            raise ValueError(f"Instruction '{normalized}' is already defined.")
        self.instructions[normalized] = _ExpressionInstruction(normalized, arg_names, expression, description)

    # ------------------------------------------------------------------
    # Assembly parsing
    def load_program(self, source: str) -> None:
        """Parse assembly source code and load the resulting program."""

        self.program.clear()
        self.labels.clear()
        self.pc = 0
        self.halted = False
        self.output.clear()

        for line_number, raw_line in enumerate(source.splitlines(), start=1):
            line = raw_line.split("#", 1)[0].split(";", 1)[0].strip()
            if not line:
                continue
            if line.endswith(":"):
                label = line[:-1].strip()
                if not label:
                    raise MachineError(f"Empty label on line {line_number}.")
                if label in self.labels:
                    raise MachineError(f"Duplicate label '{label}' on line {line_number}.")
                self.labels[label] = len(self.program)
                continue
            if line.startswith(".define"):
                self._parse_define(line, line_number)
                continue
            parts = line.split()
            name = parts[0].upper()
            args = parts[1:]
            self.program.append(InstructionCall(name=name, args=args, line_number=line_number))

    def _parse_define(self, line: str, line_number: int) -> None:
        tokens = line.split()
        if len(tokens) < 4:
            raise MachineError(f"Invalid .define directive on line {line_number}.")
        name = tokens[1].upper()
        try:
            arrow_index = tokens.index("=>")
        except ValueError as exc:
            raise MachineError(f"Missing '=>' in .define directive on line {line_number}.") from exc
        arg_names = tokens[2:arrow_index]
        if not arg_names:
            raise MachineError(f".define for '{name}' requires at least one argument on line {line_number}.")
        expression = " ".join(tokens[arrow_index + 1 :])
        if not expression:
            raise MachineError(f".define for '{name}' is missing an expression on line {line_number}.")
        self.define_instruction(name, arg_names, expression)

    # ------------------------------------------------------------------
    # Execution helpers
    def _resolve_value(self, token: str, call: InstructionCall) -> float:
        token = token.upper()
        if token in self.registers:
            return self.registers[token]
        try:
            if "." in token:
                return float(token)
            return float(int(token, 10))
        except ValueError as exc:
            raise MachineError(f"Unknown operand '{token}' on line {call.line_number}.") from exc

    def _write_register(self, token: str, value: float, call: InstructionCall) -> None:
        token = token.upper()
        if token not in self.registers:
            raise MachineError(f"Unknown register '{token}' on line {call.line_number}.")
        self.registers[token] = value

    def _resolve_label(self, label: str, call: InstructionCall) -> int:
        if label not in self.labels:
            raise MachineError(f"Unknown label '{label}' on line {call.line_number}.")
        return self.labels[label]

    def _evaluate_expression(self, expression: str, env: Dict[str, float], call: InstructionCall) -> float:
        tree = ast.parse(expression, mode="eval")
        allowed_nodes = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Load,
            ast.Name,
            ast.Constant,
            ast.USub,
            ast.UAdd,
        )
        for node in ast.walk(tree):
            if not isinstance(node, allowed_nodes):
                raise MachineError(
                    f"Expression '{expression}' for instruction '{call.name}' contains unsupported syntax "
                    f"on line {call.line_number}."
                )
            if isinstance(node, ast.BinOp) and not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                raise MachineError(
                    f"Only +, -, * and / are allowed in instruction expressions (line {call.line_number})."
                )
        compiled = compile(tree, filename="<instruction>", mode="eval")
        try:
            return float(eval(compiled, {"__builtins__": {}}, env))
        except ZeroDivisionError as exc:
            raise MachineError(f"Division by zero on line {call.line_number}.") from exc
        except NameError as exc:
            raise MachineError(
                f"Unknown identifier in expression '{expression}' on line {call.line_number}."
            ) from exc

    # ------------------------------------------------------------------
    # Execution
    def reset(self) -> None:
        for key in self.registers:
            self.registers[key] = 0.0
        self.pc = 0
        self.halted = False
        self.output.clear()

    def run(self, max_steps: Optional[int] = None) -> None:
        steps = 0
        while not self.halted and self.pc < len(self.program):
            call = self.program[self.pc]
            instruction = self.instructions.get(call.name)
            if instruction is None:
                raise MachineError(f"Unknown instruction '{call.name}' on line {call.line_number}.")
            jump_target = instruction.execute(self, call)
            if self.halted:
                break
            if jump_target is None:
                self.pc += 1
            else:
                self.pc = jump_target
            steps += 1
            if max_steps is not None and steps >= max_steps:
                raise MachineError("Maximum number of steps exceeded; possible infinite loop detected.")

    def step(self) -> None:
        self.run(max_steps=1)

    def iter_program(self) -> Iterator[InstructionCall]:
        return iter(self.program)

    def dump_registers(self) -> Dict[str, float]:
        return dict(self.registers)
