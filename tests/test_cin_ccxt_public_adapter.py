import unittest
from cin_ccxt_public_adapter import PublicSpotAdapter, PublicDataUnavailable

NOW = 1_800_000_000_000
DURATION = 3_600_000
END = NOW // DURATION * DURATION

class FakeExchange:
    def __init__(self, options):
        self.options = options
        self.symbol = 'BTC/USD'
        self.market = {'id':'XBTUSD','symbol':self.symbol,'base':'BTC','quote':'USD','spot':True,'active':True}
        self.ticker = {'symbol':self.symbol,'last':100.0,'timestamp':NOW-1000}
        self.rows = [[END-(3-i)*DURATION,100,103,99,102,20] for i in range(3)]
        self.book = {'symbol':'BTC/USD','timestamp':NOW-1000,'bids':[[99,2],[98,3]],'asks':[[101,4],[102,5]]}
        self.calls = []
        self.failure = None
    def load_markets(self):
        self.calls.append('load_markets')
        if self.failure: raise self.failure
        return {self.symbol:self.market}
    def fetch_ticker(self, symbol):
        self.calls.append('fetch_ticker'); return self.ticker
    def fetch_ohlcv(self, symbol, timeframe, limit):
        self.calls.append('fetch_ohlcv'); return self.rows
    def fetch_order_book(self, symbol, limit):
        self.calls.append('fetch_order_book'); return self.book

