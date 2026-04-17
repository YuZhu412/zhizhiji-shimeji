# 吱吱吉桌面宠物 - 行为逻辑说明

## 动作列表

| 动作名 | 类型 | 图片帧 | 速度 | 单帧时长 | 总持续时长 |
|--------|------|--------|------|----------|-----------|
| **Stand**（趴着） | Stay（原地停留） | idle_01 / idle_02 轮播 | 不移动 | 2秒/张 | **24秒** |
| **WalkLeft**（向左走） | Move（移动） | walk_right_01~04 循环 | 每帧左移 3px | 0.32秒/张 | 无限（直到出界） |
| **WalkRight**（向右走） | Move（移动） | walk_left_01~04 循环 | 每帧右移 3px | 0.32秒/张 | 无限（直到出界） |
| **Fall**（下落） | Embedded | fall_01 / fall_02 循环 | 重力加速下落 | 0.32秒/张 | 直到落地 |
| **Dragged**（被拖拽） | Embedded | drag_01 | 跟随鼠标 | — | 拖着就一直播 |
| **Thrown**（被扔出） | Embedded | fall_01 / fall_02 | 初速向上，重力加速 | 0.32秒/张 | 直到落地 |

> 每帧（tick）= 40ms，所有时长均由帧数换算而来。

---

## 行为转换概率

### 启动 / 落地后（无前一状态）

从屏幕上方落下并着陆后，按以下概率随机选择下一个行为：

| 行为 | 权重 | 概率 |
|------|------|------|
| Stand（趴着） | 30 | **30%** |
| WalkLeft（向左走） | 35 | **35%** |
| WalkRight（向右走） | 35 | **35%** |

### Stand 结束后（趴满 24 秒）

趴着自然结束后，按以下概率转换（全局权重 + NextBehaviorList 叠加）：

| 行为 | 权重合计 | 概率 |
|------|---------|------|
| Stand（继续趴） | 30+50=80 | **40%** |
| WalkLeft | 35+25=60 | **30%** |
| WalkRight | 35+25=60 | **30%** |

### WalkLeft / WalkRight 结束后

走路**没有时间限制**，会一直走到屏幕边界出界，触发 LostGround 异常 → 进入 Fall → 落地后重新按"无前一状态"概率选择（即重置为 30% Stand / 70% Walk）。

> 因此走路过程中不会直接转换为趴着，只有每次落地时才有 30% 概率触发趴着。

---

## 鼠标交互

| 操作 | 触发行为 | 说明 |
|------|----------|------|
| 左键拖拽 | Dragged | 角色跟随鼠标，播放拖拽图 |
| 松开鼠标 | Thrown | 以向上初速飞出，然后重力落下 |
| 落地后 | 重新随机选 | 30% 趴着 / 70% 走路 |

---

## 完整状态流程

```
启动
  └→ Fall（从屏幕上方落下）
       └→ 落到地板线（Y = WorkArea 底部）
            └→ 随机选（30% / 35% / 35%）
                 ├→ Stand（趴 24 秒）
                 │    └→ 随机选（40% / 30% / 30%）──→ 循环
                 │
                 ├→ WalkLeft（向左走，无限）
                 │    └→ 走出屏幕左边界
                 │         └→ Fall → 落地 → 重新随机
                 │
                 └→ WalkRight（向右走，无限）
                      └→ 走出屏幕右边界
                           └→ Fall → 落地 → 重新随机

用户拖拽
  └→ Dragged → 松手 → Thrown → Fall → 落地 → 重新随机
```

---

## 地板定义

Shimeji-ee 的"地板"是任务栏顶部边缘那条像素线（`WorkArea.bottom`），角色锚点的 Y 坐标必须**精确等于**该值才被认为站在地板上。

角色图片尺寸为 160×160px，锚点为图片底部中心 `(80, 160)`，所以角色视觉上的脚踩在任务栏顶边，身体悬浮于桌面上方。

---

## 亲和力（Affordance）系统 — 多角色相遇互动

### 概述

当桌面同时存在多只宠物时，引擎内置了一套 **Affordance（亲和力）广播/扫描机制**，让两只宠物能感知到彼此并触发专属互动动画，无需修改任何 Java 代码，纯 XML 配置驱动。

