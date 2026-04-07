"""
从单张卡通图生成 Shimeji 帧序列
原理：去白底 → 裁剪 → 缩放 → 通过镜像/轻微变形生成多帧
"""

from PIL import Image, ImageFilter, ImageChops, ImageEnhance
import numpy as np
import os

SRC = os.path.join(os.path.dirname(__file__), "微信图片_20260407162055_248_7.jpg")
OUT = os.path.join(os.path.dirname(__file__), "frames")
TARGET_SIZE = 128  # shimeji 常用尺寸

# ── 1. 去白底 ──────────────────────────────────────────────────────────────
def remove_white_bg(img: Image.Image, threshold=230) -> Image.Image:
    """将接近白色的像素变成透明"""
    img = img.convert("RGBA")
    data = np.array(img, dtype=np.float32)

    r, g, b, a = data[..., 0], data[..., 1], data[..., 2], data[..., 3]
    # 判断"白色区域"：三个通道都高且彼此接近
    is_white = (r > threshold) & (g > threshold) & (b > threshold)
    # 边缘过渡：计算与白色的距离做渐变 alpha
    dist = np.sqrt((255 - r)**2 + (255 - g)**2 + (255 - b)**2)
    edge_alpha = np.clip(dist / 30 * 255, 0, 255)
    a[is_white] = 0
    # 边缘柔化
    a = np.where(is_white, 0, np.minimum(a, edge_alpha + 200))

    data[..., 3] = np.clip(a, 0, 255)
    result = Image.fromarray(data.astype(np.uint8), "RGBA")
    return result

# ── 2. 自动裁剪内容区域 ────────────────────────────────────────────────────
def autocrop(img: Image.Image, padding=4) -> Image.Image:
    bbox = img.getbbox()
    if bbox is None:
        return img
    l, t, r, b = bbox
    l = max(0, l - padding)
    t = max(0, t - padding)
    r = min(img.width, r + padding)
    b = min(img.height, b + padding)
    return img.crop((l, t, r, b))

# ── 3. 缩放到目标尺寸（保持比例） ────────────────────────────────────────
def resize_keep_ratio(img: Image.Image, max_size: int) -> Image.Image:
    w, h = img.size
    scale = max_size / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)

# ── 4. 生成帧变体 ─────────────────────────────────────────────────────────
def make_walk_frame(base: Image.Image, shift_x=0, shift_y=0, rotate=0) -> Image.Image:
    """通过平移 / 轻微旋转模拟走路帧"""
    w, h = base.size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if rotate != 0:
        rotated = base.rotate(rotate, expand=False, resample=Image.BICUBIC)
    else:
        rotated = base
    paste_x = shift_x
    paste_y = shift_y
    canvas.paste(rotated, (paste_x, paste_y), rotated)
    return canvas

def make_fall_frame(base: Image.Image) -> Image.Image:
    """下落帧：整体向右倾斜"""
    w, h = base.size
    canvas = Image.new("RGBA", (w, h + 10), (0, 0, 0, 0))
    tilted = base.rotate(-15, expand=False, resample=Image.BICUBIC)
    canvas.paste(tilted, (0, 10), tilted)
    return canvas

# ── 主流程 ────────────────────────────────────────────────────────────────
def main():
    print(f"读取: {SRC}")
    raw = Image.open(SRC)
    print(f"原始尺寸: {raw.size}")

    print("去除白色背景...")
    no_bg = remove_white_bg(raw, threshold=235)

    print("自动裁剪...")
    cropped = autocrop(no_bg, padding=6)
    print(f"裁剪后尺寸: {cropped.size}")

    print(f"缩放到 {TARGET_SIZE}px...")
    base = resize_keep_ratio(cropped, TARGET_SIZE)

    os.makedirs(OUT, exist_ok=True)

    # 保存透明底基础图
    base_path = os.path.join(OUT, "base_transparent.png")
    base.save(base_path)
    print(f"✓ 保存透明底基础图: {base_path}")

    # ── 走路帧（左向）：4 帧循环 ──────────────────────────────────────
    walk_variants = [
        (0,  0,  0),    # 站立 / 走路第1帧
        (0, -3,  2),    # 抬脚
        (0,  0,  0),    # 还原
        (0, -2, -2),    # 另一侧
    ]
    for i, (sx, sy, rot) in enumerate(walk_variants):
        frame = make_walk_frame(base, sx, sy, rot)
        path = os.path.join(OUT, f"walk_left_{i+1:02d}.png")
        frame.save(path)
        print(f"✓ 走路帧(左) {i+1}: {path}")

    # ── 走路帧（右向）：镜像 ──────────────────────────────────────────
    for i, (sx, sy, rot) in enumerate(walk_variants):
        frame = make_walk_frame(base, sx, sy, rot)
        frame_r = frame.transpose(Image.FLIP_LEFT_RIGHT)
        path = os.path.join(OUT, f"walk_right_{i+1:02d}.png")
        frame_r.save(path)
        print(f"✓ 走路帧(右) {i+1}: {path}")

    # ── 站立待机帧 ────────────────────────────────────────────────────
    idle = base.copy()
    idle.save(os.path.join(OUT, "idle_01.png"))
    # 轻微上下浮动
    idle2 = make_walk_frame(base, 0, -2, 0)
    idle2.save(os.path.join(OUT, "idle_02.png"))
    print("✓ 站立帧: idle_01.png, idle_02.png")

    # ── 掉落帧 ────────────────────────────────────────────────────────
    fall = make_fall_frame(base)
    fall.save(os.path.join(OUT, "fall_01.png"))
    fall_r = fall.transpose(Image.FLIP_LEFT_RIGHT)
    fall_r.save(os.path.join(OUT, "fall_02.png"))
    print("✓ 掉落帧: fall_01.png, fall_02.png")

    # ── 拖拽帧 ────────────────────────────────────────────────────────
    drag = make_walk_frame(base, 0, 0, 10)
    drag.save(os.path.join(OUT, "drag_01.png"))
    print("✓ 拖拽帧: drag_01.png")

    print(f"\n全部完成！共生成 {len(os.listdir(OUT))} 张图片 → {OUT}")
    print("\n注意：这是基于图像变换的基础版本。")
    print("如需更自然的动画，建议使用 AI 生成工具（ComfyUI + IP-Adapter）")

if __name__ == "__main__":
    main()
