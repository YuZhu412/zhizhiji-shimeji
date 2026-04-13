# Shimeji-ee 代码架构与文件说明

> 基于 `shimejieesrc.zip` 源码分析，结合调试过程中实际读取的文件整理。

---

## 一、运行目录结构

```
runtime/shimejiee-local/shimejiee/
│
├── Shimeji-ee.jar              # 主程序（所有 Java 字节码打包在此）
│
├── conf/                       # 全局配置（⚠️ 对角色行为不生效，见下文）
│   ├── actions.xml             # 全局动作定义（被角色专属覆盖）
│   ├── behaviors.xml           # 全局行为定义（被角色专属覆盖）
│   ├── logging.properties      # Java 日志配置
│   └── settings.properties     # 全局开关（Multiscreen 等）
│
├── img/
│   └── Zhizhiji/               # 角色资源目录（名称即角色 ID）
│       ├── conf/               # ✅ 角色专属配置（优先级高于全局）
│       │   ├── actions.xml     # 动作与动画定义
│       │   └── behaviors.xml   # 行为状态机定义
│       │
│       ├── idle_01.png         # 趴着姿势（Stand 动作用）
│       ├── idle_02.png         # 趴着姿势（交替帧）
│       ├── fall_01.png         # 下落姿势（直立）
│       ├── drag_01.png         # 被拖拽姿势
│       ├── walk_left_01~04.png # 向左走动画帧（文件名与朝向相反）
│       └── walk_right_01~04.png# 向右走动画帧（文件名与朝向相反）
│
└── ShimejieeLog0.log           # 运行日志（XML 格式，已加入 .gitignore）
```

### 配置优先级

```
img/<角色名>/conf/actions.xml   （最高优先级，实际生效）
    └── 覆盖
conf/actions.xml                （全局配置，若角色专属不存在才读取）
```

**关键陷阱**：整个调试过程初期一直在修改全局 `conf/actions.xml`，但游戏实际只读取角色专属配置，导致大量改动完全无效。

---

## 二、源码目录结构（shimejieesrc.zip）

```
src/com/group_finity/mascot/
│
├── Main.java               # 程序入口，负责启动、托盘图标、角色创建
├── Manager.java            # 主循环调度，每 40ms tick 一次
├── Mascot.java             # 角色实体，持有 anchor（位置）、image、behavior
│
├── action/                 # 动作类（角色每帧的行为）
│   ├── Action.java         # 接口：hasNext()、next()、init()
│   ├── ActionBase.java     # 抽象基类：公共逻辑（Duration、time、eval、getAnimation）
│   ├── BorderedAction.java # 带边界检查的基类：管理 Border 对象
│   ├── Stay.java           # 原地静止（Stand 使用）
│   ├── Move.java           # 水平移动（Walk 使用）
│   ├── Fall.java           # 物理下落（重力加速）⭐ 核心问题所在
│   ├── Dragged.java        # 被鼠标拖拽
│   ├── Jump.java           # 跳跃
│   └── ...（其他扩展动作）
│
├── animation/
│   ├── Animation.java      # 一组 Pose 序列，管理帧切换
│   └── Pose.java           # 单帧：图片路径 + dx/dy 位移 + duration ⭐ Velocity 来源
│
├── behavior/
│   ├── Behavior.java       # 接口
│   └── UserBehavior.java   # 状态机核心：管理 action 执行、LostGround 处理、OOB 处理
│
├── config/
│   ├── Configuration.java  # XML 解析入口，加载 actions.xml 和 behaviors.xml
│   ├── ActionBuilder.java  # 解析 <Action> 节点，构造 Action 对象
│   ├── BehaviorBuilder.java# 解析 <Behavior> 节点，管理 NextBehaviorList
│   ├── AnimationBuilder.java# 解析 <Animation><Pose> 节点
│   └── Entry.java          # XML 节点包装器
│
├── environment/
│   ├── MascotEnvironment.java # 环境代理，提供 getFloor()、getWall() 等
│   ├── FloorCeiling.java   # 地板/天花板对象，isOn() 严格相等判断 ⭐
│   ├── Wall.java           # 左右墙壁
│   ├── Area.java           # 矩形区域（工作区）
│   └── Environment.java    # 接口，由平台实现（Windows/Linux）
│
└── exception/
    ├── LostGroundException.java  # 脱离边界时抛出
    └── VariableException.java    # 变量解析错误
```

---

## 三、核心类详解

### `Manager.java` — 主循环

