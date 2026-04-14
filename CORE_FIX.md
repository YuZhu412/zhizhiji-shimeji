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

Walk 停止条件（`±25px`）与 WallCling 触发条件（`±38px`）之间的执行顺序存在盲区：

- ham 行走中途到达边界 → 引擎触发 `Lost Ground`（OOB 传送）→ **NextBehaviorList 不被评估**
- zhizhiji 在选中 WalkLeft 时已在边界，预检即命中 WallCling，走不同的代码路径

`Move` action 的 `Lost Ground` 事件优先于 `NextBehaviorList` 的条件评估。

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
