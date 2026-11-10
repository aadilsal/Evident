; Member calls that may register routes or middleware: app.get(...), router.use(...), r.route('/x').post(...)
(call_expression
  function: (member_expression
    object: (_) @recv
    property: (property_identifier) @method)
  arguments: (arguments) @args
  (#match? @method "^(get|post|put|patch|delete|del|all|head|options|use)$")) @call
