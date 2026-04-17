# 吱吱吉 Shimeji-ee 完整修复记录

> 本文档记录所有 Bug 的排查过程、失败尝试与最终解法。
> 有效修复摘要见 [CORE_FIX.md](./CORE_FIX.md)。

---

# Bug #1：落地后无限 Fall 循环，无法显示趴着姿势

## 问题描述

吱吱吉启动后从屏幕顶部落下，落到状态栏后**始终显示直立姿势**（`fall_01.png`），从不切换到趴着的姿势（`idle_01.png`/`idle_02.png`）。

---

## 最终根本原因（一句话）

> **`img/Zhizhiji/conf/actions.xml` 中 Fall 动作的 Pose `Velocity="0,3"` 导致每帧落地后 anchor 被额外下移 3 像素，使地板检测永远无法通过，Fall 动作无限循环，从不切换到 Stand（趴着）。**

---

## 项目结构说明

```
runtime/shimejiee-local/shimejiee/
├── Shimeji-ee.jar                    # 主程序 JAR（含 Java 字节码）
├── conf/
│   ├── actions.xml                   # 全局 actions 配置（⚠️ 游戏实际上不读这个）
│   ├── behaviors.xml                 # 全局 behaviors 配置（⚠️ 游戏实际上不读这个）
│   ├── logging.properties            # 日志配置
│   └── settings.properties           # 全局设置（Multiscreen 等）
└── img/
    └── Zhizhiji/
        ├── conf/
        │   ├── actions.xml           # ✅ 角色专属配置（游戏实际读取的）
        │   └── behaviors.xml         # ✅ 角色专属配置（游戏实际读取的）
        ├── idle_01.png               # 趴着姿势帧 1
        ├── idle_02.png               # 趴着姿势帧 2
        ├── fall_01.png               # 下落姿势（直立走路造型）
        ├── walk_left_01~04.png       # 向左走动画（注：文件名与朝向相反，见下文）
        └── walk_right_01~04.png      # 向右走动画（注：文件名与朝向相反，见下文）
```

**关键发现**：游戏读取的是 `img/Zhizhiji/conf/` 下的角色专属配置，而非根目录 `conf/` 下的全局配置。这是导致大量"改了没效果"的根本原因。

---

## 完整调试时间线与所有改动

### ═══ 第一周 ═══

---

### 阶段 0：初始状态 & 资源同步问题

**现象**：角色一直在左右走路，几乎看不到趴着。

**初始 actions.xml 配置问题**：
- `Stand` 用的图片锚点还是旧版 `ImageAnchor="56,128"`（旧图 112×128 尺寸对应值）
- 新图已经更新为 160×160，但 ImageAnchor 没有同步

**操作**：将所有 Pose 的 `ImageAnchor` 从 `"56,128"` 更新为 `"80,160"`（图片中心横轴 80px，底部纵轴 160px）。

**结果**：✅ 锚点修复，但趴着仍然很少出现。

---

### 阶段 1：清理重复的运行目录

**现象**：运行目录里同时存在多份配置包（`Zhizhiji.zip`、`Zhizhiji_0408.zip` 等），程序读取产生混乱。

**操作**：
- 删除 `runtime/shimejiee-local/Zhizhiji.zip`
- 删除 `runtime/shimejiee-local/shimejiee/Zhizhiji.zip`
- 删除 `runtime/shimejiee-local/shimejiee/Zhizhiji_0408.zip`
- 将默认示例角色 `img/Shimeji` 移动到 `img/unused/Shimeji`

**结果**：✅ 只保留一套活动角色资源。

---

### 阶段 2：Stand 不显示的原因分析（错误诊断）

**现象**：角色始终在左右走路，几乎看不到趴着（Stand/idle）。

#### 错误尝试 1：给 `<Behavior>` 加 Duration 属性

**误判**：以为是 Behavior 层没有持续时间，添加了 `Duration="120"` 到 `<Behavior Name="Stand">` 元素。

**结果**：❌ **无效**。`<Behavior>` 元素本身不支持 `Duration` 属性，会被引擎忽略。Duration 需要设置在 `<Action>` 层。

---

#### 错误尝试 2：将 Stand 改为 `Type="Embedded"`

**误判**：查阅 XSD Schema 文件后误以为 `Type="Stay"` 不合法，将 Stand 修改为：

```xml
<!-- 错误改动 -->
<Action Name="Stand" Type="Embedded" Loop="true"
        Class="com.group_finity.mascot.action.Stay"
        BorderType="Floor" Duration="600">
```

**结果**：❌ **不必要**。通过反编译 JAR 的 `ActionBuilder.class` 确认，此版本 Shimeji-ee JAR **支持 `Type="Stay"`**（会自动映射到 `com.group_finity.mascot.action.Stay`），不需要写 `Type="Embedded"`。改回 `Type="Stay"`。

---

#### 正确修复：在 `<Action>` 层添加 Duration

**根本原因**：`Stand` 动作没有 `Duration`。`Stay` 类型不像 `Move` 类型那样会在碰到屏幕边缘时自然结束，它必须依靠 `Duration` 来决定持续多久。没有 `Duration` 时，动画只播一轮（2帧 × 8tick = 0.64秒），瞬间就结束了，肉眼几乎看不见。

**修复**：

```xml
<!-- 修复前 -->
<Action Name="Stand" Type="Stay" BorderType="Floor">
  <Animation>
    <Pose Image="/idle_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="8"/>
    <Pose Image="/idle_02.png" ImageAnchor="80,160" Velocity="0,0" Duration="8"/>
  </Animation>
</Action>

<!-- 修复后 -->
<Action Name="Stand" Type="Stay" BorderType="Floor" Duration="600">
  <Animation>
    <Pose Image="/idle_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="50"/>
    <Pose Image="/idle_02.png" ImageAnchor="80,160" Velocity="0,0" Duration="50"/>
  </Animation>
</Action>
```

同时将 Pose Duration 从 8 改为 50（趴着不需要像走路那样快速切帧）。

**结果**：✅ Stand 可以正常显示 24 秒（600 ticks × 40ms）。

---

### 阶段 3：走路几乎不停止的问题

**现象**：Stand 加了 Duration 后偶尔能看到趴着，但大部分时间还是在走路，走路一旦开始就很难切换到 Stand。

**根本原因**：`WalkLeft` 和 `WalkRight` 没有设置 `Duration`。`Move` 类型的动作在没有 Duration 时会一直走到屏幕边界才触发 LostGround，而不会经过正常的 NextBehaviorList 转换。完整的错误循环：

```
WalkLeft（无 Duration）→ 走到屏幕边界 → LostGround 异常 → Fall
→ 重新落地 → 按初始频率重选（Stand 30% / Walk 70%）→ 大概率又回到走路
```

**修复**：给 WalkLeft/WalkRight 加 `Duration="175"`（约 7 秒），让走路正常结束后经过 NextBehaviorList 转换：

```xml
<Action Name="WalkLeft" Type="Move" BorderType="Floor" Duration="175">
```

**结果**：✅ 走路正常结束，可以通过 NextBehaviorList 转换到 Stand。

---

### 阶段 4：走路图像方向搞反

**现象**：角色向左走时，显示的图像是朝右走的造型；向右走时，显示的是朝左走的造型。

**根本原因**：图片文件命名与实际内容相反：
- `walk_left_01.png`：角色实际**朝右**
- `walk_right_01.png`：角色实际**朝左**

**修复方式**：不重命名文件，而是在 `actions.xml` 里交叉引用：

```xml
<!-- WalkLeft（向左移动）使用 walk_right 图（朝右的图，配合镜像/速度修正后视觉朝左） -->
<Action Name="WalkLeft" Type="Move" BorderType="Floor" Duration="175">
  <Animation>
    <Pose Image="/walk_right_01.png" ImageAnchor="80,160" Velocity="-3,0" Duration="8"/>
    ...
  </Animation>
</Action>

<!-- WalkRight（向右移动）使用 walk_left 图 -->
<Action Name="WalkRight" Type="Move" BorderType="Floor" Duration="175">
  <Animation>
    <Pose Image="/walk_left_01.png" ImageAnchor="80,160" Velocity="3,0" Duration="8"/>
    ...
  </Animation>
</Action>
```

