# 吱吱吉 Shimeji

用一张静态卡通图自动生成桌面宠物帧序列，支持 wl_shimeji（Linux Wayland）和 Shimeji-ee（Windows/Mac）两种格式。

## 角色

一只穿蓝色背带裤的可爱小老鼠 🐭，名叫**吱吱吉**（Zhizhiji）。

## 动作状态

| 状态 | 帧文件 | 说明 |
|------|--------|------|
| 待机（趴着）| `idle_01.png` / `idle_02.png` | 静止趴在屏幕上 |
| 向左走 | `walk_left_01~04.png` | 4 帧行走循环 |
| 向右走 | `walk_right_01~04.png` | 4 帧行走循环 |
| 被拖拽 | `drag_01.png` | 被鼠标抓起时 |
| 下落 | `fall_01.png` / `fall_02.png` | 空中下落 |

## 文件说明

| 文件 / 目录 | 说明 |
|-------------|------|
| `gen_frames.py` | 去除白色背景，生成各状态帧图片 |
| `pack_wlshm.py` | 打包为 wl_shimeji（Linux Wayland）格式 |
| `export_shimeji_ee.py` | 导出为 Shimeji-ee（Windows/Mac）格式 |
| `frames/` | 生成的透明底 PNG 帧序列（源文件） |
| `output/` | 导出的成品 ZIP 包 |
| `raw/` | 原始素材图片 |
| `runtime/shimejiee-local/` | 本地可直接运行的 Shimeji-ee 环境 |

## 使用

```bash
# 安装依赖
pip install Pillow

# 1. 生成帧
python3 gen_frames.py

# 2a. 打包为 wl_shimeji 格式（Linux）
python3 pack_wlshm.py

# 2b. 导出为 Shimeji-ee 格式（Windows/Mac）
python3 export_shimeji_ee.py
```

## 本地直接运行（Windows）

项目已内置一份配置好的 Shimeji-ee 运行环境，**无需手动下载和配置**：

```
runtime/shimejiee-local/shimejiee/
```

只需安装 [Java 11+](https://adoptium.net)，然后双击运行：

```
runtime/shimejiee-local/shimejiee/Shimeji-ee.jar
```

吱吱吉会自动出现在屏幕上，右键托盘图标可以召唤更多或关闭。

### 运行环境说明

| 路径 | 说明 |
|------|------|
| `shimejiee/img/Zhizhiji/` | 吱吱吉的所有动作帧图片 |
| `shimejiee/img/Zhizhiji/conf/actions.xml` | 动作定义（帧、锚点、速度） |
| `shimejiee/img/Zhizhiji/conf/behaviors.xml` | 行为状态机（各状态触发权重） |
| `shimejiee/conf/` | Shimeji-ee 全局配置 |

## 从头部署（Windows）

如果需要在新机器上手动部署：

1. 下载 [Shimeji-ee](https://kilkakon.com/shimeji/)
2. 安装 [Java 11+](https://adoptium.net)
3. 把 `output/Zhizhiji.zip` 放到 Shimeji-ee 根目录
4. 双击 `Shimeji-ee.jar` 启动，右键托盘图标召唤