```java
public static final int TICK_INTERVAL = 40; // 每帧 40ms（25fps）
```

每 40ms 调用一次所有 Mascot 的 `behavior.next()`，驱动整个状态机。

---

### `Mascot.java` — 角色实体

持有以下核心状态：
- `anchor`：角色位置（锚点，对应 `ImageAnchor` 在屏幕上的坐标）
- `image`：当前显示的图片
- `behavior`：当前执行的行为（`UserBehavior`）
- `time`：全局帧计数器
- `lookRight`：朝向

---

### `ActionBase.java` — 动作基类

所有动作的公共逻辑：

```java
// 每帧入口（被 UserBehavior 调用）
public void next() throws LostGroundException, VariableException {
    initFrame();
    tick();          // 调用子类的具体逻辑
}

// 判断动作是否应该继续
public boolean hasNext() throws VariableException {
    final boolean effective = isEffective();           // Condition 表达式
    final boolean intime = getTime() < getDuration(); // 未超过 Duration
    return effective && intime;
}

// 从 XML 属性读取参数（通用方法）
protected <T> T eval(String name, Class<T> type, T defaultValue)
```

**关键点**：`Duration` 未设置时默认 `Integer.MAX_VALUE`，动作永不超时，必须依靠其他方式终止（如 Fall 的地板检测、Move 的 LostGround）。

---

### `BorderedAction.java` — 带边界的动作基类

`Stay` 和 `Move` 都继承此类：

```java
// init() 时根据 XML 的 BorderType 属性绑定边界对象
if ("Floor".equals(borderType)) {
    this.border = getEnvironment().getFloor();
} // 或 Wall、Ceiling

// tick() 时让角色跟随边界移动（窗口地板移动时角色随之移动）
protected void tick() {
    if (getBorder() != null) {
        getMascot().setAnchor(getBorder().move(getMascot().getAnchor()));
    }
}
```

**关键点**：`BorderType` 未设置时 `border = null`，子类的 `isOn()` 检查不会触发，LostGround 也不会抛出。

---

### `Stay.java` — 原地静止（Stand 动作）

```java
protected void tick() throws LostGroundException {
    super.tick();  // BorderedAction.tick()：跟随地板移动

    // 如果绑定了地板但角色已不在地板上，抛出 LostGround
    if ((getBorder() != null) && !getBorder().isOn(getMascot().getAnchor())) {
        throw new LostGroundException();
    }

    getAnimation().next(getMascot(), getTime()); // 更新图片和位置
}
```

**关键点**：只有在 `BorderType="Floor"` 时才做地板检查。无 BorderType 则 `border=null`，永远不会 LostGround。

---

### `Move.java` — 水平移动（Walk 动作）

```java
protected void tick() throws LostGroundException {
    super.tick();  // BorderedAction：跟随地板

    // 同样检查是否仍在地板上
    if ((getBorder() != null) && !getBorder().isOn(getMascot().getAnchor())) {
        throw new LostGroundException();
    }

    getAnimation().next(getMascot(), getTime()); // 图片切换 + Velocity 位移
    // 还有目标坐标 TargetX/TargetY 的到达判断...
}
```

**关键点**：无 `Duration` 时会一直走到触发 LostGround（出屏幕边界），而不会经过 NextBehaviorList 正常转换。这是早期"只会左右走"bug 的根本原因之一。

---

### `Fall.java` — 物理下落 ⭐ 核心问题所在

```java
@Override
public boolean hasNext() throws VariableException {
    Point pos = getMascot().getAnchor();
    boolean onBorder = false;
    if (getEnvironment().getFloor().isOn(pos)) {  // getFloor(false)
        onBorder = true;
    }
    return super.hasNext() && !onBorder;  // 在地板上时返回 false，动作结束
}

@Override
protected void tick() throws LostGroundException, VariableException {
    // 1. 计算物理速度（重力加速、空气阻力）
    this.velocityY += getGravity();

    // 2. 计算本帧位移
    int dy = (int) this.velocityY;

    // 3. 外层循环：按位移步进
    OUTER: for (int i = 0; i <= dev; i++) {
        int y = start.y + dy * i / dev;

        // 4. 内层循环：-80 到 0 像素容差范围扫描地板
        if (dy > 0) {
            for (int j = -80; j <= 0; j++) {
                getMascot().setAnchor(new Point(x, y + j));
                if (getEnvironment().getFloor(false).isOn(getMascot().getAnchor())) {
                    break OUTER;  // 检测到地板，anchor 定位到 floor.y
                }
            }
        }
    }

    // 5. ⚠️ 在物理循环【之后】执行动画，Pose.dy 会再次移动 anchor！
    getAnimation().next(getMascot(), getTime());
}
```

