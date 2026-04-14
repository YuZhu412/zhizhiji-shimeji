"""
处理 ham 角色的原始图片（白底），生成所有游戏资产。
输入：raw/ham/白底/
输出：processed/ham/  →  runtime/.../img/ham/
"""

import os
import shutil
import numpy as np
from PIL import Image
from collections import deque

BASE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR  = os.path.join(BASE, "raw", "ham", "白底")
PROC_DIR = os.path.join(BASE, "processed", "ham")
RUNTIME  = os.path.join(BASE, "runtime", "shimejiee-local", "shimejiee", "img", "ham")

os.makedirs(PROC_DIR, exist_ok=True)

# ── 去白底工具 ────────────────────────────────────────────────────────────────

def remove_white_bg(path):
    """
    使用 min(r,g,b) > 220 作为「可能是白色背景」的判断标准，从四边 BFS 扩散，
    将外部连通的白色区域完全透明化。
    - 白色背景：三通道都≥220（rgb 几乎相等且都亮）
    - 猪身粉色：蓝通道通常 ≤ 190，即使最亮高光蓝通道也 < 220
    - 深色特征（眼、蹄）：min 远低于220，完全不会被误删
    """
    img = Image.open(path).convert("RGBA")

    # ── 0. 合成到纯白底（清除原图自带的半透明/透明区域残留）────────────────
    white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    white_bg.paste(img, mask=img)
    arr = np.array(white_bg, dtype=np.uint8)
    h, w = arr.shape[:2]

    # ── 1. 水印区域强制涂白（右下角约 10%×25%）──────────────────────────────
    wm_h = int(h * 0.10)
    wm_w = int(w * 0.25)
    arr[h - wm_h:, w - wm_w:, :] = 255

    r = arr[..., 0].astype(np.int32)
    g = arr[..., 1].astype(np.int32)
    b = arr[..., 2].astype(np.int32)

    # ── 2. 候选掩码：min(r,g,b) > 220 ──────────────────────────────────────
    # 白色/浅灰背景：三通道都高（min≈255）
    # 猪粉色高光：蓝通道通常 ≤ 210，min < 220，不会被纳入候选
    MIN_THRESH = 220
    min_ch = np.minimum(np.minimum(r, g), b)
    bg_cand = (min_ch > MIN_THRESH)

    # ── 3. BFS 从四边出发，只在候选区域内扩散 ──────────────────────────────
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
        for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and bg_cand[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))

    # ── 4. 背景 → 完全透明，主体 → 完全不透明 ──────────────────────────────
    result = arr.copy()
    result[..., 3] = np.where(visited, 0, 255).astype(np.uint8)

    # ── 5. 去除孤立小像素团（噪点/水印碎片）────────────────────────────────
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
                    for dy2, dx2 in [(-1,0),(1,0),(0,-1),(0,1),
                                     (-1,-1),(-1,1),(1,-1),(1,1)]:
                        ny2, nx2 = cy2 + dy2, cx2 + dx2
                        if 0 <= ny2 < h and 0 <= nx2 < w \
                                and alpha_mask[ny2, nx2] and labeled[ny2, nx2] == 0:
                            labeled[ny2, nx2] = comp_id
                            q2.append((ny2, nx2))
                comp_sizes[comp_id] = size
    if comp_sizes:
        max_size = max(comp_sizes.values())
        min_keep = max(max_size * 0.01, 50)   # 保留 ≥50px 的连通域
        for cid, sz in comp_sizes.items():
            if sz < min_keep:
                result[..., 3][labeled == cid] = 0

    return Image.fromarray(result, "RGBA")


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
    r0 = max(0, r0 - pad); r1 = min(arr.shape[0]-1, r1 + pad)
    c0 = max(0, c0 - pad); c1 = min(arr.shape[1]-1, c1 + pad)
    cropped = img_rgba.crop((c0, r0, c1+1, r1+1))

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


# ── 加载并去背 ────────────────────────────────────────────────────────────────

print("正在处理 ham 角色图片（白底）...")

fall_raw  = remove_white_bg(os.path.join(RAW_DIR, "站着fall白底.png"))
idle_raw  = remove_white_bg(os.path.join(RAW_DIR, "坐着idle.png"))
walk_raw  = remove_white_bg(os.path.join(RAW_DIR, "灰猪走路 walkleft.png"))
cling_raw = remove_white_bg(os.path.join(RAW_DIR, "趴着wallcling 白底.png"))

# ── fall_01 / drag_01  (160×160，脚底对齐) ────────────────────────────────────
fall = fit_into_canvas(fall_raw, 160, 160, "center_bottom")
save(fall, "fall_01.png")
save(fall, "drag_01.png")

# ── idle_01 / idle_02  (160×160) ─────────────────────────────────────────────
idle = fit_into_canvas(idle_raw, 160, 160, "center_bottom")
save(idle, "idle_01.png")
save(idle, "idle_02.png")

# ── idle_01_r / idle_02_r  水平翻转版（StandRight 随机朝向用）────────────────
idle_r = idle.transpose(Image.FLIP_LEFT_RIGHT)
save(idle_r, "idle_01_r.png")
save(idle_r, "idle_02_r.png")

# ── walk 系列  (160×160) ──────────────────────────────────────────────────────
# 原图朝左 → walk_right_*（WalkLeft 动作使用）
# 镜像朝右 → walk_left_*（WalkRight 动作使用）
walk_l = fit_into_canvas(walk_raw, 160, 160, "center_bottom")
walk_r = walk_l.transpose(Image.FLIP_LEFT_RIGHT)
for i in range(1, 5):
    save(walk_l, f"walk_right_{i:02d}.png")
    save(walk_r, f"walk_left_{i:02d}.png")

# ── wall_cling 系列  (160×160) ────────────────────────────────────────────────
cling_base  = fit_into_canvas(cling_raw, 160, 160, "center_center")
save(cling_base, "wall_cling.png")

cling_left  = cling_base.rotate(90, expand=True).resize((160, 160), Image.LANCZOS)
save(cling_left, "wall_cling_left.png")

cling_right = cling_base.rotate(-90, expand=True).resize((160, 160), Image.LANCZOS)
save(cling_right, "wall_cling_right.png")

# ── 部署到运行目录 ────────────────────────────────────────────────────────────
print("\n正在部署到运行目录...")
files = [f for f in os.listdir(PROC_DIR) if f.endswith(".png")]
for f in sorted(files):
    shutil.copy(os.path.join(PROC_DIR, f), os.path.join(RUNTIME, f))
    print(f"  [deploy] {f}")

print(f"\n完成！共生成并部署 {len(files)} 张图片。")
