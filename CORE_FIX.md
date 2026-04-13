# 核心问题：Fall 动作落地后无限循环

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
