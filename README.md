# Anova AI Sous Vide Assistant

> Natural language control of Anova Precision Cooker via ChatGPT

**Status:** ✅ Integration Tests Complete (102/102 passing) | 🏗️ Deployment Phase Next

---

## Project Overview

An AI-powered sous vide cooking assistant that bridges ChatGPT with an Anova Precision Cooker 3.0. Talk to ChatGPT naturally (*"Cook chicken at 65°C for 90 minutes"*) and your sous vide cooker responds automatically, with built-in food safety guardrails.

**Architecture:** API Gateway / Bridge Pattern
**Deployment:** Self-hosted Raspberry Pi Zero 2 W
**Key Feature:** Food safety validation at the API level (non-bypassable)

```
ChatGPT Custom GPT ←→ Flask API Server ←→ Anova Cloud API ←→ Physical Device
   (HTTPS/OpenAPI)     (Raspberry Pi)      (Firebase Auth)
```

---

## Current Status

### ✅ Integration Test Suite Complete (2026-01-14)

**Test Coverage:**
- ✅ **102/102 tests passing** (64 unit + 38 integration)
- ✅ 87% code coverage (434/489 lines)
- ✅ All critical paths tested
- ✅ Test execution time: 0.16s
- ✅ Zero warnings or errors

**Component Implementation Status:**
- ✅ **exceptions.py** - Complete (7 exception classes, 167 LOC)
- ✅ **validators.py** - Complete (food safety rules, 295 LOC)
- ✅ **config.py** - Complete (env + JSON loading, 277 LOC)
- ✅ **middleware.py** - Complete (auth + error handling, 338 LOC)
- ✅ **anova_client.py** - Complete (Firebase + Anova API, 470 LOC)
- ✅ **routes.py** - Complete (4 endpoints, 217 LOC)
- ✅ **app.py** - Complete (Flask factory, 198 LOC)

**Total Production Code:** 1,962 lines across 7 components

### ✅ Scaffolding Complete (2026-01-09)

**Scaffolding Complete (15 files):**
- ✅ Server package (8 Python modules with comprehensive stubs)
- ✅ Test suite (5 test files with 16+ test case stubs)
- ✅ Deployment scripts (systemd service + Raspberry Pi setup)
- ✅ Exception hierarchy (complete implementation)
- ✅ Food safety constants (verified correct)
- ✅ All files syntactically valid

**Agent Audits Complete:**
- ✅ Code structure review (9/10 rating)
- ✅ Documentation consistency audit (8.5/10 rating)
- ✅ Architecture deep dive (6/10 TDD readiness)

**Documentation:**
- ✅ Comprehensive implementation guide (CLAUDE.md)
- ✅ Phased roadmap (IMPLEMENTATION.md)
- ✅ Complete API specification (docs/05-api-specification.md)
- ✅ Security architecture (docs/02-security-architecture.md)
- ✅ Audit report (docs/SCAFFOLDING-AUDIT-REPORT.md)

### ⚠️ Before Implementation

**Critical Issues to Fix (10 total):**
- 🔴 Missing `.gitignore` (security risk)
- 🔴 Missing `.env.example` (setup documentation)
- 🔴 Specification-implementation bleed (TDD blocker)
- 🔴 Food safety requirements scattered (TDD blocker)
- 🔴 Missing integration test spec (TDD blocker)

**See:** `docs/SCAFFOLDING-AUDIT-REPORT.md` for complete findings

---

## Quick Start

### Prerequisites

- Python 3.11+
- Anova Precision Cooker 3.0 (WiFi connected)
- Anova account credentials

### Development Setup

```bash
# Clone repository
git clone https://github.com/apassuello/chef-gpt.git
cd chef-gpt

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (after .env.example is created)
cp .env.example .env
# Edit .env: Add Anova credentials + generate API key

# Verify scaffolding
python -m py_compile server/*.py tests/*.py  # Should pass
python -c "from server.exceptions import ValidationError"  # Should work
```

---

## Project Structure