---

### 核心概念

| 概念 | 说明 |
|------|------|
| **Affordance 标记** | 一个字符串（如 `"greet"`），由"等待被接近"的宠物广播出去，挂在自己身上 |
| **广播方（Broadcaster）** | 进入某个 Stay 行为时，通过 `Affordance` 属性对外宣告自己可被互动 |
| **扫描方（Scanner）** | 进入 `ScanMove` / `ScanInteract` 行为时，全局搜索持有指定 affordance 的宠物 |
| **触发条件** | 扫描方到达广播方的坐标后，双方**同时**切换到各自的互动行为 |

---

### 三种互动 Action 类型

#### `ScanMove` — 主动靠近并互动

> 来源：`action/ScanMove.java`

扫描方搜索持有 affordance 的宿主，找到后**走过去**，到达同一坐标时触发双方行为。

关键参数：

| 参数 | 含义 |
|------|------|
| `Affordance` | 要搜索的标记字符串 |
| `Behavior` | 到达后**自身**跳转的行为名（⚠️ 英文 schema 里是 American 拼写 `Behavior`，**不是** `Behaviour`；写错会弹 "Failed to set behaviour. There is no corresponding behaviour ()") |
| `TargetBehavior` | 到达后**目标**跳转的行为名 |
| `TargetLook="true"` | 让双方自动面对面（方向相反） |

#### `ScanInteract` — 原地朝向并互动

> 来源：`action/ScanInteract.java`

与 ScanMove 类似，但扫描方**原地播放动画**并朝向目标，不主动移动。适合"对视"类互动。

#### `Interact` — 重叠触发

> 来源：`action/Interact.java`  
> 触发条件：`manager.hasOverlappingMascotsAtPoint(anchor)` — 两只宠物锚点完全重叠

两只宠物在完全相同的坐标重叠时才播放动画，结束后跳转到指定行为。

---

### 完整触发流程（以 ham + zhizhiji 相遇为例）

```
ham 随机进入 GreetWait 行为
  └→ Stay Action 上设置 Affordance="greet"
       └→ ham.getAffordances().add("greet")   ← 广播自己可被接近

Zhizhiji 随机进入 ScanGreet 行为
  └→ ScanMove Action
       └→ manager.getMascotWithAffordance("greet") → 找到 ham
            └→ 每 tick 驱动 Zhizhiji 向 ham 坐标移动
                 └→ 到达 ham.anchor 后：
                      Zhizhiji.setBehavior("GreetAct")    ← 播放挥手动画
                      ham.setBehavior("GreetReact")       ← ham 同步回应
                      TargetLook=true → 两人自动面对面
```

---

### 配置示例

#### ham 的配置（广播方）

`img/ham/conf/actions.xml` 追加：

```xml
<!-- ham 进入此 Action 时广播 "greet"，等待被接近 -->
<Action Name="GreetWait" Type="Stay" BorderType="Floor" Duration="300"
        Affordance="greet">
  <Animation>
    <Pose Image="/greet_wait_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="50"/>
  </Animation>
</Action>

<!-- ham 被接近后的回应动画 -->
<Action Name="GreetReact" Type="Animate">
  <Animation>
    <Pose Image="/greet_react_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="50"/>
    <Pose Image="/greet_react_02.png" ImageAnchor="80,160" Velocity="0,0" Duration="50"/>
  </Animation>
</Action>
```

`img/ham/conf/behaviors.xml` 追加：

```xml
<!-- Frequency 控制自然触发概率，越高越容易随机进入 -->
<Behavior Name="GreetWait" Frequency="10" Action="GreetWait">
  <NextBehaviorList>
    <BehaviorReference Name="Stand" Frequency="100"/>
  </NextBehaviorList>
</Behavior>

<!-- Frequency="0" 表示不会自然触发，只能被 ScanMove 强制跳转 -->
<Behavior Name="GreetReact" Frequency="0" Action="GreetReact">
  <NextBehaviorList>
    <BehaviorReference Name="Stand" Frequency="100"/>
  </NextBehaviorList>
</Behavior>
```

#### zhizhiji 的配置（扫描方）

`img/Zhizhiji/conf/actions.xml` 追加：

