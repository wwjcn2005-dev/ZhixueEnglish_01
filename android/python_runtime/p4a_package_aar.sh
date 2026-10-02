#!/bin/sh
# 智学英语 Android 本地 Python 服务：AAR 预处理（在 WSL 中执行，沿用《智学小四门》已验证流程）
#
# 作用：把 python_runtime/app（本项目的运行时载荷）交给 p4a 的 service_library dist，
#       生成 dist_aar/{AndroidManifest.xml, src/main/java, src/main/assets/private.tar, libs/arm64-v8a}
# 之后在 Windows 侧运行 assemble_aar.py 组装 AAR（离线、可复现）。
#
# 前置：WSL 中已有 p4a 环境（/home/wwjcn/p4a-venv）与已验证 dist（/home/wwjcn/p4a-store/dists/p1a_service）。
#       dist 直接复用，不重新编译 CPython（本项目服务是纯标准库）。

#: 项目根（WSL 挂载路径）。单一真相源：项目若移动，只改本行。
ROOT=/mnt/j/ZhixueEnglish_01
set -e
export PATH=/home/wwjcn/spike-fake-jdk/bin:$PATH          # 仅供 p4a recipe 存在性检测

WORK="$ROOT/android/python_runtime"
DIST="$ROOT/android/python_runtime/dist_aar"

# 0) 首次执行：从已验证 dist 复制一份工作副本（保留 p4a-store 原件不动）
if [ ! -d "$DIST" ]; then
  cp -a /home/wwjcn/p4a-store/dists/p1a_service "$DIST"
fi

# 1) 预处理：注入本项目载荷 + 指定 Java 包名与服务入口
cd "$DIST"
/home/wwjcn/p4a-venv/bin/python build.py \
  --private "$WORK/app" \
  --package com.zhixueenglish.app.dev.runtime \
  --name ZhixueEnglishRuntime \
  --version 0.1 \
  --service=zhixue:service/main.py \
  --minsdk 24 \
  --release \
  --no-byte-compile-python \
  > "$WORK/build_aar.log" 2>&1

echo "PREP_EXIT=$?"
echo "下一步（Windows）：python J:\\ZhixueEnglish_01\\android\\python_runtime\\assemble_aar.py"
