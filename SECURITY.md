# Security policy

AquaSentry reports whether drinking water is safe, so a wrong or forged reading is a safety problem,
not just a software bug.

## Reporting a vulnerability
Please **do not open a public issue**. Use GitHub's *Report a vulnerability* button (Security tab →
Advisories) to send a private report. Include what an attacker could do, the steps to reproduce and the
version (`/api/health` → `app_version`, firmware `FIRMWARE_VERSION`). You will get a reply within 7 days.

Especially in scope:
- writing, editing or deleting readings without the API key or a device key
- making the dashboard show "Safe" / "No arsenic detected" for water that tested unsafe
- getting the ESP32 node to run code or leak its Wi-Fi password or device key
- reading the server's database, backups or `.env`

## Supported versions
Only the latest release on `main` gets fixes.

## Deployment checklist
- Set `AQUASENTRY_API_KEY` (and per-device keys from `/api/admin/devices/{code}/key`) before exposing
  the server beyond one computer; without it, anyone on the network can add readings.
- Serve over HTTPS (a reverse proxy such as Caddy) when the server is reachable from the internet, and
  give the nodes the CA certificate (`ROOT_CA_PEM` in the firmware).
- Set `ALERT_WEBHOOK_SECRET` so alert receivers can verify signatures.
- Set `METRICS_PUBLIC=0` if device names and reading counts should not be public.
- OTA updates stay off on the nodes unless `OTA_PASS` is set (8+ characters).
