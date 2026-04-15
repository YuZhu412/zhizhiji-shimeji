# -*- coding: utf-8 -*-
"""
处理 Zhizhiji 角色的新增状态图片（大笑挥手、睡觉），生成游戏资产。
输入：raw/zhizhiji/
输出：processed/Zhizhiji/  →  runtime/.../img/Zhizhiji/
"""

import os
import shutil
import numpy as np
from PIL import Image
from collections import deque

BASE     = os.path.dirname(os.path.abspath(__file__))
RAW_DIR  = os.path.join(BASE, "raw", "zhizhiji")
PROC_DIR = os.path.join(BASE, "processed", "Zhizhiji")
RUNTIME  = os.path.join(BASE, "runtime", "shimejiee-local", "shimejiee", "img", "Zhizhiji")

os.makedirs(PROC_DIR, exist_ok=True)

# ── 去白底工具（与 process_ham.py 一致）────────────────────────────────────────

def remove_white_bg(path):
    """
    使用 min(r,g,b) > 220 作为候选白色背景判断，从四边 BFS 扩散，
    将外部连通的白色区域完全透明化。
    """
    img = Image.open(path).convert("RGBA")

    white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    white_bg.paste(img, mask=img)
    arr = np.array(white_bg, dtype=np.uint8)
    h, w = arr.shape[:2]

    # 水印区域强制涂白（右下角约 10%×25%）
    wm_h = int(h * 0.10)
    wm_w = int(w * 0.25)
    arr[h - wm_h:, w - wm_w:, :] = 255

    r = arr[..., 0].astype(np.int32)
    g = arr[..., 1].astype(np.int32)
    b = arr[..., 2].astype(np.int32)

    MIN_THRESH = 220
    min_ch = np.minimum(np.minimum(r, g), b)
    bg_cand = (min_ch > MIN_THRESH)

    visited = np.zeros((h, w), dtype=bool)
    queue = deque()
    for x in range(w):
        for y in [0, h - 1]:
            if bg_cand[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))
    for y in range(h):
        for x in [0, w - 1]:
            if bg_cand[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))
    while queue:
        cy, cx = queue.popleft()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and bg_cand[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))

    result = arr.copy()
    result[..., 3] = np.where(visited, 0, 255).astype(np.uint8)

    # 去除孤立小像素团（噪点）
    alpha_mask = result[..., 3] > 0
    labeled = np.zeros((h, w), dtype=np.int32)
    comp_id = 0
    comp_sizes = {}
    for sy in range(h):
        for sx in range(w):
            if alpha_mask[sy, sx] and labeled[sy, sx] == 0:
                comp_id += 1
                q2 = deque([(sy, sx)])
                labeled[sy, sx] = comp_id
                size = 0
                while q2:
                    cy2, cx2 = q2.popleft()
                    size += 1
                    for dy2, dx2 in [(-1, 0), (1, 0), (0, -1), (0, 1),
                                     (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                        ny2, nx2 = cy2 + dy2, cx2 + dx2
                        if 0 <= ny2 < h and 0 <= nx2 < w \
                                and alpha_mask[ny2, nx2] and labeled[ny2, nx2] == 0:
                            labeled[ny2, nx2] = comp_id
                            q2.append((ny2, nx2))
                comp_sizes[comp_id] = size
    if comp_sizes:
        max_size = max(comp_sizes.values())
        min_keep = max(max_size * 0.01, 50)
        for cid, sz in comp_sizes.items():
            if sz < min_keep:
                result[..., 3][labeled == cid] = 0

    return Image.fromarray(result, "RGBA")


def prepare_rgba(path):
    """
    若图片已有 alpha 通道（RGBA）直接返回，否则执行去白底处理。
    """
    img = Image.open(path)
    if img.mode == "RGBA":
        arr = np.array(img)
        if arr[..., 3].min() < 255:
            print(f"  [info] {os.path.basename(path)} 已含透明通道，直接使用")
            return img
    print(f"  [info] {os.path.basename(path)} 为纯色背景，执行去白底")
    return remove_white_bg(path)


# ── 画布适配工具 ──────────────────────────────────────────────────────────────

def fit_into_canvas(img_rgba, canvas_w, canvas_h, align="center_bottom"):
    arr = np.array(img_rgba)
    alpha = arr[..., 3]
    rows = np.any(alpha > 10, axis=1)
    cols = np.any(alpha > 10, axis=0)
    if not rows.any():
        return Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    r0, r1 = np.where(rows)[0][[0, -1]]
    c0, c1 = np.where(cols)[0][[0, -1]]
    pad = 4
    r0 = max(0, r0 - pad); r1 = min(arr.shape[0] - 1, r1 + pad)
    c0 = max(0, c0 - pad); c1 = min(arr.shape[1] - 1, c1 + pad)
    cropped = img_rgba.crop((c0, r0, c1 + 1, r1 + 1))

    cw, ch = cropped.size
    scale = min(canvas_w / cw, canvas_h / ch)
    new_w, new_h = int(cw * scale), int(ch * scale)
    resized = cropped.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    if align == "center_bottom":
        x = (canvas_w - new_w) // 2
        y = canvas_h - new_h
    else:
        x = (canvas_w - new_w) // 2
        y = (canvas_h - new_h) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def save(img, name):
    path = os.path.join(PROC_DIR, name)
    img.save(path)
    print(f"  [ok] {name}")


# ── 查找原始图片（按文件大小匹配，兼容不同编码环境）─────────────────────────

def find_raw_by_size(target_size_bytes, tolerance=5000):
    """按文件大小（精确容差）找到对应的原始图片路径。"""
    candidates = []
    for f in os.listdir(RAW_DIR):
        fp = os.path.join(RAW_DIR, f)
        if f.endswith(".png"):
            sz = os.path.getsize(fp)
            if abs(sz - target_size_bytes) < tolerance:
                candidates.append((abs(sz - target_size_bytes), fp))
    if not candidates:
        raise FileNotFoundError(
            f"在 {RAW_DIR} 中未找到大小约为 {target_size_bytes} 字节的 PNG 文件"
        )
    candidates.sort()
    return candidates[0][1]


def find_raw_smallest():
    """返回 RAW_DIR 中文件最小的 RGB PNG（用于大笑挥手）。"""
    pngs = [(os.path.getsize(os.path.join(RAW_DIR, f)), os.path.join(RAW_DIR, f))
            for f in os.listdir(RAW_DIR) if f.endswith(".png")]
    pngs.sort()
    return pngs[0][1]


def find_raw_second():
    """返回 RAW_DIR 中文件第二小的 RGB PNG（用于睡觉）。"""
    pngs = [(os.path.getsize(os.path.join(RAW_DIR, f)), os.path.join(RAW_DIR, f))
            for f in os.listdir(RAW_DIR) if f.endswith(".png")]
    pngs.sort()
    return pngs[1][1]


# ── 主流程 ────────────────────────────────────────────────────────────────────

print("正在处理 Zhizhiji 新增状态图片...")

# 列出所有 PNG 并按大小排序，方便确认匹配
all_pngs = sorted(
    [(os.path.getsize(os.path.join(RAW_DIR, f)), f)
     for f in os.listdir(RAW_DIR) if f.endswith(".png")]
)
print("原始 PNG 列表（按大小）：")
for sz, fn in all_pngs:
    print(f"  {sz:>10} bytes  {fn}")

# 大笑挥手：文件较小的那张（~974599 字节）→ laugh_01.png
laugh_path = find_raw_smallest()
print(f"\n[大笑挥手] 原始文件：{os.path.basename(laugh_path)}")
laugh_raw = prepare_rgba(laugh_path)
laugh = fit_into_canvas(laugh_raw, 160, 160, "center_bottom")
save(laugh, "laugh_01.png")

# 睡觉：第二小的那张（~1001997 字节）→ sleep_01.png
sleep_path = find_raw_second()
print(f"\n[睡觉] 原始文件：{os.path.basename(sleep_path)}")
sleep_raw = prepare_rgba(sleep_path)
sleep = fit_into_canvas(sleep_raw, 160, 160, "center_bottom")
save(sleep, "sleep_01.png")

# ── 部署到运行目录 ────────────────────────────────────────────────────────────
print("\n正在部署到运行目录...")
for name in ["laugh_01.png", "sleep_01.png"]:
    src = os.path.join(PROC_DIR, name)
    dst = os.path.join(RUNTIME, name)
    shutil.copy(src, dst)
    print(f"  [deploy] {name}")

print("\n完成！已生成并部署 laugh_01.png 和 sleep_01.png。")
