FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Paper-trade by default; pass different args to trade on the testnet or live.
CMD ["python", "main.py", "run"]
