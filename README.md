# 吱吱鸡 Shimeji

用一张静态卡通图自动生成桌面宠物帧序列，支持 wl_shimeji（Linux Wayland）和 Shimeji-ee（Windows/Mac）两种格式。

## 角色

一只穿蓝色背带裤的可爱小老鼠 🐭

## 文件说明

| 文件 | 说明 |
|------|------|
| `gen_frames.py` | 去除白色背景，生成各状态帧图片 |
| `pack_wlshm.py` | 打包为 wl_shimeji（Linux Wayland）格式 |
| `export_shimeji_ee.py` | 导出为 Shimeji-ee（Windows/Mac）格式 |
| `frames/` | 生成的透明底 PNG 帧序列 |
| `output/` | 导出的成品文件 |

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

## Windows 上运行

1. 下载 [Shimeji-ee](https://kilkakon.com/shimeji/)
2. 安装 [Java 11+](https://adoptium.net)
3. 把 `output/Zhizhiji_shimeji-ee.zip` 放到 Shimeji-ee 根目录
4. 双击 `Shimeji-ee.jar` 启动，右键托盘图标召唤
