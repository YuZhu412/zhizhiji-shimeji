"""
将帧序列打包成 wl_shimeji 格式的 .wlshm 文件
流程：
  1. 创建 Shimeji-EE 标准目录结构 + actions.xml + behaviors.xml
  2. 调用 wl_shimeji 自带的 Compiler 编译 XML → JSON
  3. 将图片转换为 QOI 格式
  4. 打包成 WLPK tar 格式的 .wlshm 文件
"""

import sys, os, io, json, tarfile, struct, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'shimejictl'))

from compiler import Compiler
from qoi.src.qoi import encode_img
from PIL import Image

# ─── 配置 ────────────────────────────────────────────────────────────────────
FRAMES_DIR   = os.path.join(os.path.dirname(__file__), 'frames')
OUT_DIR      = os.path.join(os.path.dirname(__file__), 'output')
MASCOT_NAME  = 'Zhizhiji'          # 吱吱鸡（其实是老鼠但叫啥都行）
IMG_W, IMG_H = 160, 160            # 统一画布尺寸
ANCHOR_X     = IMG_W // 2          # 脚部锚点 X（水平中心）
ANCHOR_Y     = IMG_H               # 脚部锚点 Y（画布底部）
WALK_VX      = 3                   # 走路速度（像素/帧）
FRAME_DUR    = 8                   # 每帧持续时间（tick）
# ─────────────────────────────────────────────────────────────────────────────

def make_pose(image_name: str, vx=0, vy=0, dur=FRAME_DUR) -> str:
    path = f"/img/{MASCOT_NAME}/{image_name}"
    return (
        f'<Pose Image="{path}" '
        f'ImageAnchor="{ANCHOR_X},{ANCHOR_Y}" '
        f'Velocity="{vx},{vy}" '
        f'Duration="{dur}"/>'
    )

def make_actions_xml() -> str:
    NS = 'http://www.group-finity.com/Mascot'

    walk_left_poses  = '\n        '.join(make_pose(f'walk_left_{i:02d}.png',  vx=-WALK_VX) for i in range(1,5))
    walk_right_poses = '\n        '.join(make_pose(f'walk_right_{i:02d}.png', vx= WALK_VX) for i in range(1,5))
    idle_poses       = '\n        '.join(make_pose(f'idle_{i:02d}.png') for i in range(1,3))
    fall_poses       = '\n        '.join(make_pose(f'fall_{i:02d}.png', vy=3) for i in range(1,3))
    drag_poses       = make_pose('drag_01.png')

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Mascot xmlns="{NS}">
  <ActionList>

    <Action Name="WalkLeft" Type="Move" Loop="true"
            InitialVX="-{WALK_VX}" InitialVY="0"
            BorderType="Floor">
      <Animation>
        {walk_left_poses}
      </Animation>
    </Action>

    <Action Name="WalkRight" Type="Move" Loop="true"
            InitialVX="{WALK_VX}" InitialVY="0"
            BorderType="Floor">
      <Animation>
        {walk_right_poses}
      </Animation>
    </Action>

    <Action Name="Stand" Type="Stay" Loop="true"
            BorderType="Floor">
      <Animation>
        {idle_poses}
      </Animation>
    </Action>

    <Action Name="Fall" Type="Embedded" Loop="true"
            Class="com.group_finity.mascot.action.Fall"
            InitialVX="0" InitialVY="0"
            Gravity="2">
      <Animation>
        {fall_poses}
      </Animation>
    </Action>

    <Action Name="Dragged" Type="Embedded" Loop="true"
            Class="com.group_finity.mascot.action.Dragged">
      <Animation>
        {drag_poses}
      </Animation>
    </Action>

    <Action Name="Thrown" Type="Embedded" Loop="true"
            Class="com.group_finity.mascot.action.Fall"
            InitialVX="0" InitialVY="-20"
            Gravity="2">
      <Animation>
        {fall_poses}
      </Animation>
    </Action>

  </ActionList>
</Mascot>
"""

def make_behaviors_xml() -> str:
    NS = 'http://www.group-finity.com/Mascot'
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Mascot xmlns="{NS}">
  <BehaviorList>

    <Behavior Name="Stand" Frequency="30" Action="Stand">
      <NextBehaviorList>
        <BehaviorReference Name="WalkLeft"  Frequency="25"/>
        <BehaviorReference Name="WalkRight" Frequency="25"/>
        <BehaviorReference Name="Stand"     Frequency="50"/>
      </NextBehaviorList>
    </Behavior>

    <Behavior Name="WalkLeft" Frequency="35" Action="WalkLeft">
      <NextBehaviorList>
        <BehaviorReference Name="Stand"      Frequency="30"/>
        <BehaviorReference Name="WalkLeft"   Frequency="40"/>
        <BehaviorReference Name="WalkRight"  Frequency="30"/>
      </NextBehaviorList>
    </Behavior>

    <Behavior Name="WalkRight" Frequency="35" Action="WalkRight">
      <NextBehaviorList>
        <BehaviorReference Name="Stand"      Frequency="30"/>
        <BehaviorReference Name="WalkLeft"   Frequency="30"/>
        <BehaviorReference Name="WalkRight"  Frequency="40"/>
      </NextBehaviorList>
    </Behavior>

    <Behavior Name="Fall" Frequency="0" Action="Fall">
      <NextBehaviorList>
        <BehaviorReference Name="Stand" Frequency="100"/>
      </NextBehaviorList>
    </Behavior>

    <Behavior Name="Dragged" Frequency="0" Action="Dragged">
      <NextBehaviorList>
        <BehaviorReference Name="Stand" Frequency="100"/>
      </NextBehaviorList>
    </Behavior>

    <Behavior Name="Thrown" Frequency="0" Action="Thrown">
      <NextBehaviorList>
        <BehaviorReference Name="Fall" Frequency="100"/>
      </NextBehaviorList>
    </Behavior>

  </BehaviorList>
</Mascot>
"""