```xml
<!-- Zhizhiji 扫描持有 "greet" 的宠物并走过去，到达后双方跳转行为 -->
<!-- ⚠️ 不加 BorderType="Floor"：ScanMove 的 vy=0 不需要地板，且两角色"地板集合"不同会误报 LostGround -->
<!-- ⚠️ Velocity 取负：Pose.next 里 dx 会被 lookRight 翻转，负数保证永远朝目标方向走 -->
<!-- ⚠️ 图像用 walk_right_*.png（原图朝左）：lookRight=false→原图朝左，lookRight=true→flip 后朝右，两向都对 -->
<Action Name="ScanGreet" Type="Embedded"
        Class="com.group_finity.mascot.action.ScanMove"
        Affordance="greet"
        Behavior="GreetAct"
        TargetBehavior="GreetReact"
        TargetLook="true">
  <Animation>
    <Pose Image="/walk_right_01.png" ImageAnchor="80,160" Velocity="-4,0" Duration="8"/>
    <Pose Image="/walk_right_02.png" ImageAnchor="80,160" Velocity="-4,0" Duration="8"/>
    <Pose Image="/walk_right_03.png" ImageAnchor="80,160" Velocity="-4,0" Duration="8"/>
    <Pose Image="/walk_right_04.png" ImageAnchor="80,160" Velocity="-4,0" Duration="8"/>
  </Animation>
</Action>

<!-- Zhizhiji 到达后播放的互动动画 -->
<!-- ScanMove 会把扫描方 anchor 强制设为与目标完全重合；用第一帧 Velocity 一次性错开 130px 避免重叠 -->
<!-- ⚠️ pose1.Duration 必须 >= 2（新 Action 首帧 getTime()=1 不是 0，Duration=1 的 pose1 会被跳过） -->
<!-- ⚠️ pose2.Duration 必须让 anim 总长 > Action.Duration，否则循环回 pose1 导致"一直后退" -->
<Action Name="GreetAct" Type="Stay" BorderType="Floor" Duration="300">
  <Animation>
    <Pose Image="/laugh_01.png" ImageAnchor="80,160" Velocity="130,0" Duration="2"/>
    <Pose Image="/laugh_01.png" ImageAnchor="80,160" Velocity="0,0"   Duration="300"/>
  </Animation>
</Action>
```

`img/Zhizhiji/conf/behaviors.xml` 追加：

```xml
<Behavior Name="ScanGreet" Frequency="5" Action="ScanGreet">
  <NextBehaviorList>
    <BehaviorReference Name="Stand" Frequency="100"/>
  </NextBehaviorList>
</Behavior>

<Behavior Name="GreetAct" Frequency="0" Action="GreetAct">
  <NextBehaviorList>
    <BehaviorReference Name="Stand" Frequency="100"/>
  </NextBehaviorList>
</Behavior>
```

---

### 注意事项

| 问题 | 说明 |
|------|------|
| 扫描方清空 affordance | `ScanMove.init()` 会调用 `getAffordances().clear()`，所以一只宠物**不能同时既扫描又广播** |
| 跨角色类型支持 | `getMascotWithAffordance()` 搜索全部宠物，zhizhiji 可以找到 ham，反之亦然 |
| 目标消失处理 | 若广播方在扫描途中结束了 GreetWait，`hasNext()` 返回 false，扫描方自动退出行为 |
| Frequency 调优 | 降低 ScanGreet/GreetWait 的 Frequency 可以让相遇概率更低、更稀有 |
| 需要配套动画帧 | 上述配置依赖实际存在的 PNG 文件；若图片不存在，Action 初始化时会报错 |

---

## 实战踩坑 & 底层约定（打招呼互动调试沉淀）

