// PM2 配置文件 - 用 `pm2 start ecosystem.config.js` 启动
module.exports = {
  apps: [{
    name: "veyron-solace",
    script: "run_loop.py",
    interpreter: "python3",
    cwd: "/root/veyron_bot",  // 修改为实际路径
    restart_delay: 5000,
    autorestart: true,
    watch: false,
    env: {
      PYTHONUNBUFFERED: "1"
    },
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "./logs/error.log",
    out_file: "./logs/out.log",
  }]
}
