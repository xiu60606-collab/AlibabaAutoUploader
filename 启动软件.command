#!/bin/zsh
# 从 Finder 或正常桌面终端启动；不修改系统 Python。
set -eu
PROJECT_ROOT="${0:A:h}"
cd "$PROJECT_ROOT"
if [[ ! -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    print -u2 "未找到项目虚拟环境，请先配置 Python 3.13.12 的 .venv。"
    exit 1
fi
"$PROJECT_ROOT/.venv/bin/python" -c 'import sys; assert sys.version_info[:3] == (3, 13, 12), "需要 Python 3.13.12"'
# 桌面启动不继承测试会话的离屏设置。
unset QT_QPA_PLATFORM
exec "$PROJECT_ROOT/.venv/bin/python" -B "$PROJECT_ROOT/main.py"
