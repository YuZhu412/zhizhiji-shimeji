# 吱吱吉 Shimeji-ee 核心修复摘要

> 本文档只记录有效的修复方案。完整排查过程见 [BUGFIX_LOG.md](./BUGFIX_LOG.md)。

---

# Bug #1：Fall 动作落地后无限循环

## 症状

吱吱吉从屏幕顶部落下后，**永远停留在直立的 `fall_01.png` 姿势**，从不切换到趴着的 `idle_01.png`。

---

## 根因

### Fall.java 的执行顺序

`Fall.tick()` 每帧按以下顺序执行：

```
1. 物理引擎计算新位置（gravity、velocity）
2. 内层循环（j = -80 到 0）扫描地板
   → 检测到地板时设置 anchor.y = floor.y（如 866），break
3. getAnimation().next() 执行
   → 按 Pose 的 Velocity 再次移动 anchor
```

### 问题所在

`img/Zhizhiji/conf/actions.xml` 中 Fall 动作的 Pose 配置：

```xml
<Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,3" Duration="100"/>
```

`Velocity="0,3"` 表示每帧动画将 anchor **额外向下移动 3 像素**。

### 为什么会无限循环

```
tick() 执行：
  步骤 2：物理引擎检测到地板 → anchor.y = 866  ✅ 正确落地
  步骤 3：getAnimation().next() → anchor.y = 866 + 3 = 869  ❌ 被推出地板

下一帧 hasNext() 检查：
  anchor.y = 869，地板 y = 866
  FloorCeiling.isOn() 要求严格相等：869 ≠ 866 → 返回 false
  → "还没落地"→ Fall 继续运行

→ 每帧都重复：落地 → 被推走 → 认为没落地 → 无限 Fall
```

---

## 修复

将 `img/Zhizhiji/conf/actions.xml` 中 Fall 和 Thrown 的 Pose Velocity 改为 `"0,0"`：

```xml
<!-- 修复前 -->
<Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,3" Duration="100"/>

<!-- 修复后 -->
<Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="100"/>
```

物理移动完全由 `Fall.tick()` 的引擎控制，Pose 不再额外干预位置。

---

## 修复后的效果

```
tick() 执行：
  步骤 2：物理引擎检测到地板 → anchor.y = 866  ✅
  步骤 3：getAnimation().next() → Velocity="0,0"，anchor.y 不变 = 866  ✅

下一帧 hasNext() 检查：
  anchor.y = 866 = 地板 y → isOn() = true → 返回 false
  → Fall 正常结束 → Stand 开始 → 显示 idle_01.png（趴着）✅
```

---

## 为什么之前没发现

全局配置 `conf/actions.xml`（游戏**不读取**此文件）里 Fall 的 Velocity 是 `"0,0"`，
而角色专属配置 `img/Zhizhiji/conf/actions.xml`（游戏**实际读取**此文件）里是 `"0,3"`。

两份文件内容不同，且整个排查过程长期在修改错误的那份文件，掩盖了真正的问题。


---

---

# Bug #2：拖拽放手后仍下落才触发 WallCling

## 症状

将吱吱吉拖到屏幕左右边缘放手后，角色先物理下落到地板，再切换到贴墙姿势；而非在放手位置立即贴墙。

---

## 根因

`actions.xml` 中 `Thrown` Action 一直使用 `Type="Embedded" Class="Fall"`，带有 `InitialVY="-8"`（向上初速度）和 `Gravity="2"`（重力加速度）。

放手流程：

`
mouseReleased() 触发
  → 创建 Thrown behavior
  → Thrown（Embedded Fall）启动
  → 先向上弹 (InitialVY=-8)，重力拉回，最终落地（约 0.5-1 秒）
  → 落地后 NextBehaviorList 评估 → WallClingRight/Left
`

因此用户看到的"先下落再贴墙"，并非行为状态机的 Bug（日志中 Thrown → WallCling 是正确跳转），而是 Thrown 这个 Action 本身就在运行物理引擎。

---

## 修复

修改 `img/Zhizhiji/conf/actions.xml`，将 Thrown 改为 `Type="Stay"`：

