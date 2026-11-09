"""ASGI request limits, including requests without Content-Length."""


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > self.max_bytes:
                await send({'type': 'http.response.start', 'status': 413,
                            'headers': [(b'content-type', b'application/json'), (b'connection', b'close')]})
                await send({'type': 'http.response.body', 'body': b'{"detail":"request body is too large"}'})
                return
            if not message.get('more_body', False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        await self.app(scope, replay, send)
