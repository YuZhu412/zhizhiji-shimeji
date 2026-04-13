"""
sync_config.py
将 Zhizhiji 的 actions.xml / behaviors.xml 同步到其他所有角色。

用法：
    py -3 sync_config.py              # 同步所有角色
    py -3 sync_config.py ham          # 只同步指定角色
"""

import shutil, os, sys

IMG_DIR = os.path.join(os.path.dirname(__file__),
                       "runtime", "shimejiee-local", "shimejiee", "img")
SOURCE  = os.path.join(IMG_DIR, "Zhizhiji", "conf")
FILES   = ["actions.xml", "behaviors.xml"]

# ── 需要同步的角色列表（加新角色时在这里追加）──────────────────────
TARGETS = [
    "ham",
]
# ───────────────────────────────────────────────────────────────────

def sync(name: str):
    dst = os.path.join(IMG_DIR, name, "conf")
    if not os.path.isdir(dst):
        print(f"  [skip] {name}/conf/ 不存在，请先创建角色文件夹")
        return
    for f in FILES:
        shutil.copy(os.path.join(SOURCE, f), dst)
    print(f"  [ok]   {name}/conf/ 已同步")

def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else TARGETS
    print(f"source: Zhizhiji/conf/")
    print(f"files:  {', '.join(FILES)}")
    print()
    for name in targets:
        sync(name)
    print("\n完成。")

if __name__ == "__main__":
    main()
