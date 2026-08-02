import pytest
from parser import SignalParserV3


@pytest.fixture
def parser():
    return SignalParserV3()


class TestDetectAction:
    def test_buy(self, parser):
        assert parser._detect_action("BUY GOLD") == "BUY"

    def test_sell(self, parser):
        assert parser._detect_action("SELL GOLD") == "SELL"

    def test_long_as_buy(self, parser):
        assert parser._detect_action("Long XAUUSD") == "BUY"

    def test_short_as_sell(self, parser):
        assert parser._detect_action("Short EURUSD") == "SELL"

    def test_spanish_buy(self, parser):
        assert parser._detect_action("Compra el oro") == "BUY"

    def test_spanish_sell(self, parser):
        assert parser._detect_action("Venta el oro") == "SELL"

    def test_no_action_returns_none(self, parser):
        assert parser._detect_action("Just some random text 123") is None

    def test_buy_sell_ambiguous(self, parser):
        assert parser._detect_action("Buy now then sell later") == "BUY"


class TestDetectSymbol:
    def test_xauusd(self, parser):
        sym, raw = parser._detect_symbol("BUY XAUUSD @ 4000", "buy xauusd @ 4000")
        assert sym == "XAUUSD"

    def test_gold_alias(self, parser):
        sym, raw = parser._detect_symbol("BUY GOLD", "buy gold")
        assert sym == "XAUUSD"

    def test_oro_alias(self, parser):
        sym, raw = parser._detect_symbol("COMPRA ORO", "compra oro")
        assert sym == "XAUUSD"

    def test_btc(self, parser):
        sym, raw = parser._detect_symbol("SELL BITCOIN", "sell bitcoin")
        assert sym == "BTCUSD"

    def test_silver_alias(self, parser):
        sym, raw = parser._detect_symbol("BUY SILVER", "buy silver")
        assert sym == "XAGUSD"

    def test_eurusd_forex(self, parser):
        sym, raw = parser._detect_symbol("BUY EURUSD", "buy eurusd")
        assert sym == "EURUSD"

    def test_implicit_gold(self, parser):
        sym = parser._detect_implicit_symbol("el oro")
        assert sym == "XAUUSD"


class TestDetectPrices:
    def test_at_price(self, parser):
        signal = parser._parse("buy xauusd @ 4038.5", "BUY XAUUSD @ 4038.5")
        assert signal.price == 4038.5

    def test_price_keyword(self, parser):
        signal = parser._parse("buy xauusd price: 1.12345", "BUY XAUUSD price: 1.12345")
        assert signal.price == 1.12345

    def test_entry_keyword(self, parser):
        signal = parser._parse("sell eurusd entry: 1.1050", "SELL EURUSD entry: 1.1050")
        assert signal.price == 1.1050

    def test_price_range(self, parser):
        nums = parser._extract_first_number("SL@3980", [r'sl@([\d.]+)'])
        assert nums == 3980.0

    def test_spanish_precio(self, parser):
        signal = parser._parse("buy xauusd precio: 4010", "BUY XAUUSD precio: 4010")
        assert signal.price == 4010.0


class TestDetectSLTP:
    def test_sl(self, parser):
        signal = parser._parse(
            "SELL GOLD\nSL:4020.3\nTP:3980.3",
            "SELL GOLD\nSL:4020.3\nTP:3980.3",
        )
        assert signal.sl == 4020.3
        assert 3980.3 in signal.tp

    def test_multiple_tp(self, parser):
        text = "XAUUSD buy now @ 4038.5\ntp @ 4062\ntp2 @ 4090\nSL @ 4017"
        signal = parser._parse(text, "XAUUSD buy now @ 4038.5\ntp @ 4062\ntp2 @ 4090\nSL @ 4017")
        assert signal.sl == 4017.0
        assert 4062.0 in signal.tp
        assert 4090.0 in signal.tp

    def test_sl_at_symbol(self, parser):
        signal = parser._parse(
            "Vender limit xauusd @4897\nSl@4941\ntp-1@4850\ntp-2@4772",
            "Vender limit xauusd @4897\nSl@4941\ntp-1@4850\ntp-2@4772",
        )
        assert signal.sl == 4941.0
        assert 4850.0 in signal.tp
        assert 4772.0 in signal.tp


class TestDetectLot:
    def test_lot(self, parser):
        signal = parser._parse(
            "BUY XAUUSD lot: 0.50 SL: 4000 TP: 4100",
            "BUY XAUUSD lot: 0.50 SL: 4000 TP: 4100",
        )
        assert signal.lot == 0.50

    def test_lote_spanish(self, parser):
        signal = parser._parse(
            "COMPRA ORO lote: 1.00 SL: 4000 TP: 4100",
            "COMPRA ORO lote: 1.00 SL: 4000 TP: 4100",
        )
        assert signal.lot == 1.00


class TestSLTPUpdate:
    def test_sl_only_update(self, parser):
        pending = {"action": "BUY", "symbol": "XAUUSD", "price": 4000.0, "sl": 3980.0, "tp": [4050.0]}
        result = parser.parse_message("SL 3970", pending)
        assert result["is_update"] is True
        assert result["sl"] == 3970.0

    def test_tp_only_update(self, parser):
        pending = {"action": "BUY", "symbol": "XAUUSD", "price": 4000.0, "sl": 3980.0, "tp": [4050.0]}
        result = parser.parse_message("TP 4070", pending)
        assert result["is_update"] is True
        assert 4070.0 in result["tp"]

    def test_sl_tp_update(self, parser):
        pending = {"action": "SELL", "symbol": "XAUUSD", "price": 4100.0, "sl": 4120.0, "tp": [4050.0]}
        result = parser.parse_message("SL 4130 TP 4030", pending)
        assert result["is_update"] is True