`xml
<!-- 修复前：Embedded Fall，有物理下落过程 -->
<Action Name="Thrown" Type="Embedded" Loop="true"
        Class="com.group_finity.mascot.action.Fall"
        InitialVX="0" InitialVY="-8"
        Gravity="2">
  <Animation>
    <Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="100"/>
  </Animation>
</Action>

<!-- 修复后：Stay，1 tick（40ms）后直接跳转 NextBehaviorList -->
<Action Name="Thrown" Type="Stay" Duration="1">
  <Animation>
    <Pose Image="/fall_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="1"/>
  </Animation>
</Action>
`

---

## 修复后的效果

`
mouseReleased() 触发
  → Thrown（Stay，40ms，anchor 不移动）
  → 在放手坐标评估 NextBehaviorList
     ├── 距右墙 300px 内 → WallClingRight（立即贴墙）✅
     ├── 距左墙 300px 内 → WallClingLeft（立即贴墙）✅
     └── 其他位置       → Fall（正常落地，无贴墙需求）
`

无需任何 Java 字节码修改，仅修改 XML 配置文件即可。

---

## 相关 XML 配置（behaviors.xml，Thrown 的 NextBehaviorList）

`xml
<Behavior Name="Thrown" Frequency="0" Action="Thrown">
  <NextBehaviorList>
    <BehaviorReference Name="WallClingLeft"  Frequency="9999"
        Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.left + 300}"/>
    <BehaviorReference Name="WallClingRight" Frequency="9999"
        Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.right - 300}"/>
    <BehaviorReference Name="Fall" Frequency="1"/>
  </NextBehaviorList>
</Behavior>
```

`Frequency="9999"` 保证在条件成立时 WallCling 被选中的概率约为 99.99%。

---

# Bug #3：ham 走到边界后未触发 WallCling，从屏幕顶部重新掉落

## 症状

ham 自动行走到屏幕边界后，不贴墙，而是从屏幕顶部重新掉落（OOB 重置）；zhizhiji 相同配置下正常触发 WallCling。

---

## 根因

`Lost Ground` 事件优先于 `NextBehaviorList` 评估，且检测对象是**图片包围盒**，不是 anchor 点。

```
ham 行走 → anchor 到达 left + 25
  → 图片包围盒最左侧像素已越过 workArea.left（ham 体型宽，几乎占满画布）
  → Lost Ground 触发 → OOB 传送 → NextBehaviorList 不被评估
```

zhizhiji 没有此问题的原因有两点：
1. **体型纤细**：anchor 在 `left + 25` 时，包围盒最左侧仍在 workArea 内，不触发 Lost Ground
2. **路径不同**：zhizhiji 大概率在选中 WalkLeft 时已离墙较近，Condition 预检即为 false，直接跳到 NextBehaviorList 评估 WallCling，根本不执行移动

两个角色配置值相同，差异完全来自**图片实际宽度**导致的包围盒缓冲量不同。

---

## 修复

### `actions.xml`（ham 专用）— 拓宽 Walk 停止距离

```xml
<!-- 修复前 -->
<Action Name="WalkLeft"  Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.left + 25}"/>
<Action Name="WalkRight" Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.right - 25}"/>

<!-- 修复后 -->
<Action Name="WalkLeft"  Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.left + 60}"/>
<Action Name="WalkRight" Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.right - 60}"/>
```

### `behaviors.xml`（ham 专用）— 拓宽 WallCling 触发阈值

所有行为（Stand、StandRight、WalkLeft、WalkRight、Fall、Dragged）中：

```xml
<!-- 修复前 -->
<BehaviorReference Name="WallClingLeft"  Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.left + 38}"/>
<BehaviorReference Name="WallClingRight" Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.right - 38}"/>

<!-- 修复后 -->
<BehaviorReference Name="WallClingLeft"  Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.left + 70}"/>
<BehaviorReference Name="WallClingRight" Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.right - 70}"/>
```

Walk 停在 60px 处，WallCling 触发范围覆盖到 70px，两者有 10px 的安全重叠区间。

> ⚠️ 此修复**仅应用于 ham**，zhizhiji 保留原值（`±25` / `±38`）。

---

# Bug #4：ham WallCling 贴墙方向错误

## 症状

