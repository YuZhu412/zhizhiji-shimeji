# 添加新卡通形象指南

> 本项目的互动逻辑（趴地板、走路、贴墙、拖拽）全部通过 XML 配置实现，添加新角色**只需复用配置文件 + 替换图片**，无需修改任何 Java 代码。

---

## 原理说明

Shimeji-ee 通过扫描 `img/` 目录自动发现所有角色。每个子文件夹就是一个独立角色，文件夹名即角色名。各角色的配置文件（`conf/actions.xml` / `conf/behaviors.xml`）优先级高于根目录下的全局配置，且图片路径以 `/` 开头时，引擎会自动解析为**当前角色目录下的文件**，因此两个角色之间完全隔离，互不影响。

---

## 目录结构

```
runtime/shimejiee-local/shimejiee/img/
├── Zhizhiji/                      ← 现有角色（吱吱吉）
│   ├── conf/
│   │   ├── actions.xml
│   │   └── behaviors.xml
│   ├── idle_01.png
│   ├── idle_02.png
│   ├── fall_01.png
│   ├── drag_01.png
│   ├── walk_left_01~04.png
│   ├── walk_right_01~04.png
│   ├── wall_cling_left.png
│   └── wall_cling_right.png
│
└── NewChar/                       ← 新角色（文件夹名即角色名，建议英文）
    ├── conf/
    │   ├── actions.xml            ← 从 Zhizhiji/conf/ 直接复制
    │   └── behaviors.xml          ← 从 Zhizhiji/conf/ 直接复制
    ├── idle_01.png
    ├── idle_02.png
    ├── fall_01.png
    ├── drag_01.png
    ├── walk_left_01.png
    ├── walk_left_02.png
    ├── walk_left_03.png
    ├── walk_left_04.png
    ├── walk_right_01.png
    ├── walk_right_02.png
    ├── walk_right_03.png
    ├── walk_right_04.png
    ├── wall_cling_left.png
    └── wall_cling_right.png
```

---

## 步骤详解

### 第一步：创建角色文件夹

在 `img/` 下新建一个英文命名的文件夹（中文路径会导致 Java 读取失败）：

```powershell
$BASE = "C:\Users\TCL\Desktop\zhizhiji-final\runtime\shimejiee-local\shimejiee\img"
$NEW  = "$BASE\NewChar"   # 替换 NewChar 为你想要的名称

New-Item -ItemType Directory "$NEW\conf" -Force
```

### 第二步：复制配置文件

配置文件可以直接复用，**不需要做任何修改**（图片路径是相对当前角色目录的，引擎自动处理）：

```powershell
$SRC = "$BASE\Zhizhiji\conf"

Copy-Item "$SRC\actions.xml"   "$NEW\conf\"
Copy-Item "$SRC\behaviors.xml" "$NEW\conf\"
```

### 第三步：准备图片文件

将新角色的图片按以下规范命名后放入 `$NEW\` 目录：

| 文件名 | 用途 | 推荐尺寸 | 备注 |
|---|---|---|---|
| `idle_01.png` | 趴地板第 1 帧 | 160×160 | |
| `idle_02.png` | 趴地板第 2 帧 | 160×160 | 可与 idle_01 相同 |
| `fall_01.png` | 下落 / 空中姿势 | 160×160 | |
| `drag_01.png` | 被拖动时姿势 | 160×160 | 可复用 fall_01 |
| `walk_left_01~04.png` | 向左走动画（4 帧） | 160×160 | |
| `walk_right_01~04.png` | 向右走动画（4 帧） | 160×160 | |
| `wall_cling_left.png` | 贴左墙姿势 | **80×80** | 角色侧身朝右 |
| `wall_cling_right.png` | 贴右墙姿势 | **80×80** | 角色侧身朝左 |

**格式要求**：
- PNG，背景透明（RGBA）
- 画布统一，角色脚部位于图片底边中央
- wall_cling 两张图尺寸为 80×80（其余均为 160×160）

### 第四步：图片尺寸不同时调整 actions.xml

如果新角色使用了不同的图片尺寸（例如 128×128），需要修改新角色 `conf/actions.xml` 中的 `ImageAnchor`：

```
ImageAnchor="X,Y"
  X = 图片宽度 ÷ 2       （水平中心，单位 px）
  Y = 图片高度            （脚部落地点，单位 px）
```

同时更新 wall_cling 的锚点（当前为 80×80，锚点 `23,70` / `56,70`）：
- `wall_cling_left.png`：锚点 X ≈ 图片宽 × 0.29，Y ≈ 图片高 × 0.88
- `wall_cling_right.png`：锚点 X ≈ 图片宽 × 0.70，Y ≈ 图片高 × 0.88

---

## 生成 wall_cling 图片（Python 脚本）

如果有一张正面趴地板的图片，可以用以下脚本自动生成两张贴墙图：

```python
from PIL import Image
import os

SRC_IMAGE = r"path\to\your_prone_image.png"   # 原始趴着图片
OUT_DIR   = r"path\to\NewChar"                # 输出到新角色目录

def remove_white_bg(img, threshold=240):
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > threshold and g > threshold and b > threshold:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)
    return img

img = Image.open(SRC_IMAGE)
img = remove_white_bg(img)

# 裁剪非透明区域（加 8px 内边距）
bbox = img.getbbox()
pad  = 8
bbox = (max(0, bbox[0]-pad), max(0, bbox[1]-pad),
        min(img.width, bbox[2]+pad), min(img.height, bbox[3]+pad))
img  = img.crop(bbox)

# 缩放到 80×80
img = img.resize((80, 80), Image.LANCZOS)

# 左墙：顺时针旋转 90°
img.rotate(-90, expand=True).save(os.path.join(OUT_DIR, "wall_cling_left.png"))

# 右墙：逆时针旋转 90°
img.rotate(90, expand=True).save(os.path.join(OUT_DIR, "wall_cling_right.png"))

print("wall_cling_left.png 和 wall_cling_right.png 已生成")
```

---

## 启动与切换角色

启动 Shimeji-ee 后，在系统托盘图标上**右键**，菜单中会列出 `img/` 目录下所有检测到的角色。点击角色名称即可在桌面上召唤该角色，多个角色可以同时运行，互不干扰。

```
系统托盘右键菜单
├── 召唤另一个 Zhizhiji
├── 召唤另一个 NewChar     ← 新角色出现在这里
├── 退出所有
└── ...
```

---

## 当前已有角色一览

| 角色文件夹 | 说明 |
|---|---|
| `Zhizhiji` | 吱吱吉，本项目主角色，包含完整的贴墙/趴地板/走路/拖拽逻辑 |

---

## 快速检查清单

添加新角色后，按以下清单验证：

- [ ] `img/NewChar/conf/actions.xml` 存在
- [ ] `img/NewChar/conf/behaviors.xml` 存在
- [ ] 所有 12 张图片文件已就位（`idle` ×2、`fall` ×1、`drag` ×1、`walk_left/right` ×4×2、`wall_cling_left/right` ×2）
- [ ] 图片为 PNG + 透明背景
- [ ] 普通图片尺寸为 160×160，wall_cling 为 80×80
- [ ] 若使用不同尺寸，已更新 `conf/actions.xml` 中的 `ImageAnchor`
- [ ] 重启 Shimeji-ee 后，在托盘菜单中能看到新角色名称
