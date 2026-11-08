#!/bin/bash
# 服务器端一键部署脚本：生成 run.sh 并注册 cron（每天 8:00）
set -e

APP_DIR=/opt/daily-news
cd "$APP_DIR"

cat > run.sh <<'EOS'
#!/bin/bash
cd /opt/daily-news
/usr/bin/python3 news_bot.py >> logs/cron.log 2>&1
EOS
chmod +x run.sh

( crontab -l 2>/dev/null | grep -v 'daily-news' ; echo '0 8 * * * /opt/daily-news/run.sh' ) | crontab -

echo "--- crontab ---"
crontab -l
echo "--- cron service ---"
if systemctl list-units --type=service 2>/dev/null | grep -q crond; then
  systemctl is-active crond
  systemctl is-enabled crond
else
  service crond status 2>/dev/null | head -3 || ps aux | grep -c "[c]rond"
fi
echo "--- timezone ---"
date
echo "--- files ---"
ls -la "$APP_DIR"