**结果**：✅ 走路方向视觉正确。

---

### 阶段 5：启动时的 Fall 循环（初始行为 LostGround）

**现象**：角色启动后从屏幕顶部落下，但"一直在左走一下右走一下"来回切换，直到用户手动拖拽一次才会按正常概率运作。

**根本原因（通过源码分析）**：
- 吱吱吉在 `(-1000, -1000)` 这个屏外坐标被创建，然后立刻随机选择初始行为
- 无论选到 Stand、WalkLeft 还是 WalkRight，因为不在地板上，立刻触发 LostGround → Fall
- Fall 时 x=-1000 超出屏幕左边界 → Out of Bounds → 传送到屏幕顶部 → 重新落下
- 落地后正常按 30/35/35 频率选择，没有问题

**误解**：之前以为"拖拽后才正常"是因为拖拽改变了概率，实际上拖拽前后概率完全相同（都是 30/35/35），只是初始 Fall 循环结束后用户恰好在 30% 概率的 Stand 出现时看到了。

**这是正常行为**，无需修复。

---

### 阶段 6：Fall 动画换成单帧静止图

**现象**：Fall 动画用的是 `fall_01.png` + `fall_02.png` 两帧交替，看起来像在"左右摇摆"。

**用户需求**：换成单帧静止图，下落时只显示一个固定姿势。

**修复**：将 Fall 动作改为只使用 `fall_01.png` 一帧：

```xml
<!-- 修复前 -->
<Animation>
  <Pose Image="/fall_01.png" ... Duration="8"/>
  <Pose Image="/fall_02.png" ... Duration="8"/>
</Animation>

<!-- 修复后 -->
<Animation>
  <Pose Image="/fall_01.png" ... Duration="100"/>
</Animation>
```

**结果**：✅ 下落时显示静止的直立图像。

---

### 阶段 7：版本推送问题 & 回退

**现象**：用户要求把改动推送到 GitHub，但当时改动不完整（Walk 图方向问题和 Fall 循环问题还存在）。

**操作**：
- 推送了当时的改动到 GitHub
- 用户发现内容有问题，要求回退

**回退操作**：`git revert` 了相关提交，保留了正确的 `.gitignore` 更新（忽略运行日志文件）。

**后来重新推送**（正确版本）：只在功能完全验证后推送。

---

### 阶段 8：`.gitignore` 更新

运行日志文件（`ShimejieeLog0.log` 等）不断污染 git 工作区，添加忽略规则：

```gitignore
# 不提交本地 Shimeji-ee 运行日志
runtime/shimejiee-local/shimejiee/ShimejieeLog*.log
runtime/shimejiee-local/shimejiee/ShimejieeLog*.log.lck
runtime/shimejiee-local/shimejiee/hs_err_pid*.log
```

---

### ═══ 第二周 ═══

---

### 阶段 9：落地后仍然直立——深入分析

**现象**：以上所有修复后，用户仍然反馈"落地后还是站的"。开始深入分析 Fall 动作的字节码和源码。

---

### 阶段 10：字节码补丁（Bytecode Patching）

由于没有 `javac` 编译器，无法直接重新编译源码，只能直接修改 JAR 内的 `.class` 字节码。

#### Patch 1：修复 `getFloor(true)` → `getFloor(false)`

**问题**：`Fall.class` 字节码中 `tick()` 方法（源码第 119 行）调用的是 `getFloor(true)`，而 `hasNext()` 调用的是 `getFloor(false)`。两者行为不一致，在用户系统（175% DPI 缩放）上导致地板检测失败。

**分析**：
- `getFloor(false)` = 获取普通地板（固定位置）
- `getFloor(true)` = 获取"可移动窗口"的地板（在 DPI 缩放环境下返回值可能不同）

**修复**：将 `Fall.class` 字节码 offset **4590** 处的字节从 `0x04`（`iconst_1`，即 true）改为 `0x03`（`iconst_0`，即 false）。

**JAR 操作方式**：
- 尝试 1：PowerShell `.NET ZipFile.ExtractToDirectory` + `Copy-Item` + `ZipFile.CreateFromDirectory` → ❌ 产生反斜杠路径，Java ClassLoader 无法加载
- 最终方案：Python `zipfile` 模块重建 JAR，显式替换路径分隔符为正斜杠

**结果**：✅ 统一了 getFloor() 参数。

---

#### 错误尝试 Patch 2：禁用 80 像素容差循环（后来回退）

**问题**：`Fall.tick()` 中有一个 `for(int j = -80; j <= 0; ++j)` 的内层循环，每帧调用 81 次 `getFloor()`，看起来像性能浪费。

**临时修复**：将 offset **4524-4525** 的 `bipush -80`（`0x10 0xB0`）替换为 `iconst_0`（`0x03`）+ `nop`（`0x00`），让循环从 j=0 开始（只检查一次）。

**结果**：❌ **反而引发新问题**。在 175% DPI 缩放下，一帧内 `dy`（位移量）可达数十像素，跳过 -80~0 的容差范围后，高速下落时会直接穿过地板，无法被检测到，重新出现"Out of Bounds"循环。

**回退操作**：将 offset 4524-4525 恢复为 `0x10 0xB0`（`bipush -80`）。

---

### 阶段 11：settings.properties 修复

**现象**：即使有 Patch 1，仍然出现"Out of the screen bounds"（OOB）循环，吱吱吉不断被重置到屏幕顶部再次下落。

**诊断**：用户系统被识别为多显示器环境，吱吱吉在主显示器和虚拟扩展区域之间越界。

**修复**：在 `conf/settings.properties` 中添加：

```properties
Multiscreen=false
```

**结果**：✅ 消除了多显示器越界循环问题。

---

### 阶段 12：修改全局配置文件（改了错误的文件！）

**目标**：让 Stand 落地后不触发 LostGround，减少 Stand 的边界检查。

**操作**：修改 `conf/actions.xml`（全局配置）：
- 删除 Stand 的 `BorderType="Floor"`（防止 LostGround 触发）
- 给 Fall 添加 `Duration="100"`（防止无限 Fall）
- 给 Stand 添加 `Loop="true"`

**结果**：❌ **完全无效**。原因是游戏实际读取 `img/Zhizhiji/conf/actions.xml`（角色专属配置），全局 `conf/actions.xml` 根本没有被加载！大量时间花费在改一个没有被读取的文件上。

---

### 阶段 13：LostGround 触发分析 & 确认读取哪个配置文件

**关键发现**：通过分析日志中的一行：

```
[93] Lost Ground (mascot1,Action (Stay,Stand))
```

推断出：`Stay.tick()` 中只有在 `getBorder() != null`（即 BorderType 有设置）时才会抛出 `LostGroundException`。

- 全局 `conf/actions.xml` 中 Stand **没有** `BorderType="Floor"`（已被删除）
- 角色专属 `img/Zhizhiji/conf/actions.xml` 中 Stand **有** `BorderType="Floor"`

由于日志证明 LostGround **确实**从 Stand 触发，因此**确认游戏读取角色专属配置**，而不是全局配置。

---

### 阶段 14：定位真正的 Bug & 最终修复

#### 问题分析

阅读 `Fall.java` 源码发现关键执行顺序（第 107-131 行）：

```java
OUTER: for( int i = 0; i <= dev; ++i )
{
    int x = start.x + dx * i / dev;
    int y = start.y + dy * i / dev;

    getMascot().setAnchor(new Point(x, y));
    if( dy > 0 )
    {
        for( int j = -80; j <= 0; ++j )
        {
            getMascot().setAnchor(new Point(x, y + j));
            if( getEnvironment().getFloor(false).isOn(getMascot().getAnchor()) )
            {
                break OUTER;  // 检测到地板，anchor 设置到地板位置（如 y=866）
            }
        }
    }
    // ...
}

// ⚠️ 在物理循环【之后】执行，会再次移动 anchor！
getAnimation().next(getMascot(), getTime());
```

