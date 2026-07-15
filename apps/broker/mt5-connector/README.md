# TNSVT V2 - MT5 Connector

**⚠️ IMPORTANTE: Este servicio SOLO corre en Windows** (donde está instalado MetaTrader 5).

Implementa la interfaz `Connector` para MetaTrader 5. Recibe requests HTTP del execution-engine y los ejecuta en MT5 real.

## 🏗️ Arquitectura

```
execution-engine (Linux/Docker)
    ↓ HTTP POST /api/v1/brokers/orders
mt5-connector (Windows host)
    ↓ Subprocess Python
mt5_bridge.py → MetaTrader5 library
    ↓
MT5 Terminal (terminal64.exe)
    ↓
Broker (FTMO server)
```

## 🔧 Setup Windows

### Requisitos:
1. **Windows 10/11** o **Windows Server 2019+**
2. **Python 3.12+** instalado
3. **MetaTrader 5 terminal** instalado (ej: `C:\Program Files\FTMO MetaTrader 5\terminal64.exe`)
4. **Cuenta MT5** (login, password, server)

### Instalación:

```powershell
# 1. Instalar MetaTrader5 library
pip install MetaTrader5

# 2. Verificar
python -c "import MetaTrader5; print('OK')"

# 3. Compilar el connector
cd apps\broker\mt5-connector
go build -o mt5-connector.exe .

# 4. Configurar .env (en la raíz del proyecto)
$env:MT5_PATH = "C:\Program Files\FTMO MetaTrader 5\terminal64.exe"
$env:MT5_LOGIN = "12345678"
$env:MT5_PASSWORD = "your_password"
$env:MT5_SERVER = "FTMO-Demo"
$env:MT5_SYMBOL_SUFFIX = ".m"

# 5. Ejecutar
.\mt5-connector.exe
```

### Con Docker (Windows host):

```powershell
docker build -f Dockerfile.windows -t tnsvt/mt5-connector .

docker run -d `
  --name mt5-connector `
  -p 8007:8007 `
  -e MT5_PATH="C:\Program Files\FTMO MetaTrader 5\terminal64.exe" `
  -e MT5_LOGIN=12345678 `
  -e MT5_PASSWORD=your_password `
  -e MT5_SERVER=FTMO-Demo `
  -v "C:\Program Files\FTMO MetaTrader 5:C:\Program Files\FTMO MetaTrader 5:ro" `
  tnsvt/mt5-connector
```

## 📡 HTTP API

| Método | Path | Descripción |
|--------|------|-------------|
| POST | `/api/v1/brokers/orders` | Colocar orden |
| POST | `/api/v1/brokers/positions/close` | Cerrar posición |
| GET | `/api/v1/brokers/accounts/:id` | Info de cuenta |
| GET | `/api/v1/brokers/accounts/:id/positions` | Posiciones abiertas |
| POST | `/api/v1/brokers/positions/:ticket/modify` | Modificar SL/TP |
| GET | `/api/v1/brokers/symbols/:symbol` | Info del símbolo |
| GET | `/health`, `/health/live`, `/health/ready`, `/metrics` | Health |

### Ejemplo: Place Order

```bash
curl -X POST http://localhost:8007/api/v1/brokers/orders \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD.m",
    "side": "buy",
    "order_type": "market",
    "quantity": 0.01,
    "stop_loss": 1.0830,
    "take_profit": 1.0890,
    "comment": "TNSVT signal",
    "deviation": 20
  }'
```

## 🔌 Símbolos

Soporte completo de símbolos MT5 con normalización automática:

```
EURUSD       → EURUSD
EURUSD.m     → EURUSD.m (sin cambio, ya tiene suffix)
```

Configurar suffix en `MT5_SYMBOL_SUFFIX` para tu broker (ej: `.m`, `.pro`, `.raw`).

## 🛡️ Reconexión Automática

Si MT5 se desconecta (crash, restart, network), el connector reintenta cada 30s:

```go
go mt5Client.RunReconnectLoop(ctx, 30*time.Second)
```

Mientras tanto, el execution-engine recibe error y entra en retry.

## 🐍 Bridge Python

El connector usa `subprocess` para llamar a `mt5_bridge.py` que usa la librería oficial `MetaTrader5`. Razones:

1. **Sin cgo**: la librería MT5 es Python puro con bindings nativos
2. **Debugging fácil**: logs claros en Python
3. **Updates rápidos**: actualizar Python sin recompilar Go

Operaciones soportadas:
- `initialize` — conecta y hace login
- `shutdown` — desconecta
- `account_info` — retorna balance, equity, margin
- `place_order` — MARKET, LIMIT, STOP con SL/TP
- `close_position` — cierre por ticket
- `modify_position` — modificar SL/TP
- `positions_get` — filtradas por magic number
- `symbol_info` — info del símbolo

## ⚙️ Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `MT5_PATH` | Path a terminal64.exe | `C:\Program Files\FTMO MetaTrader 5\terminal64.exe` |
| `MT5_LOGIN` | Login de cuenta | `0` |
| `MT5_PASSWORD` | Password | `""` |
| `MT5_SERVER` | Servidor (ej: FTMO-Demo) | `""` |
| `MT5_SYMBOL_SUFFIX` | Suffix de símbolos | `""` |
| `MT5_MAGIC_NUMBER` | Magic number para identificar nuestras órdenes | `123456` |
| `MT5_TIMEOUT_SECONDS` | Timeout por operación | `30` |
| `MT5_CONNECTOR_PORT` | Puerto HTTP | `8007` |

## 🔗 Integración

```
execution-engine
    ↓ HTTP
mt5-connector ← ESTE SERVICIO
    ↓ subprocess Python
mt5_bridge.py
    ↓ MetaTrader5 library
MT5 Terminal
```

## 📋 Ver También

- [`docs/02-SERVICES-CATALOG.md`](../../../docs/02-SERVICES-CATALOG.md)
- [`docs/06-SECURITY.md`](../../../docs/06-SECURITY.md) — seguridad de credenciales MT5