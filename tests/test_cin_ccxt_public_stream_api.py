import asyncio
import json
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
import cin_ccxt_public_stream_api as api

NOW = 1800000000.0
class Request:
    def __init__(self): self.calls=0
    async def is_disconnected(self):
        self.calls+=1
        return self.calls>1
class Exchange:
    def __init__(self): self.closed=False
    async def load_markets(self):
        return {'BTC/USD':{'symbol':'BTC/USD','base':'BTC','quote':'USD','spot':True,'active':True,'id':'XXBTZUSD'}}
    async def watch_trades(self, symbol, limit):
        self.asserted=(symbol,limit)
        return [
            {'id':'real','symbol':'BTC/USD','timestamp':int(NOW*1000),'price':100.0,'amount':0.2},
            {'id':'real','symbol':'BTC/USD','timestamp':int(NOW*1000),'price':100.0,'amount':0.2},
            {'id':'old','symbol':'BTC/USD','timestamp':int(NOW*1000)-1000,'price':99,'amount':0.1},
            {'id':'other','symbol':'ETH/USD','timestamp':int(NOW*1000),'price':101,'amount':0.1},
        ]
    async def close(self): self.closed=True

class StreamTests(unittest.TestCase):
    def test_disabled_without_both_flags_and_no_exchange(self):
        with patch.dict(os.environ,{},clear=True),patch.object(api,'_make_exchange') as make:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(api.public_trades_stream(Request(), 'BTC/USD'))
        self.assertEqual(error.exception.status_code,404);make.assert_not_called()
    def test_invalid_inputs_fail_before_provider_access(self):
        with patch.dict(os.environ,{'CIN_CCXT_PREVIEW_ENABLED':'1','CIN_CCXT_STREAM_ENABLED':'1'},clear=True),patch.object(api,'_make_exchange') as make:
            for symbol in ('BTC/USDT', '../BTC/USD', 'btC/USD', 'BTC/ETH', 'ABCDEFGHIJK/USD'):
                with self.subTest(symbol=symbol),self.assertRaises(HTTPException) as error:
                    asyncio.run(api.public_trades_stream(Request(), symbol))
                self.assertEqual(error.exception.status_code,400)
        make.assert_not_called()
    def test_live_event_is_validated_deduplicated_and_closed(self):
        exchange=Exchange()
        async def run():
            gate=asyncio.Semaphore(0)
            with patch.object(api,'_slot',gate),patch.object(api,'_make_exchange',return_value=exchange),patch.object(api.time,'time',return_value=NOW):
                rows=[row async for row in api._events(Request(),'BTC/USD')]
            self.assertFalse(gate.locked())
            return rows
        rows=asyncio.run(run())
        self.assertEqual(sum(row.startswith('event: trade') for row in rows),1)
        trade=json.loads(next(row for row in rows if row.startswith('event: trade')).split('data: ',1)[1])
        self.assertEqual((trade['provider'],trade['symbol'],trade['price'],trade['quantity_currency']),('kraken','BTC/USD',100.0,'BTC'))
        self.assertNotIn('id',trade)
        self.assertTrue(exchange.closed)
    def test_trade_validation_rejects_stale_future_and_bad_values(self):
        good={'id':'x','symbol':'BTC/USD','timestamp':int(NOW*1000),'price':100,'amount':1}
        for changes in ({'id':None},{'timestamp':int(NOW*1000)-30001},{'timestamp':int(NOW*1000)+1},
                        {'price':float('nan')},{'price':True},{'amount':0},{'symbol':'BTC/USDT'}):
            value={**good,**changes}
            with self.subTest(changes=changes):self.assertIsNone(api._trade(value,'BTC/USD',int(NOW*1000)))
    def test_bad_market_never_starts_stream(self):
        exchange=Exchange()
        async def bad(): return {'BTC/USD':{'symbol':'BTC/USD','base':'BTC','quote':'USDT','spot':True,'active':True,'id':'XXBTZUSD'}}
        exchange.load_markets=bad
        async def run():
            with patch.object(api,'_slot',asyncio.Semaphore(0)),patch.object(api,'_make_exchange',return_value=exchange):
                return [row async for row in api._events(Request(),'BTC/USD')]
        rows=asyncio.run(run())
        self.assertEqual(len(rows),1);self.assertIn('market_identity_unverified',rows[0]);self.assertTrue(exchange.closed)

    def test_other_usd_spot_symbols_require_and_use_exact_identity(self):
        self.assertIsNotNone(api._SPOT_SYMBOL.fullmatch('SOL/USD'))
        exchange=Exchange()
        async def markets(): return {'SOL/USD':{'symbol':'SOL/USD','base':'SOL','quote':'USD','spot':True,'active':True,'id':'SOLUSD'}}
        async def trades(symbol, limit):
            return [{'id':'one','symbol':symbol,'timestamp':int(NOW*1000),'price':100,'amount':1}]
        exchange.load_markets=markets;exchange.watch_trades=trades
        async def run():
            with patch.object(api,'_slot',asyncio.Semaphore(0)),patch.object(api,'_make_exchange',return_value=exchange),patch.object(api.time,'time',return_value=NOW):
                return [row async for row in api._events(Request(),'SOL/USD')]
        rows=asyncio.run(run())
        trade=json.loads(next(row for row in rows if row.startswith('event: trade')).split('data: ',1)[1])
        self.assertEqual((trade['symbol'],trade['quantity_currency']),('SOL/USD','SOL'))

    def test_slot_released_if_close_is_cancelled(self):
        exchange=Exchange()
        async def cancelled_close(): raise asyncio.CancelledError()
        exchange.close=cancelled_close
        async def run():
            gate=asyncio.Semaphore(0)
            with patch.object(api,'_slot',gate),patch.object(api,'_make_exchange',return_value=exchange),patch.object(api.time,'time',return_value=NOW):
                with self.assertRaises(asyncio.CancelledError):
                    _ = [row async for row in api._events(Request(),'BTC/USD')]
                self.assertFalse(gate.locked())
                await gate.acquire()
                self.assertTrue(gate.locked())  # Exactly one release.
        asyncio.run(run())

    def test_response_releases_slot_when_generator_never_starts(self):
        async def run():
            gate=asyncio.Semaphore(0)
            lease=api._StreamLease()
            async def never_started():
                yield 'unused'
            async def disconnected(response, scope, receive, send):
                raise asyncio.CancelledError()
            with patch.object(api,'_slot',gate),patch.object(api.StreamingResponse,'__call__',disconnected):
                response=api._LeasedStreamingResponse(never_started(),lease=lease)
                with self.assertRaises(asyncio.CancelledError):
                    await response({},None,None)
                self.assertFalse(gate.locked())
                lease.release()
                await gate.acquire()
                self.assertTrue(gate.locked())
        asyncio.run(run())

if __name__ == '__main__': unittest.main()
