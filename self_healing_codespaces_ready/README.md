# Self-Healing IT Incident Platform — GitHub Codespaces Edition

## Setup entirely in the browser
1. Upload **the contents of this folder** (including `.devcontainer/`) into the root of a GitHub repository. GitHub's web upload can omit hidden directories: verify `.devcontainer/devcontainer.json` exists after upload; use **Add file > Create new file** with that full path if necessary.
2. On the repository click **Code > Codespaces > Create codespace on main**. If you already have a Codespace, run **Codespaces: Rebuild Container** from Command Palette after adding `.devcontainer`.
3. In the Codespaces terminal, check `docker compose version` and `docker info`. Python is not required on the host.
4. Run `docker compose up -d --build`. Initial Maven download/build can take several minutes.
5. Run `docker compose ps`. Verify service health with `curl http://localhost:8081/actuator/health`, likewise 8082 and 8083. Wait for UP.
6. Test order: `curl -sS -X POST http://localhost:8081/order -H 'Content-Type: application/json' -d '{"item":"laptop","qty":1}'`.
7. Inject fault: `curl -sS -X POST http://localhost:8082/fault/on`.
8. Watch: `docker compose logs -f orchestrator` in a second terminal; or `curl http://localhost:8090/incidents` after ~20–60 seconds. Inventory should recover and incident status become RESOLVED.
9. Open **Ports** in Codespaces and use the forwarded URL for port 9090 (Prometheus alerts), 3000 (Grafana admin/demo123), 8090 (incidents). Keep port visibility **Private**; do not make it Public.
10. Stop: `docker compose down`.

## Architecture and limitations
- Docker services: orders, inventory, payments, Prometheus, Alertmanager, Grafana, Python orchestrator.
- Alertmanager webhook uses internal URL `http://orchestrator:8090/alert`.
- Orchestrator restarts only allowlisted `selfheal-` service containers via the mounted Docker socket. **Docker socket access grants broad host-container privileges; use only in an isolated, disposable development Codespace. Never expose the orchestrator publicly.**
- Real metrics/alerts/restarts. Incidents are **in-memory simulated tickets**, not actual ServiceNow incidents unless configured with a real ServiceNow instance and credentials. Optional AI classifier uses fallback rules unless scikit-learn is added to the orchestrator image; it is not production-grade anomaly detection.
- To connect real ServiceNow, pass `SERVICENOW_URL`, `SERVICENOW_USER`, `SERVICENOW_PASSWORD` as environment variables via Codespaces secrets or appropriate secure configuration; do not commit credentials. Flow Designer auto-closure requires separate ServiceNow configuration.
- Container restart does not repair all failure types. A killed container may restart due to Docker's restart policy, so use `/fault/on` for a predictable demonstration.
- Port forwarding and cloud resource limits depend on Codespaces account settings and quota.

## Troubleshooting
- `docker: command not found`: verify Codespace built with the included `.devcontainer/devcontainer.json` and rebuild it.
- `python3: command not found`: **not a blocker**; Python runs inside the orchestrator container.
- Build errors: `docker compose logs orders` and `docker compose build --no-cache orders`.
- No incident: `docker compose logs prometheus alertmanager orchestrator`; inspect Prometheus targets and alerts via Ports.
- Unhealthy service: `docker compose logs inventory`.
- Port conflict: stop conflicting process, or adjust port mapping.
