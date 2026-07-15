# DOCUMENT 07: INFRAESTRUCTURA

## Plataforma de Trading TNSVT V2 — Infraestructura y Despliegue

**Version:** 2.0.0  
**Fecha:** 2026-07-14  
**Estado:** Produccion  
**Autor:** Equipo de Arquitectura TNSVT V2

---

## Tabla de Contenidos

1. [Vision General de Fases](#1-vision-general-de-fases)
2. [Fase 1: Docker Compose](#2-fase-1-docker-compose)
3. [Fase 3: Kubernetes](#3-fase-3-kubernetes)
4. [Traefik Configuration](#4-traefik-configuration)
5. [CI/CD Pipeline](#5-cicd-pipeline)
6. [Blue-Green Deployment](#6-blue-green-deployment)
7. [Entornos](#7-entornos)
8. [Estrategia de Contenedores](#8-estrategia-de-contenedores)
9. [Recursos y Volumenes](#9-recursos-y-volumenes)
10. [Network Policies](#10-network-policies)
11. [Secrets en Kubernetes](#11-secrets-en-kubernetes)

---

## 1. Vision General de Fases

```
+-----------------------------------------------------------------------+
|                 ROADMAP DE INFRAESTRUCTURA TNSVT V2                    |
+-----------------------------------------------------------------------+
|                                                                       |
|  FASE 1                    FASE 2                    FASE 3           |
|  Docker Compose            Semi-automatizado         Kubernetes       |
|  (MVP -> 10K users)        (10K -> 50K users)        (50K -> 100K+)  |
|                                                                       |
|  +-----------------+      +-----------------+      +---------------+ |
|  | 25+ services    |      | Managed DB      |      | K8s cluster   | |
|  | SQLite -> PG    |      | Redis Cloud     |      | Auto-scaling  | |
|  | Monolito ->     |      | Managed NATS    |      | Helm charts   | |
|  | Microservicios  |      | Basic CI/CD     |      | Full CI/CD    | |
|  | Desarrollo      |      | Staging env     |      | Multi-region  | |
|  | local           |      |                 |      | Observability | |
|  +-----------------+      +-----------------+      +---------------+ |
|                                                                       |
|  Duracion: 3 meses        Duracion: 3 meses     Duracion: 4 meses   |
|  Costo: $500/mes          Costo: $3,000/mes     Costo: $12,000/mes  |
+-----------------------------------------------------------------------+
```

### Servicios del Sistema (25+)

| #  | Servicio             | Tipo       | Puerto | Dependencias                  |
|----|----------------------|------------|--------|-------------------------------|
| 1  | traefik              | Gateway    | 80/443 | Ninguna                       |
| 2  | auth-service         | Go         | 8080   | PostgreSQL, Redis, Vault      |
| 3  | platform-api         | Go         | 8081   | PostgreSQL, Redis, NATS       |
| 4  | trading-engine       | Go         | 8082   | PostgreSQL, NATS, Redis       |
| 5  | risk-engine          | Go         | 8083   | PostgreSQL, Redis, NATS       |
| 6  | broker-gateway       | Go         | 8084   | NATS, Redis, Vault           |
| 7  | ai-engine            | Python     | 8085   | PostgreSQL, NATS, Redis       |
| 8  | ollama-server        | AI/ML      | 11434  | GPU resources                 |
| 9  | copy-trading         | Go         | 8086   | PostgreSQL, NATS, Redis       |
| 10 | notification-service | Go         | 8087   | PostgreSQL, Redis, NATS       |
| 11 | audit-service        | Go         | 8088   | PostgreSQL, NATS              |
| 12 | websocket-gateway    | Go         | 8090   | Redis, NATS                   |
| 13 | postgresql           | Database   | 5432   | Ninguna                       |
| 14 | timescaledb          | Timeseries | 5433   | Ninguna                       |
| 15 | redis                | Cache      | 6379   | Ninguna                       |
| 16 | nats-1 (cluster)     | Messaging  | 4222   | nats-2, nats-3               |
| 17 | nats-2 (cluster)     | Messaging  | 4222   | nats-1, nats-3               |
| 18 | nats-3 (cluster)     | Messaging  | 4222   | nats-1, nats-2               |
| 19 | vault                | Secrets    | 8200   | Ninguna                       |
| 20 | loki                 | Logs       | 3100   | Ninguna                       |
| 21 | prometheus           | Metrics    | 9090   | Ninguna                       |
| 22 | grafana              | Dashboards | 3000   | Prometheus, Loki, Tempo       |
| 23 | tempo                | Traces     | 3200   | Ninguna                       |
| 24 | minio                | Object Sto | 9000   | Ninguna                       |
| 25 | mailhog              | Dev Mail   | 1025   | Ninguna                       |
| 26 | streamlit-app        | Python     | 8501   | PostgreSQL, Redis             |

---

## 2. Fase 1: Docker Compose

### docker-compose.yml (Resumen de servicios)

```yaml
version: "3.9"

x-common-env: &common-env
  TZ: "UTC"
  LOG_LEVEL: "info"
  NATS_URL: "nats://nats-1:4222,nats://nats-2:4222,nats://nats-3:4222"
  POSTGRES_HOST: "postgresql"
  POSTGRES_PORT: "5432"
  POSTGRES_DB: "tnsvt"
  POSTGRES_USER: "${POSTGRES_USER}"
  POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
  REDIS_URL: "redis://redis:6379/0"
  VAULT_ADDR: "http://vault:8200"

x-go-build: &go-build
  context: .
  dockerfile: build/Dockerfile.go
  target: production

x-python-build: &python-build
  context: .
  dockerfile: build/Dockerfile.python
  target: production

services:
  traefik:
    image: traefik:v3.1
    ports: ["80:80", "443:443", "8080:8080"]
    volumes:
      - ./traefik:/etc/traefik
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks: [frontend, backend]
    restart: unless-stopped

  auth-service:
    build: { <<: *go-build, args: { SERVICE: auth-service } }
    environment: { <<: *common-env, SERVICE_NAME: "auth-service" }
    networks: [backend]
    depends_on:
      postgresql: { condition: service_healthy }
      redis: { condition: service_healthy }
      nats-1: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 1G }
        reservations: { cpus: "0.5", memory: 256M }
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.auth.rule=PathPrefix(`/auth`)"
      - "traefik.http.services.auth.loadbalancer.server.port=8080"

  trading-engine:
    build: { <<: *go-build, args: { SERVICE: trading-engine } }
    environment: { <<: *common-env, SERVICE_NAME: "trading-engine" }
    networks: [backend]
    depends_on:
      postgresql: { condition: service_healthy }
      redis: { condition: service_healthy }
      nats-1: { condition: service_healthy }
      risk-engine: { condition: service_started }
      broker-gateway: { condition: service_started }
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:8082/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:   { cpus: "4.0", memory: 2G }
        reservations: { cpus: "1.0", memory: 512M }

  risk-engine:
    build: { <<: *go-build, args: { SERVICE: risk-engine } }
    environment: { <<: *common-env, SERVICE_NAME: "risk-engine" }
    networks: [backend]
    depends_on:
      postgresql: { condition: service_healthy }
      redis: { condition: service_healthy }
      nats-1: { condition: service_healthy }
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 1G }
        reservations: { cpus: "0.5", memory: 256M }

  broker-gateway:
    build: { <<: *go-build, args: { SERVICE: broker-gateway } }
    environment: { <<: *common-env, SERVICE_NAME: "broker-gateway" }
    networks: [backend]
    depends_on:
      redis: { condition: service_healthy }
      nats-1: { condition: service_healthy }
    deploy:
      resources:
        limits:   { cpus: "4.0", memory: 2G }
        reservations: { cpus: "1.0", memory: 512M }

  ai-engine:
    build: { <<: *python-build, args: { SERVICE: ai-engine } }
    environment: { <<: *common-env, SERVICE_NAME: "ai-engine" }
    volumes: [ai-model-cache:/app/models/cache]
    networks: [backend]
    depends_on:
      postgresql: { condition: service_healthy }
      redis: { condition: service_healthy }
      nats-1: { condition: service_healthy }
      ollama-server: { condition: service_started }
    deploy:
      resources:
        limits:   { cpus: "4.0", memory: 4G }
        reservations: { cpus: "2.0", memory: 2G }

  ollama-server:
    image: ollama/ollama:latest
    environment:
      OLLAMA_HOST: "0.0.0.0:11434"
      OLLAMA_NUM_PARALLEL: "4"
    volumes: [ollama-models:/root/.ollama]
    networks: [backend]
    deploy:
      resources:
        limits:   { cpus: "8.0", memory: 16G }
        reservations: { cpus: "4.0", memory: 8G }

  copy-trading:
    build: { <<: *go-build, args: { SERVICE: copy-trading } }
    environment: { <<: *common-env, SERVICE_NAME: "copy-trading" }
    networks: [backend]
    depends_on:
      postgresql: { condition: service_healthy }
      redis: { condition: service_healthy }
      nats-1: { condition: service_healthy }
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 1G }
        reservations: { cpus: "0.5", memory: 256M }

  notification-service:
    build: { <<: *go-build, args: { SERVICE: notification-service } }
    environment: { <<: *common-env, SERVICE_NAME: "notification-service" }
    networks: [backend]
    deploy:
      resources:
        limits:   { cpus: "1.0", memory: 512M }
        reservations: { cpus: "0.25", memory: 128M }

  audit-service:
    build: { <<: *go-build, args: { SERVICE: audit-service } }
    environment: { <<: *common-env, SERVICE_NAME: "audit-service" }
    networks: [backend]
    deploy:
      resources:
        limits:   { cpus: "1.0", memory: 512M }
        reservations: { cpus: "0.25", memory: 128M }

  websocket-gateway:
    build: { <<: *go-build, args: { SERVICE: websocket-gateway } }
    environment: { <<: *common-env, SERVICE_NAME: "websocket-gateway" }
    networks: [backend]
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 2G }
        reservations: { cpus: "0.5", memory: 256M }

  postgresql:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: "tnsvt"
      POSTGRES_USER: "${POSTGRES_USER}"
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks: [backend]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:   { cpus: "4.0", memory: 8G }
        reservations: { cpus: "1.0", memory: 2G }
    command: >
      postgres -c shared_buffers=2GB -c effective_cache_size=6GB
        -c work_mem=64MB -c maintenance_work_mem=512MB
        -c max_connections=200 -c wal_level=replica

  timescaledb:
    image: timescale/timescaledb-ha:pg16-latest
    environment:
      POSTGRES_DB: "tnsvt_timeseries"
      POSTGRES_USER: "${POSTGRES_USER}"
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
    volumes: [timescale-data:/home/postgres/pgdata/data]
    networks: [backend]
    deploy:
      resources:
        limits:   { cpus: "4.0", memory: 8G }
        reservations: { cpus: "1.0", memory: 2G }

  redis:
    image: redis:7-alpine
    command: >
      redis-server --maxmemory 4gb --maxmemory-policy allkeys-lru
        --appendonly yes --appendfsync everysec
        --requirepass "${REDIS_PASSWORD}"
    volumes: [redis-data:/data]
    networks: [backend]
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 4G }
        reservations: { cpus: "0.5", memory: 1G }

  nats-1:
    image: nats:2.10-alpine
    command: >
      --jetstream --store_dir /data --server_name nats-1
      --cluster_name tns-v2 --routes nats://nats-2:6222,nats://nats-3:6222
    volumes: [nats-1-data:/data]
    networks: [backend]
    ports: ["4222:4222", "8222:8222"]
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 2G }
        reservations: { cpus: "0.5", memory: 512M }

  nats-2:
    image: nats:2.10-alpine
    command: >
      --jetstream --store_dir /data --server_name nats-2
      --cluster_name tns-v2 --routes nats://nats-1:6222,nats://nats-3:6222
    volumes: [nats-2-data:/data]
    networks: [backend]
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 2G }
        reservations: { cpus: "0.5", memory: 512M }

  nats-3:
    image: nats:2.10-alpine
    command: >
      --jetstream --store_dir /data --server_name nats-3
      --cluster_name tns-v2 --routes nats://nats-1:6222,nats://nats-2:6222
    volumes: [nats-3-data:/data]
    networks: [backend]
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 2G }
        reservations: { cpus: "0.5", memory: 512M }

  vault:
    image: hashicorp/vault:1.16
    environment:
      VAULT_ADDR: "http://127.0.0.1:8200"
    cap_add: [IPC_LOCK]
    volumes:
      - vault-data:/vault/file
      - ./vault/config:/vault/config
    command: server -config=/vault/config/vault.hcl
    networks: [backend]
    deploy:
      resources:
        limits:   { cpus: "1.0", memory: 512M }
        reservations: { cpus: "0.25", memory: 128M }

  prometheus:
    image: prom/prometheus:v2.53.0
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alerts:/etc/prometheus/alerts
      - prometheus-data:/prometheus
    networks: [backend, monitoring]
    ports: ["9090:9090"]
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 4G }
        reservations: { cpus: "0.5", memory: 1G }

  grafana:
    image: grafana/grafana:11.1.0
    environment:
      GF_SECURITY_ADMIN_USER: "${GRAFANA_USER}"
      GF_SECURITY_ADMIN_PASSWORD: "${GRAFANA_PASSWORD}"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - grafana-data:/var/lib/grafana
    networks: [monitoring]
    ports: ["3000:3000"]
    depends_on: [prometheus, loki, tempo]
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 2G }
        reservations: { cpus: "0.5", memory: 512M }

  loki:
    image: grafana/loki:3.1.0
    volumes:
      - ./loki/loki-config.yml:/etc/loki/loki-config.yml
      - loki-data:/loki
    networks: [monitoring]
    ports: ["3100:3100"]
    command: -config.file=/etc/loki/loki-config.yml
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 2G }
        reservations: { cpus: "0.5", memory: 512M }

  tempo:
    image: grafana/tempo:2.5.0
    volumes:
      - ./tempo/tempo-config.yml:/etc/tempo/tempo-config.yml
      - tempo-data:/var/tempo
    networks: [monitoring]
    ports: ["3200:3200"]
    command: -config.file=/etc/tempo/tempo-config.yml
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 4G }
        reservations: { cpus: "0.5", memory: 1G }

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: "${MINIO_USER}"
      MINIO_ROOT_PASSWORD: "${MINIO_PASSWORD}"
    volumes: [minio-data:/data]
    networks: [backend]
    ports: ["9000:9000", "9001:9001"]
    deploy:
      resources:
        limits:   { cpus: "2.0", memory: 2G }
        reservations: { cpus: "0.5", memory: 512M }

  mailhog:
    image: mailhog/mailhog:latest
    ports: ["1025:1025", "8025:8025"]
    networks: [backend]
    deploy:
      resources:
        limits: { cpus: "0.5", memory: 256M }

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true
  monitoring:
    driver: bridge
    internal: true

volumes:
  postgres-data:
  timescale-data:
  redis-data:
  nats-1-data:
  nats-2-data:
  nats-3-data:
  vault-data:
  prometheus-data:
  grafana-data:
  loki-data:
  tempo-data:
  minio-data:
  ollama-models:
  ai-model-cache:
  vault-secrets:
```

---

## 3. Fase 3: Kubernetes

### Namespace Layout

```
+------------------------------------------------------------------+
|                    KUBERNETES CLUSTER                             |
+------------------------------------------------------------------+
|                                                                    |
|  +----------------+  +----------------+  +---------------------+ |
|  | ns: traefik    |  | ns: monitoring |  | ns: data            | |
|  | Traefik Ingress|  | Prometheus     |  | PostgreSQL          | |
|  | Cert Manager   |  | Grafana        |  | TimescaleDB         | |
|  |                |  | Loki           |  | Redis               | |
|  +----------------+  | Tempo          |  | NATS                | |
|                      +----------------+  | Vault               | |
|                                           +---------------------+ |
|  +----------------+  +----------------+  +---------------------+ |
|  | ns: trading    |  | ns: ai         |  | ns: platform        | |
|  | trading-engine |  | ai-engine      |  | auth-service        | |
|  | risk-engine    |  | ollama-server  |  | platform-api        | |
|  | broker-gateway |  | copy-trading   |  | notification-svc    | |
|  | ws-gateway     |  |                |  | audit-service       | |
|  +----------------+  +----------------+  +---------------------+ |
+------------------------------------------------------------------+
```

### Deployment: Trading Engine

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-engine
  namespace: trading
  labels:
    app: trading-engine
    version: v2.0.0
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: trading-engine
  template:
    metadata:
      labels:
        app: trading-engine
        version: v2.0.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: trading-engine
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: trading-engine
          image: registry.tnsvt.com/trading-engine:2.0.0
          ports:
            - containerPort: 8082
            - containerPort: 9090
          env:
            - name: SERVICE_NAME
              value: "trading-engine"
            - name: POSTGRES_HOST
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: host
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: password
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: redis-credentials
                  key: url
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "4000m"
              memory: "2Gi"
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8082
            initialDelaySeconds: 15
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8082
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
          startupProbe:
            httpGet:
              path: /health/startup
              port: 8082
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 30
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values: [trading-engine]
                topologyKey: kubernetes.io/hostname
---
apiVersion: v1
kind: Service
metadata:
  name: trading-engine
  namespace: trading
spec:
  selector:
    app: trading-engine
  ports:
    - name: http
      port: 8082
      targetPort: 8082
    - name: metrics
      port: 9090
      targetPort: 9090
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: trading-engine-hpa
  namespace: trading
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: trading-engine
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
```

### Deployment: Todos los servicios Go (plantilla)

| Servicio            | Namespace   | Replicas | CPU Req | CPU Lim | Mem Req | Mem Lim |
|---------------------|-------------|----------|---------|---------|---------|---------|
| auth-service        | platform    | 3        | 500m    | 2000m   | 256Mi   | 1Gi     |
| platform-api        | platform    | 3        | 500m    | 2000m   | 256Mi   | 1Gi     |
| trading-engine      | trading     | 3        | 500m    | 4000m   | 512Mi   | 2Gi     |
| risk-engine         | trading     | 3        | 500m    | 2000m   | 256Mi   | 1Gi     |
| broker-gateway      | trading     | 3        | 1000m   | 4000m   | 512Mi   | 2Gi     |
| copy-trading        | ai          | 2        | 500m    | 2000m   | 256Mi   | 1Gi     |
| notification-svc    | platform    | 2        | 250m    | 1000m   | 128Mi   | 512Mi   |
| audit-service       | platform    | 2        | 250m    | 1000m   | 128Mi   | 512Mi   |
| websocket-gateway   | trading     | 3        | 500m    | 2000m   | 512Mi   | 2Gi     |
| ai-engine           | ai          | 2        | 2000m   | 4000m   | 2Gi     | 4Gi     |
| ollama-server       | ai          | 2        | 4000m   | 8000m   | 8Gi     | 16Gi    |

---

## 4. Traefik Configuration

### traefik.yml (Static Config)

```yaml
api:
  dashboard: true
  insecure: false

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
  websecure:
    address: ":443"
    http:
      tls:
        certResolver: letsencrypt

providers:
  kubernetesIngress:
    namespace: traefik
    allowCrossNamespace: false
  kubernetesCRD:
    namespace: traefik
    allowCrossNamespace: false

certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@tnsvt.com
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web

log:
  level: INFO
  format: JSON

accessLog:
  format: json
  filters:
    statusCodes: ["400-599"]
    retryAttempts: true

metrics:
  prometheus:
    addEntryPointsLabels: true
    addRoutersLabels: true
    addServicesLabels: true
    buckets: [0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0, 5.0]
```

### Middlewares Globales

```yaml
# traefik/middleware/rate-limit.yml
http:
  middlewares:
    rate-limit-auth:
      rateLimit:
        average: 5
        burst: 10
        period: 1m
    rate-limit-trading:
      rateLimit:
        average: 100
        burst: 200
        period: 1m
    rate-limit-market:
      rateLimit:
        average: 200
        burst: 500
        period: 1m
    rate-limit-global:
      rateLimit:
        average: 500
        burst: 1000
        period: 1m

    security-headers:
      headers:
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        stsPreload: true
        forceSTSHeader: true
        contentTypeNosniff: true
        browserXssFilter: true
        referrerPolicy: "strict-origin-when-cross-origin"
        permissionsPolicy: "camera=(), microphone=(), geolocation=()"
        customResponseHeaders:
          X-Powered-By: ""
          Server: ""

    cors-policy:
      headers:
        accessControlAllowMethods: [GET, POST, PUT, PATCH, DELETE, OPTIONS]
        accessControlAllowHeaders: [Authorization, Content-Type, X-Request-ID]
        accessControlAllowOriginList: ["https://app.tnsvt.com"]
        accessControlMaxAge: 86400
        accessControlAllowCredentials: true
```

---

## 5. CI/CD Pipeline

### GitHub Actions: .github/workflows/ci-cd.yml

```yaml
name: CI/CD Pipeline TNSVT V2

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: registry.tnsvt.com
  IMAGE_PREFIX: ${{ github.repository }}

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint Go services
        run: |
          for svc in services/go/*/; do
            echo "Linting $svc..."
            golangci-lint run --timeout 5m ./$svc
          done
      - name: Lint Python services
        run: |
          for svc in services/python/*/; do
            echo "Linting $svc..."
            ruff check ./$svc
            mypy ./$svc --ignore-missing-imports
          done
      - name: Lint Frontend
        run: |
          cd frontend
          npm ci
          npm run lint
          npm run type-check

  test:
    needs: lint
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: tnsvt_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
      nats:
        image: nats:2.10-alpine
        ports: ["4222:4222"]
    steps:
      - uses: actions/checkout@v4
      - name: Unit Tests (Go)
        run: |
          for svc in services/go/*/; do
            cd $svc && go test ./... -count=1 -race -coverprofile=coverage.out
            cd -
          done
      - name: Unit Tests (Python)
        run: |
          for svc in services/python/*/; do
            cd $svc && pytest tests/ -v --tb=short
            cd -
          done
      - name: Integration Tests
        run: |
          go test ./tests/integration/... -count=1 -timeout 10m -tags=integration

  build:
    needs: test
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [auth-service, platform-api, trading-engine, risk-engine,
                  broker-gateway, copy-trading, notification-service,
                  audit-service, websocket-gateway]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Login to Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ secrets.REGISTRY_USER }}
          password: ${{ secrets.REGISTRY_PASSWORD }}
      - name: Build and Push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: build/Dockerfile.go
          target: production
          build-args: SERVICE=${{ matrix.service }}
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service }}:${{ github.sha }}
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-staging:
    needs: build
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Staging
        run: |
          helm upgrade --install tnsvt ./deploy/helm/tnsvt \
            --namespace staging --create-namespace \
            --set image.tag=${{ github.sha }} \
            --set environment=staging \
            --values ./deploy/helm/tnsvt/values-staging.yml

  deploy-production:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Production (Blue-Green)
        run: |
          helm upgrade --install tnsvt-green ./deploy/helm/tnsvt \
            --namespace production --create-namespace \
            --set image.tag=${{ github.sha }} \
            --set environment=production \
            --set replicaCount=3 \
            --values ./deploy/helm/tnsvt/values-production.yml
      - name: Run Smoke Tests
        run: |
          ./scripts/smoke-tests.sh green
      - name: Switch Traffic (Blue-Green)
        run: |
          ./scripts/blue-green-switch.sh green
      - name: Cleanup Old Version
        run: |
          helm uninstall tnsvt-blue --namespace production || true
```

---

## 6. Blue-Green Deployment

```
                    DEPLOYMENT BLUE-GREEN
+---------------------------------------------------------+
|                                                           |
|  1. DESPLEGAR VERDE (sin trafico)                        |
|                                                           |
|  Traefik ──────► tnsvt-blue  (v1.9) ── 100% trafico     |
|       │                                                   |
|       └───────► tnsvt-green (v2.0) ── 0% trafico        |
|                                                           |
|  2. VERIFICAR VERDE (smoke tests)                        |
|                                                           |
|  Traefik ──────► tnsvt-blue  (v1.9) ── 100% trafico     |
|       │                                                   |
|       └──────► tnsvt-green (v2.0) ── smoke tests pass   |
|                                                           |
|  3. SWITCH TRAFFIC                                        |
|                                                           |
|  Traefik ──────► tnsvt-green (v2.0) ── 100% trafico     |
|       │                                                   |
|       └───────► tnsvt-blue  (v1.9) ── 0% trafico        |
|                                                           |
|  4. ROLLBACK (si es necesario)                            |
|                                                           |
|  Traefik ──────► tnsvt-blue  (v1.9) ── 100% trafico     |
|       │                                                   |
|       └──────► tnsvt-green (v2.0) ── desplegar          |
+---------------------------------------------------------+
```

### Script de Switch

```bash
#!/bin/bash
# blue-green-switch.sh
TARGET=${1:-blue}

if [[ "$TARGET" != "blue" && "$TARGET" != "green" ]]; then
  echo "Uso: $0 [blue|green]"
  exit 1
fi

if [[ "$TARGET" == "green" ]]; then
  kubectl patch ingress tnsvt-ingress -n production \
    -p '{"spec":{"rules":[{"host":"api.tnsvt.com","http":{"paths":[{"path":"/","pathType":"Prefix","backend":{"service":{"name":"tnsvt-green","port":{"number":80}}}}]}}]}}'
  echo "Trafico movido a GREEN"
else
  kubectl patch ingress tnsvt-ingress -n production \
    -p '{"spec":{"rules":[{"host":"api.tnsvt.com","http":{"paths":[{"path":"/","pathType":"Prefix","backend":{"service":{"name":"tnsvt-blue","port":{"number":80}}}}]}}]}}'
  echo "Trafico movido a BLUE"
fi
```

### Rollback Procedure

```bash
#!/bin/bash
# rollback.sh
echo "=== ROLLBACK INICIADO ==="
PREVIOUS_VERSION=$1

if [[ -z "$PREVIOUS_VERSION" ]]; then
  PREVIOUS_VERSION=$(helm history tnsvt -n production --max 1 -o json | jq -r '.[0].chart')
fi

echo "Revirtiendo a version: $PREVIOUS_VERSION"

# 1. Switch trafico a la version anterior
./blue-green-switch.sh blue

# 2. Re-deploy version anterior
helm upgrade tnsvt-blue ./deploy/helm/tnsvt \
  --namespace production \
  --set image.tag=$PREVIOUS_VERSION \
  --set environment=production \
  --values ./deploy/helm/tnsvt/values-production.yml

echo "=== ROLLBACK COMPLETADO ==="
```

---

## 7. Entornos

| Caracteristica      | Development           | Staging               | Production            |
|---------------------|-----------------------|-----------------------|-----------------------|
| K8s Cluster         | kind / minikube       | GKE Autopilot (dev)   | GKE Autopilot (prod)  |
| Replicas por svc    | 1                     | 2                     | 3+ (HPA)             |
| PostgreSQL          | SQLite (local)        | Cloud SQL (dev)       | Cloud SQL HA (prod)   |
| Redis               | Local Docker          | Memorystore (dev)     | Memorystore HA (prod) |
| NATS                | Single node           | 3-node cluster        | 3-node cluster        |
| TLS                 | Self-signed           | Let's Encrypt staging | Let's Encrypt prod    |
| Monitoring          | Basic                 | Full stack            | Full + alerts         |
| Backups             | Ninguno               | Diarios               | Continuous WAL + snap |
| CI/CD               | Local deploy          | Auto on push develop  | Auto on push main + approval |

---

## 8. Estrategia de Contenedores

### Dockerfile Go (Multi-stage + Distroless)

```dockerfile
# build/Dockerfile.go
# Stage 1: Build
FROM golang:1.22-alpine AS builder

ARG SERVICE
WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY services/go/${SERVICE}/. ./
COPY shared/ ./shared/

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /app/server ./cmd/server

# Stage 2: Security scan
FROM aquasec/trivy:latest AS scanner
COPY --from=builder /app/server /tmp/server
RUN trivy filesystem --exit-code 1 --severity HIGH,CRITICAL /tmp/server || true

# Stage 3: Production (distroless)
FROM gcr.io/distroless/static-debian12:nonroot AS production

COPY --from=builder /app/server /server

USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/server"]
```

### Dockerfile Python

```dockerfile
# build/Dockerfile.python
FROM python:3.12-slim AS builder

ARG SERVICE
WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY services/python/${SERVICE}/pyproject.toml ./
RUN poetry install --no-dev --no-root

COPY services/python/${SERVICE}/. ./

FROM python:3.12-slim AS production

RUN groupadd -r appuser && useradd -r -g appuser appuser
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app .

USER appuser
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## 9. Recursos y Volumenes

### Resource Summary Total

| Categoria          | CPU Total    | Memory Total | Storage     |
|--------------------|-------------|-------------|-------------|
| Trading (3 svc)    | 10 cores    | 5 GiB       | -           |
| Platform (4 svc)   | 5.5 cores   | 3 GiB       | -           |
| AI (2 svc)         | 12 cores    | 20 GiB      | 50 GiB      |
| Data (3 svc)       | 10 cores    | 20 GiB      | 500 GiB     |
| Messaging (3 svc)  | 6 cores     | 6 GiB       | 100 GiB     |
| Observability (3)  | 6 cores     | 10 GiB      | 200 GiB     |
| Secrets (1 svc)    | 1 core      | 512 MiB     | 10 GiB      |
| **TOTAL**          | **~50 cores** | **~65 GiB** | **~860 GiB** |

### Persistent Volume Claims

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
  namespace: data
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: premium-rwo
  resources:
    requests:
      storage: 200Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: timescale-data
  namespace: data
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: premium-rwo
  resources:
    requests:
      storage: 200Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data
  namespace: data
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: premium-rwo
  resources:
    requests:
      storage: 50Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ollama-models
  namespace: ai
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: premium-rwo
  resources:
    requests:
      storage: 50Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: prometheus-data
  namespace: monitoring
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: standard-rwo
  resources:
    requests:
      storage: 100Gi
```

---

## 10. Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all
  namespace: trading
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-trading-engine
  namespace: trading
spec:
  podSelector:
    matchLabels:
      app: trading-engine
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels: { name: traefik }
      ports:
        - port: 8082
  egress:
    - to:
        - podSelector:
            matchLabels: { app: risk-engine }
      ports:
        - port: 8083
    - to:
        - podSelector:
            matchLabels: { app: broker-gateway }
      ports:
        - port: 8084
    - to:
        - namespaceSelector:
            matchLabels: { name: data }
      ports:
        - port: 5432
        - port: 6379
    - to:
        - namespaceSelector:
            matchLabels: { name: data }
      ports:
        - port: 4222
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-data-access
  namespace: data
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: {In: [trading, platform, ai]}
      ports:
        - port: 5432
        - port: 6379
        - port: 4222
```

---

## 11. Secrets en Kubernetes

### Sealed Secrets

```yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: db-credentials
  namespace: data
spec:
  encryptedData:
    host: AgBy3i4OJSWK+PiTySYZZA9rO43cGDEq...
    password: AgAxx8RkT1f5V9u8Y3e2D1bP...
    username: AgCq3J7d5s9f1g2h3j4k5l6...
---
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: jwt-signing-key
  namespace: platform
spec:
  encryptedData:
    private-key: AgDf4e6g8h0j2k4m6n8p0q2...
    public-key: AgRt5u7w9y1b3d5f7g9j1k3...
```

### External Secrets Operator (Alternativa)

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
  namespace: data
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: db-credentials
    creationPolicy: Owner
  data:
    - secretKey: password
      remoteRef:
        key: secret/data/tnsvt/db
        property: password
    - secretKey: host
      remoteRef:
        key: secret/data/tnsvt/db
        property: host
---
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: data
spec:
  provider:
    vault:
      server: "http://vault.vault.svc:8200"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "external-secrets"
          serviceAccountRef:
            name: external-secrets
```

---

**Fin del documento 07 — Infraestructura**
