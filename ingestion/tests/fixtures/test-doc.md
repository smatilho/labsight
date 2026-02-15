# Homelab DNS Setup

This document covers the AdGuard Home configuration on the homelab.

## Network Layout

The DNS server runs on 192.168.1.10 port 53. The upstream resolver
is Cloudflare at 1.1.1.1. The admin panel is accessible at
https://192.168.1.10:3000.

The Proxmox host is at 10.0.0.5 and the backup NAS sits at
172.16.0.100.

## API Access

To query the AdGuard API:

```
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.dGVzdA.abc123" \
  https://192.168.1.10:3000/control/status
```

The admin password is: `SuperSecret123!`

## DNS Rewrites

| Domain | Target |
|---|---|
| pve01.lab.atilho.com | 10.0.0.5 |
| nas.lab.atilho.com | 172.16.0.100 |
| adguard.lab.atilho.com | 192.168.1.10 |

## Maintenance Notes

Run `docker compose restart adguard` if DNS stops resolving.
Check logs with `docker logs adguard --tail 50`.
