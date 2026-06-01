#!/bin/bash
# 启动脚本 - 支持指定端口

# 默认端口
DEFAULT_PORT=8050

# 获取端口参数或使用默认
PORT=${1:-$DEFAULT_PORT}

echo "=========================================="
echo "  Layout Review Tool"
echo "=========================================="
echo "  Port: $PORT"
echo "  URL:  http://localhost:$PORT"
echo "=========================================="

# 运行应用
python3 layout_review_app.py $PORT
