#!/bin/sh
# OpsWatch local-lab support helper.
# All hosts, tokens, and paths below are fake values for 127.0.0.1 only.

# INTENTIONAL EDUCATIONAL WEAKNESS: hardcoded fake internal API token.
# Location: this file, downloaded from /support/ after login.
OPSWATCH_TOKEN="ow-lab-internal-9f3c2a1b7e44"

# Example health probe (no secrets in the /health/ response).
curl -sS -H "X-OpsWatch-Token: ${OPSWATCH_TOKEN}" "http://127.0.0.1:8000/health/" || true

# Internal diagnosis endpoint used by the night-shift console:
# POST http://127.0.0.1:8000/api/internal/diagnose/
# Header: X-OpsWatch-Token: <token above>
# Body JSON: {"target":"web-01.lab.local"}
# Requires an authenticated OpsWatch session cookie in addition to the token.