#### 真正的 Bug

角色专属配置 `img/Zhizhiji/conf/actions.xml` 中，Fall 动作的 Pose 配置为：

```xml
<Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,3" Duration="100"/>
```

`Velocity="0,3"` 表示每帧动画会让 anchor **额外向下移动 3 像素**。

**执行流程（错误状态）**：

```
第 N 帧 tick()：
  1. 物理循环检测到地板 y=866 → break OUTER → anchor.y = 866 ✅
  2. getAnimation().next() 执行，Velocity="0,3" → anchor.y = 866 + 3 = 869 ❌

第 N+1 帧 hasNext()：
  检查 anchor.y=869，地板在 y=866，869 ≠ 866 → isOn() = false
  → hasNext() 返回 true → Fall 继续！

→ 无限循环：Fall 永远不会结束，一直显示直立的 fall_01.png
```

为什么之前没有发现？因为全局 `conf/actions.xml`（没被读取的那份）里 Fall 的 Velocity 是 `"0,0"`，而角色专属配置里是 `"0,3"`，两份配置的差异掩盖了问题。

#### 最终修复

将 `img/Zhizhiji/conf/actions.xml` 中 Fall 和 Thrown 两个动作的 Pose Velocity 从 `"0,3"` 改为 `"0,0"`：

```xml
<!-- 修复前 -->
<Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,3" Duration="100"/>

<!-- 修复后 -->
<Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="100"/>
```

**修复后执行流程**：

```
第 N 帧 tick()：
  1. 物理循环检测到地板 y=866 → break OUTER → anchor.y = 866 ✅
  2. getAnimation().next() 执行，Velocity="0,0" → anchor.y 不变 = 866 ✅

第 N+1 帧 hasNext()：
  检查 anchor.y=866，地板在 y=866，866 == 866 → isOn() = true
  → hasNext() 返回 false → Fall 正常结束！

→ Stand 开始，显示趴着的 idle_01.png ✅
```

**结果**：✅ **问题彻底修复**。

---

## 所有失败改动汇总

| 时间 | 改动内容 | 文件 | 失败原因 |
|------|----------|------|----------|
| 第一周 | 给 `<Behavior>` 加 Duration 属性 | behaviors.xml | `<Behavior>` 不支持 Duration，被引擎忽略 |
| 第一周 | 将 Stand 改为 `Type="Embedded"` | actions.xml | 不必要，JAR 本身支持 `Type="Stay"` |
| 第一周 | WalkLeft/WalkRight 没有 Duration | actions.xml | Walk 无限运行直到出界，导致 LostGround 循环 |
| 第一周 | Walk 图片方向搞反 | actions.xml | `walk_left_*.png` 实际朝右，文件命名与朝向相反 |
| 第一周 | 提前推送未完成的改动到 GitHub | GitHub | 功能未验证，被用户要求回退 |
| 第二周 | 禁用 -80 像素容差循环（Patch 2）| Fall.class | 175% DPI 下高速下落穿透地板，引发 OOB 循环，最终回退 |
| 第二周 | 修改全局 conf/actions.xml | conf/actions.xml | 游戏读取角色专属配置，全局配置未被加载，改动无效 |
| 第二周 | 删除全局 Stand 的 BorderType | conf/actions.xml | 同上，无效 |

---

## 当前有效配置文件总览

### `img/Zhizhiji/conf/actions.xml`（角色专属，游戏读取此文件）

| 动作 | 关键参数 | 说明 |
|------|----------|------|
| Stand | `Type="Stay"` `BorderType="Floor"` `Duration="600"` | 趴着，持续 24 秒 |
| WalkLeft | `Type="Move"` `BorderType="Floor"` `Duration="175"` `Velocity="-3,0"` | 向左走，7 秒；使用 walk_right 图片 |
| WalkRight | `Type="Move"` `BorderType="Floor"` `Duration="175"` `Velocity="3,0"` | 向右走，7 秒；使用 walk_left 图片 |
| Fall | `Loop="true"` **`Velocity="0,0"`**（已修复）| 落地检测正常 |
| Thrown | `Loop="true"` `InitialVY="-8"` **`Velocity="0,0"`**（已修复）| 被扔出时 |

### `img/Zhizhiji/conf/behaviors.xml`

| 行为 | Frequency | 下一行为 |
|------|-----------|----------|
| Stand | 30 | Stand(50%), WalkLeft(25%), WalkRight(25%) |
| WalkLeft | 35 | Stand(30%), WalkLeft(40%), WalkRight(30%) |
| WalkRight | 35 | Stand(30%), WalkLeft(30%), WalkRight(40%) |
| Fall | 0（不自动触发） | Stand(100%) |

### `conf/settings.properties`

```properties
Multiscreen=false   # 防止多显示器越界循环
```

### `Shimeji-ee.jar` 内字节码补丁（永久有效）

| 位置 | Offset | 修改前 | 修改后 | 作用 |
|------|--------|--------|--------|------|
| `Fall.class` | 4590 | `0x04`（iconst_1 = true）| `0x03`（iconst_0 = false）| 统一 getFloor() 参数为 false |
| `Fall.class` | 4524-4525 | `0x03 0x00`（曾被临时修改）| `0x10 0xB0`（bipush -80）| 恢复 80 像素容差范围 |

---

## 行为时序图（最终状态）

```
启动
  │（初始坐标 -1000,-1000，立刻 LostGround → Fall → OOB → 传送到屏幕顶部）
  ▼
Fall（从屏幕顶部落下，显示 fall_01.png）
  │  约 1-2 秒落到地板（Velocity="0,0" 修复后正常落地）
  ▼
Stand（趴着，显示 idle_01 / idle_02）  ← 持续 24 秒
  │
  ├── 50% → Stand（继续趴着）
  ├── 25% → WalkLeft（向左走，持续 7 秒）
  └── 25% → WalkRight（向右走，持续 7 秒）
               │
               ├── 30% → Stand（趴着）
               ├── 40% → 继续走同方向
               └── 30% → 换方向走
```

在稳定状态下，吱吱吉约 **67% 的时间**处于趴着姿势，**33% 的时间**处于行走姿势。

---

## Bug #1 经验教训

1. **先确认读取的是哪个配置文件**：Shimeji-ee 的角色专属配置在 `img/<角色名>/conf/` 下，而非全局 `conf/` 目录。两套配置并存、内容不同，极易造成"改了没效果"的混淆。

2. **Pose Velocity 不只影响动画外观**：在 `Fall` 这类 Embedded 动作中，`getAnimation().next()` 在物理循环之后执行，Pose 的 Velocity 会在落地检测完成后再次移动 anchor，破坏地板检测结果。Fall 动作的 Pose Velocity 应设置为 `"0,0"`。

3. **先读源码，再改字节码**：在进行字节码补丁之前，应先理解源码逻辑（`tick()` 的执行顺序）。如果一开始就读了 Fall.java 源码，会更早发现 Velocity 问题。

4. **Windows DPI 缩放的影响**：175% DPI 缩放下，一帧内下落像素数远超 1，需要 -80~0 像素容差循环才能可靠检测地板。禁用这个循环虽然看起来是"优化"，实际上是致命错误。

5. **JAR 内路径必须用正斜杠**：Windows 下用 .NET 重建 JAR 时会产生反斜杠路径，Java ClassLoader 无法识别，必须用 Python `zipfile` 显式替换为正斜杠。

6. **不要在功能未验证时推送到主分支**：应先在本地完全验证，确认效果正确后再推送 GitHub。

---

---

# Bug #2：WallCling 贴墙功能开发——拖拽放手后仍下落才触发贴墙

## 需求描述

当吱吱吉走到或被拖到屏幕左右边缘时，应立即以侧躺姿势贴在屏幕边缘，不再行走；若无鼠标交互，则保持该状态不动。

---

## 项目结构补充（新增文件）

