#!/usr/bin/env python3
"""
Trace execution of 18m_window.py and collect statistics relevant to formal verification.
"""

import dis
import sys
from collections import defaultdict


class ExecutionTracer:
    """Traces Python execution and collects statistics."""

    def __init__(self):
        self.stats = {
            "lines_executed": 0,
            "function_calls": 0,
            "conditionals": 0,  # if/else branches
            "comparisons": 0,  # <, >, ==, !=, <=, >=
            "arithmetic_ops": 0,  # +, -, *, /, //, %
            "attribute_accesses": 0,  # obj.attr
            "subscript_ops": 0,  # dict/list lookups: obj[key]
            "loop_iterations": 0,  # for/while iterations
            "object_creations": 0,  # new object instantiations
            "returns": 0,  # return statements
        }
        self.files_seen = set()
        self.functions_called = defaultdict(int)
        self._in_loop = defaultdict(bool)

    def trace_calls(self, frame, event, arg):
        """Main trace function for sys.settrace."""
        code = frame.f_code
        filename = code.co_filename

        # Skip frozen/built-in modules
        if filename.startswith("<") or "importlib" in filename:
            return self.trace_calls

        self.files_seen.add(filename)

        if event == "line":
            self.stats["lines_executed"] += 1
            self._analyze_line(frame)

        elif event == "call":
            self.stats["function_calls"] += 1
            func_name = code.co_name
            self.functions_called[f"{filename}:{func_name}"] += 1

        elif event == "return":
            self.stats["returns"] += 1

        return self.trace_calls

    def _analyze_line(self, frame):
        """Analyze bytecode at current line to count operations."""
        code = frame.f_code
        lineno = frame.f_lineno

        # Get bytecode instructions for this line
        try:
            instructions = list(dis.get_instructions(code))
        except Exception:
            return

        for instr in instructions:
            if instr.positions and instr.positions.lineno != lineno:
                continue

            op_name = instr.opname

            # Comparisons
            if op_name == "COMPARE_OP":
                self.stats["comparisons"] += 1

            # Arithmetic operations
            elif op_name in (
                "BINARY_ADD",
                "BINARY_SUBTRACT",
                "BINARY_MULTIPLY",
                "BINARY_TRUE_DIVIDE",
                "BINARY_FLOOR_DIVIDE",
                "BINARY_MODULO",
                "BINARY_OP",
            ):
                self.stats["arithmetic_ops"] += 1

            # Attribute access
            elif op_name in ("LOAD_ATTR", "STORE_ATTR"):
                self.stats["attribute_accesses"] += 1

            # Subscript (dict/list lookup)
            elif op_name in ("BINARY_SUBSCR", "STORE_SUBSCR"):
                self.stats["subscript_ops"] += 1

            # Conditionals
            elif op_name in (
                "POP_JUMP_IF_FALSE",
                "POP_JUMP_IF_TRUE",
                "JUMP_IF_FALSE_OR_POP",
                "JUMP_IF_TRUE_OR_POP",
            ):
                self.stats["conditionals"] += 1

            # Loop iterations (FOR_ITER indicates loop iteration)
            elif op_name == "FOR_ITER":
                self.stats["loop_iterations"] += 1

    def print_stats(self):
        """Print collected statistics."""
        print("\n" + "=" * 60)
        print("EXECUTION TRACE STATISTICS")
        print("=" * 60)

        print("\n--- Core Metrics (for Formal Verification) ---\n")

        metrics = [
            ("Lines Executed", self.stats["lines_executed"]),
            ("Function Calls", self.stats["function_calls"]),
            ("Conditional Branches", self.stats["conditionals"]),
            ("Comparison Operations", self.stats["comparisons"]),
            ("Arithmetic Operations", self.stats["arithmetic_ops"]),
            ("Attribute Accesses", self.stats["attribute_accesses"]),
            ("Subscript Operations", self.stats["subscript_ops"]),
            ("Loop Iterations", self.stats["loop_iterations"]),
            ("Return Statements", self.stats["returns"]),
            ("Unique Files Touched", len(self.files_seen)),
        ]

        for name, value in metrics:
            print(f"  {name:<25}: {value:>8}")

        print("\n--- Top Functions Called ---\n")
        sorted_funcs = sorted(
            self.functions_called.items(), key=lambda x: x[1], reverse=True
        )[:10]
        for func, count in sorted_funcs:
            # Shorten path for display
            short = func.split("/")[-1] if "/" in func else func
            print(f"  {short:<45}: {count:>5}")

        print("\n" + "=" * 60)


def main():
    """Run the target script with tracing enabled."""
    tracer = ExecutionTracer()

    print("Running 18m_window.py with execution tracing...\n")

    # Set up the trace
    sys.settrace(tracer.trace_calls)

    try:
        # Import and run the target module by executing its main block
        import os
        import runpy

        script_dir = os.path.dirname(os.path.abspath(__file__))
        target_path = os.path.join(script_dir, "18m_window.py")
        runpy.run_path(target_path, run_name="__main__")

    finally:
        # Disable tracing
        sys.settrace(None)

    # Print statistics
    tracer.print_stats()


if __name__ == "__main__":
    main()
