promise_test(function() {
  var order = "";
  queueMicrotask(function() {
    order = order + "queueMicrotask";
  });
  return new Promise(function(resolve) {
    setTimeout(function() {
      order = order + ",timer";
      assert_equals(order, "queueMicrotask,timer");
      resolve();
    }, 0);
  });
}, "queueMicrotask runs before timers");
