"""QuickJS-backed JavaScript engine."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from neuzelaar.engines.js.interface import (
    JavaScriptEngine,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
    required_capability_for,
)
from neuzelaar.shell_api.events import ConsoleLog

if TYPE_CHECKING:
    from neuzelaar.core.bus import Bus
    from neuzelaar.engines.js.interface import DomBridge, PageContext

try:
    import quickjs as _quickjs
except ImportError:  # pragma: no cover - exercised through factory behavior
    _quickjs = None


class QuickJsJavaScriptEngine(JavaScriptEngine):
    name = "quickjs"

    def __init__(
        self,
        *,
        memory_limit_bytes: int | None = 8_000_000,
        time_limit_ms: int | None = 100,
        max_stack_size_bytes: int | None = 512_000,
    ) -> None:
        if _quickjs is None:
            raise RuntimeError("quickjs package is not installed")
        self.memory_limit_bytes = memory_limit_bytes
        self.time_limit_ms = time_limit_ms
        self.max_stack_size_bytes = max_stack_size_bytes

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        context = _quickjs.Context()
        if self.memory_limit_bytes is not None:
            context.set_memory_limit(self.memory_limit_bytes)
        if self.time_limit_ms is not None:
            context.set_time_limit(self.time_limit_ms)
        if self.max_stack_size_bytes is not None:
            context.set_max_stack_size(self.max_stack_size_bytes)
        try:
            context.eval(request.source)
        except Exception as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=str(exc),
                requested_capabilities=(required_capability_for(request),),
            )
        return ScriptExecutionResult(
            status=ScriptExecutionStatus.RAN,
            reason="ok",
            requested_capabilities=(required_capability_for(request),),
        )


class QuickJsTickedJavaScriptEngine(JavaScriptEngine):
    name = "quickjs-ticked"

    def __init__(
        self,
        *,
        bus: Bus | None = None,
        memory_limit_bytes: int | None = 8_000_000,
        time_limit_ms: int | None = None,
        max_stack_size_bytes: int | None = 512_000,
    ) -> None:
        if _quickjs is None:
            raise RuntimeError("quickjs package is not installed")
        self.bus = bus
        self.memory_limit_bytes = memory_limit_bytes
        self.time_limit_ms = time_limit_ms
        self.max_stack_size_bytes = max_stack_size_bytes
        self._context = None
        self._dom_bridge = None

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        capability = required_capability_for(request)
        if self._context is None:
            self.reset_for_page(None)

        try:
            self._context.eval(request.source)
            while self._context.execute_pending_job():
                pass
        except Exception as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"RuntimeError: {exc}",
                requested_capabilities=(capability,),
            )
        return ScriptExecutionResult(
            status=ScriptExecutionStatus.RAN,
            reason="ok",
            requested_capabilities=(capability,),
        )

    def tick(self, *, timeout_ms: float = 8.0) -> None:
        if self._context is None:
            return

        start_time = time.monotonic()
        while self._context.execute_pending_job():
            if (time.monotonic() - start_time) * 1000 >= timeout_ms:
                return

        try:
            self._context.eval("__wpt_run_due_timers();")
        except Exception as exc:
            if self.bus is not None:
                self.bus.publish(ConsoleLog(level="error", text=f"QuickJS tick timer error: {exc}"))

        while self._context.execute_pending_job():
            if (time.monotonic() - start_time) * 1000 >= timeout_ms:
                return

    def has_pending_work(self) -> bool:
        if self._context is None:
            return False
        try:
            return bool(self._context.eval("__wpt_has_timer_work();"))
        except Exception:
            return False

    def event_loop_snapshot(self) -> object | None:
        if self._context is None:
            return None
        try:
            queue_len = int(self._context.eval("__wpt_timer_queue.length;"))
            return {"pending_timers": queue_len}
        except Exception:
            return None

    def reset_for_page(
        self,
        page_context: PageContext | None = None,
        *,
        dom_bridge: DomBridge | None = None,
    ) -> None:
        if _quickjs is None:
            raise RuntimeError("quickjs package is not installed")

        self._context = _quickjs.Context()
        self._dom_bridge = dom_bridge

        if self.memory_limit_bytes is not None:
            self._context.set_memory_limit(self.memory_limit_bytes)
        if self.max_stack_size_bytes is not None:
            self._context.set_max_stack_size(self.max_stack_size_bytes)

        self._context.add_callable("_py_console_log", self._py_console_log)
        self._context.add_callable("_py_dom_set_property", self._py_dom_set_property)
        self._context.add_callable("_py_dom_set_attribute", self._py_dom_set_attribute)
        self._context.add_callable("_py_dom_get_attribute", self._py_dom_get_attribute)
        self._context.add_callable("_py_dom_remove_attribute", self._py_dom_remove_attribute)
        self._context.add_callable("_py_dom_set_style_property", self._py_dom_set_style_property)
        self._context.add_callable("_py_dom_insert_adjacent_html", self._py_dom_insert_adjacent_html)
        self._context.add_callable("_py_dom_remove_node", self._py_dom_remove_node)
        self._context.add_callable("_py_document_set_title", self._py_document_set_title)
        self._context.add_callable("_py_location_assign", self._py_location_assign)
        self._context.add_callable("_py_history_push_state", self._py_history_push_state)
        self._context.add_callable("_py_history_back", self._py_history_back)
        self._context.add_callable("_py_now", lambda: time.monotonic() * 1000)

        self._context.eval(self._base_shims_js())

        if page_context is not None:
            import json
            self._context.eval(f"location._href = {repr(page_context.url)};")
            self._context.eval(f"document._title = {repr(page_context.title)};")
            for node in page_context.nodes:
                attrs_json = json.dumps(list(node.attributes))
                self._context.eval(
                    f"__wpt_create_element({repr(node.id)}, {repr(node.tag)}, {repr(node.text_content)}, JSON.parse({repr(attrs_json)}));"
                )

    def _py_console_log(self, level: str, text: str) -> None:
        if self.bus is not None:
            self.bus.publish(ConsoleLog(level=level, text=text))

    def _py_dom_set_property(self, node_id: str, name: str, value: object) -> None:
        if self._dom_bridge is not None:
            self._dom_bridge.set_property(node_id, name, value)

    def _py_dom_set_attribute(self, node_id: str, name: str, value: str) -> None:
        if self._dom_bridge is not None:
            self._dom_bridge.set_attribute(node_id, name, value)

    def _py_dom_get_attribute(self, node_id: str, name: str) -> str | None:
        if self._dom_bridge is not None:
            return self._dom_bridge.get_attribute(node_id, name)
        return None

    def _py_dom_remove_attribute(self, node_id: str, name: str) -> None:
        if self._dom_bridge is not None:
            self._dom_bridge.remove_attribute(node_id, name)

    def _py_dom_set_style_property(self, node_id: str, name: str, value: object) -> None:
        if self._dom_bridge is not None:
            self._dom_bridge.set_style_property(node_id, name, value)

    def _py_dom_insert_adjacent_html(self, node_id: str, position: str, html: str) -> None:
        if self._dom_bridge is not None:
            self._dom_bridge.insert_adjacent_html(node_id, position, html)

    def _py_dom_remove_node(self, node_id: str) -> None:
        if self._dom_bridge is not None:
            self._dom_bridge.remove_node(node_id)

    def _py_document_set_title(self, title: str) -> None:
        pass

    def _py_location_assign(self, url: str) -> None:
        pass

    def _py_history_push_state(self, state: object, title: str, url: str) -> None:
        pass

    def _py_history_back(self) -> None:
        pass

    def _base_shims_js(self) -> str:
        return """
