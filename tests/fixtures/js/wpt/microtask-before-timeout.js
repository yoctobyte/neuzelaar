promise_test(function() {
  var order = "";
  Promise.resolve().then(function() {
    order = order + "microtask";
  });
  return new Promise(function(resolve) {
    setTimeout(function() {
      order = order + ",timer";
      assert_equals(order, "microtask,timer");
      resolve();
    }, 0);
  });
}, "Promise reactions run before timers");