以下是在实现"吱吱吉 + ham 相遇击掌"功能过程中踩到的非显式约定，详细问题/日志/修复见 [BUGFIX_LOG.md Bug #5](../BUGFIX_LOG.md)。

### 1. 位移方向：`Velocity` 会被 `lookRight` 翻转

`Pose.next()` 的实际位移逻辑：

```java
newX = anchor.x + (mascot.isLookRight() ? -getDx() : getDx())
```

- `lookRight=false`（朝左）时：`x = x + dx`，`dx` 正数向右走
- `lookRight=true`（朝右）时：`x = x - dx`，`dx` 正数反而向左走
- `ScanMove` 每 tick 根据 `anchor.x vs TargetX` 动态 `setLookRight`

**约定**：`ScanMove` / `Move` 动作要"朝自己当前朝向走"时，`Velocity` 的 dx **取负**。

### 2. 图像朝向：`walk_*.png` 文件名与视觉方向相反

- 吱吱吉的 `walk_right_*.png` 原图**实际朝左**；`walk_left_*.png` 原图**实际朝右**
- `ImagePairLoader` 若 `rightPath` 未指定，会把 `leftImage` 水平翻转生成 rightImage
- `ImagePair.getImage(lookRight)` 根据 `lookRight` 选择原图 / flip 版本

**约定**：单 Animation 块配合 `ScanMove` 自动 `setLookRight`，`Pose Image` 统一选**原图朝向与 `lookRight=false` 目标方向一致**的文件。吱吱吉追 ham 用 `walk_right_*.png`：左右两向都显示正确。

### 3. 动画循环：`time %= totalDuration`

`Animation.getPoseAt(time)` 会对所有 Pose 的 Duration 之和取模：

- 若 `Action.Duration > Σ Pose.Duration`，动画会**循环回到 pose1**
- 若 pose1 带位移（如 `Velocity="130,0"` 做一次性错开），循环会反复触发 → 表现为"一直后退"

**约定**：一次性偏移效果放在 pose1 时，让 Σ Pose.Duration >= Action.Duration，避免循环。

### 4. 新 Action 首帧：`getTime()` 从 1 开始（不是 0）

`Mascot.tick()` 调用 `behavior.next()` **之后**才 `setTime(getTime()+1)`；而 `ActionBase.init()` 把 `startTime` 设为当前 `mascot.getTime()`。所以切入新 Action 的**第一个生效 tick**，`getTime()` 计算出来是 1。

- `Animation.getPoseAt(1)` 对于 `pose1.Duration=1` 的情况：`1 - 1 = 0`，不满足 `< 0` → **跳过 pose1**，直接落到 pose2
- 表现为"本应错开 130px 但完全重叠"

**约定**：需要 pose1 起效的场景，`pose1.Duration >= 2`。

### 5. 边界检查：不要给 Move / ScanMove 加 `BorderType="Floor"`

- 多段任务栏拼成的 workArea 各自独立为"floor"；跨段时主角 anchor 会短暂不在任何一段上 → `Lost Ground`
- `ScanMove` 的 dy=0，本身不需要地板检测
- `Lost Ground` 硬编码跳 `Fall`，会强行打断 Walk / ScanMove

**约定**：`Move` 和 `ScanMove` 动作**移除** `BorderType="Floor"`，只保留 `Stay` 类动作上的地板约束。

### 6. 边界阈值：按实际**不透明像素宽度**算，不是画布宽度

sprite 画布是 160×160，但两个角色实际不透明像素区间不同：

| 角色 | 实际不透明 X 范围 | anchor 到左沿距离 | anchor 到右沿距离 |
|------|-------------------|-------------------|-------------------|
| ham | `[0..159]` | 80 | 79 |
| zhizhiji | `[15..144]` | 65 | 64 |

Walk 停止 Condition 必须**在包围盒撞到 workArea 边之前**停下，否则 `UserBehavior.next()` 会先抛 "Out of the screen bounds"，跳不到 WallCling。

**现行阈值**（详见 `img/<角色>/conf/behaviors.xml`）：

| 动作 | ham | zhizhiji |
|------|-----|----------|
| Walk 停止 Condition | `±300` | `±300` |
| WallCling 触发 Condition | `±130` | `±130` |
| Thrown 下 WallCling | `±200` | `±200` |

> Walk 停止阈值被放宽到 `±300` 的原因见 [Bug #6](../BUGFIX_LOG.md#bug-6)：Action 级 Condition 只在 `init` 时校验一次，所以必须**预留一整个 Walk Duration 的步长**，防止 Walk 跑完之前撞到屏幕边；把 Walk `Duration` 砍到 60（≈180px 步长），`300 - 180 = 120 > workArea.left`，不会踩到 OOB。

### 7. EL 条件表达式：只支持 `&&` / `||`，不支持 `and` / `or`

Shimeji-ee 的 EL 引擎是 Java/JS 风格，`Condition="#{x > 100 and x < 500}"` 会抛 `VariableException`。

**约定**：在 XML 里用 `&amp;&amp;` 和 `&amp;&amp;`（XML 转义的 `&&` / `||`）。

### 8. `ScanMove.setBehavior` 读 English schema

`ScanMove` 在到达目标时通过 `mascot.getMascot().setBehavior(configuration.buildBehavior(param(behaviorName)))` 切行为，`behaviorName` 默认从 English schema 读。

**约定**：XML 属性名用 **American 拼写** —— `Behavior` / `TargetBehavior`，不是 `Behaviour` / `TargetBehaviour`。写错会弹对话框 "Failed to set behaviour. There is no corresponding behaviour ()"。

### 9. `Frequency` 是**加权轮盘**权重，不是百分比 / 千分比

`Configuration.buildBehavior()` 的选 behavior 核心逻辑：

```java
long totalFrequency = 0;
for (each candidate) totalFrequency += candidate.getFrequency();
double r = Math.random() * totalFrequency;
for (each candidate) {
    r -= candidate.getFrequency();
    if (r < 0) return candidate.buildBehavior();
}
```

某个 behavior 的命中概率 = **它的 Frequency ÷ 同 NextBehaviorList 内满足 Condition 的所有候选 Frequency 之和**。所以想"提高"某个 behavior 的概率，除了抬高它自己的 Frequency，也可以压低同级其它候选。

调参时还要注意两层衰减：
- Affordance 类行为（如 `ScanGreet`）选中后还要满足"target 持有对应 affordance"才会真正播放，否则 `ScanMove` 空转丢单；
- `Fall` / `Dragged` / `Thrown` / `Sleep` / `Eat` / `PipiPlay` / `WallCling` 的 `NextBehaviorList` 中**通常不会**挂 `ScanGreet` / `GreetWait`，所以这些状态的切换机会吃不到 greet 候选。

### 10. `conf/logging.properties` 默认 `limit=50000` 会循环截断日志

Shimeji `Main.class.getResourceAsStream("/logging.properties")` 通过 `Class-Path: ./ img/ conf/` 加载到 `conf/logging.properties`，默认：

```properties
java.util.logging.FileHandler.limit = 50000    # 50 KB !
java.util.logging.FileHandler.count = 1
```

`count=1` 意味着**不轮转**，`ShimejieeLog0.log` 一旦写满 50KB 就会被**从头截断**重写。跑 1-2 分钟即会丢掉早期的 `Created a mascot` / `GreetWait` / `ScanGreet` 事件，导致日志统计脚本误报"0 次 greet"。

> ⚠️ 不要把 `count` 改成 `>1`：Java `FileHandler` 在 `count>1` 时会自动在 pattern 末尾追加 `.%g`，实际文件名变成 `ShimejieeLog0.log.0`、`ShimejieeLog0.log.1`（glob `*.log` 匹配不上，脚本会扫不到日志）。

**约定**：只加大 `limit`，保持 `count=1`。仓库已改为 `limit=20000000` (≈20MB)，足够一次几小时的长测。

---

## 自动化调试工具

为减少反复手动重启/观察带来的反馈延迟，仓库根目录提供两个 PowerShell 脚本：

| 脚本 | 用途 |
|------|------|
| `test_shimeji.ps1` | 自动 kill 旧进程、清空日志、拉起 Shimeji-ee、观察 N 秒、优雅退出以 flush 日志、扫描 `ShimejieeLog*.log` 统计 OOB / Lost Ground / VariableException / greet 计数 |
| `watch_greet.ps1` | 实时 tail `ShimejieeLog0.log`，每 5 秒报告 GreetWait / ScanGreet / GreetAct / GreetReact / 异常计数，凑齐一整轮互动后自动结束 |

配合使用方式：先 `test_shimeji.ps1 -DurationSeconds 30 -KeepRunning` 启动常驻进程，再 `watch_greet.ps1` 追日志直到触发。
