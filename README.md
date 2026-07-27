# Realms Email Worker

A standalone off-chain service that sends outbound email for [Realms GOS](https://realmsgos.org) realms.

## Why off-chain?

Internet Computer canisters cannot open SMTP connections directly. This worker runs on the same server as the realm and handles the actual email delivery. The realm canister only stores **non-sensitive** email settings (sender identity, reply-to, and event routing); SMTP credentials stay in this worker's environment.

## Features

- **Immediate send**: `POST /send-email` for test emails and canister push via HTTP outcall.
- **Pull worker**: background loop that polls the realm canister for notifications marked `email_status: pending` and sends them.
- **Pluggable SMTP**: defaults to Namecheap Private Email (`mail.privateemail.com`) but works with any SMTP provider.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with your SMTP credentials and realm canister ID

uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `SMTP_HOST` | SMTP server hostname | `mail.privateemail.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USER` | SMTP username | - |
| `SMTP_PASSWORD` | SMTP password | - |
| `ALERT_EMAIL_FROM` | Default From address | `SMTP_USER` or `noreply@realmsgos.dev` |
| `REALM_CANISTER_ID` | Realm canister to poll | - |
| `DFX_NETWORK` | dfx network for canister calls | `local` |
| `DFX_IDENTITY` | Optional dfx identity flag | - |
| `EMAIL_POLL_INTERVAL_SECONDS` | Poll interval | `60` |
| `EMAIL_WORKER_DFX_CALL_TEMPLATE` | Override dfx command template | `dfx {identity} canister --network {network} call {canister}` |

## API

### `POST /send-email`

```json
{
  "to": "user@example.com",
  "subject": "Realms notification",
  "body": "You have a new notification.",
  "from_name": "Realms GOS",
  "from_address": "noreply@realmsgos.dev",
  "reply_to": "support@realmsgos.dev"
}
```

### `GET /health`

Health check.

## How it fits into Realms

1. Realm admins configure the email sender identity and event routing in **Realm Settings → Notifications**.
2. Users add their email address and opt in/out in **Settings → Email notifications**.
3. When the realm creates a notification, the `notifications` extension marks it `email_status: pending` if the user and realm settings allow it.
4. This worker polls the canister, sends the emails, and marks them `sent` (or `failed`).

## License

MIT
