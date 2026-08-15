---
name: "engineering-skills"
description: "Index of available engineering skills for this project. Architecture, backend, DevOps, security, TDD (stdlib-only Python tools). Use when browsing or choosing among engineering role skills — load only the one specialist SKILL.md you need, never bulk-load the bundle."
version: 2.9.0
author: Alireza Rezvani
license: MIT
tags:
  - engineering
  - backend
  - devops
  - security
agents:
  - claude-code
---

# Engineering Team Skills

Production-ready engineering skills for the AAC project (FastAPI backend + Android Kotlin app).

## Quick Start

### Claude Code
```
/read .claude/skills/senior-backend/SKILL.md
```

## Skills Overview

| Skill | Folder | Focus |
|-------|--------|-------|
| Senior Architect | `senior-architect/` | System design, architecture patterns, ADR |
| Senior Backend | `senior-backend/` | FastAPI, SQLAlchemy 2.0, PostgreSQL |
| Senior DevOps | `senior-devops/` | GitHub Actions, Render, Docker |
| Senior Security | `senior-security/` | Threat modeling, STRIDE, secret scan |
| Code Reviewer | `code-reviewer/` | PR review — Python + Kotlin |
| Adversarial Reviewer | `adversarial-reviewer/` | Hostile-persona code review |
| TDD Guide | `tdd-guide/` | pytest-asyncio, SQLite in-memory |
| Tech Stack Evaluator | `tech-stack-evaluator/` | Technology comparison, TCO analysis |

## Python Tools

30+ scripts, all stdlib-only. Run directly:

```bash
python3 <skill>/scripts/<tool>.py --help
```

No pip install needed. Scripts include embedded samples for demo mode.

## Rules

- Load only the specific skill SKILL.md you need — don't bulk-load all 32
- Use Python tools for analysis and scaffolding, not manual judgment
- Check CLAUDE.md for tool usage examples and workflows
