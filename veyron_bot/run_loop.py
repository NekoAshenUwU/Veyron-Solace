"""主循环 - 每5分钟检查一次是否发推"""
import time
import schedule
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from bot import run

CHECK_INTERVAL = 5  # 分钟

print(f"Veyron Solace 已启动，每 {CHECK_INTERVAL} 分钟检查一次...")

schedule.every(CHECK_INTERVAL).minutes.do(run)

# 启动时立即运行一次
run()

while True:
    schedule.run_pending()
    time.sleep(30)
