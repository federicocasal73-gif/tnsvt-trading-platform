# Liquidity Engine (LST)

Um microserviço FastAPI baseado em Python que gera sinais de liquidez (LST — Liquidity Signal for Trading) a partir de dados OHLCV do MT5.

## Comissionamento

```bash
cd apps/ai/liquidity-engine
pip install -e . [&pytest tests/ -v]
uvicorn app.main:app --port 8050
```

## Endpoints

| Método | Rota | Descrição |
|--------|------|-------------|
| GET    | `/health` | Estado do serviço (status, serviço, versão) |
| GET    | `/lst/latest` | Retorna o sinal LST mais recente para um símbolo e período (query params: symbol, timeframe) |
| POST   | `/reset` | Reseta o buffer interno do motor LST |

## Modelo

### LSTSignal
- `symbol`: Ativo negociado
- `timestamp`: Data/hora do sinal (UTC)
- `timeframe`: Período de tempo (`M1`, `M5`, `M15`)
- `signal_type`: `liquidity_buy`, `liquidity_sell`, `neutral`
- `confidence`: 0.0 a 1.0
- `metrics`: objeto LSTMetrics

### LSTMetrics
- `relative_spread`: spread normalizado (`(ask - bid) / mid * 10000`)
- `volume_imbalance`: `(buy_vol - sell_vol) / total_vol` (aproximado via proximidade do preço de fechamento)
- `order_flow_pressure`: pressão direcional de fluxo de pedidos baseada na posição do preço de fechamento no range
- `microstructure_score`: score composto de qualidade do mercado
- `liquidity_score`: score geral de liquidez (1 = muito líquido)

### RateOHLCV
- Dados de OHLCV do MT5. Consulte MT5 connector para dados originais.

## Motor LST

Entrada → janela de barras (`n=20`) → cálculo das métricas → classificação → sinal LST

Bases:
- **Spread relativo**: spread normalizado para comparação entre ativos.
- **Desequilíbrio de volume**: leaning direcional com base no movimento do preço de fechamento na barra.
- **Pressão de fluxo de ordens**: sensibilidade à posição do preço de fechamento no range alto-baixo.
- **Score de microestrutura**: score composto ponderando spread vs volume.
- **Score de liquidez**: synthesis final ponderando qualidade do spread, consistência de volume e profundidade.

Lógica de sinal:
- Baixo score de liquidez (<0.3) → neutro
- Score de liquidez alto + pressão direcional equilibrada → buy/sell com confiança ponderada pelo score
- Negativo nos dois ou condições fora de convergência → neutro

## Arquitetura

```
MT5 Connector HTTP (/api/v1/brokers/symbols/:symbol/rates) → Liquidity Engine (LST calc) → NATS JetStream (tnsvt.lst.signal) → Execution Engine (consume)
```

- **Polling**: Consulta MT5 a cada `LST_INTERVAL_SECONDS` (padrão: 60s) por símbolo/periodo.
- **Buffer interno**: Janela deslizante de ordens para cada símbolo+período (default: `window_size=20`).
- **NATS**: Publica sinais como JSON (`LSTSignal`) via stream `tnsvt` subject `tnsvt.lst.signal`.
- **Observa**: Execution engine pode se inscrever no mesmo subject para sinais em tempo real.

## Observabilidade

- **Prometheus**: Métricas integradas em `/metrics`.
- **Logging**: Registros estruturados do motor de cálculo e pontos finais.
- **Health Check**: /health, /reset (reset manual do buffer do motor).
- **Suporte**: ao erro do MT5 connector (cf. tratação à nível do endpoint).

## Teste

```bash
cd apps/ai/liquidity-engine
python -m pytest tests/ -v
```

Testes:
- `test_neutral_until_window_filled`: warmup.
- `test_liquidity_buy_signal`: classification de compra.
- `test_liquidity_sell_signal`: classification de venda.
- `test_neutral_low_volume`: liquidez baixa força neutro.
- `test_reset`: reset do buffer.
- `test_metrics_bounds`: checks de limites dos metrics.

Passos detalhados no arquivo `docs/liquid-liquidity-engine.md` no app.

## Deploy

Configure como um serviço docker separado:

```yaml
services:
  liquidity-engine:
    build:
      context: .
      dockerfile: apps/ai/liquidity-engine/Dockerfile
    environment:
      LST_PORT: "8050"
      LST_NATS_URL: nats://nats:4222
      LST_MT5_CONNECTOR_URL: http://localhost:8007
      LST_SYMBOLS: XAUUSD
      LST_TIMEFRAMES: M1,M5,M15
    ports:
      - "8050:8050"
```

## Configuração

Variáveis de ambiente com prefixo `LST_`:

- `LST_HOST`: Bind (padrão: `0.0.0.0`)
- `LST_PORT`: HTTP port (padrão: `8050`)
- `LST_NATS_URL`: URL NATS (padrão: `nats://localhost:4222`)
- `LST_NATS_STREAM`: nome do stream (padrão: `tnsvt`)
- `LST_NATS_SUBJECT_LST`: assunto (padrão: `tnsvt.lst.signal`)
- `LST_MT5_CONNECTOR_URL`: http://localhost:8007
- `LST_SYMBOLS`: comma separado, ex: `XAUUSD`
- `LST_TIMEFRAMES`: ex: `M1,M5,M15`
- `LST_INTERVAL_SECONDS`: polling interval (padrão: `60`)

Env var `LST_APP_NAME` usado no health check.

## Observação / Fluxo de trabalho futuras

1. Modo assíncrono / streaming: assinatura estilo SSE no MT5 connector (server-sent events de rates) para menor polling.
2. Decisão baseada em sinal no execution engine (já escuta NATS).
3. Thresholds adaptativos (score de liquidez por ativo).
4. Tagging com rótulo (spread, volume, microestrutura) para mosaico de scorecard.
5. Geração de DB de histórico de sinais para feature engineering.

## Problemas conhecidos

- Polling é síncrono: um erro do MT5 connector pausa os logs do motor até retry.
- Buffer por processo: múltiplos processos liquidity-engine duplicarão janelas por ativo.

## Contribuição

```bash
cd /github.com/your-repo/tnsvt-v2-architecture
# Fork e PR para apps/ai/liquidity-engine
```