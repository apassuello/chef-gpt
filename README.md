# Anova AI Sous Vide Assistant

An AI-powered sous vide cooking assistant that enables natural language control of an Anova Precision Cooker 3.0 through ChatGPT.

## What This Does

Talk to ChatGPT like: *"Cook chicken at 65°C for 90 minutes"* and your Anova sous vide cooker will start automatically. The system enforces food safety rules, validates temperatures, and provides helpful guidance through the cooking process.

**Key Features:**
- 🗣️ Natural language control via ChatGPT Custom GPT
- 🛡️ Built-in food safety validation (temperature/time rules)
- 🔒 Secure credential management
- 🏠 Self-hosted (zero recurring costs)
- 🥧 Raspberry Pi deployment

## Architecture

```
ChatGPT Custom GPT ←→ Flask API Server ←→ Anova Cloud API ←→ Physical Device
   (HTTPS/OpenAPI)     (Raspberry Pi)      (Firebase Auth)
```

**Pattern:** API Gateway / Bridge
**Deployment:** Raspberry Pi Zero 2 W with Cloudflare Tunnel
**Security:** Server-side validation, encrypted credentials, API key auth

## Quick Start

### Prerequisites

- Python 3.11+
- Anova Precision Cooker 3.0 (connected to WiFi)
- Anova account credentials

### Setup

```bash
# Clone repository
git clone https://github.com/apassuello/chef-gpt.git
cd chef-gpt

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your Anova credentials + generate API key

# Run development server
python -m server.app
```

Visit http://localhost:5000/health to verify it's running.

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=server
```

## Documentation

Comprehensive documentation is available in the project knowledge base:

- **[CLAUDE.md](CLAUDE.md)** - Implementation guide for Claude Code (code patterns, food safety rules, testing)
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Phased implementation roadmap
- **Architecture Docs** - In Claude.ai project knowledge base:
  - 01-system-context.md - System boundaries and actors
  - 02-security-architecture.md - Credential handling and security
  - 03-component-architecture.md - Internal structure
  - 04-custom-gpt-spec.md - ChatGPT configuration
  - 05-api-specification.md - Complete API specification
  - 07-deployment-architecture.md - Deployment guide

## Project Structure

```
chef-gpt/
├── server/             # Flask application
│   ├── app.py         # Application factory
│   ├── routes.py      # HTTP endpoints
│   ├── validators.py  # Input & food safety validation
│   ├── anova_client.py # Anova API client
│   └── ...
├── tests/             # Test suite
├── deployment/        # Deployment scripts
└── docs/              # Documentation
```

## Food Safety

**This system enforces food safety rules at the API level:**
- Temperature range: 40°C - 100°C
- Poultry minimum: 57°C (with extended time) or 65°C (standard)
- Ground meat minimum: 60°C
- All validation happens server-side (cannot be bypassed)

## Deployment

**Development:** ngrok tunnel for quick testing
**Production:** Raspberry Pi + Cloudflare Tunnel for permanent deployment

See [deployment/README.md](deployment/) and `07-deployment-architecture.md` for complete setup instructions.

## API Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/health` | GET | No | Health check |
| `/start-cook` | POST | Yes | Start cooking |
| `/status` | GET | Yes | Get current status |
| `/stop-cook` | POST | Yes | Stop cooking |

Authentication: Bearer token (API key)

## Tech Stack

- **Backend:** Python 3.11+, Flask 3.0
- **Production Server:** gunicorn
- **External APIs:** Anova Cloud (Firebase Auth)
- **Deployment:** Cloudflare Tunnel, systemd
- **Testing:** pytest, pytest-flask, responses

## Security

- ✅ Credentials encrypted at rest (production)
- ✅ HTTPS-only via Cloudflare Tunnel
- ✅ API key authentication
- ✅ No credentials in logs
- ✅ Server-side validation (food safety)

## Development Workflow

1. **Phase 1:** Core server with validators and mock responses
2. **Phase 2:** Anova API integration
3. **Phase 3:** Security hardening and logging
4. **Phase 4:** Deployment to Raspberry Pi

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for detailed phase breakdown.

## Contributing

This is a personal project for a gift recipient. However, issues and suggestions are welcome!

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Anova Culinary for the Precision Cooker 3.0
- OpenAI for Custom GPT capability
- Cloudflare for free HTTPS tunneling
- Food safety guidelines from USDA and Baldwin's sous vide guide
