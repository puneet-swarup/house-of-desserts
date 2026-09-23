# ADR-0005: Local Deployment + Tailscale

## Status

Accepted

## Date

2026-09-21

## Context

The system runs on a home PC. The user needs:
- Access from the same device (desktop browser)
- Access from phone on home Wi-Fi
- Access from phone when away (at market, at a delivery location)
- Zero monthly cost
- No public IP / port forwarding / domain / SSL certificate management

## Decision

We will deploy on the **home PC** (or a Raspberry Pi / old laptop) and use
**Tailscale** (free tier, up to 3 users / 100 devices) for encrypted remote
access. No public exposure. No cloud server.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| Render / Koyeb free tier | Cold starts, data on their servers, vendor lock-in, sleeps after inactivity. |
| VPS (DigitalOcean, etc.) | Monthly cost, security surface, overkill for 1 user. |
| Port forwarding + domain + Let's Encrypt | Security risk, DNS management, ISP may block port 80/443. |
| ngrok / Cloudflare Tunnel | Third-party dependency, free tier limits, less control. |

## Consequences

- (+) ₹0/month. Full data privacy. No cold starts.
- (+) Tailscale is end-to-end encrypted (WireGuard). No open ports on router.
- (+) Works on any OS (Windows, Linux, macOS, Android, iOS).
- (−) Requires Tailscale installed on each device (one-time setup).
- (−) If home PC is off, system is unavailable (mitigation: use a Pi that stays on).   