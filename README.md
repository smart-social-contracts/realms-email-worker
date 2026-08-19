# Realms Email Worker

A standalone off-chain service that sends outbound email for [Realms GOS](https://realmsgos.org) realms.

## Why off-chain?

Internet Computer canisters cannot open SMTP connections directly. This worker runs on the same server as the realm and handles the actual email delivery. The realm canister only stores **non-sensitive** email settings (sender identity, reply-to, event routing, and optional template overrides); credentials and API keys stay in this worker's environment.

## Recommended provider: Resend

For deliverability, we recommend **[Resend](https://resend.com)**:

- Provides DKIM/SPF/DMARC setup guidance.
- Sends from a verified subdomain (e.g. `notify.realmsgos.org`).
- Reports bounces, complaints, and deliveries via webhooks.
- Free tier covers low-volume realms.

SMTP is still supported as a fallback for other providers.

## Features

- **Immediate send**: `POST /send-email` for test emails and canister push via HTTP outcall.
- **Pull worker**: background loop polls the realm canister for notifications marked `email_status: pending` and sends them.
- **HTML templates**: file-based Jinja2 templates in `app/templates/` with per-realm override support.
- **Bounce handling**: `POST /webhooks/resend` receives Resend bounce/complaint events and suppresses bad addresses.
- **Rate limiting**: caps emails per poll and adds a small delay between sends to protect sender reputation.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with your Resend API key and realm canister ID

uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## DNS setup (do not skip)

Before sending real email:

1. Pick a subdomain: `notify.realmsgos.org` or `mail.realmsgos.org`.
2. Add the domain in Resend and publish the DNS records it provides:
   - SPF (TXT)
   - DKIM (CNAME/TXT)
   - DMARC (TXT), start with `v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.org`
3. Wait for Resend verification.
4. Set `ALERT_EMAIL_FROM` to an address on that subdomain.

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `EMAIL_PROVIDER` | `resend` or `smtp` | `resend` |
| `RESEND_API_KEY` | Resend API key | - |
| `RESEND_API_URL` | Resend API endpoint | `https://api.resend.com/emails` |
| `SMTP_HOST` | SMTP server hostname | `mail.privateemail.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USER` | SMTP username | - |
| `SMTP_PASSWORD` | SMTP password | - |
| `ALERT_EMAIL_FROM` | Default From address | `noreply@notify.realmsgos.dev` |
| `REALM_CANISTER_ID` | Realm canister to poll | - |
| `REALM_PUBLIC_URL` | Public realm URL for email links (e.g. `https://gos.earth/r/myrealm`) | - |
| `DFX_NETWORK` | dfx network for canister calls | `local` |
| `DFX_IDENTITY` | Optional dfx identity flag | - |
| `EMAIL_POLL_INTERVAL_SECONDS` | Poll interval | `60` |
| `MAX_EMAILS_PER_POLL` | Max emails per poll | `50` |
| `EMAIL_SEND_DELAY_SECONDS` | Delay between sends | `0.5` |
| `EMAIL_WORKER_DFX_CALL_TEMPLATE` | Override dfx command template | `dfx {identity} canister --network {network} call {canister}` |
| `EMAIL_SUPPRESS_LIST_PATH` | Hard-bounce suppression list | `./suppress_list.txt` |

## API

### `POST /send-email`

```json
{
  "to": "user@example.com",
  "subject": "Realms notification",
  "text": "You have a new notification.",
  "html": "<p>You have a new notification.</p>",
  "from_name": "Realms GOS",
  "from_address": "noreply@notify.realmsgos.dev",
  "reply_to": "support@realmsgos.dev"
}
```

### `POST /webhooks/resend`

Resend webhook endpoint for bounce/complaint/delivery events. Configure in Resend dashboard.

### `GET /health`

Health check.

## Templates

Default HTML templates live in `app/templates/`:

- `default.html` — fallback for any event type
- `email_verification.html` — email address verification codes
- `proposal_created.html` — new proposal notifications
- `vote_reminder.html` — voting reminders

Canister reads use `dfx ... call --query extension_call`; writes use `extension_sync_call`.

Templates are Jinja2 and receive these variables:

- `title`
- `message`
- `href`
- `logo_url`
- `realm_name`
- `from_address`

Realm admins can also provide custom HTML via the Realm Settings UI, which is stored in the realm's `manifest_data.email.templates`.

## How it fits into Realms

1. Realm admins configure the email sender identity and event routing in **Realm Settings → Notifications**.
2. Users add their email address and opt in/out in **Settings → Email notifications**.
3. When the realm creates a notification, the `notifications` extension marks it `email_status: pending` if the user and realm settings allow it.
4. This worker polls the canister, renders the appropriate template, sends the email via Resend, and marks the notification `sent` (or `failed`).

## Warm-up and reputation

- Use a subdomain for sending.
- Start with low volume and ramp up gradually.
- Keep the `MAX_EMAILS_PER_POLL` and `EMAIL_SEND_DELAY_SECONDS` conservative until you have sending history.
- Monitor Resend dashboard and the worker logs for bounces and complaints.

## License

MIT