var console = {
  log: function() { _py_console_log("info", Array.prototype.join.call(arguments, " ")); },
  warn: function() { _py_console_log("warning", Array.prototype.join.call(arguments, " ")); },
  error: function() { _py_console_log("error", Array.prototype.join.call(arguments, " ")); },
  info: function() { _py_console_log("info", Array.prototype.join.call(arguments, " ")); },
  debug: function() { _py_console_log("info", Array.prototype.join.call(arguments, " ")); }
};

var location = {
  _href: "",
  get href() { return this._href; },
  set href(val) { this.assign(val); },
  assign: function(url) { _py_location_assign(url); }
};

var history = {
  _entries: [],
  _index: 0,
  get length() { return this._entries.length; },
  pushState: function(state, title, url) {
    _py_history_push_state(state, title, url);
  },
  back: function() {
    _py_history_back();
  }
};

var __wpt_timer_queue = [];
var __wpt_timer_registry = {};
var __wpt_next_timer_id = 1;

function setTimeout(fn, delay) {
  if (!fn || !fn.call) {
    throw new TypeError("Timer callback must be callable");
  }
  delay = (delay === undefined || delay === null || isNaN(Number(delay))) ? 0 : Number(delay);
  if (delay < 0) delay = 0;
  var args = Array.prototype.slice.call(arguments, 2);
  var timer = {
    id: __wpt_next_timer_id++,
    fn: fn,
    cancelled: false,
    args: args,
    repeat: false,
    delay: delay,
    dueAt: _py_now() + delay
  };
  __wpt_timer_queue.push(timer);
  __wpt_timer_registry[timer.id] = timer;
  return timer.id;
}

