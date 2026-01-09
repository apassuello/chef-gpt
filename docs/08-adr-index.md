# 08 - Architecture Decision Records Index

> **Document Type:** ADR Index  
> **Status:** Living Document  
> **Version:** 1.0  
> **Last Updated:** 2025-01-08  
> **Depends On:** All other specification documents

---

## 1. Overview

This document contains all Architecture Decision Records (ADRs) for the Anova AI Sous Vide Assistant project. ADRs capture the context, options, and rationale behind significant architectural decisions.

**ADR Status Definitions:**
- **Proposed** - Under consideration
- **Accepted** - Decision made and implemented
- **Deprecated** - No longer valid (superseded)
- **Superseded** - Replaced by another ADR

---

## 2. ADR Summary Table

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| ADR-001 | ChatGPT Custom GPT as User Interface | Accepted | 2025-01-08 |
| ADR-002 | Flask as Backend Framework | Accepted | 2025-01-08 |
| ADR-003 | Cloudflare Tunnel for HTTPS Exposure | Accepted | 2025-01-08 |
| ADR-004 | Encrypted File for Credential Storage | Accepted | 2025-01-08 |
| ADR-005 | Polling-Based Status Updates | Accepted | 2025-01-08 |
| ADR-006 | API Key Authentication | Accepted | 2025-01-08 |
| ADR-007 | Defer Notifications to Anova App | Accepted | 2025-01-08 |

---

## ADR-001: ChatGPT Custom GPT as User Interface

**Status:** Accepted  
**Date:** 2025-01-08  
**Deciders:** System Admin (Gift Giver)

### Context

We need a natural language interface for the recipient to control their Anova sous vide cooker. The recipient is non-technical and wants to use voice or text commands rather than navigating the native Anova app for every cook.

The interface must:
- Support natural language (voice and text)
- Work on iPhone and web
- Have no recurring costs
- Require minimal setup for the recipient

### Decision Drivers

1. **Recipient already has ChatGPT Plus subscription** - No new subscription needed
2. **Natural language quality** - Must understand cooking requests naturally
3. **Voice support** - ChatGPT mobile app has excellent voice mode
4. **Zero additional cost** - Gift constraint
5. **Minimal recipient setup** - Just a link to click, no app installation

### Considered Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **1. ChatGPT Custom GPT** | Custom GPT with Actions API | NL quality, voice, no cost, easy share | Requires ChatGPT Plus |
| 2. Amazon Alexa Skill | Voice-first smart speaker skill | Dedicated voice UI, always listening | Requires Echo device, no text fallback, skill approval process |
| 3. Native iOS App | Custom-built iOS application | Full control, native experience | Requires App Store approval, expensive to develop, maintenance burden |
| 4. Web App with Voice | PWA with speech recognition | No app installation, cross-platform | Voice recognition quality varies, more complex to build |
| 5. SMS/Text Interface | Twilio-based text commands | Works on any phone | Recurring costs (Twilio), limited NL capability |

### Decision Outcome

**Chosen option:** ChatGPT Custom GPT (Option 1)

**Reasoning:**
1. **Recipient already pays for ChatGPT Plus** - No incremental cost
2. **Voice quality is excellent** - ChatGPT's voice mode is state-of-the-art
3. **Text fallback seamless** - Same conversation works voice or typed
4. **Share via link** - Recipient clicks link, starts using immediately
5. **NL understanding is superior** - GPT-4 handles cooking requests naturally
6. **Built-in safety filtering** - OpenAI's safety guidelines help filter harmful requests
7. **Maintenance is minimal** - OpenAI handles infrastructure

### Consequences

**Positive:**
- Zero development cost for UI
- Best-in-class natural language understanding
- Voice and text in one interface
- Easy updates (edit GPT instructions)

**Negative:**
- Dependency on OpenAI service availability
- If recipient cancels ChatGPT Plus, interface stops working
- GPT can occasionally hallucinate (mitigated by server-side validation)
- Action timeout limit (~30 seconds) constrains long operations

**Risks:**
| Risk | Mitigation |
|------|------------|
| OpenAI changes Custom GPT pricing | Monitor announcements; have fallback plan |
| GPT hallucinates unsafe parameters | Server-side validation rejects all unsafe inputs |
| Recipient cancels subscription | Anova app still works as fallback |