```
img/Zhizhiji/
├── wall_cling.png          # 趴地板版本（备用）
├── wall_cling_left.png     # 左墙版本（原图顺时针旋转 90°，80×80）
└── wall_cling_right.png    # 右墙版本（原图逆时针旋转 90°，80×80）
```

图片由 Python + Pillow 脚本从 `raw/zhizhiji趴在屏幕上.png` 生成：去除白色背景 → 裁剪 → 缩放至 80×80 → 旋转。

---

## 完整调试时间线与所有改动

### 阶段 1：基础 WallCling 触发（走路到边界）

**问题**：吱吱吉走到边缘时直接消失（OOB 越界重置），没有贴墙动作。

**分析**：
- `UserBehavior.java` 的 OOB 检测：当图片边界超出屏幕范围时，传送角色到屏幕顶部并触发 Fall。
- 需要在角色走到边界之前主动停下并切换为 WallCling。

**操作**：
1. `actions.xml` 新增 `WallClingLeft` 和 `WallClingRight` Action（`Type="Stay"`）。
2. `behaviors.xml` 新增对应 Behavior，在 `WalkLeft`/`WalkRight` 的 `NextBehaviorList` 中添加条件触发：
   ```xml
   <BehaviorReference Name="WallClingLeft" Frequency="9999"
       Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.left + 150}"/>
   ```
3. `WalkLeft`/`WalkRight` Action 加上 `Condition` 属性，在距边界 100px 时停止移动。

**结果**：✅ 走路到边界时能触发 WallCling。

---

### 阶段 2：WallCling 图片视觉问题修复

**问题 A：白色背景未去除**

**操作**：Python 脚本用颜色阈值将白色/近白色像素替换为透明。

**结果**：✅ 背景透明。

---

**问题 B：贴左右墙时方向不对**

**需求**：贴左墙时图片向右旋转 90°，贴右墙时向左旋转 90°（即左右方向各自正确）。

**操作**：生成 `wall_cling_left.png`（顺时针 90°）和 `wall_cling_right.png`（逆时针 90°），分别对应 `WallClingLeft` 和 `WallClingRight` Action。

**结果**：✅ 方向正确。

---

**问题 C：图片尺寸过大，且触发后点击其他窗口会被任务栏遮挡**

**分析**：
- 原图 160×160，需要缩小。
- 贴墙时 anchor 位置偏低，图片底部被任务栏覆盖。

**操作**：
- 缩放至 80×80。
- 调整 `ImageAnchor` Y 值到 70（即图片底部在 anchor 上方 10px），使图片整体上移，不被任务栏遮挡。

**结果**：✅ 尺寸合适，不被任务栏挡住。

---

### 阶段 3：拖拽放手后直接贴墙（不下落）

**需求**：把吱吱吉拖到屏幕边缘放手，应立刻在原位触发 WallCling，不需要先落到地板。

---

#### 尝试 3-1：扩大 behaviors.xml 里的 WallCling 触发范围

**思路**：在 `Stand`、`Fall`、`Dragged` 的 `NextBehaviorList` 中也加入 WallCling 条件，扩大到 150px 甚至 300px。

**结果**：❌ 走路时能贴墙，但拖拽放手后仍然先下落再贴墙。原因在于 `Thrown` 行为是 Java 代码（`mouseReleased`）硬编码触发的，Dragged 的 `NextBehaviorList` 在放手时完全不执行。

---

#### 尝试 3-2：修改 Thrown 的 NextBehaviorList 条件

**思路**：在 `Thrown` behavior 的 `NextBehaviorList` 里加入 WallCling 条件（300px 范围），使放手后优先触发 WallCling。

**结果**：❌ 在日志里看到 `Thrown → WallClingRight` 直接跳转（无 Fall 中间步骤），但用户屏幕上仍然看到明显下落。

---

#### 尝试 3-3：分析日志与屏幕现象的差异

**现象**：日志显示 `Thrown → WallClingRight`（无 Fall），但用户确认屏幕上看到了下落过程。

**排查过程**：
1. 检查 `Stay.java`：`Type="Stay"` 无 `BorderType` 时不移动 anchor，理论上不应下落。✅ 代码无问题。
2. 检查 `Mascot.getBounds()`：使用 `anchor - image.center` 计算窗口位置，`center` 即 `ImageAnchor`。
3. 最终读取实际运行中的 `actions.xml` 文件——

**关键发现**：

```xml
<!-- 当时文件中 Thrown 的实际内容 -->
<Action Name="Thrown" Type="Embedded" Loop="true"
        Class="com.group_finity.mascot.action.Fall"
        InitialVX="0" InitialVY="-8"
        Gravity="2">
  <Animation>
    <Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="100"/>
  </Animation>
</Action>
```

**Thrown 仍然使用 `Embedded Fall` 类，带有 `InitialVY="-8"` 初速度和 `Gravity=2` 重力！** 之前的改动（改为 `Type="Stay" Duration="1"`）根本没有被保存到文件中，或被覆盖。

**行为逻辑**：
- `Thrown`（Embedded Fall）启动 → 先向上弹（InitialVY=-8）→ 重力拉回 → 落到地板
- 地板检测完成 → `Thrown` 结束 → `NextBehaviorList` 评估 → `WallClingRight`

用户看到的"下落"正是 Thrown 的物理模拟过程（先弹起再落地），整个过程约 0.5-1 秒。

---

#### 最终修复（阶段 3 根本原因）

**修改 `img/Zhizhiji/conf/actions.xml`**，将 `Thrown` 从 Embedded Fall 改为 Stay：

```xml
<!-- 修复前 -->
<Action Name="Thrown" Type="Embedded" Loop="true"
        Class="com.group_finity.mascot.action.Fall"
        InitialVX="0" InitialVY="-8"
        Gravity="2">
  <Animation>
    <Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="100"/>
  </Animation>
</Action>

<!-- 修复后 -->
<Action Name="Thrown" Type="Stay" Duration="1">
  <Animation>
    <Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="1"/>
  </Animation>
</Action>
```

**原理**：
- `Type="Stay"` 无物理引擎，anchor 不移动。
- `Duration="1"` 表示 1 个 tick（40ms）即完成。
- Thrown 完成后立即评估 `NextBehaviorList`，此时 anchor 仍在放手位置，若在边界范围内则直接触发 WallCling，不经过任何下落过程。

**结果**：✅ 拖拽放手后立即在原位触发 WallCling，无下落。

---

### 阶段 4：最终交互状态机（Bug #2 完成后）

```
拖拽放手（屏幕边缘附近）
  │
  ▼
Thrown（Stay，40ms，原位不动）
  │
  ├── anchor.x 在左墙 300px 内 → WallClingLeft（无限期停留）
  ├── anchor.x 在右墙 300px 内 → WallClingRight（无限期停留）
  └── 其他位置 → Fall → 落地 → Stand
                    │
                    ├── 落地在左墙 150px 内 → WallClingLeft
                    └── 落地在右墙 150px 内 → WallClingRight

自动行走到边界
  │
  ├── WalkLeft 到左墙 100px 内 → Condition 停止 → NextBehaviorList → WallClingLeft
  └── WalkRight 到右墙 100px 内 → Condition 停止 → NextBehaviorList → WallClingRight

WallClingLeft / WallClingRight
  └── Duration=999999（约 11 小时）→ 鼠标拖拽后才会离开
```

---

## Bug #2 经验教训

1. **日志行为与视觉现象不一致时，先读实际配置文件**：本次排查绕了很多弯路——日志显示无 Fall，但用户屏幕有下落。根本原因是 `actions.xml` 里 Thrown 的实际定义从未被正确修改，日志记录的 behavior 状态机是对的，但 Action 本身还在运行物理引擎。

2. **`Type="Embedded"` 与 `Type="Stay"` 有根本区别**：Embedded 使用 Java 类（如 Fall.java）执行完整物理模拟；Stay 是内置类型，直接保持位置不动。选错类型会导致完全不同的行为，且不会有任何报错提示。

