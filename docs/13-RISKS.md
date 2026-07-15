# RISKS.md — Gestión de Riesgos Técnicos y Operativos

**Proyecto:** TNSVT V2 — Plataforma SaaS de Trading  
**Versión:** 2.0.0  
**Última Actualización:** 2026-07-14  
**Estado:** Documento de Análisis de Riesgos  

---

## Tabla de Contenidos

1. [Metodología](#1-metodología)
2. [Matriz de Riesgos](#2-matriz-de-riesgos)
3. [Inventario Completo de Riesgos](#3-inventario-completo-de-riesgos)
4. [Top 5 Riesgos Críticos — Planes Detallados](#4-top-5-riesgos-críticos--planes-detallados)
5. [Matriz de Probabilidad vs Impacto](#5-matriz-de-probabilidad-vs-impacto)
6. [Procedimientos de Monitoreo](#6-procedimientos-de-monitoreo)
7. [Planes de Contingencia](#7-planes-de-contingencia)
8. [Registro de Riesgos Activos](#8-registro-de-riesgos-activos)

---

## 1. Metodología

### 1.1 Escalas de Evaluación

**Probabilidad (P):**

| Valor | Nivel | Descripción |
|-------|-------|-------------|
| 1 | Muy Baja | < 10% de probabilidad de ocurrir |
| 2 | Baja | 10-30% de probabilidad |
| 3 | Media | 30-60% de probabilidad |
| 4 | Alta | 60-80% de probabilidad |
| 5 | Muy Alta | > 80% de probabilidad |

**Impacto (I):**

| Valor | Nivel | Impacto Financiero | Impacto en Usuarios | Impacto en Timeline |
|-------|-------|-------------------|--------------------|--------------------|
| 1 | Insignificante | < $1,000 | < 10 usuarios afectados | < 1 día de retraso |
| 2 | Menor | $1,000 - $10,000 | 10-100 usuarios | 1-5 días de retraso |
| 3 | Moderado | $10,000 - $50,000 | 100-1,000 usuarios | 1-2 semanas |
| 4 | Mayor | $50,000 - $200,000 | 1,000-10,000 usuarios | 2-4 semanas |
| 5 | Catastrófico | > $200,000 | > 10,000 usuarios | > 1 mes de retraso |

**Risk Score = Probabilidad × Impacto**

| Score | Nivel de Riesgo | Acción Requerida |
|-------|----------------|-------------------|
| 1-4 | Bajo | Monitoreo rutinario |
| 5-9 | Moderado | Plan de mitigación documentado |
| 10-15 | Alto | Mitigación activa, revisión quincenal |
| 16-25 | Crítico | Mitigación urgente, revisión semanal |

### 1.2 Propietarios de Riesgos

| Abreviatura | Rol | Responsabilidad |
|-------------|-----|-----------------|
| **ENG** | Engineering Lead | Riesgos técnicos de código |
| **OPS** | DevOps / Platform | Infraestructura y despliegue |
| **AI** | ML/AI Engineer | Modelos y datos |
| **PM** | Product Manager | Riesgos de producto y mercado |
| **SEC** | Security Lead | Seguridad y compliance |
| **CEO** | CEO / Founder | Riesgos estratégicos y financieros |

---

## 2. Matriz de Riesgos

### 2.1 Resumen por Categoría

| Categoría | Total | Bajo | Moderado | Alto | Crítico |
|-----------|-------|------|----------|------|---------|
| **Técnico** | 10 | 2 | 3 | 3 | 2 |
| **Operativo** | 4 | 1 | 2 | 1 | 0 |
| **Financiero** | 3 | 0 | 1 | 1 | 1 |
| **Regulatorio** | 2 | 0 | 0 | 1 | 1 |
| **Mercado** | 3 | 0 | 1 | 1 | 1 |
| **Total** | **22** | **3** | **7** | **7** | **5** |

### 2.2 Distribución de Riesgos

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    RISK HEAT MAP — PROBABILIDAD vs IMPACTO                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Impacto →     │  1          2          3          4          5             │
│  Probabilidad↓ │ Insignif.  Menor      Moderado   Mayor      Catastrófico  │
│  ──────────────┼─────────────────────────────────────────────────────────   │
│                │                                                            │
│  5 (Muy Alta)  │            │          │  R07     │          │  R01        │
│                │            │          │ [OVERTRD]│          │ [BROKER API] │
│                │            │          │          │          │              │
│  ──────────────┼────────────┼──────────┼──────────┼──────────┼──────────── │
│                │            │          │          │          │              │
│  4 (Alta)      │            │  R15     │  R03     │  R02     │  R09        │
│                │            │ [PERF]   │ [DB FAIL]│ [SECURITY│ [DATA LOSS] │
│                │            │          │          │  BREACH] │              │
│  ──────────────┼────────────┼──────────┼──────────┼──────────┼──────────── │
│                │            │          │          │          │              │
│  3 (Media)     │  R20       │  R05     │  R06     │  R04     │  R11        │
│                │ [VENDOR    │ [GPU     │ [AI      │ [K8S     │ [REGULATORY │
│                │  LOCK-IN]  │  SHORTGE]│  ACCURCY]│  MIGRATE]│  CHANGE]    │
│                │            │          │          │          │              │
│  ──────────────┼────────────┼──────────┼──────────┼──────────┼──────────── │
│                │            │          │          │          │              │
│  2 (Baja)      │  R18       │  R12     │  R08     │  R10     │             │
│                │ [CSS       │ [CHURN   │ [KAFKA   │ [WHITE-  │             │
│                │  REACT]    │  HIGH]   │  MIGRATE]│  LABEL]  │             │
│                │            │          │          │          │              │
│  ──────────────┼────────────┼──────────┼──────────┼──────────┼──────────── │
│                │            │          │          │          │              │
│  1 (Muy Baja)  │  R22       │  R19     │  R16     │  R13     │  R14        │
│                │ [DEPRECATE │ [TALENT  │ [CHINA   │ [FUNDING │ [COMPETITOR │
│                │  LIB]      │  SCARCITY│  REGS]   │  DROUGHT]│  MONOPOLY]  │
│                │            │          │          │          │              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Inventario Completo de Riesgos

### 3.1 Riesgos Técnicos

| ID | Riesgo | Prob. | Impacto | Score | Dueño | Status | Mitigación |
|----|--------|-------|---------|-------|-------|--------|------------|
| **R01** | Broker API deprecation o cambio breaking change (MT5/cTrader/Binance) | 5 | 5 | **25** | ENG | Activo | Adapter pattern, tests de contrato, alertas de changelog |
| **R02** | Vulnerabilidad de seguridad: breach de datos de usuarios o trades | 4 | 4 | **16** | SEC | Activo | Zero trust, encryption at rest/transit, pentests trimestrales |
| **R03** | Fallo de base de datos: corrupción, pérdida de datos, deadlock | 4 | 3 | **12** | OPS | Activo | Backups diarios, réplicas, pgBouncer, monitoring |
| **R04** | Migración Kubernetes fallida: downtime, data loss durante transición | 3 | 4 | **12** | OPS | Activo | Blue-green deploy, parallel run, rollback plan |
| **R05** | GPU shortage: no hay disponibilidad de GPUs para AI Core | 3 | 3 | **9** | AI | Activo | Multi-provider (AWS, GCP, Hetzner), CPU fallback |
| **R06** | AI Model degradation: modelos pierden accuracy en producción | 3 | 3 | **9** | AI | Activo | Monitoring de métricas, auto-revert, walk-forward validation |
| **R07** | Overtrading por fallo en detección: pérdidas financieras significativas | 5 | 3 | **15** | AI | Activo | Kill switch manual, limites hard-coded, circuit breakers |
| **R08** | Kafka migration complications: data loss o inconsistencia | 2 | 4 | **8** | OPS | Activo | Dual-write period, shadow mode, 2-week parallel run |
| **R09** | Data loss por falta de backup o corrupción de backups | 4 | 5 | **20** | OPS | Activo | 3-2-1 backup strategy, recovery drills mensuales |
| **R10** | White-label complexity: cada cliente tiene requirements únicos | 2 | 4 | **8** | PM | Activo | Config-driven customization, no code forks |
| **R15** | Performance degradation a escala: latencia crece con usuarios | 4 | 2 | **8** | ENG | Activo | Load testing continuo, performance budgets, CDN |

### 3.2 Riesgos Operativos

| ID | Riesgo | Prob. | Impacto | Score | Dueño | Status | Mitigación |
|----|--------|-------|---------|-------|-------|--------|------------|
| **R12** | User churn alto: usuarios no ven valor suficiente | 2 | 3 | **6** | PM | Activo | User research, onboarding mejorado, success metrics |
| **R16** | Regulatory changes in China: nuevas regulaciones de trading | 3 | 2 | **6** | CEO | Monitoreo | Geo-restricción, compliance adaptable |
| **R18** | Core library deprecation (React, Next.js, Go major version) | 1 | 2 | **2** | ENG | Monitoreo | Version pinning, upgrade sprints, LTS versions |
| **R19** | Talent scarcity: dificultad para contratar devs Go + ML | 2 | 2 | **4** | CEO | Activo | Remote work, competitive comp, training interno |

### 3.3 Riesgos Financieros

| ID | Riesgo | Prob. | Impacto | Score | Dueño | Status | Mitigación |
|----|--------|-------|---------|-------|-------|--------|------------|
| **R11** | Cambio regulatorio que requiera licencia o compliance costoso | 3 | 5 | **15** | CEO | Monitoreo | Legal counsel, compliance-first architecture |
| **R13** | Funding drought: no se consigue inversión para Fase 3+ | 2 | 5 | **10** | CEO | Activo | Revenue-first approach, reduce burn rate option |
| **R14** | Competidor con monopoly: un competidor domina el mercado | 2 | 5 | **10** | CEO | Monitoreo | Diferenciación agresiva, nichos no servidos |

### 3.4 Riesgos de Mercado

| ID | Riesgo | Prob. | Impacto | Score | Dueño | Status | Mitigación |
|----|--------|-------|---------|-------|-------|--------|------------|
| **R17** | Crypto winter: caída extrema del mercado crypto reduce trading | 3 | 2 | **6** | CEO | Monitoreo | Multi-asset (forex, commodities), no depender de crypto |
| **R20** | Vendor lock-in: dependencia excesiva de un proveedor cloud | 1 | 3 | **3** | OPS | Monitoreo | Multi-cloud readiness, abstractions en infra |
| **R21** | Market downturn: bear market reduce volumen de trading | 3 | 3 | **9** | CEO | Monitoreo | Revenue diversificado (subscriptions > commissions) |
| **R22** | Open source library deprecated: librería crítica sin mantenimiento | 1 | 1 | **1** | ENG | Monitoreo | Fork option, alternative libraries identified |

---

## 4. Top 5 Riesgos Críticos — Planes Detallados

### 4.1 R01: Broker API Breaking Changes (Score: 25)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RIESGO R01: BROKER API BREAKING CHANGE                                       │
│  Probabilidad: 5 (Muy Alta)  │  Impacto: 5 (Catastrófico)  │  Score: 25    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DESCRIPCIÓN:                                                                │
│  Los brokers (MT5, cTrader, Binance, Bybit, IBKR) pueden cambiar sus APIs   │
│  en cualquier momento, potencialmente rompiendo integraciones activas.       │
│  Un cambio en el protocolo de conexión, formato de datos, o autenticación   │
│  puede dejar de funcionar inmediatamente, impidiendo ejecutar órdenes.      │
│                                                                              │
│  EJEMPLOS HISTÓRICOS:                                                       │
│  • Binance removió endpoints sin previo aviso (2023)                        │
│  • MT5 actualizó el protocolo de Gateway (2024)                             │
│  • IBKR cambió estructura de respuestas REST (2024)                         │
│                                                                              │
│  PLAN DE MITIGACIÓN:                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PREVENCIÓN:                                                          │  │
│  │ 1. Adapter Pattern: cada broker tiene un adapter que abstrae la API  │  │
│  │    ┌────────────┐    ┌─────────────┐    ┌──────────────┐           │  │
│  │    │ Trading    │───→│ IBrokerAdapter│───→│ MT5 Adapter  │           │  │
│  │    │ Core       │    │ (interface)  │    │ cTrader Adpt │           │  │
│  │    └────────────┘    └─────────────┘    │ Binance Adpt │           │  │
│  │                                          │ IBKR Adapter │           │  │
│  │                                          └──────────────┘           │  │
│  │                                                                      │  │
│  │ 2. Contract Testing: tests automatizados contra API schemas          │  │
│  │ 3. API Version Monitoring: alertas cuando el broker publica cambios  │  │
│  │ 4. Staging Environment: broker sandbox para testing pre-producción   │  │
│  │                                                                      │  │
│  │ RESPUESTA:                                                           │  │
│  │ 1. Detectar: Monitoring detecta error rate spike en broker adapter  │  │
│  │ 2. Contener: Circuit breaker bloquea nuevas órdenes al broker       │  │
│  │ 3. Comunicar: Notificar a usuarios afectados inmediatamente        │  │
│  │ 4. Corregir: hotfix al adapter (target: < 4 horas)                 │  │
│  │ 5. Validar: test suite completa + manual smoke test                 │  │
│  │ 6. Desplegar: blue-green deploy, verificación post-deploy          │  │
│  │                                                                      │  │
│  │ RECOVERY:                                                            │  │
│  │ • Si el cambio es irreconciliable: migrar a broker alternativo     │  │
│  │ • Rollback al adapter anterior si es posible                        │  │
│  │ • Documentar el cambio para prevención futura                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  MONITOREO:                                                                  │
│  • Error rate por broker (alerta si > 1% en 5 min)                         │
│  • Latencia de respuesta del broker (alerta si > 3× baseline)              │
│  • Subscribe a changelogs oficiales de cada broker                         │
│  • Weekly: verificar estado de sandbox environments                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 R09: Data Loss por Backup Failure (Score: 20)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RIESGO R09: DATA LOSS                                                       │
│  Probabilidad: 4 (Alta)  │  Impacto: 5 (Catastrófico)  │  Score: 20        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DESCRIPCIÓN:                                                                │
│  Pérdida de datos de usuarios, trades, configuraciones, o históricos        │
│  debido a fallo de hardware, corrupción de base de datos, o error humano.  │
│  Los datos de trading son irrecuperables si se pierden sin backup.          │
│                                                                              │
│  PLAN DE MITIGACIÓN — 3-2-1 STRATEGY:                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                                                                      │  │
│  │  3 copias de datos:                                                  │  │
│  │  ├── 1: PostgreSQL primary (producción)                            │  │
│  │  ├── 2: PostgreSQL read replica (streaming replication)             │  │
│  │  └── 3: Backup en S3 (offsite)                                     │  │
│  │                                                                      │  │
│  │  2 tipos de almacenamiento:                                          │  │
│  │  ├── NVMe SSD (local, low-latency)                                 │  │
│  │  └── S3 (object storage, durability 99.999999999%)                  │  │
│  │                                                                      │  │
│  │  1 copia offsite:                                                    │  │
│  │  └── S3 en región diferente al primary                              │  │
│  │                                                                      │  │
│  │  FRECUENCIA:                                                         │  │
│  │  • Continuous: WAL archiving (PostgreSQL)                           │  │
│  │  • Hourly: pg_basebackup incremental                                │  │
│  │  • Daily: Full backup → S3 (retención 30 días)                     │  │
│  │  • Weekly: Full backup → S3 Glacier (retención 1 año)              │  │
│  │  • Monthly: Full backup → S3 Glacier Deep Archive (retención 7 años)│  │
│  │                                                                      │  │
│  │  RECOVERY:                                                           │  │
│  │  • RPO (Recovery Point Objective): < 5 minutos (WAL replay)        │  │
│  │  • RTO (Recovery Time Objective): < 30 minutos                     │  │
│  │                                                                      │  │
│  │  RECOVERY DRILL:                                                    │  │
│  │  • Mensual: restaurar backup a staging y verificar integridad       │  │
│  │  • Trimestral: full DR drill (restore + app restart + smoke test)   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  INTEGRIDAD DE DATOS:                                                       │
│  • Event Sourcing: todos los cambios son eventos inmutables                │
│  • Checksums: verificación de integridad en cada backup                    │
│  • CRC32 en WAL: detección de corrupción temprana                         │
│  • Test de restores mensuales                                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 R02: Security Breach (Score: 16)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RIESGO R02: SECURITY BREACH                                                  │
│  Probabilidad: 4 (Alta)  │  Impacto: 4 (Mayor)  │  Score: 16                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DESCRIPCIÓN:                                                                │
│  Acceso no autorizado a datos de usuarios, credenciales de broker,         │
│  o manipulación de órdenes de trading. Un breach puede causar pérdida       │
│  financiera directa a usuarios y destruir la reputación del producto.      │
│                                                                              │
│  VECTORES DE ATAQUE IDENTIFICADOS:                                          │
│  1. SQL injection en API endpoints                                          │
│  2. Compromiso de tokens JWT                                                │
│  3. Man-in-the-middle en conexiones WebSocket                               │
│  4. Compromiso de credenciales de broker almacenadas                       │
│  5. Supply chain attack (dependencias npm/pip)                             │
│  6. Insider threat (empleado malicioso)                                     │
│  7. Zero-day vulnerability en dependencias                                  │
│                                                                              │
│  PLAN DE MITIGACIÓN:                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                                                                      │  │
│  │  PREVENCIÓN (Defense in Depth):                                      │  │
│  │  ┌──────────────────────────────────────────────────────────────┐   │  │
│  │  │ Layer 1: Network                                              │   │  │
│  │  │ • TLS 1.3 everywhere (no exceptions)                         │   │  │
│  │  │ • Cloudflare WAF + DDoS protection                           │   │  │
│  │  │ • VPN para acceso administrativo                             │   │  │
│  │  │                                                               │   │  │
│  │  │ Layer 2: Application                                          │   │  │
│  │  │ • Input validation (Zod schemas on every endpoint)           │   │  │
│  │  │ • Parameterized queries (no raw SQL)                         │   │  │
│  │  │ • Rate limiting per IP and per user                           │   │  │
│  │  │ • CORS strict policy                                         │   │  │
│  │  │ • CSP headers                                                │   │  │
│  │  │                                                               │   │  │
│  │  │ Layer 3: Authentication                                       │   │  │
│  │  │ • JWT + Refresh tokens (short-lived: 15min)                  │   │  │
│  │  │ • MFA for admin and trading operations                       │   │  │
│  │  │ • OAuth2 for SSO (Enterprise)                                │   │  │
│  │  │ • API key rotation every 90 days                              │   │  │
│  │  │                                                               │   │  │
│  │  │ Layer 4: Data                                                 │   │  │
│  │  │ • AES-256 encryption at rest (broker credentials)            │   │  │
│  │  │ • Column-level encryption for sensitive data                  │   │  │
│  │  │ • Secrets in Vault (not env vars or config files)            │   │  │
│  │  │ • No secrets in code or git history                          │   │  │
│  │  │                                                               │   │  │
│  │  │ Layer 5: Monitoring                                           │   │  │
│  │  │ • Audit log inmutable (Event Sourcing)                       │   │  │
│  │  │ • Anomaly detection on API access patterns                   │   │  │
│  │  │ • Failed login alerting (> 5 intentos en 10 min)            │   │  │
│  │  │ • Real-time alerting on suspicious activity                  │   │  │
│  │  └──────────────────────────────────────────────────────────────┘   │  │
│  │                                                                      │  │
│  │  RESPUESTA A INCIDENTES:                                             │  │
│  │  ┌──────────────────────────────────────────────────────────────┐   │  │
│  │  │ 1. DETECT: Automated alerts via monitoring                  │   │  │
│  │  │ 2. CONTAIN: Isolate affected systems (< 5 min)              │   │  │
│  │  │    • Block compromised accounts                             │   │  │
│  │  │    • Rotate all active sessions                             │   │  │
│  │  │    • Enable enhanced logging                                │   │  │
│  │  │ 3. NOTIFY: Inform affected users (< 1 hora)                │   │  │
│  │  │ 4. ERADICATE: Remove threat vector                          │   │  │
│  │  │ 5. RECOVER: Restore from clean backup if needed             │   │  │
│  │  │ 6. LEARN: Post-incident review within 48 horas              │   │  │
│  │  └──────────────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  TESTING:                                                                    │
│  • Pentest semestral (externo)                                              │
│  • Bug bounty program (HackerOne)                                          │
│  • Dependency scanning (Snyk, dependabot) semanal                          │
│  • SAST en CI/CD (Semgrep)                                                 │
│  • DAST trimestral (OWASP ZAP)                                            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 R11: Regulatory Change (Score: 15)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RIESGO R11: REGULATORY CHANGE                                               │
│  Probabilidad: 3 (Media)  │  Impacto: 5 (Catastrófico)  │  Score: 15       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DESCRIPCIÓN:                                                                │
│  Cambios en regulaciones financieras (MiFID II, SEC, CFTC, ESMA)           │
│  que requieran licencias costosas, restricciones de operación, o           │
│  cambios arquitectónicos significativos.                                    │
│                                                                              │
│  REGULACIONES RELEVANTES:                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Regulación      │ Jurisdicción │ Requisito Principal                │  │
│  │ ─────────────────────────────────────────────────────────────────── │  │
│  │ MiFID II         │ EU/UK        │ Licencia de inversión, KYC/AML    │  │
│  │ SEC Regulation   │ US           │ Broker-dealer registration        │  │
│  │ CFTC             │ US           │ FCM registration para futures     │  │
│  │ ESMA             │ EU           │ Limits en CFDs para retail        │  │
│  │ MAS              │ Singapore    │ Capital markets services license  │  │
│  │ JFSA             │ Japan        │ Specified financial instruments   │  │
│  │ Crypto-specific  │ Varios       │ VASP/MiCA compliance              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  PLAN DE MITIGACIÓN:                                                        │
│  1. Legal counsel: asesor legal especializado en fintech (retainer)        │
│  2. Compliance-first architecture: KYC/AML desde el diseño                 │
│  3. Geo-restriction capability: habilitar/deshabilitar regiones           │
│  4. Audit trail completo: Event Sourcing facilita compliance               │
│  5. Modular compliance: cada módulo de compliance es un plugin             │
│  6. Industry association: membresía en asociaciones fintech               │
│  7. Regulatory monitoring: servicio de alertas de cambios regulatorios    │
│                                                                              │
│  CONTINGENCIA:                                                               │
│  • Si se requiere licencia costosa: pivotar a B2B (white-label)           │
│  • Si se prohíbe una región: geo-block + notificar usuarios               │
│  • Si cambian límites: ajustar parámetros sin code change                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.5 R07: Overtrading por Fallo de Detección (Score: 15)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RIESGO R07: OVERTRADING POR FALLO EN DETECCIÓN                              │
│  Probabilidad: 5 (Muy Alta)  │  Impacto: 3 (Moderado)  │  Score: 15        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DESCRIPCIÓN:                                                                │
│  El sistema de AI Core permite overtrading debido a fallos en la           │
│  detección, causando pérdidas financieras innecesarias a usuarios.         │
│  Probabilidad alta porque los mercados son inherentemente impredecibles.   │
│                                                                              │
│  CENARIOS:                                                                   │
│  • Market regime cambia rapidamente y el detector no se adapta            │
│  • Señales AI generan trades frecuentes en mercados volátiles             │
│  • Correlation detector falla: múltiples posiciones correlacionadas        │
│  • Overtrading detector tiene false negatives                              │
│                                                                              │
│  PLAN DE MITIGACIÓN:                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                                                                      │  │
│  │  CAPA 1: AI Core — Detección Primaria                               │  │
│  │  • Regime detector con actualización cada 60s                       │  │
│  │  • Signal scorer con threshold configurable por tenant              │  │
│  │  • Overtrading detector con múltiples métricas                      │  │
│  │                                                                      │  │
│  │  CAPA 2: Trading Core — Hard Limits (inmutables)                    │  │
│  │  • Max trades per hour: 50 (hard-coded, no configurable)           │  │
│  │  • Max daily drawdown: 15% (hard-coded)                            │  │
│  │  • Max consecutive losses: 10 (hard-coded)                         │  │
│  │  • Max correlated positions: 3 (hard-coded)                        │  │
│  │                                                                      │  │
│  │  CAPA 3: Kill Switch — Emergencia                                   │  │
│  │  • Manual kill switch para cada usuario                             │  │
│  │  • Automatic kill switch si drawdown > 20%                          │  │
│  │  • Admin kill switch global                                         │  │
│  │                                                                      │  │
│  │  CAPA 4: Insurance Layer                                             │  │
│  │  • Max loss per trade: configurable por tenant                      │  │
│  │  • Portfolio insurance: closing all if extreme conditions           │  │
│  │  • Correlation breaker: auto-reduce if portfolio correlation > 0.9 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  MONITOREO:                                                                  │
│  • Real-time P&L monitoring por cuenta                                     │
│  • Alert inmediata si drawdown > 5%                                        │
│  • Dashboard de health de overtrading metrics                              │
│  • Daily report de todas las intervenciones del sistema                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Matriz de Probabilidad vs Impacto

### 5.1 Visualización Completa

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         RISK MATRIX — COMPLETE VIEW                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  IMPACTO →     │ 1              2               3              4               5│
│  PROB ↓        │ Insignificante Menor           Moderado        Mayor           Catastrófico│
│  ──────────────┼────────────────────────────────────────────────────────────────│
│                │                                                                │
│  5             │                 │               │ R07 [15]     │               │ R01 [25]     │
│  (80-100%)     │                 │               │ Overtrading  │               │ Broker API   │
│                │                 │               │              │               │              │
│  ──────────────┼─────────────────┼───────────────┼──────────────┼───────────────┼──────────────│
│                │                 │               │              │               │              │
│  4             │                 │ R15 [8]       │ R03 [12]     │ R02 [16]      │ R09 [20]     │
│  (60-80%)      │                 │ Performance   │ DB Failure   │ Security      │ Data Loss    │
│                │                 │               │              │ Breach        │              │
│  ──────────────┼─────────────────┼───────────────┼──────────────┼───────────────┼──────────────│
│                │                 │               │              │               │              │
│  3             │ R20 [3]         │ R05 [9]       │ R06 [9]      │ R04 [12]      │ R11 [15]     │
│  (30-60%)      │ Vendor Lock-in  │ GPU Shortage  │ AI Accuracy  │ K8s Migrate   │ Regulatory   │
│                │                 │ R21 [9]       │              │               │ Change       │
│                │                 │ Market Downtn │              │               │              │
│  ──────────────┼─────────────────┼───────────────┼──────────────┼───────────────┼──────────────│
│                │                 │               │              │               │              │
│  2             │ R18 [2]         │ R12 [6]       │ R08 [8]      │ R10 [8]       │              │
│  (10-30%)      │ Deprec. Lib     │ Churn         │ Kafka Mig.   │ White-Label   │              │
│                │ R22 [1]         │ R19 [4]       │              │ Complexity    │              │
│                │ OSS Deprec.     │ Talent Scrc.  │              │               │              │
│                │                 │ R16 [6]       │              │               │              │
│                │                 │ China Regs    │              │               │              │
│  ──────────────┼─────────────────┼───────────────┼──────────────┼───────────────┼──────────────│
│                │                 │               │              │               │              │
│  1             │ R22 [1]         │               │              │ R13 [10]      │ R14 [10]     │
│  (<10%)        │ CSS React       │               │              │ Funding       │ Competitor   │
│                │                 │               │              │ Drought       │ Monopoly     │
│                │                 │               │              │               │              │
│  ──────────────┼─────────────────┼───────────────┼──────────────┼───────────────┼──────────────│
│                                                                                 │
│  LEGENDA:                                                                      │
│  🟢 Bajo (1-4):    Monitoreo rutinario                                        │
│  🟡 Moderado (5-9): Plan de mitigación documentado                            │
│  🟠 Alto (10-15):  Mitigación activa, revisión quincenal                      │
│  🔴 Crítico (16-25): Mitigación urgente, revisión semanal                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Resumen por Nivel de Riesgo

| Nivel | Cantidad | IDs | Acción |
|-------|----------|-----|--------|
| 🔴 **Crítico** | 3 | R01, R09, R02 | Mitigación inmediata, ownership claro, revisión semanal |
| 🟠 **Alto** | 4 | R03, R04, R11, R07 | Mitigación activa, revisión quincenal |
| 🟡 **Moderado** | 7 | R05, R06, R08, R10, R12, R15, R21 | Plan documentado, revisión mensual |
| 🟢 **Bajo** | 8 | R13-R20, R22 | Monitoreo rutinario, revisión trimestral |

---

## 6. Procedimientos de Monitoreo

### 6.1 Frecuencia de Revisión

| Actividad | Frecuencia | Participantes | Output |
|-----------|------------|---------------|--------|
| Risk dashboard review | Diaria | Engineering Lead | Actualización de status |
| Risk register update | Semanal | Engineering + PM | Risk register actualizado |
| Risk assessment meeting | Quincenal | Todo el equipo | Decisiones de mitigación |
| Pentest / Security audit | Trimestral | Externo + Security | Informe de vulnerabilidades |
| Disaster recovery drill | Trimestral | Ops + Engineering | Reporte de RTO/RPO |
| Business risk review | Mensual | CEO + PM + Eng Lead | Actualización estratégica |
| Full risk audit | Semianual | Todo el equipo + externo | Auditoría completa |

### 6.2 Herramientas de Monitoreo

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    RISK MONITORING STACK                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │ Prometheus    │  │ Grafana      │  │ PagerDuty    │                      │
│  │ (Métricas)    │→ │ (Dashboard)  │→ │ (Alerting)   │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
│                                                                              │
│  Métricas de Riesgo Monitoreadas:                                           │
│                                                                              │
│  TÉCNICAS:                                                                   │
│  • Error rate por servicio (target: < 0.1%)                                │
│  • API latency p99 (target: < 100ms)                                       │
│  • Database connection pool usage (target: < 80%)                          │
│  • Disk usage (alert: > 80%)                                               │
│  • Memory usage (alert: > 85%)                                             │
│  • CPU usage (alert: > 90% sustained)                                      │
│  • GPU utilization (alert: > 95%)                                          │
│  • Backup success rate (target: 100%)                                      │
│  • SSL certificate expiry (alert: < 30 days)                               │
│                                                                              │
│  OPERATIVAS:                                                                 │
│  • Uptime (target: ≥ 99.9%)                                                │
│  • Deployment frequency                                                    │
│  • Mean time to recovery (MTTR) (target: < 30 min)                        │
│  • Change failure rate (target: < 5%)                                      │
│  • Incident count per week                                                 │
│                                                                              │
│  DE SEGURIDAD:                                                               │
│  • Failed login attempts (alert: > 5 en 10 min)                           │
│  • Unusual API access patterns                                             │
│  • Dependency vulnerabilities (alert: new critical)                        │
│  • SSL/TLS configuration grade (target: A+)                               │
│                                                                              │
│  DE NEGOCIO:                                                                 │
│  • Active users (daily, weekly, monthly)                                   │
│  • Churn rate (target: < 10% monthly)                                      │
│  • MRR growth rate                                                         │
│  • Support ticket volume                                                   │
│  • NPS score                                                               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Alertas Configuradas

| Alerta | Condición | Severidad | Canal | Acción Automática |
|--------|-----------|-----------|-------|-------------------|
| Service Down | Health check falla > 1 min | CRITICAL | PagerDuty + Slack | Restart container |
| Error Rate Spike | > 1% en 5 min | HIGH | PagerDuty | Investigar, possible rollback |
| Backup Failed | Backup job falla | HIGH | Email + Slack | Reintentar, alertar OPS |
| SSL Expiring | < 30 días | MEDIUM | Email | Renovación automática (Let's Encrypt) |
| Disk > 80% | Disk usage | HIGH | Slack | Cleanup scripts |
| DB Connections > 80% | Pool exhaustion | HIGH | PagerDuty | Scale connection pool |
| Latency > 2× baseline | Performance degradation | MEDIUM | Slack | Investigar causa raíz |
| New Critical CVE | Dependency vulnerability | HIGH | Email + Slack | Patch within 24h |
| Trading Loss > 5% | Drawdown alert | CRITICAL | PagerDuty + Telegram | Pause affected strategy |

---

## 7. Planes de Contingencia

### 7.1 Plan de Contingencia: Caída Total del Sistema

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CONTINGENCIA: CAÍDA TOTAL DEL SISTEMA                                       │
│  Trigger: Todos los servicios inoperables > 5 minutos                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FASE 1: DETECCIÓN (0-5 min)                                                │
│  ├─ Health checks fallan en Prometheus                                      │
│  ├─ PagerDuty alerta al on-call engineer                                   │
│  └─ On-call confirma que no es falso positivo                              │
│                                                                              │
│  FASE 2: CONTENCIÓN (5-15 min)                                              │
│  ├─ Activar status page: "Investigando incidente"                          │
│  ├─ Notificar a team via Slack war-room                                    │
│  ├─ Determinar si es infraestructura o código                              │
│  └─ Si infra: verificar VPS/cloud provider status                          │
│                                                                              │
│  FASE 3: RESOLUCIÓN (15-60 min)                                             │
│  ├─ Infra issue → contactar soporte del proveedor                          │
│  ├─ Code issue → revert al último commit funcional                         │
│  ├─ DB issue → failover a replica                                          │
│  ├─ Network issue → verificar DNS, firewall, CDN                          │
│  └─ Si no se resuelve en 30 min: activar DR plan                          │
│                                                                              │
│  FASE 4: COMUNICACIÓN (durante todo el proceso)                             │
│  ├─ Status page: updates cada 15 min                                       │
│  ├─ Email a usuarios afectados                                             │
│  ├─ Telegram broadcast si es prolongado                                    │
│  └─ Post-mortem: dentro de 48 horas                                       │
│                                                                              │
│  FASE 5: RECUPERACIÓN (post-resolución)                                     │
│  ├─ Verificar integridad de datos                                          │
│  ├─ Verificar que trades no se perdieron                                   │
│  ├─ Notificar resolución a usuarios                                        │
│  ├─ Compensación si aplica (créditos, extensión de plan)                  │
│  └─ Post-mortem con action items                                           │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Plan de Contingencia: Data Breach

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CONTINGENCIA: DATA BREACH                                                   │
│  Trigger: Evidence de acceso no autorizado a datos                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FASE 1: CONTENCIÓN INMEDIATA (0-30 min)                                    │
│  ├─ Aislar sistemas afectados                                              │
│  ├─ Revocar todas las sesiones activas                                     │
│  ├─ Rotar todas las credenciales                                            │
│  ├─ Activar enhanced logging                                               │
│  └─ No destruir evidencia (preservar logs)                                 │
│                                                                              │
│  FASE 2: ASSESSMENT (30 min - 4 horas)                                      │
│  ├─ Determinar alcance: qué datos fueron comprometidos                     │
│  ├─ Determinar vector: cómo entró el atacante                              │
│  ├─ Determinar timeline: cuándo empezó el breach                           │
│  ├─ Evaluar impacto: usuarios afectados, tipo de datos                    │
│  └─ Consultar asesor legal                                                 │
│                                                                              │
│  FASE 3: NOTIFICACIÓN (según jurisdicción)                                  │
│  ├─ EU (GDPR): autoridad de protección de datos en 72h                    │
│  ├─ US: notificación a usuarios según state laws                           │
│  ├─ Affected users: notificación personalizada                             │
│  ├─ Si datos de broker comprometidos: notificar al broker                  │
│  └─ Si es material: prensa/reguladores proactivamente                      │
│                                                                              │
│  FASE 4: ERADICACIÓN (1-7 días)                                             │
│  ├─ Eliminar acceso del atacante                                           │
│  ├─ Patch de la vulnerabilidad                                              │
│  ├─ Restore from clean backup si necesario                                 │
│  ├─ Security audit completo                                                │
│  └─ Implementar controles adicionales                                      │
│                                                                              │
│  FASE 5: POST-INCIDENT (1-4 semanas)                                        │
│  ├─ Post-mortem detallado                                                  │
│  ├─ Actualizar incident response plan                                      │
│  ├─ Implementar nuevas medidas de seguridad                                │
│  ├─ Seguimiento a usuarios afectados                                       │
│  └─ Revisión de compliance (GDPR, PCI si aplica)                          │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Plan de Contingencia: Financial Loss por AI Failure

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CONTINGENCIA: AI CORE FAILURE CAUSING FINANCIAL LOSS                        │
│  Trigger: Pérdida financiera > 10% del balance de un usuario por fallo AI  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FASE 1: CIRCUIT BREAKER (instantáneo)                                      │
│  ├─ Auto-kill switch: pausa todas las estrategias AI                       │
│  ├─ Notificación inmediata al usuario                                      │
│  ├─ Log completo de todas las órdenes ejecutadas                           │
│  └─ Snapshot del estado del portfolio                                      │
│                                                                              │
│  FASE 2: ANÁLISIS (1-4 horas)                                               │
│  ├─ Determinar causa raíz del fallo AI                                     │
│  ├─ Cuantificar pérdidas exactas                                           │
│  ├─ Verificar si es isolated o systemic                                    │
│  ├─ Revisar otros usuarios afectados                                       │
│  └─ Desactivar AI Core si es systemic                                      │
│                                                                              │
│  FASE 3: MITIGACIÓN (inmediata)                                             │
│  ├─ Trading Core sigue operando manualmente                                │
│  ├─ Users pueden operar sin AICore (fallback mode)                        │
│  ├─ Rollback AI model a versión anterior si aplica                         │
│  └─ Revisar y ajustar parámetros de overtrading                           │
│                                                                              │
│  FASE 4: COMPENSACIÓN (1-7 días)                                            │
│  ├─ Evaluar si aplica compensación financiera                              │
│  ├─ Créditos en cuenta para usuarios afectados                             │
│  ├─ Extensión de suscripción gratuita                                      │
│  └─ Comunicación transparente sobre lo ocurrido                            │
│                                                                              │
│  FASE 5: PREVENCIÓN (1-4 semanas)                                           │
│  ├─ Mejorar overtrading detection                                           │
│  ├─ Añadir más hard limits en Trading Core                                │
│  ├─ Implementar insurance layer adicional                                  │
│  ├─ Testing con escenarios extremos                                         │
│  └─ Actualizar documentación de riesgos                                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Plan de Contingencia: Key Person Dependency

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CONTINGENCIA: KEY PERSON DEPARTURE                                          │
│  Trigger: Un miembro clave del equipo se va inesperadamente                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PREVENCIÓN (siempre activa):                                               │
│  ├─ Documentation: ADRs, runbooks, decisiones documentadas                 │
│  ├─ Code review: mínimo 2 personas aprueban cada PR                        │
│  ├─ Pair programming: knowledge sharing continuo                           │
│  ├─ Bus factor: ≥ 2 personas conocen cada componente crítico              │
│  ├─ Knowledge base: documentación de arquitectura actualizada             │
│  └─ Repository: todo el código en Git, no en laptops individuales         │
│                                                                              │
│  RESPUESTA:                                                                  │
│  ├─ Day 1: Identificar knowledge gaps críticos                            │
│  ├─ Day 1-3: Knowledge transfer sessions                                   │
│  ├─ Day 1-7: Redistribuir responsabilidades                               │
│  ├─ Week 2-4: Hiring para reemplazo                                        │
│  ├─ Week 4-8: Onboarding del nuevo miembro                                │
│  └─ Ongoing: Verificar bus factor ≥ 2 por componente                     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Registro de Riesgos Activos

### 8.1 Status Actual (Julio 2026)

| ID | Riesgo | Status | Última Revisión | Próxima Revisión | Notas |
|----|--------|--------|-----------------|------------------|-------|
| R01 | Broker API Breaking Change | 🔴 Activo | 2026-07-14 | 2026-07-28 | Adapter pattern implementado en diseño |
| R02 | Security Breach | 🔴 Activo | 2026-07-14 | 2026-07-28 | Pentest pendiente (Fase 1) |
| R03 | Database Failure | 🟠 Activo | 2026-07-14 | 2026-07-28 | Backup strategy definida |
| R04 | K8s Migration Failure | 🟡 Monitoreo | 2026-07-14 | 2026-08-14 | No aplica hasta Fase 3 |
| R05 | GPU Shortage | 🟡 Monitoreo | 2026-07-14 | 2026-08-14 | CPU fallback planeado |
| R06 | AI Model Degradation | 🟡 Monitoreo | 2026-07-14 | 2026-08-14 | Walk-forward validation |
| R07 | Overtrading by Detection Failure | 🔴 Activo | 2026-07-14 | 2026-07-28 | Kill switch implementado en diseño |
| R08 | Kafka Migration Complications | 🟡 Monitoreo | 2026-07-14 | 2026-08-14 | No aplica hasta Fase 3 |
| R09 | Data Loss | 🔴 Activo | 2026-07-14 | 2026-07-28 | 3-2-1 strategy definida |
| R10 | White-Label Complexity | 🟡 Monitoreo | 2026-07-14 | 2026-08-14 | No aplica hasta Fase 4 |
| R11 | Regulatory Change | 🟠 Monitoreo | 2026-07-14 | 2026-08-14 | Legal counsel pendiente |
| R12 | User Churn | 🟡 Monitoreo | 2026-07-14 | 2026-08-14 | Post-MVP |
| R13 | Funding Drought | 🟡 Monitoreo | 2026-07-14 | 2026-10-14 | Revenue-first approach |
| R14 | Competitor Monopoly | 🟡 Monitoreo | 2026-07-14 | 2026-10-14 | Diferenciación strategy |
| R15 | Performance Degradation | 🟠 Activo | 2026-07-14 | 2026-07-28 | Load testing en roadmap |
| R16 | China Regulatory Changes | 🟢 Bajo | 2026-07-14 | 2026-10-14 | Geo-restriction capability |
| R17 | Crypto Winter | 🟡 Monitoreo | 2026-07-14 | 2026-10-14 | Multi-asset strategy |
| R18 | Library Deprecation | 🟢 Bajo | 2026-07-14 | 2026-12-14 | Version pinning |
| R19 | Talent Scarcity | 🟡 Monitoreo | 2026-07-14 | 2026-08-14 | Remote work + competitive comp |
| R20 | Vendor Lock-in | 🟢 Bajo | 2026-07-14 | 2026-12-14 | Abstractions en infra |
| R21 | Market Downturn | 🟡 Monitoreo | 2026-07-14 | 2026-10-14 | Subscription model |
| R22 | OSS Deprecation | 🟢 Bajo | 2026-07-14 | 2026-12-14 | Alternatives identified |

### 8.2 Historial de Cambios

| Fecha | ID | Cambio | Responsable |
|-------|-----|--------|-------------|
| 2026-07-14 | ALL | Registro inicial de 22 riesgos | Architect |
| — | — | Próxima revisión: 2026-07-28 | — |

---

## Documentos Relacionados

| Documento | Relación |
|-----------|----------|
| [ROADMAP.md](./ROADMAP.md) | Riesgos por fase del roadmap |
| [SCALE-100K.md](./SCALE-100K.md) | Riesgos de escalamiento |
| [AI-CORE.md](./AI-CORE.md) | Riesgos específicos del AI Core |
| [INFRASTRUCTURE.md](./INFRASTRUCTURE.md) | Riesgos de infraestructura |
| [SECURITY.md](./SECURITY.md) | Detalles de seguridad |

---

*Documento generado como parte de la arquitectura de TNSVT V2.*  
*Última revisión: 2026-07-14*
