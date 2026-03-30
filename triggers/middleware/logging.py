import logging

from triggers.router import Handler, Middleware, Request, Response

_logger = logging.getLogger("graphmind")


async def logging_middleware(req: Request, next: Handler) -> Response:
    _logger.debug(f"[graphmind] → {req.params.get('method', 'POST')} {req.params.get('path', '')}")
    response = await next(req)
    _logger.debug(f"[graphmind] ← {response.status_code}")
    return response
