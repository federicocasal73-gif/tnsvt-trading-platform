# Contributing to TNSVT V2

Thank you for your interest in contributing! This document explains how to
set up your environment, run the project locally, and submit changes.

---

## Code of Conduct

We are committed to providing a welcoming and inclusive experience for
everyone. By participating, you agree to:

- Be respectful of differing viewpoints and experiences
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy toward other community members

Unacceptable behavior (harassment, discrimination, trolling) will not be
tolerated and may result in a ban from the project.

---

## How to Contribute

### Reporting Bugs

Open an issue with:

1. Clear, descriptive title
2. Steps to reproduce
3. Expected vs actual behavior
4. Environment (OS, Go/Python/Node version, docker version)
5. Relevant logs or screenshots

### Suggesting Features

Open an issue tagged `enhancement` with:

1. The problem you're trying to solve
2. Your proposed solution
3. Alternatives you've considered
4. Whether you'd like to implement it

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/short-description`
3. Make your changes
4. Add or update tests
5. Run `make test` and `make lint`
6. Commit with a clear message (Conventional Commits preferred):
   - `feat(scope): add new thing`
   - `fix(scope): resolve issue #123`
   - `docs(scope): update guide`
   - `refactor(scope): restructure without behavior change`
   - `test(scope): add tests only`
7. Push and open a Pull Request against `master`

A PR should:

- Pass CI (lint + test + build)
- Include tests for new behavior
- Update relevant docs (README, comments, ARCHITECTURE.md)
- Have < 400 lines of diff (split larger PRs)

---

## Development Setup

### Prerequisites

- **Go 1.22+** — backend services
- **Python 3.12+** — AI services (ai-core, telegram-bridge)
- **Node.js 20+** — frontend
- **Docker + Docker Compose** — infrastructure
- **PostgreSQL client** (psql) — optional, for local debugging

### Local Environment

```bash
# Clone your fork
git clone https://github.com/<your-username>/TNSVT-V2-Architecture
cd TNSVT-V2-Architecture

# Copy environment template
cp .env.example .env

# Start the stack (Postgres, Redis, NATS, Ollama, monitoring)
./scripts/start.sh --seed

# In another terminal: run a single Go service in dev mode
cd apps/platform/auth-service
go run .

# Frontend dev server
cd apps/frontend
npm install
npm run dev
```

### Running Tests

```bash
# Everything (via Make)
make test

# Single Go service
./scripts/test-service.sh auth-service

# Python service
cd apps/ai/ai-core
pytest tests/ -v

# Frontend type-check
cd apps/frontend
npx tsc --noEmit
```

---

## Project Structure

```
apps/                  # Microservices (Go + Python)
  ├── trading/         # signal/execution/copy trading + telegram-bridge
  ├── risk/            # risk engine
  ├── broker/          # MT5 connector
  ├── ai/              # AI core (Python)
  ├── market-data/     # Price feed (WebSocket → NATS)
  ├── platform/        # auth-service, user-service
  ├── notification/    # telegram-bot-service
  ├── audit/           # audit-engine (event sourcing)
  └── gateway/         # api-gateway (Traefik-friendly)

apps/frontend/         # Vite + React 18 + TypeScript

shared/                # Code shared across services
  ├── proto/           # gRPC contracts
  ├── schemas/         # JSON schemas for NATS events
  └── go-common/       # Shared Go libs (circuit, logging, metrics, config)

infrastructure/        # Docker, observability, DB init
scripts/               # start/stop/migrate/seed/test-all
docs/                  # 15 architecture docs
```

When adding a new service, follow this layout:

```
apps/<context>/<service-name>/
├── Dockerfile
├── README.md
├── go.mod          # module github.com/tnsvt/<service-name>
├── main.go
├── internal/
│   ├── handlers/   # HTTP layer (Gin)
│   ├── service/    # business logic
│   ├── repository/ # DB layer (pgx)
│   └── models/     # types
└── *_test.go       # at least one per package
```

---

## Style Guide

### Go

- `gofmt` for formatting (run `make format`)
- `go vet ./...` must pass (run `make lint`)
- Prefer small interfaces; accept them in constructors
- Use the shared logging (`github.com/tnsvt/shared-go/logging`) — don't use `log` directly
- Use structured logging (`log.Info("event", "key", val)`)
- Errors: wrap with `fmt.Errorf("ctx: %w", err)`, don't use `panic` outside startup

### Python (AI services)

- PEP 8, formatted with `black`
- Type hints on every function signature
- `structlog` for JSON logging
- `httpx` async (not `requests`) for HTTP
- `pytest` for tests, `pytest-asyncio` for async

### TypeScript (frontend)

- `tsc --noEmit` must pass (run from `apps/frontend`)
- Use the design tokens from `tailwind.config.js` (`tnvs-purple`, `tnvs-void`, etc.)
- No hardcoded colors outside `tnvs-*` palette
- Keep components small (< 200 lines)

### Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(signal-engine): add CSV export endpoint
fix(risk-engine): clamp position size when SL = 0
docs(architecture): update FASE 1 service list
test(auth-service): add JWT expiry test
refactor(price-feed): split TickStore into separate files
```

The PR title becomes the squash-merge commit, so it must follow this format.

---

## Release Process

1. Merge accepted PRs to `master`
2. Bump versions in service READMEs and any CHANGELOG.md
3. Tag: `git tag -a v0.2.0 -m "Release v0.2.0"`
4. Push tag: `git push origin v0.2.0`
5. The release workflow:
   - Builds per-service Docker images (tagged with SHA + `latest` + git tag)
   - Generates a changelog from commits since the last tag
   - Creates a GitHub Release with notes
   - Marks pre-releases for tags containing `rc` or `beta`

---

## Getting Help

- Open an issue for bugs / features
- Discussions tab for questions
- Email maintainers (see commit history) for security issues

---

## License

By contributing, you agree that your contributions will be licensed under the
MIT License (see `LICENSE`).