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

def load_remove_black(path, dark_thresh=12, feather=18, shadow_bright=80, shadow_chroma=10):
    """
    从图片边缘做 BFS 洪泛填充，只去掉与边缘相连的近纯黑背景。
    - dark_thresh 极低（12），只有真正的纯黑像素才参与 BFS 扩展，
      不会误吃蹄子/眼睛等深色但非纯黑的部位。
    - 背景去除后，额外清除孤立的亮色小像素团（水印文字）。
    """
    from collections import deque

    img = Image.open(path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    h, w = arr.shape[:2]

    # ── 预处理：把右下角水印区域涂成纯黑，让 BFS 一起清掉 ────────────────
    wm_h = int(h * 0.12)   # 底部 12%
    wm_w = int(w * 0.28)   # 右侧 28%
    arr[h - wm_h:, w - wm_w:, :3] = 0   # RGB → 纯黑，alpha 不动

    brightness = arr[..., :3].max(axis=2).astype(np.int32)

    # BFS 扩展条件：亮度 < dark_thresh + feather（仅扩展真正暗的像素）
    dark_mask = brightness < (dark_thresh + feather)

    # ── BFS 从四边出发 ─────────────────────────────────────────────────────
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

    # 背景区域根据亮度做羽化过渡
    result = arr.copy()
    bg_alpha = np.clip((brightness - dark_thresh) / feather * 255, 0, 255).astype(np.uint8)
    new_alpha = np.where(visited, bg_alpha, arr[..., 3])
    result[..., 3] = new_alpha.astype(np.uint8)

    # ── 去除地面阴影/反光 ──────────────────────────────────────────────────
    r2 = result[..., 0].astype(np.int32)
    g2 = result[..., 1].astype(np.int32)
    b2 = result[..., 2].astype(np.int32)
    br2 = np.maximum(np.maximum(r2, g2), b2)
    chroma2 = br2 - np.minimum(np.minimum(r2, g2), b2)

    # 全图：极严格（chroma<10），只去纯灰像素，保留有色调的蹄子
    shadow_mask = (br2 < shadow_bright) & (chroma2 < shadow_chroma) & (result[..., 3] > 0)
    result[..., 3][shadow_mask] = 0

    # 底部 8%：放宽到 chroma<22，强力清除紧贴地面的阴影烟雾
    # 蹄子主体在 75-85% 位置，不会被这一步误删
    bottom_strip = int(h * 0.08)
    r3 = result[h - bottom_strip:, :, 0].astype(np.int32)
    g3 = result[h - bottom_strip:, :, 1].astype(np.int32)
    b3 = result[h - bottom_strip:, :, 2].astype(np.int32)
    br3 = np.maximum(np.maximum(r3, g3), b3)
    chroma3 = br3 - np.minimum(np.minimum(r3, g3), b3)
    floor_mask = (br3 < shadow_bright) & (chroma3 < 22) & (result[h - bottom_strip:, :, 3] > 0)
    result[h - bottom_strip:, :, 3][floor_mask] = 0

    # ── 去除孤立亮色像素团（水印文字）─────────────────────────────────────
    # 对当前 alpha>0 的像素做连通区域标记，找出与主体不相连的小块并清除
    alpha_mask = result[..., 3] > 30  # 当前不透明区域

    # 用 BFS 找出所有连通区域，保留最大的（猪身体），其余小块清除
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
                    for dy, dx in [(-1,0),(1,0),(0,-1),(0,1),
                                   (-1,-1),(-1,1),(1,-1),(1,1)]:
                        ny2, nx2 = cy2 + dy, cx2 + dx
                        if 0 <= ny2 < h and 0 <= nx2 < w \
                                and alpha_mask[ny2, nx2] and labeled[ny2, nx2] == 0:
                            labeled[ny2, nx2] = comp_id
                            q2.append((ny2, nx2))
                comp_sizes[comp_id] = size

    if comp_sizes:
        # 主体是最大连通区域；小于主体 1% 的区域视为噪点/水印，清除
        max_size = max(comp_sizes.values())
        remove_threshold = max(max_size * 0.01, 200)   # 至少 200px 才保留
        for cid, sz in comp_sizes.items():
            if sz < remove_threshold:
                result[..., 3][labeled == cid] = 0

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
