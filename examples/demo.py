"""Demonstration program for the arithmetic model machine."""

from arithmetic_machine import ArithmeticMachine


def build_program() -> str:
    return """
.define DEC dst src => src - 1
.define INC dst src => src + 1

SET R0 5       # 初始计数
SET R1 1

loop:
PRINT R0
SUB R0 R0 R1
JNZ R0 loop
HALT
"""


def main() -> None:
    machine = ArithmeticMachine(echo=True)
    machine.load_program(build_program())
    machine.run()


if __name__ == "__main__":
    main()
