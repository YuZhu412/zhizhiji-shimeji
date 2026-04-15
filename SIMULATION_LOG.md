# Zhizhiji 行为模拟器设计文档

> 记录用于调参的随机游走模拟器的设计原理、物理假设、搜索结果与最终配置。

---

## 一、问题背景

用户观察到 zhizhiji 在正常运行时，走路触发频率过高、每次移动距离过大，导致角色几分钟内就漂移到屏幕边缘并触发 WallCling 贴墙状态。

**目标：** 找到合适的参数组合，使首次触发 WallCling 的平均时间约为 **30 分钟**。

---

## 二、物理模型假设

### 2.1 时间单位

Shimeji-ee 引擎以固定帧率运行，每帧（tick）约 **40ms**（即 25fps）。

| 时间单位 | 换算 |
|---|---|
| 1 tick | 40 ms |
| 1 秒 | 25 ticks |
| 30 分钟 | 45,000 ticks |

### 2.2 屏幕坐标

模拟使用标准 1080p 屏幕宽度（1920px），角色初始位置为屏幕中央（x = 960）。

| 边界名 | x 坐标 | 来源 |
|---|---|---|
| Walk 左侧停止线 | `left + 60` = 60 | `actions.xml` Condition |
| Walk 右侧停止线 | `right - 60` = 1860 | `actions.xml` Condition |
| WallCling 左触发 | `left + 70` = 70 | `behaviors.xml` Condition |
| WallCling 右触发 | `right - 70` = 1850 | `behaviors.xml` Condition |

**重叠安全区：** Walk 停在 60px 处，WallCling 触发在 70px 处，10px 重叠确保走到边界后必然触发贴墙而非 OOB。

### 2.3 Walk 移动模型

- **Pose Velocity**：`±3 px/tick`（每 tick 移动 3 像素）
- **Walk 每次位移** = `min(velocity × duration, x - stop_boundary)`
  - 若未到达停止线：走满 `duration` ticks，位移 = `3 × duration`
  - 若中途到达停止线：提前停下，实际位移 = `x - stop_boundary`
- **WallCling 判定**：Walk 停下后，若 `x < left+70` 或 `x > right-70`，则触发 WallCling（视为本次模拟结束）

---

## 三、状态机模型

模拟完整还原 `behaviors.xml` 的 8 个状态及其转移规则。

```
                    ┌──────────────────────────────────────────────────┐
                    │                                                  │
         ┌──────────▼──────────┐         ┌──────────────────┐         │
    ┌───►│   Stand/StandRight  │────────►│      Sleep       │─────────┤
    │    └──────────┬──────────┘         └──────────────────┘         │
    │               │                                                  │
    │      WalkLeft │ WalkRight                                        │
    │               │                                                  │
    │    ┌──────────▼──────────┐                                       │
    │    │  WalkLeft/WalkRight │                                       │
    │    └──────────┬──────────┘                                       │
    │               │                                                  │
    │       ┌───────┴──────┐                                           │
    │       │              │                                           │
    │    (边界?)        (无边界)                                        │
    │       │              │                                           │
    │    ┌──▼──┐    ┌──────▼──────┐                                   │
    │    │WALL │    │    Laugh    │──────────────────────────────────►─┘
    │    │CLING│    └─────────────┘
    │    └─────┘
    │
    └─── Stand/StandRight ◄── WallCling（触发后可从贴墙返回，不在本模拟范围内）
```

### 状态持续时间

| 状态 | Duration（ticks） | 实际时长 |
|---|---|---|
| Stand / StandRight | 600 | 24 秒 |
| Sleep | 600 | 24 秒 |
| Laugh | 300 | 12 秒 |
| WalkLeft / WalkRight | ≤ walk_duration | ≤ walk_duration × 40ms |

### 状态转移权重

**Stand → 下一状态（当前参数）：**

| 下一状态 | 频率权重 | 实际概率 |
|---|---|---|
| WalkLeft | `walk_freq` | `walk_freq / total` |
| WalkRight | `walk_freq` | `walk_freq / total` |
| Sleep | 15 | 固定 |
| Stand（自循环） | `self_freq` | `self_freq / total` |

> `total = walk_freq × 2 + 15 + self_freq`，默认令 `self_freq = 100 - walk_freq × 2 - 15`

**WalkLeft/WalkRight → 下一状态：**

| 下一状态 | 频率权重 | 实际概率 |
|---|---|---|
| Laugh | 15 | 18.5% |
| Stand | 13 | 16.0% |
| StandRight | 13 | 16.0% |
| 继续同向 Walk | 20 | 24.7% |
| 反向 Walk | 20 | 24.7% |

---

## 四、模拟算法

```python
def simulate_once(params, x_start=960):
    x = x_start
    state = 'Stand'
    ticks = 0

    while True:
        if state in ('Stand', 'StandRight'):
            ticks += DUR_STAND
            if x < LEFT_CLING or x > RIGHT_CLING:   # 站立时已在边界区
                break
            state = sample_next_from_stand(params)

        elif state == 'Sleep':
            ticks += DUR_SLEEP
            state = 'Stand'

        elif state == 'Laugh':
            ticks += DUR_LAUGH
            state = 'Stand'

        elif state == 'WalkLeft':
            steps = min(walk_duration, (x - LEFT_STOP) / velocity)
            ticks += steps
            x -= velocity * steps
            if x < LEFT_CLING:                        # 到达边界 → WallCling
                break
            state = sample_next_from_walk()

        elif state == 'WalkRight':
            steps = min(walk_duration, (RIGHT_STOP - x) / velocity)
            ticks += steps
            x += velocity * steps
            if x > RIGHT_CLING:
                break
            state = sample_next_from_walk()

    return ticks * TICK_MS / 1000  # 返回秒数
```

