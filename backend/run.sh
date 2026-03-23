#!/bin/bash
# Sepsis Sentinel Backend startup script for Unix/Mac

echo "Activating Python virtual environment..."
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

echo ""
echo "Starting Sepsis Sentinel API..."
echo "Server will be available at http://localhost:8000"
echo "Interactive docs at http://localhost:8000/docs"
echo ""

uvicorn main:app --reload --host 0.0.0.0 --port 8000
