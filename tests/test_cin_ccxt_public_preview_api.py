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
        self.assertEqual((result['mode'],result['status'],result['provider']),('read_only','experimental','kraken'))
        self.assertEqual(candles['count'],24)
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

if __name__=='__main__': unittest.main()
