"""Dependency-free checks runnable even before pip installation."""
import asyncio
import unittest

from app.middleware import BodyLimitMiddleware
from app.services.deduplicator import find_title_duplicate, normalize_url


class CoreTests(unittest.TestCase):
    def test_url_credentials_rejected(self):
        with self.assertRaises(ValueError):
            normalize_url('https://user:password@example.com/')

    def test_tracking_removed(self):
        self.assertEqual(normalize_url('https://example.com/a?utm_source=rss&id=1#top'), 'https://example.com/a?id=1')

    def test_candidates_consumed_lazily(self):
        from types import SimpleNamespace
        def candidates():
            yield SimpleNamespace(id=1, title='Linux kernel release')
            raise AssertionError('Iterator consumed past first match')
        self.assertEqual(find_title_duplicate('Linux kernel release', candidates()).id, 1)

    def test_chunked_request_limit(self):
        async def run():
            called = False
            async def app(*_args):
                nonlocal called
                called = True
            chunks = iter([{'type': 'http.request', 'body': b'123', 'more_body': True},
                           {'type': 'http.request', 'body': b'456', 'more_body': False}])
            async def receive():
                return next(chunks)
            sent = []
            async def send(message):
                sent.append(message)
            await BodyLimitMiddleware(app, 5)({'type': 'http', 'method': 'POST'}, receive, send)
            self.assertFalse(called)
            self.assertEqual(sent[0]['status'], 413)
        asyncio.run(run())

    def test_request_at_exact_limit_replayed(self):
        async def run():
            async def app(scope, receive, send):
                self.assertEqual((await receive())['body'], b'12345')
            async def receive():
                return {'type': 'http.request', 'body': b'12345', 'more_body': False}
            async def send(_message):
                pass
            await BodyLimitMiddleware(app, 5)({'type': 'http', 'method': 'POST'}, receive, send)
        asyncio.run(run())

    def test_disconnected_request_not_processed(self):
        async def run():
            async def app(*_args):
                self.fail('Disconnected request processed')
            async def receive():
                return {'type': 'http.disconnect'}
            await BodyLimitMiddleware(app, 5)({'type': 'http', 'method': 'POST'}, receive, None)
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
