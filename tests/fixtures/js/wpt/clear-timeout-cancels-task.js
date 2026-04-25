promise_test(function() {
  var fired = false;
  var done = false;
  var timer = setTimeout(function() {
    fired = true;
  }, 0);
  clearTimeout(timer);
  return new Promise(function(resolve) {
    setTimeout(function() {
      done = true;
      assert_true(done, "control timer should fire");
      assert_equals(fired, false, "cancelled timer must not fire");
      resolve();
    }, 0);
  });
}, "clearTimeout prevents timer callback execution");