```
chef-gpt/
├── server/                    # Flask application (9 files)
│   ├── exceptions.py          # ✅ Complete (6 exception classes)
│   ├── validators.py          # 🏗️ Stub (food safety validation)
│   ├── anova_client.py        # 🏗️ Stub (Anova Cloud API)
│   ├── routes.py              # 🏗️ Stub (4 HTTP endpoints)
│   ├── app.py                 # 🏗️ Stub (application factory)
│   └── ...                    # middleware, config
├── tests/                     # Test suite (5 files)
│   ├── test_validators.py     # 🏗️ 16 test case stubs
│   ├── test_routes.py         # 🏗️ Integration test stubs
│   └── test_anova_client.py   # 🏗️ API client test stubs
├── deployment/                # Deployment (2 files)
│   ├── anova-server.service   # ✅ Complete systemd service
│   └── setup_pi.sh            # 🏗️ Raspberry Pi setup script
├── docs/                      # Documentation
│   ├── SCAFFOLDING-AUDIT-REPORT.md  # ✅ Agent audit findings
│   ├── 01-system-context.md         # Requirements
│   ├── 02-security-architecture.md  # Security design
│   ├── 03-component-architecture.md # Component specs
│   ├── 05-api-specification.md      # Complete API spec
│   └── 07-deployment-architecture.md # Deployment guide
├── CLAUDE.md                  # ✅ Implementation guide (1,176 lines)
├── IMPLEMENTATION.md          # ✅ Phased roadmap
└── requirements.txt           # ✅ Dependencies

Legend: ✅ Complete | 🏗️ Stub (ready for implementation)
```

---

## Documentation

### Implementation Guides

- **[CLAUDE.md](CLAUDE.md)** - Comprehensive implementation guide
  - Code patterns (validation, auth, logging, error handling)
  - Food safety rules (with exact temperature constants)
  - Testing strategy (16 test cases specified)
  - Security patterns (constant-time comparison, credential handling)
  - Anti-patterns (what NOT to do)

- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Phased implementation roadmap
  - Phase 1: Core server (validators, mock responses)
  - Phase 2: Anova integration (real device control)
  - Phase 3: Security & polish (auth, logging)
  - Phase 4: Deployment (Raspberry Pi)

### Architecture Specifications

- **[docs/01-system-context.md](docs/)** - System boundaries, actors, requirements
- **[docs/02-security-architecture.md](docs/)** - Credential handling, threat model
- **[docs/03-component-architecture.md](docs/)** - Internal structure, interfaces
- **[docs/05-api-specification.md](docs/)** - Complete OpenAPI 3.0 specification
- **[docs/07-deployment-architecture.md](docs/)** - Raspberry Pi deployment

### Audit & Status

- **[docs/SCAFFOLDING-AUDIT-REPORT.md](docs/SCAFFOLDING-AUDIT-REPORT.md)** - Complete audit findings
  - 3 agent reviews (code, docs, architecture)
  - 10 critical issues identified
  - TDD readiness assessment (60% → 90% needed)
  - Prioritized action plan

---

## Food Safety (Critical)

**This system enforces food safety rules server-side (non-bypassable):**

| Rule | Value | Rationale |
|------|-------|-----------|
| **Minimum Temperature** | 40.0°C | Below is bacterial danger zone |
| **Maximum Temperature** | 100.0°C | Water boils above |
| **Poultry Minimum** | 57.0°C | Pasteurization with extended time |
| **Poultry Safe** | 65.0°C | Standard safe cooking |
| **Ground Meat Minimum** | 60.0°C | Bacteria mixed throughout |
| **Time Range** | 1-5999 min | Practical device limits |

**All constants verified against food safety science and consistent across 4 documents.**

---

## API Endpoints

| Endpoint | Method | Auth | Purpose | Status |
|----------|--------|------|---------|--------|
| `/health` | GET | No | Health check | 🏗️ Stub |
| `/start-cook` | POST | Yes | Start cooking session | 🏗️ Stub |
| `/status` | GET | Yes | Get current status | 🏗️ Stub |
| `/stop-cook` | POST | Yes | Stop cooking | 🏗️ Stub |

**Authentication:** Bearer token (API key)
**Format:** JSON request/response
**Error Codes:** 36 unique codes (comprehensive taxonomy)

---

## Development Workflow

### Current Phase: Pre-Implementation

**Recommended sequence:**

1. **Today (1-2 hours):** Fix critical issues
   ```bash
   # Create .gitignore, .env.example
   # Fix type hints in routes.py
   # Move hardcoded Firebase API key to config
   ```

2. **Week 1-2:** Documentation improvements (TDD blockers)
   ```bash
   # Create docs/06-food-safety-requirements.md
   # Refactor docs/03-component-architecture.md
   # Create integration test specification
   # Add measurable acceptance criteria to QR-XX
   ```

3. **Week 3:** Test implementation (spec-driven, not code-driven)
   ```bash
   # Read requirement → Read test spec → Write test → Implement
   # Use test-automator agent for spec-driven test generation
   ```

4. **Week 4+:** Implementation (red-green-refactor TDD)
   ```bash
   # Follow IMPLEMENTATION.md phased approach
   # validators.py → middleware.py → anova_client.py → routes.py
   ```

### Testing

