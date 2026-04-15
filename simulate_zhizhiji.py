# -*- coding: utf-8 -*-
"""
Zhizhiji 行为模拟器
================
模拟角色在屏幕上的随机游走，找出让首次 WallCling 平均发生在 ~30 分钟后的参数组合。

物理模型：
  - 每个 game-tick ≈ 40ms（Shimeji-ee 约 25fps）
  - WalkLeft/Right Pose Velocity=±3：每 tick 移动 3px
  - Walk 停止条件：x ≤ left+60（WalkLeft）/ x ≥ right-60（WalkRight）
  - WallCling 触发：walk 停下时 x < left+70 / x > right-70 → 必然 WallCling
  - Stand 中如果已处于 WallCling 区内，也触发 WallCling
"""

import random
import statistics
import itertools

# ── 固定参数 ─────────────────────────────────────────────────────────────────
TICK_MS           = 40          # 每 tick 毫秒数
SCREEN_W          = 1920        # 屏幕宽度（像素）
WALK_VELOCITY     = 3           # px/tick（pose velocity）
WALK_STOP_MARGIN  = 60          # Walk 停止边距（actions.xml 条件）
WALLCLING_MARGIN  = 70          # WallCling 触发边距（behaviors.xml 条件）

LEFT_STOP     = WALK_STOP_MARGIN          # x ≤ this → WalkLeft 停下
RIGHT_STOP    = SCREEN_W - WALK_STOP_MARGIN
LEFT_CLING    = WALLCLING_MARGIN          # x < this → WallClingLeft
RIGHT_CLING   = SCREEN_W - WALLCLING_MARGIN

# 固定行为持续时间
DUR_STAND  = 600    # Stand / StandRight
DUR_SLEEP  = 600    # Sleep
DUR_LAUGH  = 300    # Laugh


def simulate_once(
    stand_walk_freq,   # Stand 中 WalkLeft+WalkRight 各自的频率（当前=25）
    stand_sleep_freq,  # Stand 中 Sleep 频率（当前=15）
    stand_self_freq,   # Stand 自循环频率（当前=35）
    walk_duration,     # Walk Action Duration（当前=175 ticks）
    post_walk_laugh,   # WalkLeft/Right 后 Laugh 频率（当前=15）
    post_walk_stand,   # WalkLeft/Right 后 Stand 频率（当前=13）
    post_walk_walk,    # WalkLeft/Right 后同向 Walk 频率（当前=20）
    post_walk_opp,     # WalkLeft/Right 后反向 Walk 频率（当前=20）
    x_start=None,
    max_ticks=10_000_000,   # 安全上限（约 111 小时）
):
    """
    模拟一次从 x_start 出发，到第一次触发 WallCling 的时间（秒）。
    """
    x = x_start if x_start is not None else SCREEN_W / 2

    # Stand 转移权重
    w_walk_l  = stand_walk_freq
    w_walk_r  = stand_walk_freq
    w_sleep   = stand_sleep_freq
    w_stand   = stand_self_freq
    total_stand = w_walk_l + w_walk_r + w_sleep + w_stand

    # Walk 结束后转移权重
    total_post = post_walk_laugh + post_walk_stand * 2 + post_walk_walk + post_walk_opp

    state = 'Stand'
    ticks = 0

    while ticks < max_ticks:
        # ── Stand / StandRight ──────────────────────────────────────────────
        if state in ('Stand', 'StandRight'):
            ticks += DUR_STAND

            # 检查是否已在 WallCling 区（极少发生但要处理）
            if x < LEFT_CLING or x > RIGHT_CLING:
                break

            r = random.uniform(0, total_stand)
            if r < w_walk_l:
                state = 'WalkLeft'
            elif r < w_walk_l + w_walk_r:
                state = 'WalkRight'
            elif r < w_walk_l + w_walk_r + w_sleep:
                state = 'Sleep'
            else:
                state = 'StandRight' if state == 'Stand' else 'Stand'

        # ── Sleep ────────────────────────────────────────────────────────────
        elif state == 'Sleep':
            ticks += DUR_SLEEP
            state = 'Stand'

        # ── Laugh ────────────────────────────────────────────────────────────
        elif state == 'Laugh':
            ticks += DUR_LAUGH
            state = 'Stand'

        # ── WalkLeft ─────────────────────────────────────────────────────────
        elif state == 'WalkLeft':
            # 每 tick 移动 -3px，直到 x ≤ LEFT_STOP 或走满 walk_duration
            steps = min(walk_duration, max(0, int((x - LEFT_STOP) / WALK_VELOCITY)))
            actual_ticks = steps
            ticks += actual_ticks
            x -= WALK_VELOCITY * steps

            # 判断是否触发 WallCling
            if x < LEFT_CLING:
                break

            # Walk 结束后的转移
            r = random.uniform(0, total_post)
            if r < post_walk_laugh:
                state = 'Laugh'
            elif r < post_walk_laugh + post_walk_stand:
                state = 'Stand'
            elif r < post_walk_laugh + post_walk_stand * 2:
                state = 'StandRight'
            elif r < post_walk_laugh + post_walk_stand * 2 + post_walk_walk:
                state = 'WalkLeft'
            else:
                state = 'WalkRight'

        # ── WalkRight ────────────────────────────────────────────────────────
        elif state == 'WalkRight':
            steps = min(walk_duration, max(0, int((RIGHT_STOP - x) / WALK_VELOCITY)))
            actual_ticks = steps
            ticks += actual_ticks
            x += WALK_VELOCITY * steps

            if x > RIGHT_CLING:
                break

            r = random.uniform(0, total_post)
            if r < post_walk_laugh:
                state = 'Laugh'
            elif r < post_walk_laugh + post_walk_stand:
                state = 'Stand'
            elif r < post_walk_laugh + post_walk_stand * 2:
                state = 'StandRight'
            elif r < post_walk_laugh + post_walk_stand * 2 + post_walk_walk:
                state = 'WalkRight'
            else:
                state = 'WalkLeft'

    return ticks * TICK_MS / 1000.0  # 秒


