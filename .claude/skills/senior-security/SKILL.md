---
name: "senior-security"
description: Use when the user asks for STRIDE threat modeling, DREAD risk scoring, data-flow-diagram threat analysis, or a quick secret scan. Covers Samsung Health 생체 데이터 전송 보안, X-User-Id 헤더 인증 위협 모델링, API secret 스캔. This skill owns threat modeling; secure code review routes to code-reviewer or adversarial-reviewer.
---

# Senior Security Engineer — Threat Modeling + Security Router

This skill does exactly one job itself — **STRIDE/DREAD threat modeling** (plus a quick secret scan) — and routes every other security request to the specialist skill that owns that lane. Do not duplicate sibling content here; route instead.

## Routing Table (read this first)

| The user wants... | Route to | Why that skill owns it |
|---|---|---|
| Hostile/adversarial code review | `../adversarial-reviewer/` | 3-persona review with BLOCK/CONCERNS/CLEAN verdict |
| Secure code review as part of general review | `../code-reviewer/` | Python + Kotlin language dispatch |

If the request spans lanes (e.g., "secure this new architecture"), do the threat model here first — its output (prioritized threats + mitigations) tells you which sibling to load next.

## What This Skill Owns: STRIDE Threat Modeling

### Workflow

1. **Scope:** assets to protect, trust boundaries, data flows (external entities, processes, data stores, flows).
2. **Generate the threat model** per component:
   ```bash
   python3 scripts/threat_modeler.py --component "User Authentication" --assets "credentials,sessions" --json --output threats.json
   ```
   Output: per-threat STRIDE category, DREAD score (Damage, Reproducibility, Exploitability, Affected users, Discoverability — each 1–10), and suggested mitigations. Repeat per DFD element; `--interactive` walks scoping questions; `--list-threats` shows the threat database.
3. **Consume the output:** sort `threats.json` by DREAD score descending; everything ≥ 7 average needs a named mitigation owner before the design ships. Map each mitigation to the responsible sibling lane (e.g., IAM threats → `cloud-security`, injection threats → `code-reviewer`).
4. **Quick secret sweep** while you have the codebase open:
   ```bash
   python3 scripts/secret_scanner.py /path/to/project --format json --severity high
   ```
   20+ patterns (AWS keys, GitHub tokens, private keys, generic credentials). Any critical/high finding blocks merge until rotated and moved to a secret manager.
5. **Verification gate:** every DFD element has ≥ 1 STRIDE row considered, every threat with DREAD ≥ 7 has an owner + mitigation, and the secret scan exits with zero high/critical findings. Re-run both tools after mitigations land — that re-run is the done signal, not the document.

### STRIDE per Element Matrix

| DFD Element | S | T | R | I | D | E |
|-------------|---|---|---|---|---|---|
| External Entity | X | | X | | | |
| Process | X | X | X | X | X | X |
| Data Store | | X | X | X | X | |
| Data Flow | | X | | X | X | |

(S=Spoofing→authn, T=Tampering→integrity, R=Repudiation→audit logs, I=Info Disclosure→encryption/access control, D=DoS→rate limiting/redundancy, E=Elevation→least privilege.)

## References (load on demand)

| Document | Content |
|----------|---------|
| [references/threat-modeling-guide.md](references/threat-modeling-guide.md) | STRIDE methodology, attack trees, DREAD scoring, DFD creation |
| [references/security-architecture-patterns.md](references/security-architecture-patterns.md) | Zero Trust, defense-in-depth, authentication patterns, API security |
| [references/cryptography-implementation.md](references/cryptography-implementation.md) | AES-GCM, Ed25519, password hashing (Argon2id), key management |

The architecture and crypto references are kept because no sibling ships them; for *operating* those controls (scanning, compliance, monitoring) still route to `senior-secops`.