3. **`mouseReleased` 直接触发 Thrown，绕过 Dragged 的 NextBehaviorList**：放手事件在 `UserBehavior.mouseReleased()` 中硬编码调用 `buildBehavior("Thrown")`，与 Dragged 行为的 NextBehaviorList 无关。要控制放手后的行为，必须修改 Thrown 的 NextBehaviorList，而不是 Dragged 的。

4. **Duration 的单位是 tick（40ms），不是秒**：`Duration="1"` = 40ms，`Duration="600"` = 24 秒。设置极大值（`Duration="999999"` ≈ 11 小时）是实现"无限等待用户交互"的有效方法。

5. **DPI 缩放影响 anchor 偏移量**：`Dragged.java` 的 `DEFAULT_OFFSETY=120`，乘以 DPI 缩放 1.75 = 210 像素。放手时 anchor.y = cursor.y + 210，在屏幕下方拖拽时 anchor 可能超出 workArea 底部，触发 OOB 重置——这是另一个潜在的下落原因，但在本次修复中未复现（因为 Thrown 的 imageAnchor.y=160 使 getBounds().getY() 有足够余量）。

---

# Bug #3：ham 走到边界后未触发 WallCling，从屏幕顶部重新掉落

## 问题描述

ham 角色自动行走到屏幕左右边界时，不触发 WallCling，而是直接从屏幕顶部重新掉落；zhizhiji 在相同配置下能正常触发 WallCling。

---

## 最终根本原因（一句话）

> **ham 的 Walk action 停止条件（`±25px`）与 NextBehaviorList 中 WallCling 触发条件（`±38px`）之间存在盲区：ham 在距墙 25px 处停下后，该位置处于 38px 的触发范围之外，导致 WallCling 条件永远不成立，Shimeji-ee 引擎转而触发 `Lost Ground`（位置超出工作区），将角色瞬间传送回顶部重新下落。**

---

## 排查过程

### 阶段 1：现象对比

- ham：`WalkLeft` 走到左边界 → 直接从屏幕顶部掉落（`Lost Ground` OOB 重置）
- zhizhiji：`WalkLeft` 走到左边界 → 正常触发 `WallClingLeft` 并贴墙

### 阶段 2：日志分析

读取 `ShimejieeLog0.log`，发现 ham 的日志序列为：

```
WalkRight → [Lost Ground 事件] → OOB 传送 → Fall（从顶部）
```

而 zhizhiji 的日志序列为：

```
WalkLeft → WallClingLeft
```

### 阶段 3：根因定位

对比 `actions.xml` 中 WalkLeft/WalkRight 的 `Condition`：

```xml
<!-- ham（有问题时）-->
<Action Name="WalkLeft"  Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.left + 25}"/>
<Action Name="WalkRight" Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.right - 25}"/>
```

对比 `behaviors.xml` 中 WallCling 的触发条件：

```xml
<!-- ham（有问题时）-->
<BehaviorReference Name="WallClingLeft"  Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.left + 38}"/>
<BehaviorReference Name="WallClingRight" Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.right - 38}"/>
```

**关键盲区：**

```
Walk 停下位置：距墙 25px（anchor.x = left + 25）
WallCling 触发范围：距墙 < 38px（anchor.x < left + 38）

看似 25 < 38，应该能触发？
```

但 Shimeji-ee 的 `Move` action 在 Walk 结束时，会先执行一次 `Condition` 检查：如果此刻 anchor.x 已越过 `left + 25` 的边界（即角色在边界外），引擎触发 `Lost Ground` 事件并立即 OOB 传送，**NextBehaviorList 的条件根本不会被评估**。而 zhizhiji 的 WalkLeft 在选中时已处于墙边，预检直接命中 WallCling，绕过了 Lost Ground。

**为什么同配置下 zhizhiji 没问题，ham 有问题？**

两个角色的 anchor 均设为 `80,160`（160×160 画布正中底部），配置数值完全相同，但关键差异在于**图片内容的实际宽度**：

- **zhizhiji** 体型纤细，图案与画布左边缘之间有较多透明空白。当 anchor 行走至 `left + 25` 时，图片包围盒的最左侧像素仍在 workArea 内，不触发 Lost Ground。zhizhiji 还因为大概率在选中 WalkLeft 时已离墙较近，直接走"预检命中 WallCling"的快捷路径，根本不经过 Lost Ground 判断。

- **ham** 体型更宽（猪身横向几乎占满画布），图案延伸至画布最左列附近。当 anchor 行走至 `left + 25` 时，图片包围盒的最左侧像素已触碰或越过 `workArea.left`，Lost Ground 先于 NextBehaviorList 评估触发，角色被 OOB 传送。

**结论**：`Lost Ground` 检测用的是整个图片包围盒，不是 anchor 点。ham 更宽的身体导致包围盒更早越界，这是同配置下 ham 独有此 Bug 的根本原因。

---

## 修复

### 1. `actions.xml`：拓宽 Walk 停止距离

```xml
<!-- 修复前 -->
<Action Name="WalkLeft"  Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.left + 25}"/>
<Action Name="WalkRight" Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.right - 25}"/>

<!-- 修复后 -->
<Action Name="WalkLeft"  Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.left + 60}"/>
<Action Name="WalkRight" Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.right - 60}"/>
```

角色在距墙 60px 处停下，给 NextBehaviorList 的评估留出充足余量。

### 2. `behaviors.xml`：拓宽 WallCling 触发阈值

将所有行为（Stand、StandRight、WalkLeft、WalkRight、Fall、Dragged）中的 WallCling 条件从 `±38` 扩大到 `±70`：

```xml
<!-- 修复前 -->
<BehaviorReference Name="WallClingLeft"  Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.left + 38}"/>
<BehaviorReference Name="WallClingRight" Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.right - 38}"/>

<!-- 修复后 -->
<BehaviorReference Name="WallClingLeft"  Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.left + 70}"/>
<BehaviorReference Name="WallClingRight" Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.right - 70}"/>
```

两者配合，确保 Walk 停下后（距墙 60px）处于 WallCling 触发区间（70px）内。

---

## 修复后的效果

```
WalkLeft 走到 left + 60 处停下
  → NextBehaviorList 评估
  → anchor.x < left + 70 → WallClingLeft 命中（Frequency=9999）
  → 立即贴左墙 ✅
```

---

## 经验教训

1. **`Lost Ground` 优先于 `NextBehaviorList`**：`Move` action 结束时若角色位置超出工作区，引擎触发 OOB 传送，NextBehaviorList 不会被执行。必须保证 Walk 停止位置在工作区边界内。
2. **Walk 停止条件与 WallCling 触发条件必须有重叠区间**：停止条件（`left + N`）要小于触发条件（`left + M`），且 N 要给 Walk 执行期间的累计位移留出足够余量。
3. **相同配置两个角色行为不同，说明触发时机不同**：zhizhiji 在选中 WalkLeft 时已在边界附近（预检即触发 WallCling），ham 是在行走过程中到达边界（需要靠 NextBehaviorList 触发），两者路径不同。

---

# Bug #4：ham WallCling 贴墙方向错误

## 问题描述

ham 角色贴墙（WallClingLeft / WallClingRight）时，猪身朝向与实际所贴的墙相反——贴左墙时猪身朝左（应朝右/中央），贴右墙时猪身朝右（应朝左/中央）。

---

## 最终根本原因（一句话）

> **`process_ham.py` 中生成 `wall_cling_left.png` / `wall_cling_right.png` 时，`rotate(-90)` 和 `rotate(90)` 的语义理解正确，图片生成本身没有问题。错误修复尝试（交换两者）才是导致"方向全部反转"的原因；还原后问题消失。**

---

## 排查过程

### 阶段 1：初步报告

用户反馈 ham 触发 WallCling 后方向反了（随机出现）。

### 阶段 2：错误修复（引入新 Bug）

误判为 `process_ham.py` 旋转方向写反，将：

```python
# 原始（正确）
cling_left  = cling_base.rotate(-90, expand=True).resize(...)
cling_right = cling_base.rotate( 90, expand=True).resize(...)
```

