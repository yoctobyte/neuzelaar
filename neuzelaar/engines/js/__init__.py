"""JavaScript engine interfaces and implementations."""

from neuzelaar.engines.js.factory import EngineUnavailableError, create_javascript_engine, engine_specs
from neuzelaar.engines.js.interface import (
    JavaScriptEngine,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
    required_capability_for,
)
from neuzelaar.engines.js.noop import NoopJavaScriptEngine

__all__ = [
    "EngineUnavailableError",
    "JavaScriptEngine",
    "NoopJavaScriptEngine",
    "ScriptExecutionRequest",
    "ScriptExecutionResult",
    "ScriptExecutionStatus",
    "create_javascript_engine",
    "engine_specs",
    "required_capability_for",
]
