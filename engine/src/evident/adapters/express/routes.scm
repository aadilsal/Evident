; Member calls that may register routes, middleware or plugins (Express and Fastify).
(call_expression
  function: (member_expression
    object: (_) @recv
    property: (property_identifier) @method)
  arguments: (arguments) @args
  (#match? @method "^(get|post|put|patch|delete|del|all|head|options|use|route|register|addHook)$")) @call
