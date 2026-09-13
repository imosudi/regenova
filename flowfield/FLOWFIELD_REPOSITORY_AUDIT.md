# REGENOVA FlowField — Repository Audit (F0)

## 1. Repository Status & Layout

- **Local Working Directory**: `/home/mosud/flowfield/`
- **Git Status**: Currently uninitialized.
- **Remote Server Directory**: `/home/mosud/flowfield/` prepared for deployment.

---

## 2. Version Control Hygiene & Rules

Per Section 8 & 9 of the **Master Implementation Specification** and `AGENTS.md`:
- Version-control ONLY approved deliberate project artefacts:
  - `package.json`, `package-lock.json`
  - Approved flow definitions (`flows.json`)
  - Approved settings template (`settings.js`)
  - Custom nodes / subflows
  - Database migration scripts (`migrations/`)
  - Systemd service configurations (`systemd/`)
  - Apache reverse proxy templates (`apache/`)
  - Documentation and test suites
- Strictly EXCLUDE from Git:
  - `node_modules/`
  - `.env` files and runtime secrets
  - Runtime databases and SQLite/context caches
  - Credential files (`flows_cred.json`)
  - Agent logs, reasoning, and temporary planning files
  - Scratch dumps and temporary test outputs

---

## 3. Canonical `.gitignore` Template

The following `.gitignore` will be established in `/home/mosud/flowfield/.gitignore`:
```gitignore
# Dependencies
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Runtime secrets & environment
.env
.env.*
!.env.example
*.key
*.pem
*.pfx

# Node-RED runtime credentials and context
flows_cred.json
.config.runtime.json
.config.nodes.json
.sessions.json
context/

# Logs & temp
*.log
logs/
.tmp/
tmp/

# AI Agent & IDE artifacts
.gemini/
.system_generated/
*.tmp
*.bak
```

---

## 4. Repository Verdict
- **Status**: `READY` for Phase F2 (Repository & Configuration Architecture).