ham 贴左墙时猪身朝左（应朝右），贴右墙时猪身朝右（应朝左）——方向与所贴墙相反。

---

## 根因

`process_ham.py` 中的旋转方向原本是正确的，误操作将其交换后导致方向全部反转。

PIL 的 `rotate()` 以**逆时针**为正方向：

| 调用 | 等效 | 躺平猪旋转后朝向 |
|------|------|-----------------|
| `rotate(-90)` | 顺时针 90° | 猪腹朝右 → 适合贴**左**墙 ✅ |
| `rotate(90)`  | 逆时针 90° | 猪腹朝左 → 适合贴**右**墙 ✅ |

---

## 修复

将 `process_ham.py` 恢复为原始旋转方向：

```python
# process_ham.py — wall_cling 生成部分（正确版本）
cling_left  = cling_base.rotate(-90, expand=True).resize((160, 160), Image.LANCZOS)
save(cling_left, "wall_cling_left.png")

cling_right = cling_base.rotate(90, expand=True).resize((160, 160), Image.LANCZOS)
save(cling_right, "wall_cling_right.png")
```

重新执行脚本并部署后，贴墙方向恢复正常。

---

## 注意

`wall_cling_left.png` / `wall_cling_right.png` 的旋转方向**不可修改**。如需调整姿势，应修改原始素材 `raw/ham/白底/趴着wallcling 白底.png`，而非修改脚本中的旋转角度。

---

# Bug #5：吱吱吉 + ham 相遇击掌互动（新功能 + 连环坑）

## 新功能

- ham 随机进入 `GreetWait` 广播 `Affordance="greet"`，等待被接近
- zhizhiji 随机进入 `ScanGreet`（`ScanMove`）扫到 ham 后走向它
- 到达后：zhizhiji → `GreetAct`（`laugh_01.png`），ham → `GreetReact`（`greet_01.png`，来自 `raw/ham/ham击掌.jpg` 去白底）
- 两人**贴近静态错开 130px，不重叠**
- 全部 XML 层实现，零 Java 代码改动

## 关键机制摘要（调试中发现的非显式约定）

| 机制 | 要点 |
|------|------|
| `Pose.next()` dx 翻转 | `newX = x + (lookRight ? -dx : dx)`。`ScanMove` 动态 setLookRight，所以 Velocity 的 dx **取负**才"朝当前朝向走" |
| `Animation.getPoseAt(t)` | `t %= Σ Pose.Duration`，Action.Duration > Animation 总长时会**循环回 pose1** |
| 新 Action 首个生效 tick | `getTime() = 1` 不是 0，`pose1.Duration=1` 会被跳过，至少要 `Duration=2` |
| `ImagePair` flip 约定 | `rightPath` 未指定时，从 `leftImage` 水平翻转生成 rightImage；`getImage(lookRight)` 按 lookRight 选择 |
| 吱吱吉素材命名反约定 | `walk_right_*.png` 原图**实际朝左**；`walk_left_*.png` 原图**实际朝右** |
| `ScanMove` schema | XML 属性必须是 American `Behavior` / `TargetBehavior`，不是 `Behaviour` |
| Shimeji EL | 只支持 `&&` / `||`（转义 `&amp;&amp;`），不支持 `and` / `or` |
| `BorderType="Floor"` | 只能加在 `Stay` 类动作；挂在 `Move` / `ScanMove` 上会因为多段 workArea / 跨 mascot floor 差异频繁误报 Lost Ground |
| 边界阈值 | 按角色实际不透明 alpha 包围盒算，不是 160 画布。ham ±100/±110，zhizhiji ±80/±90 |

