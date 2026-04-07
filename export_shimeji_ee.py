"""
导出为 Shimeji-ee 格式 zip，可在 Windows/Mac/Linux 的 Shimeji-ee 程序中使用
Shimeji-ee 下载：https://kilkakon.com/shimeji/
"""

import os, sys, zipfile, shutil, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'shimejictl'))

FRAMES_DIR  = os.path.join(os.path.dirname(__file__), 'frames')
OUT_DIR     = os.path.join(os.path.dirname(__file__), 'output')
MASCOT_NAME = 'Zhizhiji'
IMG_W, IMG_H = 113, 128
ANCHOR_X    = IMG_W // 2
ANCHOR_Y    = IMG_H
WALK_VX     = 3
FRAME_DUR   = 8

def make_pose(image_name, vx=0, vy=0, dur=FRAME_DUR):
    path = f"/img/{MASCOT_NAME}/{image_name}"
    return (
        f'        <Pose Image="{path}" '
        f'ImageAnchor="{ANCHOR_X},{ANCHOR_Y}" '
        f'Velocity="{vx},{vy}" '
        f'Duration="{dur}"/>'
    )

def make_actions_xml():
    NS = 'http://www.group-finity.com/Mascot'
    walk_left_poses  = '\n'.join(make_pose(f'walk_left_{i:02d}.png',  vx=-WALK_VX) for i in range(1,5))
    walk_right_poses = '\n'.join(make_pose(f'walk_right_{i:02d}.png', vx= WALK_VX) for i in range(1,5))
    idle_poses       = '\n'.join(make_pose(f'idle_{i:02d}.png') for i in range(1,3))
    fall_poses       = '\n'.join(make_pose(f'fall_{i:02d}.png', vy=3) for i in range(1,3))
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

def make_behaviors_xml():
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

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    out_zip = os.path.join(OUT_DIR, f'{MASCOT_NAME}_shimeji-ee.zip')

    png_files = [f for f in sorted(os.listdir(FRAMES_DIR))
                 if f.endswith('.png') and f != 'base_transparent.png']

    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        # XML 配置文件
        zf.writestr(f'conf/actions.xml',   make_actions_xml())
        zf.writestr(f'conf/behaviors.xml', make_behaviors_xml())
        print('✓ 写入 conf/actions.xml')
        print('✓ 写入 conf/behaviors.xml')

        # 图片
        for fname in png_files:
            src = os.path.join(FRAMES_DIR, fname)
            arcname = f'img/{MASCOT_NAME}/{fname}'
            zf.write(src, arcname)
            print(f'✓ 写入 {arcname}')

    size_kb = os.path.getsize(out_zip) // 1024
    print(f'\n✓ 导出完成！')
    print(f'  文件：{out_zip}')
    print(f'  大小：{size_kb} KB')
    print(f"""
─────────────────────────────────────────────────
在 Windows 上使用步骤：

1. 下载 Shimeji-ee：
   https://kilkakon.com/shimeji/

2. 解压 Shimeji-ee，把 {MASCOT_NAME}_shimeji-ee.zip
   放到 Shimeji-ee 的根目录

3. 双击 Shimeji-ee.jar 启动
   （需要 Java 11+，可从 https://adoptium.net 下载）

4. 在系统托盘右键 → 点击角色名称召唤

注意：Shimeji-ee 支持多角色，可以把多个 zip 放在同一目录
─────────────────────────────────────────────────
""")

if __name__ == '__main__':
    main()