改为：

```python
# 错误修改
cling_left  = cling_base.rotate( 90, expand=True).resize(...)
cling_right = cling_base.rotate(-90, expand=True).resize(...)
```

重新生成后，方向由"随机反"变为"始终全反"，问题加重。

### 阶段 3：还原（正确修复）

将 `process_ham.py` 恢复为原始旋转方向（`rotate(-90)` 对应 left，`rotate(90)` 对应 right），重新执行脚本并部署，问题消除。

---

## 根本原因分析

`PIL.Image.rotate(angle)` 以**逆时针**为正方向：

| 调用 | 等效 | 躺平猪旋转后朝向 |
|------|------|-----------------|
| `rotate(-90)` | 顺时针 90° | 猪腹朝右 → 适合贴**左**墙 ✅ |
| `rotate(90)`  | 逆时针 90° | 猪腹朝左 → 适合贴**右**墙 ✅ |

原始代码是正确的，不应修改。

---

## Bug #4 经验教训

1. **不要凭直觉猜测旋转方向**：PIL 的 `rotate()` 方向是逆时针正，容易与直觉相反。修改前先用小测试图验证。
2. **"随机反"≠图片文件问题**：如果问题是偶发性的，更可能是 behaviors.xml 的条件判断在某些位置边界产生误触发，而不是图片本身的朝向。
3. **修改 process_ham.py 后必须立即验证视觉结果**：脚本生成的图片是不可见的数值变换，必须在游戏中目视确认方向才能判断对错。

---

# Bug #5：吱吱吉 + ham 相遇击掌互动 — 连环坑总集

## 新功能概述

当屏幕上同时存在 ham 和 zhizhiji 时，两人会随机相遇并触发"击掌"互动：

- **ham**：进入 `GreetWait` 行为广播 `Affordance="greet"`，等待被接近
- **zhizhiji**：随机进入 `ScanGreet` 行为，用 `ScanMove` 扫到 ham 后**朝其走过去**
- 到达后：zhizhiji 切入 `GreetAct` 播放 `laugh_01.png`（大笑），ham 切入 `GreetReact` 播放 `greet_01.png`（击掌，由 `raw/ham/ham击掌.jpg` 去白底加工而来）
- 两人贴近但**静态错开**（不重叠）

实现全部在 XML 配置层（`img/ham/conf/*.xml` + `img/Zhizhiji/conf/*.xml`），没有改任何 Java 源码。配套脚本：

- `test_shimeji.ps1`：自动拉起/kill/抓日志并做统计
- `watch_greet.ps1`：实时 tail 日志直到打满一轮 greet

但从"写好配置"到"稳定触发 + 视觉正确"中间踩了 8 个非显式坑，逐个记录在下方。

---

## Bug #5.1：EL 条件里写 `and` 导致 `VariableException`

### 现象

Shimeji 启动后疯狂抛：

```
javax.el.ELException: javax.el.PropertyNotFoundException: ELResolver cannot handle a null base Object with identifier 'and'
```

相遇行为完全不触发。

### 根因

`behaviors.xml` 里为 `GreetWait` / `ScanGreet` 加的边界 Condition 写成了：

```xml
Condition="#{mascot.anchor.x > mascot.environment.workArea.left + 200 and mascot.anchor.x < mascot.environment.workArea.right - 200}"
```

Shimeji-ee 的 EL 引擎只支持 Java/JS 风格的 `&&` / `||`，不认 `and` / `or`。

### 修复

XML 里用 `&amp;&amp;`（`&&` 的 XML 转义）：

```xml
Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.left + 200 &amp;&amp; mascot.anchor.x &lt; mascot.environment.workArea.right - 200}"
```

---

## Bug #5.2：Walk / WallCling 阈值按画布宽度算，还是 OOB

### 现象

两个角色走到屏幕边就直接抛 `Out of the screen bounds` → 从顶部重新掉落，完全跳过 WallCling。现象比 Bug #3 那版更严重，因为互动上线后增加了更多 Walk 触发机会。

### 根因

之前 Bug #3 只针对 ham，且阈值是按经验值 `±60` 调的。真正决定"何时抛 OOB"的是 **bounding box 触碰到 workArea 边**，而 bounding box 是**图片实际不透明像素的包围盒**，不是 160×160 画布。

逐角色测了每帧 PNG 的不透明 X 区间：

| 角色 | alpha≠0 的 X 范围 | anchor (80, 160) 到左沿 | 到右沿 |
|------|--------------------|-------------------------|--------|
| ham | `[0..159]`（几乎占满） | 80 | 79 |
| zhizhiji | `[15..144]` | 65 | 64 |

### 修复

按实际不透明宽度 + 10px 安全重叠重算所有阈值：

| 动作 | ham | zhizhiji |
|------|-----|----------|
| Walk 停止 | `±100` | `±80` |
| WallCling 触发 | `±110` | `±90` |
| Thrown 下 WallCling | `±200` | `±200` |

并补全了 `GreetWait` / `ScanGreet` / `GreetAct` / `Eat` / `Sleep` / `PipiPlay` / `Laugh` 等新 Behavior 的 `WallClingLeft/Right` BehaviorReference（之前只加在 Stand/Walk 上）。

---

## Bug #5.3：`BorderType="Floor"` 加在 Walk / ScanMove 上 → `Lost Ground`

### 现象

日志频繁：

```
Lost Ground (mascot2, Action (ScanMove, ScanGreet))
Lost Ground (mascot1, Action (Move, WalkRight))
```

两个角色走路或追向目标时会被强行切 `Fall`，互动动作被打断。

### 根因

- 多段任务栏拼出的 workArea 在 Shimeji 里是**多个独立 floor 矩形**，跨段时 anchor 会短暂不在任何一个 floor 上
- 两个 mascot 的 "floor 集合" 是从各自 `environment` 构造的，互不同步
- `BorderType="Floor"` 每 tick 调用 `FloorCeiling.isOn()`，一旦不在任一段 floor 上立即 `Lost Ground`
- `ScanMove` 本身 `vy=0`，根本不需要地板检测

### 修复

`actions.xml` 中以下 Action **移除** `BorderType="Floor"`：

- `WalkLeft` / `WalkRight`（ham + zhizhiji）
- `ScanGreet`（zhizhiji）

只在 `Stay` 类动作（`Stand`、`GreetAct`、`GreetWait`、`Laugh`、`Eat` 等）上保留 `BorderType="Floor"`。

---

## Bug #5.4：`ScanMove` 属性名拼写 — schema 读的是 `Behavior` 不是 `Behaviour`

### 现象

弹出对话框：

```
Failed to set behaviour. There is no corresponding behaviour ()
```

括号里行为名是空的。

### 根因

老 Shimeji 文档和源码常数里是 British 拼写 `Behaviour`，但实际跑的时候 `ScanMove` 调 `configuration.buildBehavior(param(behaviorName))` 读的 `behaviorName` 变量名来自 **English schema**（`conf/schema_en.properties`），映射的 key 是 American 拼写 `Behavior`。

XML 里写 `Behaviour="GreetAct"` → schema 查不到 → 读到空字符串 → `buildBehavior("")` 失败。

### 修复

```xml
<!-- 修复前 -->
<Action Name="ScanGreet" ... Behaviour="GreetAct" TargetBehaviour="GreetReact" ...>

<!-- 修复后 -->
<Action Name="ScanGreet" ... Behavior="GreetAct" TargetBehavior="GreetReact" ...>
```

---

## Bug #5.5：ScanGreet 方向反了 — `Pose.next()` 里 dx 被 `lookRight` 翻转

### 现象

用户肉眼看到 zhizhiji 在追 ham 的途中**往反方向走了一次**。日志上 `ScanGreet` 正常结束并进入 `GreetAct`，但中途方向是错的。

### 根因

看 `Pose.next()` 源码：

```java
mascot.setAnchor( new Point(
    mascot.getAnchor().x + ( mascot.isLookRight() ? -getDx() : getDx() ),
    ...
));
```