---

## ADR-002: Flask as Backend Framework

**Status:** Accepted  
**Date:** 2025-01-08  
**Deciders:** System Admin (Gift Giver)

### Context

We need a Python web framework to create the REST API that ChatGPT's Custom GPT Actions will call. The API has only 4 endpoints and must run on a Raspberry Pi Zero 2 W with 512MB RAM.

### Decision Drivers

1. **Simplicity** - Only 4 simple endpoints needed
2. **Resource constraints** - Pi Zero 2 W has limited RAM/CPU
3. **Developer familiarity** - Single developer, moderate Python experience
4. **Maintainability** - Code must be understandable for future debugging
5. **Ecosystem** - Good documentation and community support

### Considered Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **1. Flask** | Lightweight WSGI framework | Simple, minimal, well-documented | Manual validation, no async |
| 2. FastAPI | Modern async framework with Pydantic | Auto-validation, async, auto-docs | More complex, heavier, overkill for 4 endpoints |
| 3. Django | Full-featured framework | Batteries included, admin UI | Far too heavy, massive overhead |
| 4. Bottle | Single-file microframework | Extremely minimal | Less ecosystem, fewer patterns |
| 5. Raw HTTP server | http.server or socketserver | No dependencies | Too low-level, error-prone |

### Decision Outcome

**Chosen option:** Flask (Option 1)

**Reasoning:**
1. **Right-sized for the task** - 4 endpoints don't need FastAPI's features
2. **Mature and stable** - Flask has been around since 2010, battle-tested
3. **Excellent documentation** - Easy to learn and debug
4. **Low memory footprint** - Works well on Pi Zero 2 W
5. **Simple mental model** - Request comes in, response goes out
6. **gunicorn compatibility** - Production-ready WSGI server
7. **Extensive examples** - Easy to find patterns for any problem

**Why not FastAPI:**
- Async is not needed (API calls are synchronous to Anova)
- Auto-validation is nice but not critical for 4 endpoints
- More dependencies, more things to break
- Overkill complexity for the problem size

### Consequences

**Positive:**
- Simple, readable codebase
- Easy to debug when something goes wrong
- Light memory usage on constrained hardware
- Admin can understand and modify code

**Negative:**
- No automatic request validation (must implement manually)
- No built-in async (not needed, but limits future extensions)
- Must choose and configure WSGI server separately

**Trade-offs Accepted:**
- Implemented manual validation in `validators.py` (actually provides more control over error messages)
- Using gunicorn for production (well-documented pattern)

---

## ADR-003: Cloudflare Tunnel for HTTPS Exposure

**Status:** Accepted  
**Date:** 2025-01-08  
**Deciders:** System Admin (Gift Giver)

### Context

ChatGPT Custom GPT Actions require an HTTPS endpoint to call. The Raspberry Pi is behind a home router with no static IP and likely carrier-grade NAT. We need a way to expose the local Flask server to the internet securely.

### Decision Drivers

1. **Zero recurring cost** - Gift constraint
2. **No port forwarding** - Many home routers/ISPs don't support it
3. **Stable URL** - URL can't change or GPT Actions break
4. **HTTPS required** - ChatGPT only calls HTTPS endpoints
5. **Reliability** - Must work 24/7 without intervention

### Considered Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **1. Cloudflare Tunnel** | Outbound tunnel through Cloudflare's network | Free, stable URL, no port forwarding, auto-TLS | Cloudflare dependency |
| 2. ngrok (free tier) | Quick tunnel service | Easy setup, instant | URL changes on restart, free tier limits |
| 3. ngrok (paid) | Stable subdomain | Stable URL, easy | $10+/month recurring cost |
| 4. Tailscale Funnel | Tailscale's tunnel feature | Good for Tailscale users | Requires Tailscale setup, less mature |
| 5. Port forwarding + DDNS | Traditional approach | No third-party dependency | Many ISPs block, needs router config, needs DDNS, needs TLS cert |
| 6. VPS reverse proxy | Rent small VPS, tunnel to it | Full control | Recurring cost, complexity |

### Decision Outcome

**Chosen option:** Cloudflare Tunnel (Option 1)