```bash
# When tests are implemented:
pytest                          # Run all tests
pytest --cov=server            # With coverage
pytest tests/test_validators.py # Specific file
pytest -v                      # Verbose
pytest -x                      # Stop on first failure
```

### Code Quality

```bash
# Syntax check (works now)
python -m py_compile server/*.py tests/*.py

# When ready:
ruff check server/             # Linting
ruff format server/            # Formatting
mypy server/                   # Type checking
```

---

## Security

### Current Implementation

- ✅ Security patterns documented (constant-time comparison)
- ✅ Exception hierarchy with proper error codes
- ✅ Food safety validation at API level
- ✅ Credential handling patterns defined
- ⚠️ Missing `.gitignore` (CRITICAL - fix today)

### Production Security

- Credentials encrypted at rest (Fernet symmetric encryption)
- HTTPS-only via Cloudflare Tunnel
- API key authentication with constant-time comparison
- No credentials in logs (enforced by patterns)
- Server-side validation (food safety rules)

---

## Tech Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Runtime | Python | 3.11+ | Modern type hints, AsyncIO |
| Framework | Flask | 3.0.* | Lightweight API framework |
| Production Server | gunicorn | 21.* | WSGI server with process mgmt |
| HTTP Client | requests | 2.31.* | Anova Cloud API calls |
| Config | python-dotenv | 1.0.* | Environment variable management |
| Encryption | cryptography | 42.* | Fernet symmetric encryption |
| Testing | pytest | 7.* | Test framework |
| Test Utils | pytest-flask | 1.* | Flask test utilities |
| HTTP Mocking | responses | 0.24.* | Mock Anova API responses |

---

## Metrics

### Scaffolding Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Files Created | 15 | All syntactically valid |
| Total Lines of Code | ~2,500 | Mostly docstrings/stubs |
| Exceptions Defined | 6 | Complete implementations |
| Food Safety Constants | 9 | All verified correct |
| Test Cases Specified | 16+ | Comprehensive validator tests |
| API Endpoints | 4 | All documented |
| Error Codes | 36 | Full taxonomy |

### Documentation Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Specification Docs | 8 | In docs/ folder |
| Implementation Guide | 1,176 lines | CLAUDE.md |
| Cross-References | 100+ | Between documents |
| Documentation Consistency | 95% | Excellent alignment |

### Requirements Coverage

| Type | Total | Tested | Coverage | Target |
|------|-------|--------|----------|--------|
| Functional (FR-XX) | 13 | 11 | 85% | 100% |
| Quality (QR-XX) | 14 | 4 | 29% | 80% |
| Security (SEC-REQ-XX) | 6 | 3 | 50% | 100% |
| **Overall** | **33** | **18** | **55%** | **90%** |

**Gap:** 45% of requirements need test specifications (see audit report)

---

## Next Steps

### Immediate (Today)

1. ✅ Review `docs/SCAFFOLDING-AUDIT-REPORT.md`
2. 🔲 Create `.gitignore` (CRITICAL)
3. 🔲 Create `.env.example`
4. 🔲 Fix type hints compatibility (routes.py)
5. 🔲 Move Firebase API key to config

**Estimated time:** 1-2 hours

### This Week

1. 🔲 Create food safety requirements document
2. 🔲 Separate specifications from implementations
3. 🔲 Create integration test specification
4. 🔲 Add measurable acceptance criteria

**Estimated time:** 10-15 hours (1-2 weeks at 1-2 hours/day)

### Before Implementation

- [ ] TDD readiness >= 90%
- [ ] Requirements traceability >= 90%
- [ ] All test specifications created
- [ ] Critical issues resolved

---

## Contributing

This is a personal project for a gift recipient. Issues and suggestions welcome!

**Current Status:** Scaffolding phase - not yet accepting PRs
**Future:** May accept contributions after MVP complete

---

## License

MIT License - See LICENSE file for details

---

## Acknowledgments

- **Anova Culinary** - Precision Cooker 3.0
- **OpenAI** - Custom GPT capability
- **Cloudflare** - Free HTTPS tunneling
- **Food Safety** - USDA guidelines, Baldwin's sous vide guide
- **Agent Reviewers** - code-reviewer, docs-architect, architect-review agents

---

## Contact

**Project:** Anova AI Sous Vide Assistant
**Repository:** https://github.com/apassuello/chef-gpt
**Status:** 🏗️ Scaffolding Complete (2026-01-09)

**For Implementation Questions:** See CLAUDE.md
**For Architecture Questions:** See docs/ specifications
**For Status Updates:** See docs/SCAFFOLDING-AUDIT-REPORT.md

---

**Next Action:** Read the audit report, fix critical issues, then proceed with documentation improvements before implementation.
