# 吱吱吉 Shimeji-ee 落地趴着问题修复完整记录

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

## 经验教训

1. **先确认读取的是哪个配置文件**：Shimeji-ee 的角色专属配置在 `img/<角色名>/conf/` 下，而非全局 `conf/` 目录。两套配置并存、内容不同，极易造成"改了没效果"的混淆。

2. **Pose Velocity 不只影响动画外观**：在 `Fall` 这类 Embedded 动作中，`getAnimation().next()` 在物理循环之后执行，Pose 的 Velocity 会在落地检测完成后再次移动 anchor，破坏地板检测结果。Fall 动作的 Pose Velocity 应设置为 `"0,0"`。

3. **先读源码，再改字节码**：在进行字节码补丁之前，应先理解源码逻辑（`tick()` 的执行顺序）。如果一开始就读了 Fall.java 源码，会更早发现 Velocity 问题。

4. **Windows DPI 缩放的影响**：175% DPI 缩放下，一帧内下落像素数远超 1，需要 -80~0 像素容差循环才能可靠检测地板。禁用这个循环虽然看起来是"优化"，实际上是致命错误。

5. **JAR 内路径必须用正斜杠**：Windows 下用 .NET 重建 JAR 时会产生反斜杠路径，Java ClassLoader 无法识别，必须用 Python `zipfile` 显式替换为正斜杠。

6. **不要在功能未验证时推送到主分支**：应先在本地完全验证，确认效果正确后再推送 GitHub。
