# Security Policy for LoRa IoT Simulator

## Supported Versions

Security patches are applied to the following release lines:

| Version | Supported | Notes |
|---------|-----------|-------|
| `main` branch | ✅ | Live development branch — latest features and fixes. |
| `v1.2.x` | ✅ | Release family tagged from the hardening / packaging sprints. |
| `v1.1.x` | 🟡 | Security-only fixes on a best-effort basis. |
| `< v1.0.x` | ❌ | No longer supported — please upgrade. |

If you are running a version older than `v1.1.0`, **upgrade first** and then
reproduce the issue. Older branches receive no security backports.

---

## Reporting a Vulnerability

**DO NOT open a public GitHub issue for security bugs.** Publicly disclosing a
vulnerability before a patch is ready puts every downstream user of the simulator
at risk.

### Preferred (private, encrypted): GitHub Security Advisories

Use the private vulnerability reporting flow in this repository:

1. Navigate to
   [Security → Advisories → New draft security advisory](https://github.com/Dlyar-buxi/LoRa-IoT-Simulator/security/advisories/new)
   (the `Private vulnerability reporting` feature must be enabled — it is for this
   repo).
2. Fill in the template with:
   - Affected versions (exact commit or tag if possible).
   - A minimal reproduction script / curl sequence / Docker command.
   - Expected vs actual behaviour.
   - Estimated severity (Low / Medium / High / Critical) and why.
3. Submit. The maintainer will be notified by email and in-app.

### Fallback (unencrypted)

If the private-advisory flow is unavailable for any reason, email:

```
security@lora-sim.dev  (placeholder — monitored by repo maintainer)
```

Include **"[VULN] LoRa-IoT-Simulator:"** followed by a short title in the
subject line, and attach the reproduction details from above.

### Response SLA

| Stage | Target |
|-------|--------|
| Acknowledge receipt | **5 business days** |
| Initial severity assessment + confirmation | **10 business days** |
| Patch draft available for review | **30 calendar days** |
| Public disclosure (tag + advisory published) | **30 – 90 calendar days** depending on severity |

If we cannot meet the timeline (e.g., it's a cross-dependency issue that
requires coordination with an upstream vendor), we will keep you in the loop
and propose a mutually-agreed disclosure date.

---

## Security Update Process

For every confirmed vulnerability:

1. **Triage.** Maintainer reproduces the bug and confirms the attack surface
   (local only / docker-only / HTTP reachable / WebSocket reachable / MQTT).
2. **CVE request.** For remotely reachable or data-loss vulnerabilities, we
   request a CVE ID via GitHub Advisories during the embargo window.
3. **Patch on a private branch.** Fixes live on `security/<issue>` branches so
   public `main` does not reveal the flaw before release.
4. **Release** a new tag (e.g. `v1.2.1`). The tag message + GitHub Release note
   reference the advisory ID and include **workarounds** for users who cannot
   immediately upgrade.
5. **Publish the advisory** with CVSS score, affected versions, fixed version,
   and reproduction steps redacted to just what downstream users need to assess
   exposure.
6. **Backport** to `v1.2.x` (and best-effort to `v1.1.x`) for critical issues.

---

## Known Security Properties & Attack Surface

For reference — this is how the codebase **intentionally** behaves; anything
outside these bounds should be reported:

| Surface | Behaviour |
|---------|-----------|
| REST API (`/api/*`) | **Optional** `X-API-Key` header guard via `API_KEY` env var. When disabled (default), anyone on the network can control the simulation engine. Recommended when exposing the service beyond localhost. |
| WebSocket `/ws` | **Optional** `?token=` query guard (same env var). Broadcasts only simulation telemetry; never sinks commands back into the engine. |
| SQLite recorder | Standard-library `sqlite3`, no SQL-string concatenation for event insert (uses parameterised `executemany`). |
| MQTT export | Publish-only. Never subscribes. Broker URL comes from an env var. |
| Static frontend | Vanilla JS. No `innerHTML` of user-controlled strings. DOM writes go through `textContent` / SVG attribute binding. |
| Docker image | Multi-stage build; runtime runs as the unprivileged `simulator` user; DB volume mounted at `/app/data`. |
