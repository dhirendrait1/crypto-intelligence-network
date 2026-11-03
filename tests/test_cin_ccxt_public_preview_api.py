import asyncio
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
import cin_ccxt_public_preview_api as api
from cin_ccxt_public_adapter import PublicDataUnavailable

class FakeAdapter:
    def ticker(self, symbol):
        return {'provider':'kraken','symbol':symbol,'kind':'ticker','last':100}
    def candles(self, symbol, interval, limit):
        return {'provider':'kraken','symbol':symbol,'kind':'ohlcv','interval':interval,'count':limit}
    def order_book(self, symbol):
        return {'provider':'kraken','symbol':symbol,'kind':'order_book'}
    def compare_closed_candles(self, symbol):
        return {'symbol':symbol,'kind':'closed_candle_comparison','comparison_status':'partial'}

class PreviewTests(unittest.TestCase):
    def setUp(self):
        async def inline(function, *args): return function(*args)
        self.patcher = patch.object(api.asyncio, 'to_thread', side_effect=inline)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
    def test_disabled_does_not_construct_provider(self):
        with patch.dict(os.environ,{},clear=True), patch.object(api,'_get_adapter') as get:
            with self.assertRaises(HTTPException) as error: asyncio.run(api.ticker())
        self.assertEqual(error.exception.status_code,404); get.assert_not_called()
    def test_only_public_preview_shape(self):
        with patch.dict(os.environ,{'CIN_CCXT_PREVIEW_ENABLED':'1'},clear=True),patch.object(api,'_get_adapter',return_value=FakeAdapter()):
            result=asyncio.run(api.ticker('BTC/USD'))
            candles=asyncio.run(api.candles('BTC/USD','1h',24))
            book=asyncio.run(api.order_book('BTC/USD'))
            comparison=asyncio.run(api.closed_candle_comparison('BTC/USD'))
        self.assertEqual((result['mode'],result['status'],result['provider']),('read_only','experimental','kraken'))
        self.assertEqual(candles['count'],24)
        self.assertEqual(book['kind'],'order_book')
        self.assertEqual(comparison['status'],'experimental')
        self.assertEqual(comparison['kind'],'closed_candle_comparison')
    def test_rejects_unknown_inputs_before_provider_access(self):
        with patch.dict(os.environ,{'CIN_CCXT_PREVIEW_ENABLED':'1'},clear=True),patch.object(api,'_get_adapter') as get:
            with self.assertRaises(HTTPException) as error:asyncio.run(api.ticker('BTC/EUR'))
            self.assertEqual(error.exception.status_code,400)
            with self.assertRaises(HTTPException) as error:asyncio.run(api.candles('BTC/USD','2w',24))
            self.assertEqual(error.exception.status_code,400)
            get.assert_not_called()
    def test_provider_failures_are_sanitized(self):
        class Broken:
            def ticker(self, symbol): raise PublicDataUnavailable([{'provider':'kraken','reason':'timeout'}])
        with patch.dict(os.environ,{'CIN_CCXT_PREVIEW_ENABLED':'1'},clear=True),patch.object(api,'_get_adapter',return_value=Broken()):
            with self.assertRaises(HTTPException) as error:asyncio.run(api.ticker('BTC/USD'))
        self.assertEqual(error.exception.status_code,503)
        self.assertEqual(error.exception.detail['attempts'][0]['reason'],'timeout')

    def test_concurrent_requests_wait_instead_of_failing_after_250ms(self):
        async def run():
            started = asyncio.Event()
            release = asyncio.Event()
            async def delayed(function, *args):
                if function.__name__ == 'candles':
                    started.set()
                    await release.wait()
                return function(*args)
            with patch.object(api.asyncio, 'to_thread', side_effect=delayed), patch.object(api, '_gate', asyncio.Semaphore(1)):
                first = asyncio.create_task(api.candles('BTC/USD', '1h', 24))
                await started.wait()
                second = asyncio.create_task(api.ticker('BTC/USD'))
                await asyncio.sleep(.35)
                self.assertFalse(second.done())
                release.set()
                candle, ticker = await asyncio.gather(first, second)
                self.assertEqual(candle['kind'], 'ohlcv')
                self.assertEqual(ticker['kind'], 'ticker')
        with patch.dict(os.environ, {'CIN_CCXT_PREVIEW_ENABLED':'1'}, clear=True), patch.object(api, '_get_adapter', return_value=FakeAdapter()):
            asyncio.run(run())

    def test_full_queue_returns_retry_hint(self):
        with patch.dict(os.environ, {'CIN_CCXT_PREVIEW_ENABLED':'1'}, clear=True), patch.object(api, '_pending', api._MAX_PENDING):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(api.ticker('BTC/USD'))
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(error.exception.headers['Retry-After'], '5')

    def test_cancelled_client_does_not_release_gate_while_work_continues(self):
        async def run():
            started = asyncio.Event()
            release = asyncio.Event()
            async def delayed(function, *args):
                started.set()
                await release.wait()
                return function(*args)
            gate = asyncio.Semaphore(1)
            with patch.object(api.asyncio, 'to_thread', side_effect=delayed), patch.object(api, '_gate', gate):
                request = asyncio.create_task(api.ticker('BTC/USD'))
                await started.wait()
                request.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await request
                self.assertTrue(gate.locked())
                release.set()
                await asyncio.sleep(0.01)
                self.assertFalse(gate.locked())
        with patch.dict(os.environ, {'CIN_CCXT_PREVIEW_ENABLED':'1'}, clear=True), patch.object(api, '_get_adapter', return_value=FakeAdapter()):
            asyncio.run(run())

if __name__=='__main__': unittest.main()
