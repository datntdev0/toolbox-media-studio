This document outlines the rules and conventions for backend routers in the project.
- The @router annotation must be defined in a single line.
- All functions defining API endpoints must have suffix `_route` in their names. For example, a function handling user login should be named `login_route`.
- All functions defining API endpoints must have a response_model, status_code, operation_id defined their decorators.
- The parameters of the functions defining API endpoints must be ordered as follows: injections, path parameters, query parameters, body parameters, and header parameters.
- Do try catch exceptions that defined as custom exceptions in the `app/core/exceptions` module. For example, if a resource is not found, raise a `NotFoundException` instead of catching that specific exception and returning a 404 response directly. This ensures that the global exception handler can handle it appropriately.
- Do not raise `HttpException` directly in the API endpoint functions. This causes losing tracestack because it returns the response directly and skips the global exception handler. Instead, raise custom exceptions defined in the `app/core/exceptions` module.