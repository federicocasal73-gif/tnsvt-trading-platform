# 🤖 MT5 Bot Admin PRO v14.2 (AI Golden Release)
### Guía Definitiva de Instalación y Uso

Este sistema ha evolucionado. Ahora cuenta con un **Cerebro IA (Gemini)** y **Auto-Resolución de Símbolos**, lo que lo hace el bot más sencillo y potente del mercado.

---

## 📋 1. Requisitos Previos

1.  **MetaTrader 5 (MT5):** Ten tu broker logueado y el botón **"Trading algorítmico"** en **VERDE** (Play).
2.  **Python 3.10+:** Asegúrate de tenerlo instalado en tu PC.
3.  **Google AI Key:** El bot ya viene configurado con una, pero puedes poner la tuya en `ai_parser.py`.

---

## 🚀 2. Instalación (Solo la primera vez)

1.  Abre la carpeta `Señales`.
2.  Escribe `cmd` en la barra de direcciones de la carpeta y presiona Enter.
3.  Instala las librerías necesarias ejecutando este comando:
    ```powershell
    pip install -r requirements.txt
    ```

---

## 🎮 3. Inicio Rápido

Para arrancar todo el ecosistema (Panel Web + Bot), usa el archivo:
> **🖲️ `START_BOT.bat`** (Doble clic)

---

## 🧠 4. Lo NUEVO de la v14.2

### 📡 Auto-Discovery de Símbolos
**Ya no tienes que elegir Broker ni poner sufijos.** El bot es inteligente:
*   Si la señal dice `EURUSD` pero tu broker usa `EURUSD-T`, el bot lo encontrará solo.
*   Funciona con todos los brokers (Exness, Admirals, IC Markets, etc.) sin configuración extra.

### 🧠 Cerebro IA (Google Gemini)
El bot ahora "entiende" lo que lee:
*   **Regex:** Detecta señales estándar instantáneamente.
*   **IA Fallback:** Si la señal es un mensaje hablado ("Compren oro ahora muchachos..."), la IA lo interpreta y extrae la orden automáticamente.

---

## 🛠️ 5. Configuración en el Panel

1.  **Pestaña Cuenta & Operativa:** Configura tu lotaje (Fijo o % de Riesgo).
2.  **Pestaña Gestión de Riesgo:** Pon tus metas de ganancia o límites de pérdida del día.
3.  **Pestaña Conexión:** 
    *   Escanea el QR para conectar tu Telegram.
    *   Pulsa "🔍 ESCANEAR CANALES" para ver tus grupos y sub-canales.
    *   **Selecciona** los canales donde llegan las señales.

---

## 🚀 6. Activación Final

1.  En la barra lateral, pulsa **"🚀 INICIAR PROGRAMA"**.
2.  Mira la ventana negra (consola). Debe decir:
    *   `✅ Conexión MT5 EXITOSA`.
    *   `🧠 Cerebro IA: ACTIVO`.
3.  ¡Listo! El bot ya está operando por ti.

---
*MT5 Bot Admin PRO v14.2 - Inteligencia y Simplicidad.*
