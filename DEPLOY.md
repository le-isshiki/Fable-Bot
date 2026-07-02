# Running Fable-Bot 24/7 on a server

A laptop that sleeps, loses power, or leaves the house is the wrong home for a
trading bot. This guide puts the bot on an always-on Linux server. Thanks to
`state.json` persistence, crashes, reboots, and updates are all safe — the bot
picks up exactly where it left off.

## Choosing a host

| Option | Cost | Notes |
|---|---|---|
| **Oracle Cloud "Always Free"** | $0 forever | Real 24/7 VM (ARM, up to 4 cores/24 GB). Card required for signup verification; free capacity varies by region. |
| **Small VPS** (Hetzner, DigitalOcean, ...) | ~$4–6/mo | The boring, reliable option. |
| **Koyeb / similar PaaS** | ~$2+/mo (Worker) | Use the `Dockerfile`. Free tiers won't work: they only run web services and sleep them when idle — fatal for a bot. |

**Pick a region where Binance's API is available** (e.g. Frankfurt, not any US
region — US IPs get HTTP 451 from binance.com). This must match where *you* are
allowed to use Binance: a server region is not a way around account
restrictions, and accounts detected doing that get frozen.

## Setup on a fresh Ubuntu server

```bash
sudo apt update && sudo apt install -y python3-venv git
git clone https://github.com/le-isshiki/Fable-Bot && cd Fable-Bot
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# sanity check: fetch real data and run a backtest
.venv/bin/python main.py backtest --limit 1000
```

## Run it as a service (survives reboots, restarts on crash)

```bash
sudo cp deploy/fable-bot.service /etc/systemd/system/
# edit User= and paths in the unit file if your username isn't "ubuntu"
sudo systemctl daemon-reload
sudo systemctl enable --now fable-bot
```

Watch it:

```bash
journalctl -u fable-bot -f          # live logs
systemctl status fable-bot          # is it running?
cat state.json                      # current position / daily risk state
```

Update it:

```bash
cd ~/Fable-Bot && git pull && sudo systemctl restart fable-bot
```

## Koyeb free tier (web service + keepalive)

Koyeb's free tier only runs **web services** and puts them to sleep without
traffic. The bot handles this: when the `PORT` env var is set (Koyeb sets it
automatically), it serves a JSON status page — position, balances, uptime —
so it passes health checks, can be pinged awake, and doubles as a phone-friendly
dashboard.

1. Koyeb dashboard → **Create Web Service** → GitHub → select this repo and branch.
2. Builder: **Dockerfile**. Region: **Frankfurt** (US regions are geo-blocked by
   Binance). Instance: **Free**.
3. To use the once-or-twice-a-day profile, override the run command to:
   `python main.py --config config.daily.yaml run`
4. Deploy, then open the public URL — you should see the bot's status JSON.
5. **Keepalive**: create a free monitor at [uptimerobot.com](https://uptimerobot.com)
   (or cron-job.org) pinging your Koyeb URL every 5 minutes, so the free
   instance never goes to sleep.

Caveats of the free tier, stated honestly: no persistent disk (`state.json` is
lost on redeploys — harmless for paper trading, not acceptable for live), and
the keepalive ping is a workaround, not a guarantee. Fine for the paper phase;
move to a VM (above) before trading real funds.

## Docker alternative (Koyeb paid, Fly, any container host)

```bash
touch state.json           # once, so the volume mount is a file not a dir
docker compose up -d --build
docker compose logs -f
```

On a PaaS, deploy the repo with the included `Dockerfile` as a **worker**
process (not a web service) and add a persistent volume for `/app/state.json`.

## Going live later

Paper trading (`main.py run`, the service file's default) needs **no API keys**.
When — and only when — the paper phase has earned your trust:

1. Create API keys in your exchange account. Restrict them: **enable spot trading
   only, disable withdrawals**, and IP-whitelist your server's address.
2. Put them in `.env` on the server (`cp .env.example .env`, then edit;
   `chmod 600 .env`).
3. Test the plumbing against the testnet first (`--live` with
   `exchange.testnet: true`), then flip to real funds per the README.

Never commit `.env`, and never give a trading bot's key withdrawal permission —
if the key leaks, the worst case should be bad trades, not an emptied account.
