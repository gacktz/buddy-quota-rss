#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Buddy 积分 → Quote/0 墨水屏推送脚本
流程: 读取积分数据 → 生成 v8 卡片 → 推送到设备图像 API

用法:
    # 完整流程（查询接口 + 生成 + 推送）
    BUDDY_KEY=... DOT_TOKEN=... DEVICE_SN=... python3 scripts/push_card.py

    # 从 rss.xml 复用数据（GitHub Actions 中与 query_balance.py 配合）
    DOT_TOKEN=... DEVICE_SN=... python3 scripts/push_card.py --rss rss.xml

    # 只生成卡片不推送（本地预览）
    python3 scripts/push_card.py --rss rss.xml --no-push --out /tmp/card.png

环境变量:
    BUDDY_KEY    积分查询密钥（--rss 模式不需要）
    DOT_TOKEN    Dot.App API 密钥（dot_app_ 开头）
    DEVICE_SN    设备序列号（12 位十六进制）
输出:
    推送成功打印服务器返回；失败以非零退出码结束
"""

import argparse
import base64
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

from gen_card_v8 import draw_card, parse_rss, query_balance

PUSH_URL = "https://dot.mindreset.tech/api/authV2/open/device/{sn}/image"


def push_image(png_path: str, token: str, sn: str) -> tuple:
    """推送 PNG 到设备图像 API，返回 (http_status, response_body)"""
    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    url = PUSH_URL.format(sn=sn)
    payload = json.dumps({
        "image": b64,
        "ditherType": "NONE",     # 文本类图片不抖更锐利
        "refreshNow": True,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rss", help="从 rss.xml 解析数据（配合 query_balance.py）")
    parser.add_argument("--no-push", action="store_true", help="只生成卡片不推送")
    parser.add_argument("--out", default="/tmp/buddy_card.png", help="卡片输出路径")
    args = parser.parse_args()

    # 1. 取数据
    if args.rss:
        data = parse_rss(args.rss)
    else:
        key = os.environ.get("BUDDY_KEY", "").strip()
        if not key:
            print("错误: 需要 --rss 或环境变量 BUDDY_KEY", file=sys.stderr)
            sys.exit(1)
        data = query_balance(key)

    # 2. 生成卡片
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    draw_card(data, now, args.out)

    # 3. 推送
    if args.no_push:
        print("跳过推送 (--no-push)")
        return

    token = os.environ.get("DOT_TOKEN", "").strip()
    sn = os.environ.get("DEVICE_SN", "").strip()
    if not token or not sn:
        print("错误: 需要环境变量 DOT_TOKEN 和 DEVICE_SN", file=sys.stderr)
        sys.exit(1)

    status, body = push_image(args.out, token, sn)
    if status == 200:
        print(f"✅ 已推送 {args.out} 到设备 {sn} (HTTP {status})")
        print(f"   服务器: {body[:200]}")
    else:
        print(f"❌ 推送失败 HTTP {status}: {body[:300]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