**Bug 路径**：若 Pose 的 `Velocity="0,3"`，步骤 4 把 anchor 定在 floor.y=866，步骤 5 又把它推到 869，下一帧 `hasNext()` 检查 869≠866，认为没落地，无限循环。

---

### `Animation.java` — 动画序列

```java
// 根据当前时间选取对应帧（时间对总帧长取模，循环播放）
public void next(final Mascot mascot, final int time) {
    getPoseAt(time).next(mascot);  // 调用 Pose.next()
}

public Pose getPoseAt(int time) {
    time %= getDuration();         // 循环
    for (final Pose pose : poses) {
        time -= pose.getDuration();
        if (time < 0) return pose;
    }
    return null;
}
```

---

### `Pose.java` — 单帧 ⭐ Velocity 的实际执行者

```java
public void next(final Mascot mascot) {
    // ⚠️ 直接修改 mascot 的 anchor 坐标！
    mascot.setAnchor(new Point(
        mascot.getAnchor().x + (mascot.isLookRight() ? -getDx() : getDx()),
        mascot.getAnchor().y + getDy()   // ← Velocity 的 Y 分量在这里生效
    ));
    mascot.setImage(...);  // 更新显示图片
}
```

XML 中的 `Velocity="dx,dy"` 被解析为 `Pose.dx` 和 `Pose.dy`，每帧调用 `next()` 时直接叠加到 anchor 上。

---

### `FloorCeiling.java` — 地板/天花板对象

```java
// ⚠️ 严格要求 Y 坐标精确相等，不允许任何误差
@Override
public boolean isOn(final Point location) {
    return getArea().isVisible()
        && (getY() == location.y)      // 严格相等！
        && (getLeft() <= location.x)
        && (location.x <= getRight());
}
```

`getY()` 返回工作区底边坐标（如 866）。anchor 只要偏移 1 像素就返回 false。这是 DPI 缩放环境下容易出问题的地方，也是 Fall.tick() 需要 -80~0 容差循环的原因。

---

### `UserBehavior.java` — 行为状态机

处理以下关键事件：

| 事件 | 处理逻辑 |
|------|----------|
| **LostGroundException** | 记录日志 → 切换到 Fall 行为 |
| **Out of Bounds（OOB）** | 将角色传送到 `(random_x, workArea.top - 256)` → 重新 Fall |
| **动作正常结束**（hasNext=false）| 按 NextBehaviorList 概率随机选下一个行为 |
| **鼠标拖拽** | 切换到 Dragged 行为 |
| **松手抛出** | 切换到 Thrown 行为 |

```java
// OOB 处理：传送到屏幕顶部等待重新落下
mascot.setAnchor(new Point(
    (int)(Math.random() * workArea.getWidth()) + workArea.getLeft(),
    workArea.getTop() - 256   // 256 像素高于屏幕顶部
));
```

---

### `Configuration.java` — XML 配置加载

```java
public void load(final Entry configurationNode, final String imageSet) {
    // 1. 检测 XML 是日语还是英语标签
    // 2. 加载对应 schema（字段名映射表）
    // 3. 解析 <ActionList> → 构造 ActionBuilder 列表
    // 4. 解析 <BehaviorList> → 构造 BehaviorBuilder 列表
}
```

**schema 的作用**：支持中/英/日文 XML 标签。`schema.getString("BorderType")` 返回当前语言对应的标签名字符串（如 `"BorderType"` 或 `"境界タイプ"`）。

---

### `ActionBuilder.java` — 动作解析

```java
// 解析 <Action Name="Stand" Type="Stay" BorderType="Floor" Duration="600">
// 所有属性都放入 params Map
getParams().putAll(actionNode.getAttributes());

// 根据 Type 映射到对应 Java 类
switch (type) {
    case "Stay":     return new Stay(schema, animations, variables);
    case "Move":     return new Move(schema, animations, variables);
    case "Embedded": return 反射调用 className 指定的类;
    // ...
}
```

---

## 四、配置文件详解

### `actions.xml` 结构