详细排查过程见 [BUGFIX_LOG.md Bug #5](./BUGFIX_LOG.md)。

---

## 修复（最终可用配置）

### ham — 广播方

`img/ham/conf/actions.xml`：

```xml
<!-- 广播 greet，等待被接近。Frequency 在 behaviors.xml 里调 -->
<Action Name="GreetWait" Type="Stay" BorderType="Floor" Duration="400"
        Affordance="greet">
  <Animation>
    <Pose Image="/idle_02.png" ImageAnchor="80,160" Velocity="0,0" Duration="400"/>
  </Animation>
</Action>

<!-- 被接近后的击掌回应 -->
<Action Name="GreetReact" Type="Stay" BorderType="Floor" Duration="300">
  <Animation>
    <Pose Image="/greet_01.png" ImageAnchor="80,160" Velocity="0,0" Duration="300"/>
  </Animation>
</Action>
```

`img/ham/conf/behaviors.xml`：在 Stand/StandRight/WalkLeft/WalkRight 的 `NextBehaviorList` 里挂 `GreetWait`（`Frequency="500"`）；`GreetWait` / `GreetReact` 主体定义时带离屏阈值 `&amp;&amp;` 连接：

```xml
<Behavior Name="GreetWait" Frequency="0" Action="GreetWait">
  <NextBehaviorList>
    <BehaviorReference Name="Stand" Frequency="1"/>
  </NextBehaviorList>
</Behavior>
<Behavior Name="GreetReact" Frequency="0" Action="GreetReact">
  <NextBehaviorList>
    <BehaviorReference Name="Stand" Frequency="1"/>
  </NextBehaviorList>
</Behavior>
```

并给 `GreetWait` / `GreetReact` / 所有新 Behavior 补上 `WallClingLeft`/`WallClingRight` 的 `BehaviorReference`（阈值 `±110`）。

### zhizhiji — 扫描方

`img/Zhizhiji/conf/actions.xml`：

```xml
<!-- 追向 ham。单 Animation 块，Velocity 取负，walk_right_*.png 原图朝左。 -->
<!-- 不加 BorderType="Floor"：避免 LostGround 误报 -->
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

<!-- 大笑互动。pose1 Duration=2 确保 t=1 落在 pose1 上，完成一次 130px 错开 -->
<!-- Animation 总长 302 > Action.Duration=300，不会循环回 pose1 -->
<Action Name="GreetAct" Type="Stay" BorderType="Floor" Duration="300">
  <Animation>
    <Pose Image="/laugh_01.png" ImageAnchor="80,160" Velocity="130,0" Duration="2"/>
    <Pose Image="/laugh_01.png" ImageAnchor="80,160" Velocity="0,0"   Duration="300"/>
  </Animation>
</Action>
```

`img/Zhizhiji/conf/behaviors.xml`：

- `Stand` / `StandRight` / `WalkLeft` / `WalkRight` 的 `NextBehaviorList` 挂 `ScanGreet`（`Frequency="500"`）+ 边界 Condition `&amp;&amp;` 条件（左右各 `+150`）
- 降低 `Eat` / `Sleep` / `PipiPlay` 的 Frequency（3）、提高 `WalkLeft` / `WalkRight` 的 Frequency（20），保证 ScanGreet 有足够的机会轮到
- 所有新 Behavior 的 `NextBehaviorList` 加 `WallClingLeft/Right`（阈值 `±90`）和 `Thrown` 的 `±200`

### 配套素材

- `img/ham/greet_01.png`：从 `raw/ham/ham击掌.jpg` 用 PowerShell `System.Drawing` 去白底 + 缩放到 160×160（中文路径先 copy 成英文临时名再读）
- `img/Zhizhiji/laugh_01.png`：已存在

### 自动化调试脚本

- `test_shimeji.ps1`：kill → 清空日志 → 启动 → 观察 → 优雅 shutdown（flush 日志） → 扫描 `ShimejieeLog*.log` 统计 OOB / LostGround / VariableException / greet 计数
- `watch_greet.ps1`：实时 tail `ShimejieeLog0.log`，每 5 秒汇报 GreetWait / ScanGreet / GreetAct / GreetReact / 异常计数，凑齐一轮后自动退出

典型用法：

```powershell
# 开一个常驻 30 秒观察窗口
.\test_shimeji.ps1 -DurationSeconds 30 -KeepRunning
# 另开窗口，追到打招呼触发为止
.\watch_greet.ps1
```

---

## Bug #6：Walk 中途直接 OOB，跳不进 WallCling

### 根因

- Walk Action 的 `Duration` 太长（ham 原值 175 → 单次 525px 步长），`Condition` 只在 `init` 时校验一次，Walk 过程中撞到屏幕边→ `UserBehavior.next()` 直接抛 OOB。
- Walk 停止 Condition 与 WallCling 触发 Condition 之间有 40px 间隙（Walk `±150` vs WallCling `±110`），Walk 正常结束时两个候选都摸不到。

### 修复（两角色 `actions.xml` + `behaviors.xml` 同时改）

```xml
<!-- 把单次步长缩到 60 帧 = 180px，给 Condition 留余量 -->
<Action Name="WalkLeft"  Type="Move" BorderType="Floor" Duration="60">...</Action>
<Action Name="WalkRight" Type="Move" BorderType="Floor" Duration="60">...</Action>
```

```xml
<!-- Walk 停止 ±300；WallCling 触发 ±130；之间落点区间有交集 -->
<BehaviorReference Name="WalkLeft"
    Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.left + 300}"/>
<BehaviorReference Name="WalkRight"
    Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.right - 300}"/>
<BehaviorReference Name="WallClingLeft"  Frequency="9999"
    Condition="#{mascot.anchor.x &lt; mascot.environment.workArea.left + 130}"/>
<BehaviorReference Name="WallClingRight" Frequency="9999"
    Condition="#{mascot.anchor.x &gt; mascot.environment.workArea.right - 130}"/>
```

推导：入口 `x > 300`，一次最多走 180 → 落点 `x ≥ 120`，屏幕像素 `120 - anchorX(80) = 40 > 0`，不 OOB；落点区间 `[120, 300]` 有一段能触发 `WallCling (< 130)`，摸不到就回 Stand 下轮再摇。

验证：180s 自动化测试，`Walk/Stay/ScanMove` 运行中 LostGround 全部 0；OOB 只出现在 `Created a mascot` 后数百毫秒内的启动初始化（可忽略）。

---

## Bug #7：`conf/logging.properties` 默认 50KB 循环截断，日志统计失真

### 根因

Shimeji 从 classpath 加载 `conf/logging.properties`（Manifest 的 `Class-Path: ./ img/ conf/`），默认 `limit=50000 / count=1`。`count=1` 意味着**不轮转**，50KB 写满后从头截断，Shimeji 跑 1-2 分钟就会丢前面的日志，`test_shimeji.ps1` 扫出来永远是"0 次 greet / 0 mascot created"。

### 修复

```properties
# runtime/shimejiee-local/shimejiee/conf/logging.properties
java.util.logging.FileHandler.limit = 20000000   # ≈20MB
java.util.logging.FileHandler.count = 1          # 千万别改成 >1
```

> 坑中坑：改成 `count=3` 的话 Java `FileHandler` 会自动把 pattern 末尾追加 `.%g`，真实文件名变成 `ShimejieeLog0.log.0` / `.1` / `.2`，分析脚本的 `ShimejieeLog*.log` glob 匹配不上，一样扫不到日志。

配套 `test_shimeji.ps1` 的改动：

- 清理阶段用 `ShimejieeLog*.log` / `ShimejieeLog*.lck` 两个通配全清，避免残留老编号文件被误采样
- 分析阶段按 `LastWriteTime` 排序拼接读取所有 `ShimejieeLog*.log`
- 增加 `read: <name> (<bytes>)` 诊断输出，一眼能看出日志有没有被读到

---

## 澄清：`Frequency` 是加权轮盘权重

`Configuration.buildBehavior()`：

```java
long total = 0;
for (c in candidates) total += c.getFrequency();
double r = Math.random() * total;
for (c in candidates) { r -= c.getFrequency(); if (r < 0) return c.build(); }
```

所以 `Frequency="45"` 不是 4.5% / 0.45%，是**与同级其它候选比的相对权重**。zhi `Stand` 状态下 ScanGreet 的瞬时被选概率 = `45 / (45+35+20+20+12+12+12) ≈ 28.8%`，但完整 greet 命中率还要乘两层衰减：

1. 选中 ScanGreet 时 ham 必须正在 `GreetWait` 持有 affordance，否则 `ScanMove` 空转；
2. `Fall` / `Dragged` / `Thrown` / `Sleep` / `Eat` / `PipiPlay` / `WallCling` 等状态的 NextBehaviorList 里**不挂 ScanGreet**，这些切换不贡献命中机会。

调参别按 `Frequency / 1000` 估算。
