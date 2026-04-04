#!/bin/bash
# 一键安装脚本

echo "安装依赖..."
pip3 install -r requirements.txt

echo "创建日志目录..."
mkdir -p logs

# 创建 .env 文件（如果不存在）
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "请编辑 .env 文件填入你的 API keys："
    echo "  nano .env"
fi

echo ""
echo "安装完成！"
echo "启动方式："
echo "  测试运行：python3 bot.py"
echo "  PM2 后台：pm2 start ecosystem.config.js"