`ScanMove.tick()` 每 tick 根据 `anchor.x vs TargetX` 动态 `setLookRight(...)`：

- 目标在右 → `lookRight=true` → `Velocity="3,0"` 实际走 `-3`（向左！）
- 目标在左 → `lookRight=false` → `Velocity="3,0"` 实际走 `+3`（向右！）

两种情况方向**都反**。

### 修复

`ScanGreet` 的 `Velocity` 取**负数**，单 Animation 块，交给 `ScanMove` 的 `setLookRight` 自动翻转朝向：

```xml
<Pose Image="/walk_right_01.png" ImageAnchor="80,160" Velocity="-4,0" Duration="8"/>
```

- 目标在右 → `lookRight=true` → 走 `-(-4) = +4`（向右）✅
- 目标在左 → `lookRight=false` → 走 `-4`（向左）✅

---

## Bug #5.6：GreetAct 后吱吱吉"一直后退" — `Animation.getPoseAt` 循环

### 现象

触发击掌后，zhizhiji 正确错开 ham 约 130px，但随后**每隔 2 秒**又跳走一次，最终离 ham 越来越远。

### 根因

`GreetAct` 配置：

```xml
<Action Name="GreetAct" Type="Stay" Duration="300">
  <Animation>
    <Pose Image="/laugh_01.png" Velocity="130,0" Duration="1"/>
    <Pose Image="/laugh_01.png" Velocity="0,0"   Duration="50"/>
  </Animation>
</Action>
```

看 `Animation.getPoseAt(time)`：

```java
time %= getDuration();  // getDuration() = 所有 Pose.Duration 之和 = 51
```

Animation 总长 **51 tick**，但 Action 总长 **300 tick** → 每过 51 tick 动画 loop 回 pose1，又做一次 `Velocity="130,0"` 的位移。

### 修复

让 `Animation` 总长 > `Action.Duration`，第一个 Pose 只生效一次：

```xml
<Action Name="GreetAct" Type="Stay" Duration="300">
  <Animation>
    <Pose ... Velocity="130,0" Duration="2"/>
    <Pose ... Velocity="0,0"   Duration="300"/>  <!-- 总长 302 > 300 -->
  </Animation>
</Action>
```

---

## Bug #5.7：错开没生效又重叠了 — 新 Action 首帧 `getTime()=1` 不是 0

### 现象

修完 #5.6 之后发生退化：不再"一直后退"了，但 **130px 错开也完全没生效**，zhizhiji 再次和 ham 完全重叠。

### 根因

跟到 `Mascot.tick()`：

```java
getBehavior().next();          // ← 这里已经执行了 Stay.tick() / Pose.next() 一次
setTime(getTime() + 1);        // ← 然后才 +1
```

而 `ActionBase.init()` 把 `startTime` 设为当前 `mascot.getTime()`；`getTime()` 减去 startTime 得到 Action 内相对时间。结果是**新 Action 的第一个生效 tick 对应相对时间 = 1**，不是 0。

再看 `Animation.getPoseAt(1)`：

```java
time = 1
for (Pose p : poses) {
  time -= p.getDuration();
  if (time < 0) return p;
}
```

- pose1.Duration=1 → `time = 1 - 1 = 0`，**不满足 `< 0`**
- 往下 pose2.Duration=300 → `time = 0 - 300 = -300 < 0` → 返回 pose2

→ pose1 **被完全跳过**，`Velocity="130,0"` 从未应用。

### 修复

pose1 的 Duration 至少为 2（让 t=1 落在 pose1 范围内）：

```xml
<Pose ... Velocity="130,0" Duration="2"/>
<Pose ... Velocity="0,0"   Duration="300"/>  <!-- 仍然 > Action.Duration -->
```

---

## Bug #5.8：走路方向和图像朝向反了 — `ImagePair` flip 约定

### 现象

肉眼观察：zhizhiji 确实**向右**走（位置在变大、追向右侧 ham），但贴图是**朝左**的"walkleft"造型。

### 根因

吱吱吉素材命名和视觉方向**反直觉**：

- `walk_right_*.png` 原图**实际画的是朝左**的吱吱吉
- `walk_left_*.png` 原图**实际画的是朝右**的吱吱吉

原因是早期素材是"蓝色背带面向画面左侧"这张，被命名为 walk_right（当时定义向右走画面朝左）。

`ImagePairLoader.load()` 在 `rightPath` 未指定时，会把 `leftImage` 水平翻转生成 rightImage。`ImagePair.getImage(lookRight)` 则按 `lookRight` 选择原图 vs flip 版本。

之前 ScanGreet 的两条件 Animation：

- 目标在左（`lookRight=false`）：用 `walk_right_01.png` 原图（朝左） ✅
- 目标在右（`lookRight=true`）：用 `walk_left_01.png` 原图（朝右），但 `lookRight=true` 会拿它的 **flip 版**（朝左）❌

于是"往右走 → 显示 walkleft（朝左）"。

### 修复

单 Animation 块统一用 `walk_right_*.png`（原图朝左）：

- `lookRight=false`（走向左侧目标）→ 用原图（朝左）✅
- `lookRight=true`（走向右侧目标）→ 用 flip 版（朝右）✅

```xml
<Action Name="ScanGreet" ... TargetLook="true">
  <Animation>
    <Pose Image="/walk_right_01.png" ImageAnchor="80,160" Velocity="-4,0" Duration="8"/>
    <Pose Image="/walk_right_02.png" ImageAnchor="80,160" Velocity="-4,0" Duration="8"/>
    <Pose Image="/walk_right_03.png" ImageAnchor="80,160" Velocity="-4,0" Duration="8"/>
    <Pose Image="/walk_right_04.png" ImageAnchor="80,160" Velocity="-4,0" Duration="8"/>
  </Animation>
</Action>
```

---

## Bug #5 经验教训

1. **属性名拼写跟 schema 走，不跟源码常数走**：`Behavior` / `TargetBehavior`（American）才是 XML 里正确写法。
2. **EL 只懂 `&&` / `||`**：在 XML 里记得转义为 `&amp;&amp;`。
3. **Move / ScanMove 不要挂 `BorderType="Floor"`**：多段 workArea + 跨 mascot 的 floor 差异会在 tick 之间频繁误报 Lost Ground。
4. **边界阈值按实际 alpha 包围盒算**，不是画布宽。每次换素材重新测。
5. **`Pose.next()` 会对 `lookRight` 做 dx 翻转**：`ScanMove` / 动态朝向的动作里 Velocity 取负更稳。
6. **Animation 总长设计要考虑 `time %= totalDuration` 的循环**：一次性偏移必须放在 Σ Pose.Duration > Action.Duration 的 Animation 里，或者让那个 Pose 覆盖到结束。
7. **新 Action 首帧 `getTime()=1`**：首个生效 Pose 的 Duration 至少为 2，否则会被跳过。
8. **素材命名 ≠ 视觉朝向**：吱吱吉这套图是反的。单 Animation 块配合 `TargetLook="true"` + `setLookRight` 自动翻转最稳；写双分支 Animation 时务必确认每个分支的 `Pose Image` 对应的 flip 方向是要的那个。
9. **调试手段**：`test_shimeji.ps1` + `watch_greet.ps1` 替代反复手动重启/肉眼盯屏，是这轮能闭环的前提。

---

## Bug #6：Walk 过程中直冲屏幕边 OOB，WallCling 跳不进去 <a id="bug-6"></a>

### 现象

ham / zhizhiji 在 `WalkLeft` 或 `WalkRight` 过程中频繁触发 `Out of the screen bounds`，而不是按设计转到 `WallClingLeft` / `WallClingRight`。日志里看到的典型时间线（120s 测试）：

```
Default Behavior(mascot2,Behavior(WalkLeft))
Out of the screen bounds(mascot2,Behavior(WalkLeft))     ← 直接 OOB
Default Behavior(mascot2,Behavior(Fall))
Out of the screen bounds(mascot2,Behavior(Fall))
```