class TestIsComplete:
    def test_complete_signal(self, parser):
        signal = parser._parse(
            "BUY XAUUSD @ 4000 SL 3980 TP 4050",
            "BUY XAUUSD @ 4000 SL 3980 TP 4050",
        )
        assert signal.is_complete is True

    def test_incomplete_no_sl(self, parser):
        signal = parser._parse(
            "BUY XAUUSD @ 4000",
            "BUY XAUUSD @ 4000",
        )
        assert signal.is_complete is False

    def test_incomplete_no_tp(self, parser):
        signal = parser._parse(
            "BUY XAUUSD SL 3980",
            "BUY XAUUSD SL 3980",
        )
        assert signal.is_complete is False


class TestIsValidSignal:
    def test_valid(self, parser):
        assert parser.is_valid_signal({"action": "BUY", "symbol": "XAUUSD"}) is True

    def test_invalid_no_action(self, parser):
        assert parser.is_valid_signal({"symbol": "XAUUSD"}) is False

    def test_invalid_no_symbol(self, parser):
        assert parser.is_valid_signal({"action": "BUY"}) is False


class TestHasSlTp:
    def test_has_sl(self, parser):
        assert parser.has_sl_tp({"sl": 3980.0}) is True

    def test_has_tp(self, parser):
        assert parser.has_sl_tp({"tp": [4050.0]}) is True

    def test_has_neither(self, parser):
        assert parser.has_sl_tp({"action": "BUY"}) is False


class TestRealWorldScenarios:
    def test_xau_liquidity_venta(self, parser):
        text = "VENTA EN EL ORO\nSL:4020.3 (100 PIPS)\nTP:3980.3 (300 PIPS)"
        result = parser.parse_message(text)
        assert result["action"] == "SELL"
        assert result["symbol"] == "XAUUSD"
        assert result["sl"] == 4020.3
        assert 3980.3 in result["tp"]

    def test_xau_liquidity_compra(self, parser):
        text = "COMPRA EN EL ORO\nSL:4059.1 (100 PIPS)\nTP:4099.1 (300 PIPS)"
        result = parser.parse_message(text)
        assert result["action"] == "BUY"
        assert result["symbol"] == "XAUUSD"
        assert result["sl"] == 4059.1
        assert 4099.1 in result["tp"]

    def test_world_forex_buy(self, parser):
        text = "XAUUSD buy now @ 4038.5\nother buy @ 4031\ntp @ 4062\ntp2 @ 4090\nSL @ 4017"
        result = parser.parse_message(text)
        assert result["action"] == "BUY"
        assert result["symbol"] == "XAUUSD"
        assert result["sl"] == 4017.0
        assert 4062.0 in result["tp"]
        assert 4090.0 in result["tp"]

    def test_world_forex_sell_limit(self, parser):
        text = "XAUUSD sell limit @ 4122\nTp @ 4090\nSl @ 4137"
        result = parser.parse_message(text)
        assert result["action"] == "SELL"
        assert result["symbol"] == "XAUUSD"
        assert result["sl"] == 4137.0
        assert 4090.0 in result["tp"]

    def test_cobrax_noisy(self, parser):
        text = "SELL GOLD/XAUUSD @ NOW\nEntry: 3990-3992\nSL: 3997\n+TP1 3984\n.+TP2 3975\nTP3: Open"
        result = parser.parse_message(text)
        assert result["action"] == "SELL"
        assert result["symbol"] == "XAUUSD"
        assert result["price"] == 3990.0
        assert result["sl"] == 3997.0
        assert 3984.0 in result["tp"]
        assert 3975.0 in result["tp"]

    def test_cobrax_buy(self, parser):
        text = "BUY GOLD/XAUUSD @ NOW\nEntry: 3995-3993\nSL: 3989\nTP1 4001\nTP2 4010\nLTP3: Open"
        result = parser.parse_message(text)
        assert result["action"] == "BUY"
        assert result["symbol"] == "XAUUSD"
        assert result["sl"] == 3989.0
        assert 4001.0 in result["tp"]
        assert 4010.0 in result["tp"]

    def test_vip_signals_oil(self, parser):
        text = "Vender limit xauusd @4897\nSl@4941\ntp-1@4850\ntp-2@4772"
        result = parser.parse_message(text)
        assert result["action"] == "SELL"
        assert result["symbol"] == "XAUUSD"
        assert result["sl"] == 4941.0
        assert 4850.0 in result["tp"]
        assert 4772.0 in result["tp"]

    def test_vip_signals_oil_2(self, parser):
        text = "Vender EURUSD ahora @1.18182\n@1.18320\nTp-1@1.18020\nTp-2@1.17880"
        result = parser.parse_message(text)
        assert result["action"] == "SELL"
        assert result["symbol"] == "EURUSD"
        assert 1.18020 in result["tp"]
        assert 1.17880 in result["tp"]


class TestTPPercentages:
    def test_single_tp(self, parser):
        assert parser._calculate_tp_percentages(1) == [100]

    def test_two_tp(self, parser):
        assert parser._calculate_tp_percentages(2) == [50, 50]

    def test_three_tp(self, parser):
        assert parser._calculate_tp_percentages(3) == [50, 25, 25]

    def test_four_tp(self, parser):
        assert parser._calculate_tp_percentages(4) == [25, 25, 25, 25]

    def test_five_tp(self, parser):
        result = parser._calculate_tp_percentages(5)
        assert sum(result) == 100
        assert len(result) == 5