def run_trials(n=3000, **kwargs):
    times = [simulate_once(**kwargs) for _ in range(n)]
    return {
        'mean_min':   statistics.mean(times) / 60,
        'median_min': statistics.median(times) / 60,
        'p10_min':    sorted(times)[int(n * 0.10)] / 60,
        'p90_min':    sorted(times)[int(n * 0.90)] / 60,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 第一步：测量当前参数的表现
# ══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("【当前参数测量】")
current = dict(
    stand_walk_freq  = 25,
    stand_sleep_freq = 15,
    stand_self_freq  = 35,
    walk_duration    = 175,
    post_walk_laugh  = 15,
    post_walk_stand  = 13,
    post_walk_walk   = 20,
    post_walk_opp    = 20,
)
r = run_trials(n=5000, **current)
print(f"  均值={r['mean_min']:.1f}分钟  中位={r['median_min']:.1f}分钟"
      f"  P10={r['p10_min']:.1f}  P90={r['p90_min']:.1f}")

# ══════════════════════════════════════════════════════════════════════════════
# 第二步：网格搜索
# 调节 stand_walk_freq（走路概率）和 walk_duration（单次走路距离）
# 目标：mean ≈ 30 分钟
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("【网格搜索：walk_freq × walk_duration】")
print(f"{'walk_freq':>10} {'walk_dur':>10} {'mean_min':>10} {'median_min':>11} {'P10':>7} {'P90':>7}")

TARGET_MIN = 30.0
TOLERANCE  = 5.0   # 接受 [25, 35] 分钟

best = []

for wf, wd in itertools.product(
    [5, 8, 10, 12, 15, 18, 20, 25],   # stand_walk_freq
    [40, 60, 80, 100, 120, 150, 175],  # walk_duration
):
    params = {**current, 'stand_walk_freq': wf, 'walk_duration': wd,
              # 调整 stand_self_freq 保持总和一致（Sleep 固定 15）
              'stand_self_freq': max(1, 100 - 2 * wf - 15)}
    r = run_trials(n=2000, **params)
    m = r['mean_min']
    tag = " ← 目标!" if abs(m - TARGET_MIN) < TOLERANCE else ""
    print(f"{wf:>10} {wd:>10} {m:>10.1f} {r['median_min']:>11.1f}"
          f" {r['p10_min']:>7.1f} {r['p90_min']:>7.1f}{tag}")
    if abs(m - TARGET_MIN) < TOLERANCE:
        best.append((m, wf, wd, r))

# ══════════════════════════════════════════════════════════════════════════════
# 第三步：输出推荐参数
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
if best:
    best.sort(key=lambda x: abs(x[0] - TARGET_MIN))
    m, wf, wd, r = best[0]
    print(f"【推荐参数】walk_freq={wf}, walk_duration={wd}")
    print(f"  均值={m:.1f}分钟  中位={r['median_min']:.1f}分钟"
          f"  P10={r['p10_min']:.1f}  P90={r['p90_min']:.1f}")
    print(f"\n  对应 behaviors.xml 修改：")
    print(f"    Stand NextBehaviorList:")
    print(f"      WalkLeft  Frequency=\"{wf}\"")
    print(f"      WalkRight Frequency=\"{wf}\"")
    print(f"      Sleep     Frequency=\"15\"  (不变)")
    sf = max(1, 100 - 2 * wf - 15)
    print(f"      Stand     Frequency=\"{sf}\"  (自动调整)")
    print(f"\n  对应 actions.xml 修改：")
    print(f"    WalkLeft/WalkRight Duration=\"{wd}\"")
else:
    print("未找到符合目标的参数，请扩展搜索范围。")