### 根因分析

两个耦合的原因：

1. **Walk Action 的 `Duration` 偏长，单次 Action 走的距离超过 Condition 与 workArea 边的间距。**

   - 原 ham `WalkLeft` / `WalkRight` `Duration="175"`、Velocity dx = `-3` / `3`，一次 Action 连续走 `175 × 3 = 525px`。
   - 原 ham `WalkLeft` `Condition="+150"`（`anchor.x > workArea.left + 150`），一次 `init` 校验通过后之后**不会再重新校验** → 走到 `anchor.x = 150 - 525 = -375`（远在屏幕外），才结束本次 Action。
   - 在 Action 跑完前每一帧都要过 `UserBehavior.next()` 的 bounds 检查，bounds 超出屏幕 → 直接抛 OOB 事件，**压根走不到 Walk 结束后的 NextBehaviorList 判定**。

2. **WallCling 触发 Condition 与 Walk 停止 Condition 不对齐。**

   - 原 ham `WallClingLeft` Condition 是 `anchor.x < workArea.left + 110`。
   - 原 ham `WalkLeft` 停止 Condition 是 `anchor.x > workArea.left + 150`。
   - 两者之间有 40px 间隙，这段距离内 Walk 结束选 NextBehavior 时：`150` 不满足 `< +110`，`WallClingLeft` 候选被 Condition 过滤掉。

### 修复

核心思路：**缩短 Walk Duration 让单次步长可控**，再把 Walk 停止 Condition 推到一个"走完还不会 OOB 且 WallCling Condition 能接上"的位置。

```xml
<!-- img/ham/conf/actions.xml & img/Zhizhiji/conf/actions.xml -->
<!-- Duration 60 = 60 frames × 3 px = 180px 步长 -->
<Action Name="WalkLeft" Type="Move" BorderType="Floor" Duration="60">...</Action>
<Action Name="WalkRight" Type="Move" BorderType="Floor" Duration="60">...</Action>
```

```xml
<!-- img/ham/conf/behaviors.xml & img/Zhizhiji/conf/behaviors.xml -->
<!-- Walk 停止阈值放到 ±300，预留一个完整步长的余量 -->
<BehaviorReference Name="WalkLeft"
    Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.left + 300}"/>
<BehaviorReference Name="WalkRight"
    Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.right - 300}"/>

<!-- WallCling 触发阈值统一放到 ±130，和 "Walk 走完后可能落点" 相交 -->
<BehaviorReference Name="WallClingLeft"  Frequency="9999"
    Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.left + 130}"/>
<BehaviorReference Name="WallClingRight" Frequency="9999"
    Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.right - 130}"/>
```

阈值推导：

- `Walk` 入口 Condition `> workArea.left + 300`，单次最大行走 180px → Action 结束时 `anchor.x ≥ 300 - 180 = 120 > workArea.left`（`anchor` 距画布左沿 80px，实际屏幕像素 `120 - 80 = 40 > 0`，不 OOB）。
- `WallClingLeft` 入口 Condition `< workArea.left + 130`，且 Action 结束时 `anchor.x` 落点区间 `[120, 300]`，有部分落点（`[120, 130]`）能触发 WallCling。没触发的话还会回到 `Stand/StandRight`，下一轮重新摇号。
- `Thrown` 的 `WallCling` Condition 保持 `±200`（比 Walk 路径更保守，防止被甩飞时错过）。

### 验证

180 秒自动化测试（`test_shimeji.ps1 -DurationSeconds 180`）日志统计：

```
Walk LG after init     : 0
Stay LG after init     : 0
ScanMove LG after init : 0
Out Of Screen Bounds   : 2   ← 都是 Created a mascot 后 <100ms 的启动初始化副作用
```

没有一次 OOB 发生在 Walk 运行过程中。

---

## Bug #7：自动化日志统计总是 0 次 greet —— `conf/logging.properties` 默认 50KB 循环截断

### 现象

跑 `test_shimeji.ps1 -DurationSeconds 180`，`ShimejieeLog0.log` 才 ~3KB，分析脚本报告 `mascot created: 0 / GreetWait: 0 / ScanGreet: 0`，但屏幕上明显看到两个 mascot 正常活动甚至 greet。

### 根因

Shimeji 的 `Main.class.getResourceAsStream("/logging.properties")` 通过 Jar Manifest `Class-Path: ./ img/ conf/` 加载到 `conf/logging.properties`，默认：

```properties
java.util.logging.FileHandler.limit = 50000    # 50 KB
java.util.logging.FileHandler.count = 1
```

`count=1` 时 Java `FileHandler` **不轮转**：`ShimejieeLog0.log` 写满 50KB 后会被**从头截断**覆盖。Shimeji 跑 1-2 分钟就超出 50KB，早期的 `Created a mascot` / `GreetWait` / `ScanGreet` 事件全部丢失，脚本当然统计不到。

日志里 `<sequence>` 是 JVM 级累加计数器，截断不会重置。所以现象表现为：文件开头出现 `<sequence>515</sequence>`（而不是 0），中间缺失 1~514 条 record。

### 踩坑修复

- 尝试 1：`count=3`，`limit=20000000`。结果 `FileHandler` 检测到 `count>1` 自动把 pattern 末尾追加 `.%g`，文件名从 `ShimejieeLog0.log` 变成 `ShimejieeLog0.log.0` / `ShimejieeLog0.log.1` / `ShimejieeLog0.log.2` —— 统计脚本的 glob `ShimejieeLog*.log` 匹配不上，又扫不到日志。
- 尝试 2（最终方案）：保持 `count=1`，只把 `limit` 放大到 `20000000` (20MB)。文件名维持 `ShimejieeLog0.log`，日志不再截断，足够几小时测试。

```properties
# runtime/shimejiee-local/shimejiee/conf/logging.properties
java.util.logging.FileHandler.limit = 20000000
java.util.logging.FileHandler.count = 1
```

### 配套脚本改动

`test_shimeji.ps1`：

1. 清理阶段：原本只 `Remove-Item ShimejieeLog0.log` 和 `ShimejieeLog1.log`，改成 glob `ShimejieeLog*.log` + `ShimejieeLog*.lck` 全清，避免 Java 轮转编号残留的老文件被误认为当次产物。
2. 分析阶段：改成按 `LastWriteTime` 排序读所有 `ShimejieeLog*.log`，一并拼接后统计，兼容极端情况下的多文件。
3. 增加 `read: <file> (<size> bytes)` 的诊断输出，调用者一眼能看出日志有没有掉。

### 顺带澄清：`Frequency` 是加权轮盘，不是千分比

`Configuration.buildBehavior()`：

```java
long totalFrequency = 0;
for (each candidate) totalFrequency += candidate.getFrequency();
double r = Math.random() * totalFrequency;
for (each candidate) {
    r -= candidate.getFrequency();
    if (r < 0) return candidate.buildBehavior();
}
```

所以 `Frequency="45"` 的 `ScanGreet` 并不是 4.5% 或 0.45%，它是与同级其它候选比的**相对权重**。以 zhi 的 `Stand` 状态为例：

| 候选 | Frequency | 权重占比 |
|------|-----------|----------|
| ScanGreet | 45 | 45/156 ≈ 28.8% |
| Stand | 35 | 22.4% |
| WalkLeft / WalkRight | 20 + 20 | 25.6% |
| Sleep / Eat / PipiPlay | 12 × 3 | 23.1% |
| **合计** | **156** | 100% |

真实 greet 命中率再乘上两层衰减：

1. zhi 选中 ScanGreet 时 ham 必须正在 `GreetWait` 持 affordance，否则 `ScanMove` 空转丢单。
2. zhi 在 `Fall` / `Dragged` / `Thrown` / `Sleep` / `Eat` / `PipiPlay` / `WallCling` 这些状态下切换时，`NextBehaviorList` 里都没有 `ScanGreet` 候选，这些切换对 greet 命中率"无贡献"。

调参时别简单按 `Frequency / 1000` 估算概率。
