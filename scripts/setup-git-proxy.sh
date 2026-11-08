#!/usr/bin/env bash
# 在本机任意 Git 仓库根目录执行本脚本，写入「仓库级」GitHub 直连配置。
# 用法：cd <仓库根目录> && bash setup-git-proxy.sh
# 只改当前仓库，不动全局配置。

set -e

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "错误：当前目录不是 Git 仓库"; exit 1;
}

git config user.name "kgchaos1"
git config user.email "kgchaos1@users.noreply.github.com"
git config http.proxy "http://127.0.0.1:7897"
git config https.proxy "http://127.0.0.1:7897"
git config http.sslBackend schannel

echo "已写入仓库级配置："
git config --local --list | grep -E "^(user\.|http\.)"
echo
echo "提示：代理端口若变化（默认 7897），改这里的两条 proxy 后重跑即可。"
