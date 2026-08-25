#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Buddy 积分 → 墨水屏卡片生成脚本 v4（今日指标下沉左栏版）
- 296×152 纯黑白 PNG（Quote/0 图像 API 全屏规格）
- 布局：标题行 + 左右分栏
  左栏（余额区）：剩余积分超大数字 + 已用进度条 + 已用百分比
                  下方两个指标格：今日消耗 / 今日请求
  右栏（详情区）：2×2 指标网格（余额包/累计已用/累计充值/更新时间）

用法:
    python3 scripts/gen_card_v4.py                # 从 BUDDY_KEY 查询并生成
    python3 scripts/gen_card_v4.py --data <json>  # 直接传入积分数据 JSON
    python3 scripts/gen_card_v4.py --rss <xml>    # 从 rss.xml 解析数据（离线预览调试）
环境变量:
    BUDDY_KEY    查询密钥（--data/--rss 模式不需要）
输出:
    card_v4.png (仓库根目录)
"""

import argparse
import json
import os
import sys
import datetime
import urllib.request
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

API_URL = "https://btc-gz-cn3.chicross.cn/client/api/v1/query"
W, H = 296, 152  # Quote/0 屏幕分辨率
MARGIN = 12
BLACK = 0
WHITE = 255

# 分栏几何
SPLIT_X = 144          # 左右分栏竖线 x 坐标
LEFT_X0, LEFT_X1 = MARGIN, SPLIT_X - 3
RIGHT_X0, RIGHT_X1 = SPLIT_X + 3, W - MARGIN


def find_font(sizes: list) -> list:
    """探测系统中文字体，返回与 sizes 一一对应的 [font, ...]"""
    candidates = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        # Linux (GitHub Actions: fonts-noto-cjk)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
    ]
    fonts = []
    for size in sizes:
        f = None
        for path in candidates:
            if os.path.exists(path):
                try:
                    f = ImageFont.truetype(path, size)
                    break
                except Exception:
                    continue
        if f is None:
            print(f"⚠️  警告: 未找到中文字体(size={size})，将使用默认字体(中文会显示为方框)",
                  file=sys.stderr)
            f = ImageFont.load_default()
        fonts.append(f)
    return fonts


def fit_font(d, base_font, text, max_w, min_size=16):
    """从 base_font 起逐级缩小字号，直到文本宽度不超过 max_w"""
    f = base_font
    while True:
        bbox = d.textbbox((0, 0), text, font=f)
        if (bbox[2] - bbox[0]) <= max_w or f.size <= min_size:
            return f
        try:
            f = ImageFont.truetype(f.path, f.size - 2)
        except Exception:
            return f


def query_balance(api_key: str) -> dict:
    payload = json.dumps({"buddy_key": api_key}).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("success"):
        raise RuntimeError(f"接口返回失败: {body.get('message', '未知错误')}")
    return body.get("data", {})


def parse_num(s: str) -> float:
    try:
        # 兼容 "224 次" / "0 个" 等带单位后缀的字符串
        return float(str(s).replace(",", "").replace("次", "").replace("个", "").strip())
    except (TypeError, ValueError):
        return 0.0


def parse_rss(path: str) -> dict:
    """从 rss.xml 解析出与接口 data 同构的字典（离线调试用）"""
    tree = ET.parse(path)
    desc = tree.find(".//item/description")
    if desc is None or not desc.text:
        raise RuntimeError(f"{path} 中未找到 item/description")
    kv = {}
    for line in desc.text.strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    used_str = kv.get("累计已用", "0").split(" ")[0]
    return {
        "credits_balance": parse_num(kv.get("剩余积分", 0)),
        "credits_used": parse_num(used_str),
        "total_recharged": parse_num(kv.get("累计充值", 0)),
        "today_requests": int(parse_num(kv.get("今日请求", 0))),
        "today_billed": parse_num(kv.get("今日消耗", 0)),
        "credit_packs_count": int(parse_num(kv.get("额度包", 0))),
    }


def fmt_num(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f):
        return f"{int(f):,}"
    return f"{f:,.2f}"


def draw_card(data: dict, now: datetime.datetime, out_path: str = "card_v4.png"):
    img = Image.new("L", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    balance = float(data.get("credits_balance", 0))
    used = float(data.get("credits_used", 0))
    recharged = float(data.get("total_recharged", 0))
    today_req = int(data.get("today_requests", 0))
    today_billed = float(data.get("today_billed", 0))
    packs = int(data.get("credit_packs_count", 0))
    version = str(data.get("version", "AGG")).upper()

    total = balance + used
    pct_used = (used / total * 100) if total > 0 else 0

    # 字体: [标题(14), 左栏大数字(36), 左栏标签(9), 左栏格子数值(18), 右栏标签(9), 右栏数值(14)]
    f_title, f_bal, f_lbl, f_left_val, f_rc_lbl, f_rc_val = find_font(
        [14, 36, 9, 18, 9, 14])

    # ---- 标题行 ----
    d.text((MARGIN, 4), "BUDDY 积分", font=f_title, fill=BLACK)
    d.text((W - MARGIN, 7), version, font=f_lbl, fill=BLACK, anchor="ra")
    d.line([(MARGIN, 21), (W - MARGIN, 21)], fill=BLACK, width=1)

    # ================= 左栏：余额区 + 今日指标 =================
    lx = LEFT_X0
    lw = LEFT_X1 - LEFT_X0  # 129

    # 标签
    d.text((lx, 25), "剩余积分", font=f_lbl, fill=BLACK)

    # 超大数字（自动适配宽度）
    num_str = fmt_num(balance)
    f_num = fit_font(d, f_bal, num_str, lw, min_size=20)
    bbox = d.textbbox((0, 0), num_str, font=f_num)
    nw, nh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # 垂直居中于 34..80 区域
    d.text((lx + (lw - nw) / 2, 34 + (46 - nh) / 2), num_str,
           font=f_num, fill=BLACK)

    # 进度条
    bar_y, bar_h = 80, 6
    d.rectangle([lx, bar_y, LEFT_X1, bar_y + bar_h],
                outline=BLACK, width=1)
    fill_w = int(lw * pct_used / 100)
    if fill_w > 0:
        d.rectangle([lx, bar_y, lx + fill_w, bar_y + bar_h], fill=BLACK)

    # 已用百分比
    d.text((lx, bar_y + bar_h + 4), f"已用 {pct_used:.1f}%",
           font=f_lbl, fill=BLACK)

    # 今日指标两个格子（左栏下方）
    cell_y0, cell_y1 = 100, 144
    gap = 5
    cell_w = (lw - gap) // 2          # (129-5)//2 = 62
    left_cells = [
        ("今日消耗", fmt_num(today_billed)),
        ("今日请求", f"{today_req} 次"),
    ]
    for i, (label, value) in enumerate(left_cells):
        x0 = lx + i * (cell_w + gap)
        x1 = x0 + cell_w
        # 格子边框
        d.rectangle([x0, cell_y0, x1, cell_y1], outline=BLACK, width=1)
        # 标签
        d.text((x0 + 3, cell_y0 + 2), label, font=f_lbl, fill=BLACK)
        # 数值（垂直居中于下半部）
        f_val = fit_font(d, f_left_val, value, cell_w - 6, min_size=11)
        bbox_v = d.textbbox((0, 0), value, font=f_val)
        vw, vh = bbox_v[2] - bbox_v[0], bbox_v[3] - bbox_v[1]
        vy_mid = (cell_y0 + 15 + cell_y1) / 2  # 标签之下到格底的中间
        d.text((x0 + (cell_w - vw) / 2, vy_mid - vh / 2), value,
               font=f_val, fill=BLACK)

    # ================= 右栏：详情网格 =================
    rx, rw = RIGHT_X0, RIGHT_X1 - RIGHT_X0  # 136
    d.line([(SPLIT_X, 24), (SPLIT_X, H - 8)], fill=BLACK, width=1)

    cells = [
        ("余额包", f"{packs} 个"),
        ("累计已用", fmt_num(used)),
        ("累计充值", fmt_num(recharged)),
        ("更新时间", now.strftime("%m-%d %H:%M")),
    ]
    n_col, n_row = 2, 2
    col_w = rw // n_col
    row_h = (H - 24 - 8) // n_row  # 120//2 = 60
    for i, (label, value) in enumerate(cells):
        r, c = divmod(i, n_col)
        x0 = rx + c * col_w
        x1 = rx + (c + 1) * col_w
        y0 = 24 + r * row_h
        y1 = y0 + row_h
        # 格子分隔线
        d.line([(x0, y1), (x1, y1)], fill=BLACK, width=1)
        if c == 0:
            d.line([(x1, y0), (x1, y1)], fill=BLACK, width=1)
        # 标签 + 数值
        d.text((x0 + 4, y0 + 3), label, font=f_rc_lbl, fill=BLACK)
        f_val = fit_font(d, f_rc_val, value, col_w - 8, min_size=10)
        d.text((x0 + 4, y1 - 17), value, font=f_val, fill=BLACK)

    img.save(out_path, "PNG")
    print(f"✅ 卡片 v4 已生成: {out_path} ({W}x{H})")
    print(f"   剩余 {num_str} | 已用 {pct_used:.1f}% | "
          f"今日消耗 {fmt_num(today_billed)} | 今日请求 {today_req} 次 | "
          f"余额包 {packs} 个")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", help="直接传入积分数据 JSON 字符串")
    parser.add_argument("--rss", help="从 rss.xml 解析数据（离线调试）")
    parser.add_argument("--out", default="card_v4.png", help="输出路径")
    args = parser.parse_args()

    if args.data:
        data = json.loads(args.data)
    elif args.rss:
        data = parse_rss(args.rss)
    else:
        key = os.environ.get("BUDDY_KEY", "").strip()
        if not key:
            print("错误: 需要 --data / --rss 或环境变量 BUDDY_KEY", file=sys.stderr)
            sys.exit(1)
        data = query_balance(key)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    draw_card(data, now, args.out)


if __name__ == "__main__":
    main()
