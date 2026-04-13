"""
处理 ham 角色的原始图片，生成所有游戏资产。
输入：raw/ham/  (黑底 PNG)
输出：processed/ham/  →  runtime/.../img/ham/
"""

import os
import shutil
import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR  = os.path.join(BASE, "raw", "ham")
PROC_DIR = os.path.join(BASE, "processed", "ham")
RUNTIME  = os.path.join(BASE, "runtime", "shimejiee-local", "shimejiee", "img", "ham")

os.makedirs(PROC_DIR, exist_ok=True)

# ── 工具函数 ─────────────────────────────────────────────────────────────────

def load_remove_black(path, dark_thresh=60, feather=40):
    """
    从图片边缘做 BFS 洪泛填充，只去掉与边缘相连的黑色背景。
    眼睛、蹄子等内部深色部分因为孤立而被完整保留。
    """
    from collections import deque

    img = Image.open(path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    h, w = arr.shape[:2]

    # 亮度图（最亮通道）
    brightness = arr[..., :3].max(axis=2).astype(np.int32)

    # "暗像素"掩码：亮度 < dark_thresh + feather（用于 BFS 邻居扩展）
    dark_mask = brightness < (dark_thresh + feather)

    # BFS：从四条边界上所有暗像素出发，找到所有与背景相连的暗区域
    visited = np.zeros((h, w), dtype=bool)
    queue = deque()

    for x in range(w):
        for y in [0, h - 1]:
            if dark_mask[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))
    for y in range(h):
        for x in [0, w - 1]:
            if dark_mask[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))

    while queue:
        cy, cx = queue.popleft()
        for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and dark_mask[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))

    # visited == True 的像素是背景，根据亮度做平滑透明过渡
    result = arr.copy()
    bg = visited  # shape (h, w)

    # 背景区域：按亮度做 feather 渐变（亮度越高越不透明，模拟边缘羽化）
    bg_alpha = np.clip((brightness - dark_thresh) / feather * 255, 0, 255).astype(np.uint8)
    # 非背景区域保持原透明度
    new_alpha = np.where(bg, bg_alpha, arr[..., 3])
    result[..., 3] = new_alpha.astype(np.uint8)

    return Image.fromarray(result, "RGBA")


def fit_into_canvas(img_rgba, canvas_w, canvas_h, align="center_bottom"):
    """
    将图片（已去背景）裁掉空白、保持比例缩放后放到画布中。
    align:
      "center_bottom" → 脚部对齐底部中央（fall/drag/walk/idle）
      "center_center"  → 居中
    """
    # 找有效内容边界
    arr = np.array(img_rgba)
    alpha = arr[..., 3]
    rows = np.any(alpha > 10, axis=1)
    cols = np.any(alpha > 10, axis=0)
    if not rows.any():
        # 全透明：返回空画布
        return Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    r0, r1 = np.where(rows)[0][[0, -1]]
    c0, c1 = np.where(cols)[0][[0, -1]]

    pad = 4
    r0 = max(0, r0 - pad)
    r1 = min(arr.shape[0] - 1, r1 + pad)
    c0 = max(0, c0 - pad)
    c1 = min(arr.shape[1] - 1, c1 + pad)

    cropped = img_rgba.crop((c0, r0, c1 + 1, r1 + 1))

    # 保持比例，适配画布
    cw, ch = cropped.size
    scale = min(canvas_w / cw, canvas_h / ch)
    new_w = int(cw * scale)
    new_h = int(ch * scale)
    resized = cropped.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    if align == "center_bottom":
        x = (canvas_w - new_w) // 2
        y = canvas_h - new_h       # 底部对齐
        canvas.paste(resized, (x, y), resized)
    else:
        x = (canvas_w - new_w) // 2
        y = (canvas_h - new_h) // 2
        canvas.paste(resized, (x, y), resized)

    return canvas


def save(img, name):
    path = os.path.join(PROC_DIR, name)
    img.save(path)
    print(f"  [ok] {name}")


# ── 加载原图 ─────────────────────────────────────────────────────────────────

print("正在处理 ham 角色图片...")

stand_raw    = load_remove_black(os.path.join(RAW_DIR, "基本站姿黑底.png"))
prone_raw    = load_remove_black(os.path.join(RAW_DIR, "趴着idle.png"))
walk_raw     = load_remove_black(os.path.join(RAW_DIR, "向左走.png"))
cling_raw    = load_remove_black(os.path.join(RAW_DIR, "趴着wallcling.png"))

# ── fall_01.png / drag_01.png  (160×160，脚底对齐) ───────────────────────────
fall = fit_into_canvas(stand_raw, 160, 160, "center_bottom")
save(fall, "fall_01.png")
save(fall, "drag_01.png")

# ── idle_01.png / idle_02.png  (160×160) ────────────────────────────────────
idle = fit_into_canvas(prone_raw, 160, 160, "center_bottom")
save(idle, "idle_01.png")
save(idle, "idle_02.png")

# ── walk 系列  (160×160) ─────────────────────────────────────────────────────
# 向左走.png 朝左 → 用于 walk_right_*.png（WalkLeft 动作使用）
# 镜像后朝右  → 用于 walk_left_*.png（WalkRight 动作使用）
walk_facing_left  = fit_into_canvas(walk_raw, 160, 160, "center_bottom")
walk_facing_right = walk_facing_left.transpose(Image.FLIP_LEFT_RIGHT)

for i in range(1, 5):
    save(walk_facing_left,  f"walk_right_{i:02d}.png")   # WalkLeft 动作
    save(walk_facing_right, f"walk_left_{i:02d}.png")    # WalkRight 动作

# ── wall_cling 系列  (80×80) ─────────────────────────────────────────────────
cling_base = fit_into_canvas(cling_raw, 80, 80, "center_center")
save(cling_base, "wall_cling.png")

# 左墙：顺时针转 90°（头朝右，背朝墙）
cling_left  = cling_base.rotate(-90, expand=True).resize((80, 80), Image.LANCZOS)
save(cling_left, "wall_cling_left.png")

# 右墙：逆时针转 90°（头朝左，背朝墙）
cling_right = cling_base.rotate(90, expand=True).resize((80, 80), Image.LANCZOS)
save(cling_right, "wall_cling_right.png")

# ── 部署到运行目录 ────────────────────────────────────────────────────────────
print("\n正在部署到运行目录...")
files = [f for f in os.listdir(PROC_DIR) if f.endswith(".png")]
for f in sorted(files):
    shutil.copy(os.path.join(PROC_DIR, f), os.path.join(RUNTIME, f))
    print(f"  [deploy] {f}")

print(f"\n完成！共生成并部署 {len(files)} 张图片。")
