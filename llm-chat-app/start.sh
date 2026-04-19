#!/bin/bash

APP_NAME="app.py"
PORT=21000
LOG_FILE="app.log"
PID_FILE="app.pid"

# 检查是否已经在运行
if [ -f "$PID_FILE" ]; then
    PID=$(cat $PID_FILE)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Application is already running (PID: $PID)"
        exit 1
    fi
fi

echo "Starting LLM Chat Application on port $PORT..."
nohup python $APP_NAME > $LOG_FILE 2>&1 &

# 保存 PID
echo $! > $PID_FILE
echo "Application started (PID: $!)"
echo "Log file: $LOG_FILE"