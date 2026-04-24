from pathlib import Path

from neuzelaar.engines.js.interface import JavaScriptEngine, ScriptExecutionRequest, ScriptExecutionResult, ScriptExecutionStatus
from neuzelaar.engines.js.test262 import build_program, load_case, run_case, run_cases


class PassEngine(JavaScriptEngine):
    name = "pass"

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        return ScriptExecutionResult(status=ScriptExecutionStatus.RAN, reason="ok")


class SyntaxErrorEngine(JavaScriptEngine):
    name = "syntax"

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        return ScriptExecutionResult(status=ScriptExecutionStatus.ERROR, reason="SyntaxError: bad input")


def case_path(relative: str) -> Path:
    return Path(".cache/test262") / relative


def test_load_case_parses_flags_and_negative_expectation() -> None:
    case = load_case(case_path("test/language/global-code/yield-strict.js"))

    assert case.strict is True
    assert case.negative is not None
    assert case.negative.error_type == "SyntaxError"


def test_build_program_includes_harness_and_strict_mode() -> None:
    case = load_case(case_path("test/language/global-code/yield-strict.js"))

    program = build_program(case)

    assert "function Test262Error" in program
    assert '"use strict";' in program
    assert "$DONOTEVALUATE();" not in program


def test_run_case_passes_positive_case() -> None:
    case = load_case(case_path("test/language/expressions/addition/S11.6.1_A4_T3.js"))

    outcome = run_case(PassEngine(), case)

    assert outcome.status == "passed"


def test_run_case_matches_negative_case() -> None:
    case = load_case(case_path("test/language/global-code/return.js"))

    outcome = run_case(SyntaxErrorEngine(), case)

    assert outcome.status == "passed"


def test_run_cases_summarizes_results() -> None:
    cases = [
        load_case(case_path("test/language/expressions/addition/S11.6.1_A4_T3.js")),
        load_case(case_path("test/language/global-code/return.js")),
    ]

    summary = run_cases(PassEngine(), cases)

    assert summary.total == 2
    assert summary.passed == 1
    assert summary.failed == 1
