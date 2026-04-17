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
| `Behaviour` | 到达后**自身**跳转的行为名 |
| `TargetBehaviour` | 到达后**目标**跳转的行为名 |
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
<Action Name="ScanGreet" Type="Embedded"
        Class="com.group_finity.mascot.action.ScanMove"
        Affordance="greet"
        Behaviour="GreetAct"
        TargetBehaviour="GreetReact"
        TargetLook="true"
        BorderType="Floor">
  <Animation>
    <Pose Image="/walk_left_01.png" ImageAnchor="80,160" Velocity="3,0" Duration="8"/>
    <Pose Image="/walk_left_02.png" ImageAnchor="80,160" Velocity="3,0" Duration="8"/>
  </Animation>
</Action>

<!-- Zhizhiji 到达后播放的互动动画 -->
<Action Name="GreetAct" Type="Animate">
  <Animation>
    <Pose Image="/greet_act_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="50"/>
    <Pose Image="/greet_act_02.png" ImageAnchor="80,160" Velocity="0,0" Duration="50"/>
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