function setInterval(fn, delay) {
  if (!fn || !fn.call) {
    throw new TypeError("Timer callback must be callable");
  }
  delay = (delay === undefined || delay === null || isNaN(Number(delay))) ? 0 : Number(delay);
  if (delay < 0) delay = 0;
  var args = Array.prototype.slice.call(arguments, 2);
  var timer = {
    id: __wpt_next_timer_id++,
    fn: fn,
    cancelled: false,
    args: args,
    repeat: true,
    delay: delay,
    dueAt: _py_now() + delay
  };
  __wpt_timer_queue.push(timer);
  __wpt_timer_registry[timer.id] = timer;
  return timer.id;
}

function clearTimeout(id) {
  if (__wpt_timer_registry[id]) {
    __wpt_timer_registry[id].cancelled = true;
  }
}

function clearInterval(id) {
  clearTimeout(id);
}

function queueMicrotask(fn) {
  if (!fn || !fn.call) {
    throw new TypeError("queueMicrotask callback must be callable");
  }
  Promise.resolve().then(function() {
    fn();
  });
}

function __wpt_has_timer_work() {
  for (var i = 0; i < __wpt_timer_queue.length; i++) {
    if (!__wpt_timer_queue[i].cancelled) return true;
  }
  return false;
}

function __wpt_run_due_timers() {
  var now = _py_now();
  var due = [];
  var remaining = [];
  for (var i = 0; i < __wpt_timer_queue.length; i++) {
    var timer = __wpt_timer_queue[i];
    if (timer.cancelled) {
      delete __wpt_timer_registry[timer.id];
      continue;
    }
    if (timer.dueAt <= now) {
      due.push(timer);
    } else {
      remaining.push(timer);
    }
  }
  __wpt_timer_queue = remaining;

  due.sort(function(a, b) {
    if (a.dueAt !== b.dueAt) {
      return a.dueAt - b.dueAt;
    }
    return a.id - b.id;
  });

  for (var j = 0; j < due.length; j++) {
    var t = due[j];
    if (t.cancelled) continue;
    try {
      t.fn.apply(null, t.args);
    } catch (e) {
      _py_console_log("error", "Error in timer: " + e);
    }
    if (t.repeat && !t.cancelled) {
      t.dueAt = _py_now() + t.delay;
      __wpt_timer_queue.push(t);
      __wpt_timer_registry[t.id] = t;
    } else {
      delete __wpt_timer_registry[t.id];
    }
  }
}

var __wpt_nodes = {};

