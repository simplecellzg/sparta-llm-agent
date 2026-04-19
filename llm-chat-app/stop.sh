#!/bin/bash

PID_FILE="app.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat $PID_FILE)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Stopping application (PID: $PID)..."
        kill $PID
        rm -f $PID_FILE
        echo "Application stopped"
    else
        echo "Process not found, cleaning up PID file"
        rm -f $PID_FILE
    fi
else
    echo "PID file not found, trying to find process..."
    pkill -f "python app.py"
    echo "Done"
fi