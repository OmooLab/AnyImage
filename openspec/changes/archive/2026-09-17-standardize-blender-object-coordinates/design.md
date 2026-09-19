## Context

当前 Plane、Depth Plane、Relief Plane、Cutout 与 Depth Cutout 的生成网格沿 Image Empty 局部坐标：图片平面为 XY，图片向上为 +Y，深度向纸内为 -Z。Cutout 的 BaseShape 位于 `Z=0`，Geometry Nodes 沿 Z 做厚度、投影和对称。这个约定与 Blender 常规对象坐标不一致：Blender 对象通常 up=Z、front=-Y。

为了把侧视对象最终摆成“左右对称轴为 X、up 为 Z”，现有实现给 Cutout 节点加入 `Depth Axis`，把输出整体转到 +X。该参数把最终摆放轴与对称轴耦合，还要求 Object Space Normal 额外补偿，使用户在四个 Cutout 入口间看到不一致的最终方向。

本次变更把生成几何的 canonical local frame 统一到 Blender 对象坐标，并删除 `Depth Axis`。

## Goals / Non-Goals

**Goals:**

- 为所有生成几何定义并实现同一套 Blender canonical local frame。
- 让 Cutout BaseShape、Plane、Depth Plane、Relief Plane 的未修改网格都位于 XZ 平面，`Y=0`。
- 让 Depth Symmetry 在 canonical 坐标中沿 Y 镜像，最后绕 Z 转到 X，保持 up=Z。
- 让 Object Space Normal 随 canonical frame 和 Depth Symmetry 最终朝向一致。
- 删除 `O Image Cutout` 与 `O Image Depth Cutout` 的 `Depth Axis` 接口和实现。

**Non-Goals:**

- 不改变 Image Empty 自身坐标或 Blender 相机/Server 模型输出坐标。
- 不为用户新增轴向选择项。
- 不自动迁移用户工程中已保存的旧节点组或已生成对象。

## Decisions

### 1. 新 canonical frame 由创建阶段直接生成

不添加“全局坐标变换”节点，而是在 Python 建网和节点构建阶段直接按新坐标生成。

```text
旧 Image Empty local → 新 canonical object local

X   → X
Y   → Z
-Z  → +Y
+Z  → -Y
```

结果：

```text
X = 图片右
Z = 图片 up
+Y = 图片纸内 / depth
front = -Y
BaseShape / Plane 未修改网格位于 XZ 平面，Y=0
```

备选方案是在所有 modifier 前统一旋转，但会让 BaseShape、UV、metric 和节点内部轴反复转换，且不能消除 `Depth Axis` 类补偿。直接生成更直接，符合“少就是多”。

### 2. 所有节点深度轴从 Z 改为 Y

厚度、投影、Shell、Balloon、Relief 位移和 Depth Symmetry 镜像均改为 Y 轴语义：

- Image Plane 的网格/立方体尺寸使用 X/Z，厚度沿 Y。
- Depth Plane 与 Relief Plane 的投影位移沿 Y。
- Cutout 与 Depth Cutout 的 front/back 方向由 -Y/+Y 表达。
- `Depth Direction` 默认值从 `(0, 0, 1)` 改为 `(0, 1, 0)`。

### 3. Depth Symmetry 作为两阶段坐标语义

`O Image Cutout Symmetry` 保持“先 canonical 对称、后最终摆放”：

```text
canonical step:
  mirror plane = XZ, mirror axis = +Y
  keep one Y sign, mirror to the other side

final step:
  rotate around Z so +Y → +X
  keep +Z as up
```

该 yaw 旋转同时会把 canonical front `-Y` 变成 `-X`。这是本变更明确接受的最终朝向。

删除 `O Image Cutout` 与 `O Image Depth Cutout` 的 `Depth Axis`。Depth Symmetry 的最终朝向只存在于 `O Image Cutout Symmetry`。

### 4. Object Space Normal 使用明确的几何属性契约

材质仍通过 Geometry 属性把 Object Space Normal 从生成坐标转换到最终渲染坐标：

- canonical frame 转换进入 Object Normal 的解释路径。
- Depth Symmetry 的 front/back 反射改为 canonical Y 反射。
- 最终 yaw 旋转由 `O Image Cutout Symmetry` 写入最终朝向属性，材质读取同一属性。
- 删除旧 `Depth Axis` 对应的 `CUTOUT_Z_TO_X` 补偿路径。

普通 Plane / Depth Plane / Relief Plane 的 Object Normal 也按新 canonical frame 验证，不再依赖 Cutout 的旧轴补偿。

## Risks / Trade-offs

- 影响面很大，几乎覆盖所有生成几何和节点资产 → 使用既有 `uv run node-group build` 与全量测试闭环；不保留兼容层。
- BaseShape 和 Plane 世界位置可能出现符号/方向回归 → 对每个入口比较源 Image Empty 的世界 bounds 和生成网格 world-space 包围盒。
- Object Space Normal 在渲染中的表现可能不易从网格位置直接推断 → 保留/扩展材质渲染测试，覆盖 front、back、wall 和最终朝向。
- Depth Symmetry 最终 front 从 -Y 变为 -X，可能影响后续用户操作 → 在 spec 中明确该行为，不提供旧行为。
- 旧 `.blend` 内嵌节点和已生成对象无法自动迁移 → 运行时继续从 `O_AnyImage.blend` 资产加载，不扫描用户工程。

## Migration Plan

1. 先在 Python 建网层实现新 canonical frame，并同步 Cutout BaseShape、Plane、Depth Plane、Relief Plane 的顶点/UV/法线。
2. 重写 Geometry Nodes 的轴语义并删除 `Depth Axis`。
3. 调整 Depth Symmetry 与 Object Normal 属性契约。
4. 更新测试、`tools/nodes/check.py` 和资产构建；运行 `uv run node-group build`。
5. 运行全量测试并检查旧 `Depth Axis`、旧轴常量与旧 world-space 方向引用。

回滚策略为从版本控制恢复本次变更前的源码与 `O_AnyImage.blend`，不涉及数据迁移。

## Open Questions

- 最终 yaw 旋转选择 `+Y → +X` 还是 `+Y → -X`：在实现时用一个小型 orientation test 固定，保持 front 变化方向可预测。
- 普通 Plane / Depth Plane 的 Object Normal 转换放在材质节点内还是图片加载阶段：设计倾向保留材质属性契约，实现时按节点复杂度和测试成本选择。
