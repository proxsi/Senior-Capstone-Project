#!/bin/bash
# Legacy Linux build/restart script; its broad Python kill command requires care.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.

cd /home/devbox/project

echo "构建前端..."
cd frontend && npm run build && cd ..

echo "启动后端服务..."
pkill -9 -f "python" 2>/dev/null || true
sleep 2
nohup python -m api_server.server > server.log 2>&1 &
sleep 3

echo "服务已启动: http://0.0.0.0:8080"