**Reasoning:**
1. **Genuinely free** - Free tier is sufficient, no credit card required
2. **Stable URL** - Get a *.cfargotunnel.com URL or use custom domain
3. **No inbound ports** - Works behind any NAT/firewall (outbound tunnel)
4. **Automatic TLS** - Cloudflare handles certificates
5. **High reliability** - Cloudflare's infrastructure is enterprise-grade
6. **Good documentation** - Well-documented setup process
7. **systemd integration** - `cloudflared` runs as a proper service

### Consequences

**Positive:**
- Zero recurring cost
- Works behind strict NAT/CGNAT
- No TLS certificate management
- DDoS protection included
- Easy to set up with systemd

**Negative:**
- Dependency on Cloudflare (if they change/remove free tier)
- Adds latency (traffic goes through Cloudflare)
- Requires Cloudflare account setup

**Risks:**
| Risk | Mitigation |
|------|------------|
| Cloudflare removes free tier | ngrok or Tailscale as backup |
| Cloudflare outage | Rare; accept temporary downtime |
| Tunnel daemon crashes | systemd auto-restarts |

---

## ADR-004: Encrypted File for Credential Storage

**Status:** Accepted  
**Date:** 2025-01-08  
**Deciders:** System Admin (Gift Giver)

### Context

The server needs access to Anova account credentials (email/password) and an API key. These secrets must:
- Be available at server startup
- Survive reboots
- Not be exposed in logs or to ChatGPT
- Be protected if the SD card is physically stolen

### Decision Drivers

1. **Persistence** - Credentials must survive reboots
2. **Security** - Protect against physical theft of SD card
3. **Simplicity** - Don't over-engineer for a single-user system
4. **Development flexibility** - Easy to work with during development

### Considered Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| 1. Environment variables | Export in .bashrc or systemd env | Simple, well-understood | Doesn't persist reliably, visible in process list |
| 2. Plain text config file | JSON/YAML with permissions | Very simple | No protection against physical theft |
| **3. Encrypted config file** | AES-256 encrypted JSON | Protected at rest, survives reboot | Key management complexity |
| 4. OS keychain/secret store | libsecret, GNOME Keyring | OS-level protection | Complex on headless Pi |
| 5. Hardware security module | TPM or external HSM | Hardware-backed security | Overkill, Pi Zero doesn't have TPM |

### Decision Outcome

**Chosen option:** Encrypted config file (Option 3)

**Hybrid approach:**
- **Development:** Plain environment variables (`.env` file, python-dotenv)
- **Production:** AES-256-GCM encrypted JSON file

**Reasoning:**
1. **Physical security** - If SD card is stolen, credentials aren't readable
2. **Persistence** - File survives reboots cleanly
3. **Reasonable complexity** - Python's cryptography library makes this straightforward
4. **Dev/prod split** - Simple for development, secure for production

**Key derivation strategy:**
- Derive encryption key from combination of:
  - Machine-specific identifier (MAC address, CPU serial)
  - Optional admin-provided passphrase
