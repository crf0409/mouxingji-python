# Arithmetic Model Machine

本项目实现了一个**只依赖加减乘除运算**的可编程虚拟机。通过自定义汇编指令，可以在不编写 Python 逻辑的情况下组合出不同的算法与流程，轻松构建属于自己的“模型机”。

## 特性

- 🧮 默认指令只包含 `SET`、`ADD`、`SUB`、`MUL`、`DIV` 五种算术运算。
- 🧱 通过 `.define` 指令或 Python API 注册新的汇编指令，内部仍然只允许使用加减乘除表达式。
- 🔁 内置 `JMP`、`JZ`、`JNZ`、`PRINT`、`HALT` 等控制指令，可配合算术指令完成循环与分支。
- 🧾 支持标签、注释以及将运行结果收集到输出缓冲区。

## 快速上手

```python
from arithmetic_machine import ArithmeticMachine

source = """
.define INC dst src => src + 1
.define DOUBLE dst src => src * 2

SET R0 1
INC R0 R0
DOUBLE R1 R0
PRINT R1
HALT
"""

machine = ArithmeticMachine(echo=True)
machine.load_program(source)
machine.run()
```

执行后，`R1` 的值为 `4`，同时在终端输出 `4`。

## 汇编语言

- **寄存器**：默认提供 `R0`~`R7` 八个寄存器，可在初始化时调整数量。
- **自定义指令**：
  - 写在汇编文件中：`.define NAME dst arg1 ... => expression`
  - 或者在 Python 中调用 `machine.define_instruction("NAME", ["dst", "a", "b"], "a + b")`
- **程序结构**：支持 `label:` 定义标签，`#` 与 `;` 后视为注释。
- **执行结果**：`PRINT` 指令会将值追加到 `machine.output` 列表，若初始化时传入 `echo=True` 则同时打印。

## 示例程序

`examples/demo.py` 展示了如何使用自定义指令实现一个简单的倒计时循环。运行方式如下：

```bash
python examples/demo.py
```

## 测试

使用 `pytest` 运行单元测试：

```bash
pytest
```
