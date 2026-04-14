# 白底图片抠图方法论

本文档记录为 Shimeji 角色素材处理白底 PNG 图片、生成透明背景精灵的完整方法论，以及踩过的坑和最终可靠方案。

---

## 核心问题

将 AI 生成的白底角色图片转换为游戏可用的透明背景 PNG 时，面临三类挑战：

1. **原始透明区域残留**：AI 工具生成的 PNG 部分区域本身已有透明度（alpha < 255），若直接处理，这些半透明区域会在图片查看器中显示为棋盘格（网格背景）。
2. **水印文字**：AI 工具通常在右下角叠加水印文字。
3. **前景/背景颜色接近**：猪身体的高光区域（浅粉色）与白色背景颜色相近，阈值设错会把猪身体部分删掉。

---

## 失败的方案（历史记录）

### 方案一：亮度 + 饱和度阈值（全局，无连通判断）

```python
# brightness = max(r, g, b)
# chroma = max(r,g,b) - min(r,g,b)
white_mask = (brightness >= 185) & (chroma < 40)
result[white_mask] = transparent
```

**问题**：  
- `chroma < 40` 过宽，猪身上的浅粉色高光（chroma ≈ 20-35）被误判为白色背景删除。
- 导致猪身体出现"空洞"，蹄子、眼睛等小特征被整块删掉。

### 方案二：收紧饱和度阈值（chroma < 15）

```python
white_mask = (brightness >= 190) & (chroma < 15)
```

**问题**：  
- 阈值过严，背景中色调略微偏暖（chroma ≈ 15-25）的像素不被识别为背景。
- 尤其是 AI 生成图片中因 JPEG 压缩或渲染产生的轻微色偏背景区域，无法被清除。

### 方案三：合成白底 + chroma 阈值

在处理之前先把原图合成到纯白背景（解决原始透明区域问题），再用 chroma 判断。

**问题**：  
- 合成后，原本半透明的猪身边缘像素变成了轻微粉白色，chroma 接近临界值（12-18），容易在严格/宽松阈值之间左右为难。
- 实际上还是依赖 chroma，本质问题未解决。

---

## 最终可靠方案

### 核心思路：`min(r, g, b) > 220` 作为背景判断标准

**为什么这个方法有效：**

| 像素类型 | 典型颜色值 | `min(r,g,b)` | 判断结果 |
|---------|-----------|-------------|--------|
| 纯白背景 | (255, 255, 255) | 255 | 背景 ✓ |
| 近白灰背景 | (240, 240, 240) | 240 | 背景 ✓ |
| 猪粉色高光 | (245, 220, 210) | **210** | 保留 ✓ |
| 猪中等粉色 | (220, 170, 155) | **155** | 保留 ✓ |
| 眼睛/蹄子 | (50, 35, 30) | **30** | 保留 ✓ |

关键洞察：**白色背景三通道都高（min ≈ 255）；猪身粉色因含"蓝色"通道偏低，min 通常 ≤ 210，绝不会被误判**。这比 chroma（最大值-最小值）更稳定——chroma 容易受颜色偏移影响，而 min 通道直接反映"最暗通道"。

### 完整处理流程

```python
def remove_white_bg(path):
    img = Image.open(path).convert("RGBA")

    # Step 1: 合成到纯白底
    # 原因：AI 生成的 PNG 可能在背景区域有 alpha < 255 的像素
    # 不合成的话，这些"本来透明"的区域会被当作前景保留，导致棋盘格残留
    white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    white_bg.paste(img, mask=img)           # 按 alpha 合成到白底
    arr = np.array(white_bg, dtype=np.uint8)
    h, w = arr.shape[:2]

    # Step 2: 水印区域强制涂白（右下角 10%×25%）
    wm_h = int(h * 0.10)
    wm_w = int(w * 0.25)
    arr[h - wm_h:, w - wm_w:, :] = 255     # 强制为白，让 BFS 一并清掉

    r = arr[..., 0].astype(np.int32)
    g = arr[..., 1].astype(np.int32)
    b = arr[..., 2].astype(np.int32)

    # Step 3: 候选掩码 —— min(r,g,b) > 220
    MIN_THRESH = 220
    min_ch = np.minimum(np.minimum(r, g), b)
    bg_cand = (min_ch > MIN_THRESH)

    # Step 4: BFS 从四边出发，只在候选区域内扩散
    # 原因：全局阈值会把猪身体内部的封闭白色高光也删掉
    # BFS 只删"从外部连通到的"白色区域，内部孤立的白色区域保留
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

    # Step 5: 背景完全透明，主体完全不透明
    result = arr.copy()
    result[..., 3] = np.where(visited, 0, 255).astype(np.uint8)

    # Step 6: 连通域分析，去除孤立小像素团（水印碎片、噪点）
    alpha_mask = result[..., 3] > 0
    # ... BFS 标记连通域，删除 < min_keep 像素的小团 ...
    # min_keep = max(最大连通域 * 0.01, 50)

    return Image.fromarray(result, "RGBA")
```

### 参数选取指南

| 参数 | 推荐值 | 说明 |
|-----|--------|------|
| `MIN_THRESH` | `220` | 白底图片用 220；如果背景偏米黄可降到 210 |
| 水印区域 | 右下角 10%×25% | 根据实际水印位置调整 |
| `min_keep` | `max(max_size×0.01, 50)` | 保留 ≥50px 的前景团，防止删掉蹄子等小特征 |

---

## 为什么用 BFS 而不是全局阈值

```
         纯白背景
        /         \
      /             \
  猪边缘        腿之间的白色区域
  (min≈215)       (min=255, 与外部连通)
      \
    猪身体
    (min≈150)
```

- **全局阈值**：min>220 的像素全部删除，包括猪身体内部封闭的白色区域 → 猪身体出现空洞。
- **BFS 从四边出发**：只删除"从图像边界出发能连通到的"白色像素。猪身体内部被猪轮廓包围的任何浅色区域都无法被 BFS 到达，因此被安全保留。

---

## 踩坑总结

| 坑 | 原因 | 解决 |
|----|------|------|
| 蹄子和眼睛被删 | `chroma < 40` 过宽，dark small features connected to bg | 改用 `min_ch > 220` + BFS |
| 猪高光被删 | chroma 阈值设为 15 过窄，高光 chroma 约 20-35 | `min_ch` 直接避开此问题 |
| 棋盘格残留 | 原始 PNG 的半透明区域未处理 | Step 1 先合成到纯白底 |
| 水印未消除 | BFS 阈值太严，无法扩散到水印位置 | Step 2 先强制涂白再 BFS |
| 连通域误删小特征 | `min_keep = 300` 过大，小蹄子（~80px）被当噪点删掉 | 降低到 `max(…, 50)` |

---

## 相关文件

- `process_ham.py`：ham 角色的完整处理脚本（本方法的实现）
- `raw/ham/白底/`：原始白底 PNG 素材
- `processed/ham/`：处理后的透明背景精灵
- `runtime/.../img/ham/`：部署到游戏的最终图片
