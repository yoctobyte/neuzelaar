from neuzelaar.core.policy.capability import Capability
from neuzelaar.engines.js.interface import ScriptExecutionRequest, ScriptExecutionStatus
from neuzelaar.engines.js.noop import NoopJavaScriptEngine
from neuzelaar.engines.wasm.interface import WasmExecutionRequest, WasmExecutionStatus
from neuzelaar.engines.wasm.noop import NoopWasmEngine


def test_noop_javascript_engine_blocks_inline_scripts() -> None:
    result = NoopJavaScriptEngine().execute(ScriptExecutionRequest(source="alert(1)"))

    assert result.status == ScriptExecutionStatus.BLOCKED
    assert result.requested_capabilities == (Capability.EXEC_INLINE_JS,)


def test_noop_javascript_engine_blocks_external_scripts() -> None:
    result = NoopJavaScriptEngine().execute(
        ScriptExecutionRequest(source="", url="https://example.com/app.js", inline=False, same_origin=True)
    )

    assert result.status == ScriptExecutionStatus.BLOCKED
    assert result.requested_capabilities == (Capability.EXEC_SAMEORIGIN_JS,)


def test_noop_javascript_engine_marks_third_party_scripts_separately() -> None:
    result = NoopJavaScriptEngine().execute(
        ScriptExecutionRequest(source="", url="https://cdn.example.com/app.js", inline=False, same_origin=False)
    )

    assert result.status == ScriptExecutionStatus.BLOCKED
    assert result.requested_capabilities == (Capability.EXEC_THIRDPARTY_JS,)


def test_noop_wasm_engine_blocks_modules() -> None:
    result = NoopWasmEngine().execute(WasmExecutionRequest(module=b"\0asm"))

    assert result.status == WasmExecutionStatus.BLOCKED
    assert result.requested_capabilities == (Capability.LOAD_WASM,)