- This ties credentials to specific Pi (can't decrypt on different hardware)

### Consequences

**Positive:**
- Credentials protected if SD card stolen
- Clean separation of dev (simple) and prod (secure)
- No external dependencies for secret storage

**Negative:**
- Implementation complexity for encryption/decryption
- If machine identifier changes, must re-encrypt
- Admin must remember passphrase (if used)

**Implementation Note:**
For MVP, plain JSON with strict file permissions (600) is acceptable. Encryption can be added as an enhancement once core functionality works.

---

## ADR-005: Polling-Based Status Updates

**Status:** Accepted  
**Date:** 2025-01-08  
**Deciders:** System Admin (Gift Giver)

### Context

Users need to check cooking progress (current temperature, time remaining). The question is whether to:
1. Poll the Anova API when the user asks (reactive)
2. Maintain a persistent connection and push updates (proactive)

### Decision Drivers

1. **ChatGPT's architecture** - Actions are request/response, not streaming
2. **Resource constraints** - Pi Zero has limited resources
3. **Simplicity** - Fewer moving parts
4. **Reliability** - Must work without complex reconnection logic

### Considered Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **1. Polling on demand** | Query Anova API when user asks | Simple, stateless | User must ask for updates |
| 2. WebSocket with push | Maintain connection, push updates | Real-time updates | Can't push to ChatGPT, complex reconnection |
| 3. Polling with cache | Poll periodically, cache locally | Faster responses | Stale data, background task complexity |
| 4. Server-Sent Events | Long-lived HTTP for server push | Standard HTTP | ChatGPT doesn't support SSE |

### Decision Outcome

**Chosen option:** Polling on demand (Option 1)

**Reasoning:**
1. **ChatGPT can't receive pushes** - Actions are synchronous; no way to push updates to GPT
2. **Anova app handles notifications** - User already has real-time updates via Anova app
3. **Stateless is simpler** - No connection state to manage
4. **Pi resources preserved** - No background polling consuming CPU/memory
5. **Perfectly adequate UX** - User can ask "how's it going?" anytime

### Consequences

**Positive:**
- Dead-simple implementation
- No connection management
- No background tasks
- Anova API rate limits aren't a concern (user-driven queries)

**Negative:**
- Users must explicitly ask for status
- Can't proactively inform about issues
- Relies on Anova app for timer notifications

**Accepted Trade-off:**
Users who want automatic notifications should use the Anova app (which they already have). This system adds conversational control, not a notification replacement.

---

## ADR-006: API Key Authentication

**Status:** Accepted  
**Date:** 2025-01-08  
**Deciders:** System Admin (Gift Giver)

### Context

The API is exposed to the internet via Cloudflare Tunnel. While the URL is obscure, anyone who discovers it could potentially control the Anova device. We need to decide what level of authentication to implement.

### Decision Drivers

1. **Security** - Unauthorized access could affect cooking
2. **Simplicity** - Single-user system, don't over-engineer
3. **ChatGPT compatibility** - Must work with Custom GPT Actions
4. **Operational burden** - Admin shouldn't need frequent intervention

### Considered Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| 1. No authentication | Rely on obscure URL | Simplest | Anyone with URL can control device |
| **2. API key (Bearer token)** | Static key in Authorization header | Simple, ChatGPT supports it | Key rotation is manual |
| 3. OAuth 2.0 | Industry-standard auth flow | Very secure, standard | Massive overkill, complex to implement |
| 4. IP allowlist | Only allow OpenAI IPs | Simple concept | OpenAI IPs change, impractical |
| 5. Mutual TLS | Client certificate authentication | Strong authentication | Complex setup, ChatGPT doesn't support |

### Decision Outcome

**Chosen option:** API key authentication (Option 2)

**Implementation details:**
- Generate 256-bit random key: `sk-anova-{random_urlsafe_32}`
- Send as Bearer token: `Authorization: Bearer sk-anova-xxx`
- Constant-time comparison to prevent timing attacks
- Health endpoint (`/health`) exempt for uptime monitoring

**Reasoning:**
1. **ChatGPT supports it natively** - Actions have built-in Bearer token support
2. **Sufficient security** - Random 256-bit key is infeasible to guess
3. **Simple to implement** - Few lines of middleware code
4. **Single point of configuration** - Just the key, no OAuth flows

**Why not no auth:**
Even with an obscure URL, discovery is possible (search engines, access logs, etc.). The consequences of unauthorized access (starting unwanted cooks, wasting food) justify the small overhead of an API key.

### Consequences

**Positive:**
- Meaningful security barrier
- Easy to implement and understand
- ChatGPT handles key storage/transmission

**Negative:**
- Admin must manage the key
- If key is compromised, manual rotation required
- No per-user tracking (single key for all access)

**Key Management:**
- Generate key once during setup
- Store in server config and ChatGPT Actions
- Rotate immediately if compromised
- No expiration (manual rotation only)

---

## ADR-007: Defer Notifications to Anova App

**Status:** Accepted  
**Date:** 2025-01-08  
**Deciders:** System Admin (Gift Giver)

### Context

Users need to know when their cook is done. We could build a notification system, but the recipient already has the Anova app installed, which provides native notifications.

### Decision Drivers

1. **Development effort** - Notifications are complex to implement well
2. **Recipient's existing setup** - Already has Anova app with notifications
3. **Reliability** - Native app notifications are battle-tested
4. **Scope management** - Keep v1 focused on core value proposition

### Considered Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| 1. Build push notifications | Implement via Firebase/APNS | Complete solution | Complex, costly, maintenance burden |
| 2. Build SMS notifications | Twilio integration | Universal, reliable | Recurring costs, complexity |
| 3. Build email notifications | SMTP integration | Free, simple | Email isn't timely, often missed |
| **4. Defer to Anova app** | Let native app handle it | Zero effort, already works | Not integrated with our system |
| 5. ChatGPT scheduled messages | Have GPT check back | Uses existing interface | ChatGPT doesn't support scheduled messages |

### Decision Outcome

**Chosen option:** Defer to Anova app (Option 4)

**Reasoning:**
1. **Already exists and works** - Recipient has Anova app, notifications already configured
2. **Zero implementation** - No code to write, test, or maintain
3. **No recurring costs** - No Twilio, no Firebase, no push notification service
4. **Core value preserved** - Our system adds conversational control, not notifications
5. **Risk avoidance** - Building notifications is scope creep with failure modes

**User experience:**
1. User tells ChatGPT to start cooking
2. ChatGPT confirms: "Your Anova app can send you a notification when it's done"
3. Anova app sends push notification when timer completes
4. User can also ask ChatGPT "is it done yet?" anytime

### Consequences

**Positive:**
- Dramatically reduced scope
- No notification infrastructure to maintain
- Leverages existing reliable system
- Focus on conversational control (unique value)

**Negative:**
- Notifications not "integrated" (two separate systems)
- User must have Anova app properly configured
- Can't customize notification messages

**Accepted Trade-off:**
The recipient already uses the Anova app for notifications. Our system adds value by enabling conversational control, not by reinventing notifications.

---

## 3. Decision Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DECISION DEPENDENCY GRAPH                             │
└─────────────────────────────────────────────────────────────────────────────┘

  ADR-001                     ADR-003                    ADR-007
  ChatGPT GPT ────────────────Cloudflare ────────────────Notifications
       │                      Tunnel                     (Defer)
       │                         │
       │    ┌────────────────────┼────────────────────┐
       │    │                    │                    │
       ▼    ▼                    ▼                    ▼
  ADR-006               ADR-002                 ADR-005
  API Key Auth          Flask                   Polling
       │                   │
       │                   │
       └───────┬───────────┘
               │
               ▼
           ADR-004
           Credential
           Storage

KEY:
───► "Influences" or "requires"

READING:
- ChatGPT as interface (001) requires API Key auth (006) to secure the actions
- Cloudflare Tunnel (003) enables both GPT access and simplifies deployment
- Flask (002) is chosen because GPT actions are simple HTTP calls
- Polling (005) is chosen because GPT can't receive pushes
- Credential storage (004) secures both Flask server and API key
- Notifications (007) are deferred because GPT can't push to users
```

---

## 4. Future ADR Candidates

If the project evolves, these decisions may need ADRs:

| Potential ADR | Trigger |
|---------------|---------|
| Multi-device support | Recipient gets second Anova |
| Recipe database | Users want saved presets |
| OAuth for multi-user | System shared beyond household |
| Scheduled cooks | Request for delayed start (food safety concerns) |
| Alternative LLM | OpenAI pricing changes or availability issues |

---

## 5. ADR Template

Use this template for new ADRs:

```markdown
## ADR-XXX: [Title]

**Status:** Proposed | Accepted | Deprecated | Superseded  
**Date:** YYYY-MM-DD  
**Deciders:** [Who made this decision]

### Context

[What is the issue that we're seeing that is motivating this decision?]

### Decision Drivers

1. [Driver 1]
2. [Driver 2]
3. [Driver 3]

### Considered Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **1. [Chosen]** | ... | ... | ... |
| 2. [Alternative] | ... | ... | ... |

### Decision Outcome

**Chosen option:** [Option X]

**Reasoning:**
[Why this option was selected over others]

### Consequences

**Positive:**
- [Consequence 1]

**Negative:**
- [Consequence 2]

**Risks:**
| Risk | Mitigation |
|------|------------|
| ... | ... |
```

---

## 6. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-08 | Claude | Initial ADR collection |

---

## 7. References

- [01-System Context](01-system-context.md) - System boundaries and constraints
- [02-Security Architecture](02-security-architecture.md) - Security decisions detail
- [03-Component Architecture](03-component-architecture.md) - Implementation structure
- [05-API Specification](05-api-specification.md) - API contract
- [07-Deployment Architecture](07-deployment-architecture.md) - Deployment decisions