def build_wlshm():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── 搭建 Shimeji-EE 格式临时目录 ──────────────────────────────────────
    tmpdir = tempfile.mkdtemp(prefix='zhizhiji_shimeji_')
    try:
        img_dir  = os.path.join(tmpdir, 'img', MASCOT_NAME)
        conf_dir = os.path.join(tmpdir, 'conf')
        os.makedirs(img_dir,  exist_ok=True)
        os.makedirs(conf_dir, exist_ok=True)

        # 复制帧图片
        png_files = [f for f in os.listdir(FRAMES_DIR) if f.endswith('.png') and f != 'base_transparent.png']
        for f in png_files:
            shutil.copy(os.path.join(FRAMES_DIR, f), os.path.join(img_dir, f))
        print(f'复制了 {len(png_files)} 张帧图片')

        # 写 XML
        with open(os.path.join(conf_dir, 'actions.xml'), 'w', encoding='utf-8') as fp:
            fp.write(make_actions_xml())
        with open(os.path.join(conf_dir, 'behaviors.xml'), 'w', encoding='utf-8') as fp:
            fp.write(make_behaviors_xml())
        print('生成了 actions.xml 和 behaviors.xml')

        # ── 编译 XML → JSON ────────────────────────────────────────────────
        conf_dirfd = os.open(conf_dir, os.O_PATH)
        try:
            print('编译配置...')
            scripts_json, actions_json, behaviors_json = Compiler.compile_shimeji(img_dir, conf_dirfd)
        finally:
            os.close(conf_dirfd)
        print('编译成功')

        # ── 构建 manifest ─────────────────────────────────────────────────
        manifest = {
            'name':         f'Shimeji.{MASCOT_NAME}',
            'version':      '0.1.0',
            'description':  '吱吱鸡桌宠',
            'display_name': MASCOT_NAME,
            'programs':     'scripts.json',
            'actions':      'actions.json',
            'behaviors':    'behaviors.json',
            'assets':       'assets',
            'icon':         None,
            'artist':       None,
            'scripter':     None,
            'commissioner': None,
            'support':      None
        }

        # ── 打包成 tar + WLPK 头 ─────────────────────────────────────────
        memfile = io.BytesIO()
        tar = tarfile.open(fileobj=memfile, mode='w')

        def add_str(name, content):
            data = content.encode('utf-8')
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))

        add_str('manifest.json', json.dumps(manifest))
        add_str('scripts.json',  scripts_json)
        add_str('actions.json',  actions_json)
        add_str('behaviors.json', behaviors_json)

        # 资产目录
        ti = tarfile.TarInfo('assets/')
        ti.type = tarfile.DIRTYPE
        tar.addfile(ti)

        # 图片 PNG → QOI
        for png_file in png_files:
            src_path = os.path.join(img_dir, png_file)
            img = Image.open(src_path)
            qoi_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.qoi')
            qoi_tmp.close()
            encode_img(img, False, qoi_tmp.name)
            qoi_name = os.path.splitext(png_file)[0] + '.qoi'
            with open(qoi_tmp.name, 'rb') as qf:
                ti = tarfile.TarInfo(f'assets/{qoi_name}')
                ti.size = os.path.getsize(qoi_tmp.name)
                tar.addfile(ti, qf)
            os.remove(qoi_tmp.name)
            print(f'  → assets/{qoi_name}')

        tar.close()

        # ── 写 .wlshm 文件 ────────────────────────────────────────────────
        name_bytes    = manifest['name'].encode('utf-8')
        version_bytes = manifest['version'].encode('utf-8')
        header = b'WLPK'
        header += struct.pack(f'B{len(name_bytes)}s',    len(name_bytes),    name_bytes)
        header += struct.pack(f'B{len(version_bytes)}s', len(version_bytes), version_bytes)
        header += b'\x00' * (512 - len(header))

        out_path = os.path.join(OUT_DIR, f'Shimeji.{MASCOT_NAME}.wlshm')
        with open(out_path, 'wb') as fp:
            fp.write(header)
            fp.write(memfile.getvalue())

        size_kb = os.path.getsize(out_path) // 1024
        print(f'\n✓ 打包完成！')
        print(f'  文件：{out_path}')
        print(f'  大小：{size_kb} KB')
        print(f'\n下一步，导入到 wl_shimeji：')
        print(f'  shimejictl prototypes import {out_path}')
        print(f'  shimejictl mascot summon {MASCOT_NAME}')

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == '__main__':
    build_wlshm()
