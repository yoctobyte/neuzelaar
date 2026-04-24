"""Small Test262 runner for backend comparison.

This intentionally supports a narrow subset:

- sync script tests
- positive tests
- simple parse/runtime negative tests
- no modules, async, includes, or agent-based harness features
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from pathlib import Path

from neuzelaar.engines.js.interface import JavaScriptEngine, ScriptExecutionResult, ScriptExecutionStatus

_FRONTMATTER_RE = re.compile(r"/\*---\n(?P<body>.*?)\n---\*/", re.DOTALL)
_KEY_VALUE_RE = re.compile(r"^(?P<key>[A-Za-z0-9_]+):\s*(?P<value>.*)$")
_LIST_ITEM_RE = re.compile(r"^- (?P<value>.*)$")
_INLINE_LIST_RE = re.compile(r"^\[(?P<body>.*)\]$")

_UNSUPPORTED_FLAGS = {"async", "module", "raw"}

_HARNESS_PREFIX = """
function Test262Error(message) {
  this.message = String(message || "");
  this.name = "Test262Error";
}
Test262Error.prototype = Object.create(Error.prototype);
Test262Error.prototype.constructor = Test262Error;

var assert = {
  _isSameValue: function(a, b) {
    if (a === 0 && b === 0) {
      return 1 / a === 1 / b;
    }
    if (a !== a && b !== b) {
      return true;
    }
    return a === b;
  },
  sameValue: function(actual, expected, message) {
    if (!assert._isSameValue(actual, expected)) {
      throw new Test262Error(message || ("Expected SameValue, got " + actual + " and " + expected));
    }
  },
  notSameValue: function(actual, expected, message) {
    if (assert._isSameValue(actual, expected)) {
      throw new Test262Error(message || ("Expected different values, got " + actual));
    }
  },
  throws: function(ExpectedError, func, message) {
    try {
      func();
    } catch (error) {
      if (error instanceof ExpectedError || error.name === ExpectedError.name) {
        return;
      }
      throw new Test262Error(message || ("Unexpected error: " + error));
    }
    throw new Test262Error(message || ("Expected " + ExpectedError.name + " to be thrown"));
  }
};
""".strip()


@dataclass(frozen=True, slots=True)
class NegativeExpectation:
    phase: str
    error_type: str


@dataclass(frozen=True, slots=True)
class Test262Case:
    path: Path
    source: str
    metadata: dict[str, object]
    flags: tuple[str, ...] = ()
    includes: tuple[str, ...] = ()
    negative: NegativeExpectation | None = None

    @property
    def is_supported(self) -> bool:
        if self.includes:
            return False
        return not any(flag in _UNSUPPORTED_FLAGS for flag in self.flags)

    @property
    def strict(self) -> bool:
        return "onlyStrict" in self.flags

    @property
    def display_name(self) -> str:
        return self.path.as_posix()


@dataclass(frozen=True, slots=True)
class Test262Outcome:
    case: Test262Case
    engine_name: str
    status: str
    reason: str
    execution: ScriptExecutionResult | None = None


@dataclass(frozen=True, slots=True)
class Test262RunSummary:
    engine_name: str
    total: int
    passed: int
    failed: int
    skipped: int
    outcomes: tuple[Test262Outcome, ...] = field(default_factory=tuple)


def load_case(path: str | Path) -> Test262Case:
    case_path = Path(path)
    source = case_path.read_text(encoding="utf-8")
    metadata = _parse_metadata(source)
    flags = tuple(metadata.get("flags", ()))
    includes = tuple(metadata.get("includes", ()))
    negative_data = metadata.get("negative")
    negative = None
    if isinstance(negative_data, dict):
        negative = NegativeExpectation(
            phase=str(negative_data.get("phase", "")),
            error_type=str(negative_data.get("type", "")),
        )
    return Test262Case(
        path=case_path,
        source=source,
        metadata=metadata,
        flags=flags,
        includes=includes,
        negative=negative,
    )


def run_case(engine: JavaScriptEngine, case: Test262Case) -> Test262Outcome:
    if not case.is_supported:
        return Test262Outcome(
            case=case,
            engine_name=engine.name,
            status="skipped",
            reason="unsupported Test262 features for local runner",
        )

    program = build_program(case)
    execution = engine.evaluate_program(program, url=case.display_name)
    if case.negative is not None:
        if execution.status is not ScriptExecutionStatus.ERROR:
            return Test262Outcome(
                case=case,
                engine_name=engine.name,
                status="failed",
                reason=f"expected {case.negative.error_type}, got {execution.status.value}",
                execution=execution,
            )
        if case.negative.error_type and case.negative.error_type not in execution.reason:
            return Test262Outcome(
                case=case,
                engine_name=engine.name,
                status="failed",
                reason=f"expected {case.negative.error_type}, got {execution.reason}",
                execution=execution,
            )
        return Test262Outcome(
            case=case,
            engine_name=engine.name,
            status="passed",
            reason="negative expectation matched",
            execution=execution,
        )
    if execution.status is ScriptExecutionStatus.RAN:
        return Test262Outcome(
            case=case,
            engine_name=engine.name,
            status="passed",
            reason="completed without error",
            execution=execution,
        )
    return Test262Outcome(
        case=case,
        engine_name=engine.name,
        status="failed",
        reason=execution.reason,
        execution=execution,
    )


def run_cases(engine: JavaScriptEngine, cases: list[Test262Case]) -> Test262RunSummary:
    outcomes = tuple(run_case(engine, case) for case in cases)
    passed = sum(outcome.status == "passed" for outcome in outcomes)
    failed = sum(outcome.status == "failed" for outcome in outcomes)
    skipped = sum(outcome.status == "skipped" for outcome in outcomes)
    return Test262RunSummary(
        engine_name=engine.name,
        total=len(outcomes),
        passed=passed,
        failed=failed,
        skipped=skipped,
        outcomes=outcomes,
    )


def build_program(case: Test262Case) -> str:
    parts: list[str] = []
    if case.strict:
        parts.append('"use strict";')
    parts.append(_HARNESS_PREFIX)
    parts.append(_strip_donotevaluate(case.source))
    return "\n".join(parts)


def _strip_donotevaluate(source: str) -> str:
    return source.replace("$DONOTEVALUATE();", "")


def _parse_metadata(source: str) -> dict[str, object]:
    match = _FRONTMATTER_RE.search(source)
    if match is None:
        return {}
    body = match.group("body")
    lines = body.splitlines()
    metadata: dict[str, object] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("  "):
            index += 1
            continue
        match_key = _KEY_VALUE_RE.match(line)
        if match_key is None:
            index += 1
            continue
        key = match_key.group("key")
        raw_value = match_key.group("value").strip()
        if raw_value == "":
            nested: dict[str, str] = {}
            index += 1
            while index < len(lines) and lines[index].startswith("  "):
                nested_line = lines[index].strip()
                nested_match = _KEY_VALUE_RE.match(nested_line)
                if nested_match is not None:
                    nested[nested_match.group("key")] = nested_match.group("value").strip()
                index += 1
            metadata[key] = nested
            continue
        if raw_value == "|":
            block_lines: list[str] = []
            index += 1
            while index < len(lines) and lines[index].startswith("  "):
                block_lines.append(lines[index][2:])
                index += 1
            metadata[key] = "\n".join(block_lines)
            continue
        inline_list = _INLINE_LIST_RE.match(raw_value)
        if inline_list is not None:
            body_value = inline_list.group("body").strip()
            if not body_value:
                metadata[key] = []
            else:
                metadata[key] = [item.strip() for item in body_value.split(",")]
            index += 1
            continue
        if raw_value == ">":
            folded_lines: list[str] = []
            index += 1
            while index < len(lines) and lines[index].startswith("    "):
                folded_lines.append(lines[index].strip())
                index += 1
            metadata[key] = " ".join(folded_lines)
            continue
        metadata[key] = raw_value
        index += 1
        if index < len(lines) and lines[index].startswith("- "):
            items: list[str] = []
            while index < len(lines):
                item_match = _LIST_ITEM_RE.match(lines[index].strip())
                if item_match is None:
                    break
                items.append(item_match.group("value").strip())
                index += 1
            metadata[key] = items
    return metadata