每组参数运行 **2000~5000 次** 独立模拟，统计均值、中位数、P10、P90。

---

## 五、网格搜索结果

搜索范围：`walk_freq ∈ {5,8,10,12,15,18,20,25}`，`walk_duration ∈ {40,60,80,100,120,150,175}`

**当前参数（搜索前）：**

| walk_freq | walk_duration | 均值（分钟） | 中位数 | P10 | P90 |
|---|---|---|---|---|---|
| 25 | 175 | **2.8** | 2.2 | 0.6 | 5.9 |

**部分搜索结果（均值接近 30 分钟的组合）：**

| walk_freq | walk_duration | 均值（分钟） | 中位数 | P10 | P90 | 备注 |
|---|---|---|---|---|---|---|
| 5 | 80 | 40.1 | 30.8 | 8.5 | 82.7 | 偏高 |
| 8 | 60 | 39.5 | 30.2 | 9.2 | 82.0 | 偏高 |
| **10** | **60** | **31.6** | **24.2** | **7.6** | **65.8** | ✅ 推荐 |
| 12 | 60 | 27.2 | 20.8 | 6.2 | 56.0 | 略低 |
| 25 | 40 | 33.9 | 25.9 | 9.0 | 69.5 | 偏高方差 |

### 推荐参数：`walk_freq=10, walk_duration=60`

| 指标 | 数值 | 含义 |
|---|---|---|
| 均值 | 31.6 分钟 | 平均需要 ~30 分钟才触发 WallCling |
| 中位数 | 24.2 分钟 | 一半情况下超过 24 分钟才触发 |
| P10 | 7.6 分钟 | 最倒霉 10% 的情况约 7-8 分钟内触发 |
| P90 | 65.8 分钟 | 最幸运 10% 的情况超过 1 小时不触发 |

---

## 六、参数物理含义对比

### Walk 移动距离

| walk_duration | 单次最大位移 | 从中心到边界所需步数（理论） |
|---|---|---|
| 175（修改前） | 525 px | ~1.7 步 → 几乎 2 步就能到达 |
| **60（修改后）** | **180 px** | **~5 步** → 需要多次连续向同侧走 |

### Walk 触发概率

| walk_freq | 每次 Stand 结束后走路概率 | 平均每 N 次 Stand 触发一次走路 |
|---|---|---|
| 25（修改前） | 50%（25+25） | 每 2 次 Stand 就走一次 |
| **10（修改后）** | **20%（10+10）** | **每 5 次 Stand 才走一次** |

---

## 七、最终应用配置

### `actions.xml` 修改

```xml
<!-- 修改前 -->
<Action Name="WalkLeft"  Duration="175" .../>
<Action Name="WalkRight" Duration="175" .../>

<!-- 修改后 -->
<Action Name="WalkLeft"  Duration="60" .../>
<Action Name="WalkRight" Duration="60" .../>
```

### `behaviors.xml` 修改（Stand / StandRight）

```xml
<!-- 修改前 -->
<BehaviorReference Name="WalkLeft"  Frequency="25"/>
<BehaviorReference Name="WalkRight" Frequency="25"/>
<BehaviorReference Name="Sleep"     Frequency="15"/>
<BehaviorReference Name="Stand"     Frequency="35"/>

<!-- 修改后 -->
<BehaviorReference Name="WalkLeft"  Frequency="10"/>
<BehaviorReference Name="WalkRight" Frequency="10"/>
<BehaviorReference Name="Sleep"     Frequency="15"/>
<BehaviorReference Name="Stand"     Frequency="65"/>
```

---

## 八、调参建议

若实际观感需要微调，参照以下方向：

| 需求 | 操作 | 预期效果 |
|---|---|---|
| 走路更频繁，但仍 ~30 分钟贴墙 | `walk_freq` 从 10→12，`walk_duration` 从 60→50 | 两者互补，均值基本不变 |
| 更慢贴墙（>30 分钟） | `walk_freq` 从 10→8，或 `walk_duration` 从 60→40 | 均值升至 ~40 分钟 |
| 更快贴墙（<30 分钟） | `walk_freq` 从 10→15 | 均值降至 ~14 分钟 |
| 减少 P10（避免"倒霉的早贴墙"） | 减小 `walk_duration`，增大 `walk_freq` | 减小单步偏移，随机性更均匀 |

> 修改参数后，重新运行 `py simulate_zhizhiji.py` 验证新均值，再重启 shimejiee 生效。

---

## 九、模型局限性

1. **屏幕宽度假设**：模拟使用 1920px。若用户屏幕更窄（如 1280px），实际贴墙时间会更短；更宽则更长。可在脚本中修改 `SCREEN_W` 参数重新搜索。

2. **WallCling 后的行为未建模**：模拟在第一次触发 WallCling 时停止，不模拟贴墙后返回 Stand 再继续游走的循环过程。实际中 WallCling 是可重复触发的。

3. **tick 速率误差**：实际帧率受系统负载影响，40ms/tick 为理论值，真实值可能在 35~50ms 之间波动。

4. **单屏幕模型**：模拟为 1D 随机游走，不考虑多显示器场景。
