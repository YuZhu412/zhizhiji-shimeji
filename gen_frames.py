"""
从多张卡通图生成 Shimeji 帧序列

素材：
  raw/zhizhi走路.jpg   → walk_left / walk_right / fall / drag 帧
  raw/zhizhi趴着.jpg   → idle（趴着待机）帧

所有帧统一放在 frames/ 目录，采用固定画布尺寸，锚点统一。
"""

from PIL import Image
import numpy as np
import os

RAW_DIR    = os.path.join(os.path.dirname(__file__), "raw")
OUT        = os.path.join(os.path.dirname(__file__), "frames")

SRC_WALK   = os.path.join(RAW_DIR, "zhizhi走路.jpg")
SRC_PRONE  = os.path.join(RAW_DIR, "zhizhi趴着.jpg")

# 统一画布尺寸：所有帧都放在这个大小的透明底上
CANVAS_W = 160
CANVAS_H = 160

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def remove_white_bg(img: Image.Image, threshold=230) -> Image.Image:
    img = img.convert("RGBA")
    data = np.array(img, dtype=np.float32)
    r, g, b, a = data[..., 0], data[..., 1], data[..., 2], data[..., 3]
    is_white = (r > threshold) & (g > threshold) & (b > threshold)
    dist = np.sqrt((255 - r)**2 + (255 - g)**2 + (255 - b)**2)
    edge_alpha = np.clip(dist / 30 * 255, 0, 255)
    a[is_white] = 0
    a = np.where(is_white, 0, np.minimum(a, edge_alpha + 200))
    data[..., 3] = np.clip(a, 0, 255)
    return Image.fromarray(data.astype(np.uint8), "RGBA")

def autocrop(img: Image.Image, padding=6) -> Image.Image:
    bbox = img.getbbox()
    if bbox is None:
        return img
    l, t, r, b = bbox
    return img.crop((max(0, l-padding), max(0, t-padding),
                     min(img.width, r+padding), min(img.height, b+padding)))

def resize_keep_ratio(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    w, h = img.size
    scale = min(max_w / w, max_h / h)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

def place_on_canvas(img: Image.Image,
                    canvas_w=CANVAS_W, canvas_h=CANVAS_H,
                    align_bottom=True,
                    shift_x=0, shift_y=0) -> Image.Image:
    """把图贴到固定大小透明画布上，水平居中，底部对齐"""
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    x = (canvas_w - img.width) // 2 + shift_x
    y = (canvas_h - img.height) + shift_y if align_bottom else shift_y
    canvas.paste(img, (x, y), img)
    return canvas

def process_source(path: str, max_w: int, max_h: int) -> Image.Image:
    """读取 → 去白底 → 裁剪 → 缩放"""
    raw = Image.open(path)
    no_bg = remove_white_bg(raw, threshold=232)
    cropped = autocrop(no_bg)
    return resize_keep_ratio(cropped, max_w, max_h)

def save(img: Image.Image, name: str):
    path = os.path.join(OUT, name)
    img.save(path)
    print(f"  ✓ {name}")
    return path

# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT, exist_ok=True)

    # ── 走路素材（保持高度最大 140px，留出画布空间） ──────────────────────
    print("处理走路图...")
    walk_base = process_source(SRC_WALK, max_w=130, max_h=140)
    print(f"  走路图尺寸: {walk_base.size}")

    # 走路右向（原图面朝右）：4帧，上下轻微抖动模拟迈步
    print("生成 walk_right 帧:")
    bob = [0, -4, -1, -4]   # 每帧的垂直偏移，模拟重心起伏
    for i, dy in enumerate(bob):
        frame = place_on_canvas(walk_base, shift_y=dy)
        save(frame, f"walk_right_{i+1:02d}.png")

    # 走路左向：镜像
    walk_base_l = walk_base.transpose(Image.FLIP_LEFT_RIGHT)
    print("生成 walk_left 帧:")
    for i, dy in enumerate(bob):
        frame = place_on_canvas(walk_base_l, shift_y=dy)
        save(frame, f"walk_left_{i+1:02d}.png")

    # ── 趴着素材（宽图，限宽 150px） ─────────────────────────────────────
    print("处理趴着图...")
    prone_base = process_source(SRC_PRONE, max_w=150, max_h=100)
    print(f"  趴着图尺寸: {prone_base.size}")

    # idle 待机：2帧，模拟轻微呼吸（垂直微浮动）
    print("生成 idle 帧:")
    for i, dy in enumerate([0, -2]):
        frame = place_on_canvas(prone_base, shift_y=dy)
        save(frame, f"idle_{i+1:02d}.png")

    # ── 掉落帧：走路图倾斜 ────────────────────────────────────────────────
    print("生成 fall 帧:")
    fall_img = walk_base.rotate(-20, expand=True, resample=Image.BICUBIC)
    fall_img = resize_keep_ratio(fall_img, max_w=130, max_h=140)
    frame = place_on_canvas(fall_img)
    save(frame, "fall_01.png")
    frame_r = place_on_canvas(fall_img.transpose(Image.FLIP_LEFT_RIGHT))
    save(frame_r, "fall_02.png")

    # ── 拖拽帧：走路图向右倾斜（被抓起的感觉） ───────────────────────────
    print("生成 drag 帧:")
    drag_img = walk_base.rotate(15, expand=True, resample=Image.BICUBIC)
    drag_img = resize_keep_ratio(drag_img, max_w=130, max_h=140)
    frame = place_on_canvas(drag_img)
    save(frame, "drag_01.png")

    # ── 保存透明底基础图（供参考） ────────────────────────────────────────
    save(place_on_canvas(walk_base), "base_transparent.png")

    total = len([f for f in os.listdir(OUT) if f.endswith('.png')])
    print(f"\n全部完成！共生成 {total} 张图片 → {OUT}")
    print(f"画布尺寸统一为 {CANVAS_W}x{CANVAS_H}，锚点: ({CANVAS_W//2}, {CANVAS_H})")

if __name__ == "__main__":
    main()