```xml
<Mascot>
  <ActionList>
    <Action Name="Stand"         <!-- 动作名，与 behaviors.xml 的 Action 属性对应 -->
            Type="Stay"          <!-- Java 类型映射 -->
            BorderType="Floor"   <!-- 绑定地板边界（触发 LostGround 检查） -->
            Duration="600">      <!-- 动作持续帧数（600 帧 × 40ms = 24秒） -->
      <Animation>
        <Pose Image="/idle_01.png"
              ImageAnchor="80,160"   <!-- 图片中锚点位置（从左上角量） -->
              Velocity="0,0"         <!-- ⚠️ 每帧额外位移，Fall 中必须为 0,0 -->
              Duration="50"/>        <!-- 此帧持续帧数 -->
      </Animation>
    </Action>
  </ActionList>
</Mascot>
```

**`ImageAnchor` 解读**：图片 160×160，`ImageAnchor="80,160"` 表示锚点在图片横向 80px、纵向 160px 处（即图片底部中心）。角色的 anchor 坐标对应屏幕上这个点的位置。

### `behaviors.xml` 结构

```xml
<Mascot>
  <BehaviorList>
    <Behavior Name="Stand"       <!-- 行为名 -->
              Frequency="30"     <!-- 初始被选中的权重 -->
              Action="Stand">    <!-- 对应 actions.xml 的 Action Name -->
      <NextBehaviorList>
        <BehaviorReference Name="WalkLeft"  Frequency="25"/>
        <BehaviorReference Name="WalkRight" Frequency="25"/>
        <BehaviorReference Name="Stand"     Frequency="50"/>
      </NextBehaviorList>         <!-- 本行为结束后的转换概率 -->
    </Behavior>
  </BehaviorList>
</Mascot>
```

**行为选择逻辑**：NextBehaviorList 内的 Frequency 按比例计算概率，不需要加和到 100。

### `settings.properties`

```properties
Multiscreen=false   # false = 只使用主显示器，防止多屏越界循环
```

`MascotEnvironment.getWorkArea()` 读取此属性决定工作区范围。

### `logging.properties`

```properties
handlers= java.util.logging.FileHandler
java.util.logging.FileHandler.pattern = ./ShimejieeLog%u.log
java.util.logging.FileHandler.limit = 50000   # 最大 50KB
java.util.logging.FileHandler.count = 1       # 保留 1 个文件
.level= INFO
```

日志为 XML 格式，每条记录包含 `<sequence>`（序号）、`<date>`、`<message>`。

---

## 五、调用链总览

```
Manager（40ms 定时器）
  └── Mascot.tick()
        └── UserBehavior.next()
              ├── Action.hasNext()？ → 否 → 按 NextBehaviorList 选下一个行为
              └── Action.next()
                    ├── ActionBase.initFrame()
                    └── ActionBase.tick()  →  具体子类实现
                          │
                          ├── Stay.tick()
                          │     ├── BorderedAction.tick()（跟随地板移动）
                          │     ├── 检查 isOn(anchor) → 失败则 LostGround
                          │     └── Animation.next() → Pose.next()（更新图片+位移）
                          │
                          ├── Move.tick()
                          │     ├── BorderedAction.tick()
                          │     ├── 检查 isOn(anchor) → 失败则 LostGround
                          │     └── Animation.next() → Pose.next()
                          │
                          └── Fall.tick()
                                ├── 物理引擎：计算 velocityY（重力加速）
                                ├── 外层循环：按步进移动 anchor
                                ├── 内层循环（j=-80~0）：扫描地板 isOn()
                                │     └── 检测到 → break，anchor 定位到 floor.y
                                └── Animation.next() → Pose.next()  ← ⚠️ Bug 所在
                                      └── 若 Velocity="0,3"，anchor.y 被额外 +3
```

---

## 六、字节码层面（Shimeji-ee.jar）

由于没有 `javac` 编译器，调试过程中直接修改了 JAR 内 `Fall.class` 的字节码：

| Offset | 原值 | 改后 | 含义 |
|--------|------|------|------|
| 4590 | `0x04`（iconst_1 = true） | `0x03`（iconst_0 = false）| `getFloor(true)` → `getFloor(false)` |
| 4524-4525 | `0x10 0xB0`（bipush -80）| （曾临时改为 0x03 0x00，已恢复）| 内层 j 循环起点 |

**JAR 修改流程**：
```
1. Python zipfile 提取 Fall.class
2. 用 .NET byte[] 修改指定 offset
3. Python zipfile 重建 JAR（必须用正斜杠路径）
```

Windows 下 .NET `ZipFile.CreateFromDirectory` 生成的 JAR 内路径为反斜杠（`com\group_finity\...`），Java ClassLoader 只认正斜杠，会导致类加载失败。必须用 Python `zipfile` 显式替换路径分隔符。
