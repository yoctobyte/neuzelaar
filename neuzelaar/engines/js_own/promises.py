"""Promise primitives for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.engines.js_own.host import ConstructibleHostObject, HostCallable, HostObject
from neuzelaar.engines.js_own.runtime_state import current_runtime_state


@dataclass(slots=True)
class PromiseReaction:
    on_fulfilled: object | None
    on_rejected: object | None
    resolve_next: object
    reject_next: object


class JavaScriptPromise(HostObject):
    def __init__(self, prototype: HostObject | None = None) -> None:
        super().__init__(prototype=prototype)
        self.state = "pending"
        self.value: object = None
        self.reactions: list[PromiseReaction] = []

    def fulfill(self, value: object) -> None:
        if self.state != "pending":
            return
        self.state = "fulfilled"
        self.value = value
        self._schedule_flush()

    def reject(self, reason: object) -> None:
        if self.state != "pending":
            return
        self.state = "rejected"
        self.value = reason
        self._schedule_flush()

    def subscribe(
        self,
        on_fulfilled: object | None,
        on_rejected: object | None,
        *,
        resolve_next,
        reject_next,
    ) -> None:
        self.reactions.append(
            PromiseReaction(
                on_fulfilled=on_fulfilled,
                on_rejected=on_rejected,
                resolve_next=resolve_next,
                reject_next=reject_next,
            )
        )
        if self.state != "pending":
            self._schedule_flush()

    def _schedule_flush(self) -> None:
        runtime = current_runtime_state()
        if runtime is None:
            self._flush_reactions()
            return
        runtime.queue_microtask(self._flush_reactions, reason=f"promise-{self.state}")

    def _flush_reactions(self) -> None:
        if self.state == "pending":
            return
        reactions = self.reactions
        self.reactions = []
        for reaction in reactions:
            _run_promise_reaction(self, reaction)


def create_promise_builtins() -> tuple[ConstructibleHostObject, HostCallable]:
    promise_prototype = HostObject()

    def promise_then(arguments: tuple[object, ...], this_value: object | None) -> object:
        if not isinstance(this_value, JavaScriptPromise):
            raise TypeError("Promise.then receiver must be a promise")
        next_promise = JavaScriptPromise(prototype=promise_prototype)
        on_fulfilled = arguments[0] if len(arguments) > 0 else None
        on_rejected = arguments[1] if len(arguments) > 1 else None
        this_value.subscribe(
            on_fulfilled,
            on_rejected,
            resolve_next=next_promise.fulfill,
            reject_next=next_promise.reject,
        )
        return next_promise

    def promise_catch(arguments: tuple[object, ...], this_value: object | None) -> object:
        if not isinstance(this_value, JavaScriptPromise):
            raise TypeError("Promise.catch receiver must be a promise")
        return promise_then((None, arguments[0] if arguments else None), this_value)

    def promise_finally(arguments: tuple[object, ...], this_value: object | None) -> object:
        if not isinstance(this_value, JavaScriptPromise):
            raise TypeError("Promise.finally receiver must be a promise")
        callback = arguments[0] if arguments else None
        next_promise = JavaScriptPromise(prototype=promise_prototype)

        def handle_fulfilled(value: object) -> None:
            try:
                if callback is not None and hasattr(callback, "call"):
                    callback.call((), this_value=None)
                next_promise.fulfill(value)
            except Exception as exc:
                next_promise.reject(exc)

        def handle_rejected(reason: object) -> None:
            try:
                if callback is not None and hasattr(callback, "call"):
                    callback.call((), this_value=None)
                next_promise.reject(reason)
            except Exception as exc:
                next_promise.reject(exc)

        this_value.subscribe(
            HostCallable("<promise.finally.fulfilled>", lambda args, _this: handle_fulfilled(args[0] if args else None)),
            HostCallable("<promise.finally.rejected>", lambda args, _this: handle_rejected(args[0] if args else None)),
            resolve_next=lambda value: value,
            reject_next=lambda reason: reason,
        )
        return next_promise

    promise_prototype.set("then", HostCallable("Promise.prototype.then", promise_then))
    promise_prototype.set("catch", HostCallable("Promise.prototype.catch", promise_catch))
    promise_prototype.set("finally", HostCallable("Promise.prototype.finally", promise_finally))

    def construct_promise(arguments: tuple[object, ...]) -> object:
        promise = JavaScriptPromise(prototype=promise_prototype)
        executor = arguments[0] if arguments else None
        if executor is None or not hasattr(executor, "call"):
            raise TypeError("Promise executor must be callable")
        resolve = HostCallable("Promise.resolve", lambda args, _this: _resolve_into(promise, args[0] if args else None))
        reject = HostCallable("Promise.reject", lambda args, _this: _reject_into(promise, args[0] if args else None))
        try:
            executor.call((resolve, reject), this_value=None)
        except Exception as exc:
            promise.reject(exc)
        return promise

    promise_constructor = ConstructibleHostObject(construct_impl=construct_promise)
    promise_constructor.set("prototype", promise_prototype)
    promise_constructor.set(
        "resolve",
        HostCallable(
            "Promise.resolve",
            lambda args, _this: promise_resolve(args[0] if args else None, prototype=promise_prototype),
        ),
    )
    promise_constructor.set(
        "reject",
        HostCallable(
            "Promise.reject",
            lambda args, _this: promise_reject(args[0] if args else None, prototype=promise_prototype),
        ),
    )

    queue_microtask = HostCallable("queueMicrotask", _queue_microtask)
    return promise_constructor, queue_microtask


def promise_resolve(value: object, *, prototype: HostObject | None = None) -> JavaScriptPromise:
    if isinstance(value, JavaScriptPromise):
        return value
    promise = JavaScriptPromise(prototype=prototype)
    promise.fulfill(value)
    return promise


def promise_reject(reason: object, *, prototype: HostObject | None = None) -> JavaScriptPromise:
    promise = JavaScriptPromise(prototype=prototype)
    promise.reject(reason)
    return promise


def await_value(value: object, on_fulfilled, on_rejected) -> None:
    if isinstance(value, JavaScriptPromise):
        value.subscribe(
            None,
            None,
            resolve_next=on_fulfilled,
            reject_next=on_rejected,
        )
        return
    on_fulfilled(value)


def _resolve_into(promise: JavaScriptPromise, value: object) -> object:
    if isinstance(value, JavaScriptPromise):
        value.subscribe(
            None,
            None,
            resolve_next=promise.fulfill,
            reject_next=promise.reject,
        )
    else:
        promise.fulfill(value)
    return None


def _reject_into(promise: JavaScriptPromise, reason: object) -> object:
    promise.reject(reason)
    return None


def _queue_microtask(arguments: tuple[object, ...], _this: object | None) -> object:
    callback = arguments[0] if arguments else None
    if callback is None or not hasattr(callback, "call"):
        raise TypeError("queueMicrotask callback must be callable")
    runtime = current_runtime_state()
    if runtime is None:
        callback.call((), this_value=None)
        return None
    runtime.queue_microtask(lambda: callback.call((), this_value=None), reason="queueMicrotask")
    return None


def _run_promise_reaction(source: JavaScriptPromise, reaction: PromiseReaction) -> None:
    handler = reaction.on_fulfilled if source.state == "fulfilled" else reaction.on_rejected
    value = source.value
    try:
        if handler is None or not hasattr(handler, "call"):
            if source.state == "fulfilled":
                reaction.resolve_next(value)
            else:
                reaction.reject_next(value)
            return
        result = handler.call((value,), this_value=None)
        if isinstance(result, JavaScriptPromise):
            result.subscribe(
                None,
                None,
                resolve_next=reaction.resolve_next,
                reject_next=reaction.reject_next,
            )
            return
        reaction.resolve_next(result)
    except Exception as exc:
        reaction.reject_next(exc)
