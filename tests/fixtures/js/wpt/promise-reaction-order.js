promise_test(function() {
  var order = "";
  return Promise.resolve()
    .then(function() {
      order = order + "a";
    })
    .then(function() {
      order = order + "b";
    })
    .then(function() {
      assert_equals(order, "ab");
    });
}, "Promise reactions preserve chaining order");
