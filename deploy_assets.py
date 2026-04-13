"""
deploy_assets.py
将 processed/<角色>/ 下的成品图片部署到 runtime 运行目录。

工作流：
  1. 在 processed/<角色>/ 里准备好处理后的图片
  2. 运行此脚本，图片自动复制到 runtime/img/<角色>/
  3. 重启 Shimeji-ee 即可看到效果

用法：
    py -3 deploy_assets.py              # 部署所有角色
    py -3 deploy_assets.py Zhizhiji     # 只部署指定角色
    py -3 deploy_assets.py Zhizhiji ham # 部署多个指定角色
"""

import os, sys, shutil

BASE      = os.path.dirname(__file__)
PROCESSED = os.path.join(BASE, "processed")
RUNTIME   = os.path.join(BASE, "runtime", "shimejiee-local", "shimejiee", "img")


def deploy(character: str):
    src_dir = os.path.join(PROCESSED, character)
    dst_dir = os.path.join(RUNTIME, character)

    if not os.path.isdir(src_dir):
        print(f"  [skip] processed/{character}/ 不存在")
        return
    if not os.path.isdir(dst_dir):
        print(f"  [skip] runtime/img/{character}/ 不存在，请先用 ADD_NEW_CHARACTER.md 的步骤创建角色")
        return

    files = [f for f in os.listdir(src_dir) if f.endswith(".png")]
    if not files:
        print(f"  [skip] processed/{character}/ 里没有 png 文件")
        return

    for f in sorted(files):
        shutil.copy(os.path.join(src_dir, f), dst_dir)
    print(f"  [ok]   {character}/ ← 已部署 {len(files)} 张图片: {', '.join(sorted(files))}")


def list_characters():
    if not os.path.isdir(PROCESSED):
        return []
    return [d for d in os.listdir(PROCESSED)
            if os.path.isdir(os.path.join(PROCESSED, d))]


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list_characters()

    if not targets:
        print("processed/ 目录为空，没有可部署的角色。")
        return

    print(f"部署目标: {', '.join(targets)}")
    print()
    for name in targets:
        deploy(name)
    print("\n完成。重启 Shimeji-ee 后生效。")


if __name__ == "__main__":
    main()
