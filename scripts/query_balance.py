#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Buddy 服务积分查询 → RSS 生成脚本
- 调用 Buddy 聚合额度平台 /client/api/v1/query 接口
- 将余额/已用/今日消耗等数据生成为 RSS 2.0 XML
- 供 Quote/0 墨水屏设备订阅展示

用法:
    BUDDY_KEY=agg_sk_xxx python3 scripts/query_balance.py
环境变量:
    BUDDY_KEY      必填, 查询密钥
    RSS_TITLE      可选, RSS 标题 (默认 "Buddy 积分")
输出:
    rss.xml (仓库根目录)
"""

import os
import sys
import json
import html
import urllib.request
import datetime

API_URL = "https://btc-gz-cn3.chicross.cn/client/api/v1/query"
OUTPUT_FILE = "rss.xml"


def query_balance(api_key: str) -> dict:
    """调用积分查询接口, 返回 data 部分"""
    payload = json.dumps({"buddy_key": api_key}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    if not body.get("success"):
        raise RuntimeError(f"接口返回失败: {body.get('message', '未知错误')}")
    return body.get("data", {})


def fmt_num(v) -> str:
    """数字格式化: 整数加千分位, 小数保留两位"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f):
        return f"{int(f):,}"
    return f"{f:,.2f}"


def build_rss(data: dict, now: datetime.datetime) -> str:
    """生成 RSS 2.0 XML"""
    balance = fmt_num(data.get("credits_balance", 0))
    used = fmt_num(data.get("credits_used", 0))
    recharged = fmt_num(data.get("total_recharged", 0))
    today_req = int(data.get("today_requests", 0))
    today_billed = fmt_num(data.get("today_billed", 0))
    packs = int(data.get("credit_packs_count", 0))
    version = str(data.get("version", "agg")).upper()

    # 计算已用百分比
    total = data.get("credits_balance", 0) + data.get("credits_used", 0)
    pct = (data.get("credits_used", 0) / total * 100) if total > 0 else 0

    title = f"Buddy 积分 | 剩余 {balance}"
    desc_lines = [
        f"剩余积分: {balance}",
        f"累计已用: {used} ({pct:.1f}%)",
        f"累计充值: {recharged}",
        f"今日请求: {today_req} 次",
        f"今日消耗: {today_billed}",
        f"额度包: {packs} 个",
        f"版本: {version}",
        f"更新时间: {now.strftime('%Y-%m-%d %H:%M')}",
    ]
    description = "\n".join(desc_lines)

    pub_date = now.strftime("%a, %d %b %Y %H:%M:%S +0800")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>{html.escape(title)}</title>
<link>https://btc-gz-cn3.chicross.cn/client/</link>
<description>Buddy 服务聚合额度平台积分监控</description>
<language>zh-cn</language>
<lastBuildDate>{pub_date}</lastBuildDate>
<item>
<title>{html.escape(title)}</title>
<description>{html.escape(description)}</description>
<pubDate>{pub_date}</pubDate>
<guid isPermaLink="false">buddy-quota-{now.strftime('%Y%m%d%H%M%S')}</guid>
</item>
</channel>
</rss>
"""
    return rss


def main():
    api_key = os.environ.get("BUDDY_KEY", "").strip()
    if not api_key:
        print("错误: 缺少环境变量 BUDDY_KEY", file=sys.stderr)
        sys.exit(1)

    data = query_balance(api_key)
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    rss = build_rss(data, now)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"✅ 已生成 {OUTPUT_FILE}")
    print(f"   剩余 {fmt_num(data.get('credits_balance', 0))} | "
          f"已用 {fmt_num(data.get('credits_used', 0))} | "
          f"今日请求 {data.get('today_requests', 0)} 次")


if __name__ == "__main__":
    main()
