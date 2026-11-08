#!/bin/bash
# 注册 /etc/cron.d 定时任务（每天 08:00 执行）
cat > /etc/cron.d/daily-news <<'EOS'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 8 * * * root /opt/daily-news/run.sh
EOS
chmod 644 /etc/cron.d/daily-news
echo "--- /etc/cron.d/daily-news ---"
cat /etc/cron.d/daily-news
echo "--- cron service ---"
systemctl is-active crond 2>/dev/null || service crond status 2>/dev/null | head -2
echo "--- test run.sh (dry) ---"
cd /opt/daily-news && bash -n run.sh && echo "run.sh syntax OK"
