#!/bin/bash
set -e

echo "=== Project Kiwi — Setup ==="
echo ""

# Ensure we're in the project root
if [ ! -f "pyproject.toml" ]; then
  echo "Error: run this script from the project root (kiwi/)"
  exit 1
fi

echo "[1/5] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "[2/5] Installing Python dependencies..."
pip install -q -r requirements.txt

echo "[3/5] Installing Playwright browser (Chromium)..."
playwright install chromium

echo "[4/5] Configuring environment..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  → .env created from .env.example"
  echo "  → Fill in your API keys before starting the app"
else
  echo "  → .env already exists, skipping"
fi

mkdir -p logs

echo "[5/5] Installing frontend dependencies..."
cd frontend && npm install --silent && cd ..

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. Create Telegram bot — follow docs/TELEGRAM_SETUP.md"
echo "  3. Start backend:  source .venv/bin/activate && uvicorn backend.main:app --reload"
echo "  4. Start frontend: cd frontend && npm run dev"
echo "  5. Open dashboard: http://localhost:5173"
echo "  6. Test Telegram:  click 'Send Test Notification' in the dashboard"