function __wpt_create_element(nodeId, tag, text, attrs) {
  var el = {
    _id: nodeId,
    _tag: tag,
    _text: text,
    _attrs: {},

    get tagName() { return this._tag.toUpperCase(); },
    get id() { return this._id; },

    get textContent() { return this._text; },
    set textContent(val) {
      this._text = String(val);
      _py_dom_set_property(this._id, "textContent", this._text);
    },

    get innerHTML() { return ""; },
    set innerHTML(val) {
      _py_dom_set_property(this._id, "innerHTML", String(val));
    },

    get className() { return this._attrs["class"] || ""; },
    set className(val) {
      this._attrs["class"] = String(val);
      _py_dom_set_property(this._id, "className", String(val));
    },

    setAttribute: function(name, value) {
      var n = String(name).toLowerCase();
      var v = String(value);
      this._attrs[n] = v;
      _py_dom_set_attribute(this._id, n, v);
    },

    getAttribute: function(name) {
      var n = String(name).toLowerCase();
      return this._attrs[n] !== undefined ? this._attrs[n] : null;
    },

    removeAttribute: function(name) {
      var n = String(name).toLowerCase();
      delete this._attrs[n];
      _py_dom_remove_attribute(this._id, n);
    },

    insertAdjacentHTML: function(position, html) {
      _py_dom_insert_adjacent_html(this._id, String(position), String(html));
    },

    remove: function() {
      _py_dom_remove_node(this._id);
      delete __wpt_nodes[this._id];
    }
  };

  for (var i = 0; i < attrs.length; i++) {
    var attr = attrs[i];
    el._attrs[attr[0].toLowerCase()] = attr[1];
  }

  var styleProxy = {};
  var initialStyle = el._attrs["style"] || "";
  var decls = initialStyle.split(";");
  for (var j = 0; j < decls.length; j++) {
    var decl = decls[j];
    if (decl.indexOf(":") !== -1) {
      var parts = decl.split(":");
      var prop = parts[0].trim();
      var val = parts[1].trim();
      var jsProp = prop.replace(/-([a-z])/g, function(g) { return g[1].toUpperCase(); });
      styleProxy[jsProp] = val;
    }
  }

  el.style = new Proxy(styleProxy, {
    set: function(target, prop, value) {
      var val = String(value);
      target[prop] = val;
      _py_dom_set_style_property(el._id, String(prop), val);
      return true;
    },
    get: function(target, prop) {
      return target[prop] || "";
    }
  });

  __wpt_nodes[nodeId] = el;
  return el;
}

var document = {
  _title: "",
  get title() { return this._title; },
  set title(val) {
    this._title = String(val);
    _py_document_set_title(this._title);
  },
  getElementById: function(id) {
    var s = String(id);
    for (var nodeId in __wpt_nodes) {
      if (__wpt_nodes[nodeId]._attrs["id"] === s || nodeId === s) {
        return __wpt_nodes[nodeId];
      }
    }
    return null;
  },
  querySelector: function(selector) {
    var s = String(selector).trim();
    if (s.startsWith("#")) {
      return this.getElementById(s.substring(1));
    }
    if (s.startsWith(".")) {
      var cls = s.substring(1);
      for (var nodeId in __wpt_nodes) {
        var el = __wpt_nodes[nodeId];
        if (el.className.split(" ").indexOf(cls) !== -1) {
          return el;
        }
      }
    }
    for (var nodeId in __wpt_nodes) {
      var el = __wpt_nodes[nodeId];
      if (el._tag.toLowerCase() === s.toLowerCase()) {
        return el;
      }
    }
    return null;
  },
  querySelectorAll: function(selector) {
    var s = String(selector).trim();
    var results = [];
    if (s.startsWith("#")) {
      var el = this.getElementById(s.substring(1));
      if (el) results.push(el);
    } else if (s.startsWith(".")) {
      var cls = s.substring(1);
      for (var nodeId in __wpt_nodes) {
        var el = __wpt_nodes[nodeId];
        if (el.className.split(" ").indexOf(cls) !== -1) {
          results.push(el);
        }
      }
    } else {
      for (var nodeId in __wpt_nodes) {
        var el = __wpt_nodes[nodeId];
        if (el._tag.toLowerCase() === s.toLowerCase()) {
          results.push(el);
        }
      }
    }
    return results;
  }
};
"""
