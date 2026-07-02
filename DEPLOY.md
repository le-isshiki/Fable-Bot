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

## Docker alternative (Koyeb, Fly, any container host)

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