class Tests(unittest.TestCase):
    def setUp(self):
        self.exchanges={}
        def factory(name):
            def make(options):
                self.exchanges[name]=FakeExchange(options); return self.exchanges[name]
            return make
        self.adapter=PublicSpotAdapter(factories={n:factory(n) for n in ('kraken','coinbase')},clock_ms=lambda:NOW,monotonic=lambda:100)
    def test_only_safe_options_and_public_methods_exposed(self):
        for ex in self.exchanges.values():
            self.assertEqual(ex.options, {'enableRateLimit':True,'timeout':10000})
        for method in ('create_order','cancel_order','fetch_balance','withdraw','deposit'):
            self.assertFalse(hasattr(self.adapter,method))
    def test_ticker_attaches_exact_market_and_source(self):
        result=self.adapter.ticker('BTC/USD')
        self.assertEqual((result['provider'],result['symbol'],result['quote_currency'],result['last']),('kraken','BTC/USD','USD',100.0))
        self.assertEqual(self.exchanges['kraken'].calls,['load_markets','fetch_ticker'])
    def test_retrieval_clock_is_read_after_provider_response(self):
        clock = [NOW]
        ex = self.exchanges['kraken']
        def fetch(symbol):
            clock[0] += 500
            return {'symbol':symbol,'last':100.0,'timestamp':NOW+200}
        ex.fetch_ticker = fetch
        adapter = PublicSpotAdapter(factories={'kraken':lambda options: ex},clock_ms=lambda:clock[0])
        result = adapter.ticker('BTC/USD', providers=('kraken',))
        self.assertEqual(result['observed_at_ms'], NOW+200)
        self.assertTrue(result['retrieved_at'].endswith('.500000+00:00'))
    def test_fallback_stays_same_market_and_explains_failure(self):
        self.exchanges['kraken'].failure=TimeoutError('not exposed')
        result=self.adapter.ticker('BTC/USD')
        self.assertEqual(result['provider'],'coinbase')
        self.assertEqual(result['attempts'],[{'provider':'kraken','reason':'timeout'}])
        self.assertEqual(result['symbol'],'BTC/USD')
    def test_usd_is_not_substituted_for_usdt(self):
        with self.assertRaises(PublicDataUnavailable): self.adapter.ticker('BTC/USDT')
        self.assertNotIn('fetch_ticker',self.exchanges['kraken'].calls)
    def test_unknown_inactive_and_derivative_markets_rejected(self):
        for change in ({'active':False},{'spot':False},{'base':'ETH'},{'quote':'USDT'}):
            with self.subTest(change=change):
                for ex in self.exchanges.values(): ex.market.update({'active':True,'spot':True,'base':'BTC','quote':'USD'});ex.market.update(change)
                with self.assertRaises(PublicDataUnavailable): self.adapter.ticker('BTC/USD')
    def test_missing_provider_market_identifier_is_rejected(self):
        for ex in self.exchanges.values(): ex.market['id'] = None
        with self.assertRaises(PublicDataUnavailable): self.adapter.ticker('BTC/USD')
    def test_ticker_timestamp_and_price_integrity(self):
        for key,value in [('timestamp',None),('timestamp',NOW+1),('timestamp',NOW-900001),('last',float('nan')),('last',True),('last',0),('symbol','BTC/USDT')]:
            with self.subTest(key=key,value=value):
                for ex in self.exchanges.values(): ex.ticker={'symbol':'BTC/USD','last':100.,'timestamp':NOW-1000};ex.ticker[key]=value
                with self.assertRaises(PublicDataUnavailable): self.adapter.ticker('BTC/USD')
    def test_timestamp_missing_is_reported_without_relaxing_freshness(self):
        self.exchanges['kraken'].ticker['timestamp'] = None
        result = self.adapter.ticker('BTC/USD')
        self.assertEqual(result['provider'], 'coinbase')
        self.assertEqual(result['attempts'], [{'provider':'kraken','reason':'provider_timestamp_missing'}])
        self.assertEqual(result['observed_at_ms'], NOW-1000)
    def test_ticker_data_quality_reasons_are_safe_and_precise(self):
        for key, value, expected in [('timestamp', None, 'provider_timestamp_missing'),
                                     ('timestamp', True, 'provider_timestamp_invalid'),
                                     ('timestamp', NOW+1, 'provider_timestamp_future'),
                                     ('timestamp', NOW-900001, 'provider_timestamp_stale'),
                                     ('last', float('nan'), 'invalid_ticker_price'),
                                     ('symbol', 'BTC/USDT', 'ticker_market_mismatch')]:
            with self.subTest(expected=expected):
                self.exchanges['kraken'].ticker = {'symbol':'BTC/USD','last':100.,'timestamp':NOW-1000}
                self.exchanges['kraken'].ticker[key] = value
                result = self.adapter.ticker('BTC/USD')
                self.assertEqual(result['attempts'][0]['reason'], expected)
    def test_closed_continuous_candles(self):
        result=self.adapter.candles('BTC/USD','1h',3)
        self.assertEqual(result['count'],3)
        self.assertTrue(result['closed_candles'])
        self.assertEqual(result['data'][-1][0],END-DURATION)
    def test_extra_closed_candle_keeps_latest_requested_window(self):
        result = self.adapter.candles('BTC/USD', '1h', 2)
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['data'][0][0], END - 2 * DURATION)
    def test_gaps_duplicates_invalid_and_stale_candles_fail_closed(self):
        cases=[lambda rows: rows.__setitem__(1,rows[0]),lambda rows: rows[1].__setitem__(1,-1),lambda rows: rows[1].__setitem__(2,1),lambda rows: rows[1].__setitem__(5,float('nan')),lambda rows: rows[1].__setitem__(0,rows[1][0]+1),lambda rows: rows.pop(),lambda rows: [r.__setitem__(0,r[0]-20*DURATION) for r in rows]]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                for ex in self.exchanges.values(): ex.rows=[[END-(3-i)*DURATION,100,103,99,102,20] for i in range(3)];mutate(ex.rows)
                with self.assertRaises(PublicDataUnavailable): self.adapter.candles('BTC/USD','1h',3)
    def test_forming_candle_excluded_and_future_rejected(self):
        for ex in self.exchanges.values(): ex.rows.append([END,100,103,99,102,20])
        self.assertEqual(self.adapter.candles('BTC/USD','1h',3)['count'],3)
        for ex in self.exchanges.values(): ex.rows[-1][0]=END+DURATION
        with self.assertRaises(PublicDataUnavailable): self.adapter.candles('BTC/USD','1h',3)
    def test_limits_and_provider_allowlist(self):
        for args in [('BTC/USD','1h',True),('BTC/USD','1h',201),('BTC/USD','9m',3),('XXX/USD','1h',3)]:
            with self.subTest(args=args),self.assertRaises(ValueError):self.adapter.candles(*args)
        with self.assertRaises(ValueError):self.adapter.ticker('BTC/USD',providers=('binance',))
    def test_per_provider_budget_limits_repeated_operations(self):
        for _ in range(20):self.adapter.ticker('BTC/USD',providers=('kraken',))
        with self.assertRaises(PublicDataUnavailable) as exc:self.adapter.ticker('BTC/USD',providers=('kraken',))
        self.assertEqual(exc.exception.attempts[0]['reason'],'local_budget_exhausted')
    def test_public_order_book_has_explicit_units_and_spread(self):
        book = self.adapter.order_book('BTC/USD')
        self.assertEqual((book['provider'], book['kind'], book['quantity_unit'], book['price_currency']), ('kraken', 'order_book', 'BTC', 'USD'))
        self.assertEqual((book['best_bid'], book['best_ask'], book['spread']), (99,101,2))
        self.assertAlmostEqual(book['spread_percent_midpoint'], 2)
        self.assertFalse(book['analysis_eligible'])
        self.assertEqual(book['freshness_status'], 'fresh_by_provider_timestamp')
    def test_decimal_spread_does_not_show_binary_float_artifact(self):
        self.exchanges['kraken'].book['bids'] = [[76763.7, 1]]
        self.exchanges['kraken'].book['asks'] = [[76763.8, 1]]
        self.assertEqual(self.adapter.order_book('BTC/USD')['spread'], 0.1)
    def test_missing_book_time_is_unknown_and_ineligible(self):
        self.exchanges['kraken'].book['timestamp'] = None
        book = self.adapter.order_book('BTC/USD')
        self.assertEqual(book['freshness_status'], 'unknown')
        self.assertFalse(book['analysis_eligible'])
    def test_provider_level_metadata_is_not_misidentified(self):
        self.exchanges['kraken'].book['bids'] = [[99, 2, 1234567890], [98, 3, 1234567890]]
        book = self.adapter.order_book('BTC/USD')
        self.assertEqual(book['bids'], [[99.0, 2.0], [98.0, 3.0]])
    def test_invalid_order_books_fail_closed(self):
        cases = [({'bids':[]}, 'invalid_order_book_depth'),
                 ({'bids':[[99,0]]}, 'invalid_order_book_level'),
                 ({'bids':[[99,1],[100,1]]}, 'order_book_out_of_order'),
                 ({'asks':[[98,1]]}, 'crossed_or_locked_order_book'),
                 ({'timestamp':NOW+1}, 'provider_timestamp_future'),
                 ({'timestamp':NOW-60001}, 'provider_timestamp_stale'),
                 ({'symbol':'BTC/USDT'}, 'order_book_market_mismatch')]
        for changes, reason in cases:
            with self.subTest(reason=reason):
                for ex in self.exchanges.values():
                    ex.book = {'symbol':'BTC/USD','timestamp':NOW-1000,'bids':[[99,2],[98,3]],'asks':[[101,4],[102,5]]}
                    ex.book.update(changes)
                with self.assertRaises(PublicDataUnavailable) as error:
                    self.adapter.order_book('BTC/USD')
                self.assertEqual(error.exception.attempts[0]['reason'], reason)
    def test_comparison_requires_exact_same_closed_candle(self):
        for ex in self.exchanges.values(): ex.rows = ex.rows[-2:]
        self.exchanges['coinbase'].market['id'] = 'BTC-USD'
        self.exchanges['coinbase'].rows[-1][4] = 102.5
        result = self.adapter.compare_closed_candles('BTC/USD')
        self.assertEqual(result['comparison_status'], 'comparable_closed_window')
        self.assertEqual(result['comparison']['difference_quote'], 0.5)
        self.assertFalse(result['analysis_eligible'])
        for row in self.exchanges['coinbase'].rows: row[0] -= DURATION
        result = self.adapter.compare_closed_candles('BTC/USD')
        self.assertEqual(result['comparison_status'], 'window_mismatch')
        self.assertIsNone(result['comparison'])
    def test_comparison_remains_partial_when_provider_fails(self):
        self.exchanges['kraken'].rows = self.exchanges['kraken'].rows[-2:]
        self.exchanges['coinbase'].failure = TimeoutError('secret ignored')
        result = self.adapter.compare_closed_candles('BTC/USD')
        self.assertEqual(result['comparison_status'], 'partial')
        self.assertEqual(len(result['sources']), 1)
        self.assertIsNone(result['comparison'])
        self.assertEqual(result['failures'][0]['reason'], 'timeout')
    def test_comparison_reports_unavailable_when_both_providers_fail(self):
        for ex in self.exchanges.values(): ex.failure = TimeoutError()
        result = self.adapter.compare_closed_candles('BTC/USD')
        self.assertEqual(result['comparison_status'], 'unavailable')
        self.assertEqual(result['sources'], [])
        self.assertIsNone(result['comparison'])

if __name__=='__main__': unittest.main()
