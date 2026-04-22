#!/bin/bash
cd "$(dirname "$0")"

echo "Checking dependencies..."
pip install -r requirements.txt --quiet --break-system-packages 2>/dev/null || pip install -r requirements.txt --quiet

echo "Starting NOC Report System..."
python3 noc_app.py
