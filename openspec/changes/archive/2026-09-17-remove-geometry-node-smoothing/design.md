## Context

五个主节点组在业务几何完成后调用共享 `expand_smooth()`，由公开的 `Smooth` 与 `Smooth Weight` 控制整体顶点位置平滑。三个深度节点组还通过同一个 `Smooth Weight` 驱动 `Boundary Smooth`；`O Image Cutout` 与 `O Image Relief Plane` 则没有该权重的其他消费者。项目同时存在 `Boundary Smooth`、`Normal Smooth`、`Fill Smooth` 和 shade smooth，它们分别承担切边修整、位移法线处理、填充墙体构造与着色职责，不属于待移除的末端整体 smooth。

## Goals / Non-Goals

**Goals:**

- 移除五个主节点组输出前的整体 `expand_smooth()` 后处理及其 `Smooth` 接口。
- 按真实消费关系处理 `Smooth Weight`：深度节点组保留，Cutout 与 Relief Plane 删除。
- 保持边界、法线、填充墙体与着色平滑行为不变。
- 使源码、保存的节点资产、接口测试与行为测试保持一致。

**Non-Goals:**

- 不移除或重新调参 `Boundary Smooth`、`Normal Smooth`、`Fill Smooth`。
- 不取消 `GeometryNodeSetShadeSmooth` 或 Blender object polygon 的 smooth shading。
- 不改变生成前的轮廓平滑、深度字段模糊或其他不位于主输出末端的专用算法。

## Decisions

1. 以“主几何构建完成后，由 `Smooth` socket 控制的 `expand_smooth()`”作为删除边界。这样可直接对应用户可见接口和五条真实调用链，避免把名称含 smooth 的不同业务误删。备选方案是删除所有含 smooth 的节点，但会破坏边界、法线和墙体生成能力。
2. 五个节点组均删除 `Smooth` socket，并把原本送入整体平滑的几何直接连接至现有 shade smooth 或 group output。此方式不引入旁路或兼容 socket，符合项目不保留旧路径的约束。
3. `Smooth Weight` 按消费者保留：`O Image Depth Cutout`、`O Image Depth Plane`、`O Image Depth Panorama` 继续用于 `smooth_cut_boundary()`；`O Image Cutout` 与 `O Image Relief Plane` 删除该 socket。共享 `expand_smooth()` 仍由边界平滑实现使用，因此保留公共实现。
4. 测试从“整体 smooth 可配置”改为验证接口不存在、未追加整体平滑、专用平滑仍有效。节点组逻辑与接口变化后执行规定的 `uv run node-group build`，由构建流程更新并验证 `.blend` 资产。

## Risks / Trade-offs

- [已有文件中的 modifier 仍保存旧 socket 值] → 这是明确的接口破坏；不提供兼容层，新资产和新建对象只暴露当前接口。
- [删除整体平滑后表面更忠实但可能更显离散] → 由细分密度及各专用平滑控制负责各自质量，不重新引入通用末端处理。
- [误删共享权重或公共 helper] → 以调用图和节点接口测试确认三个边界平滑消费者仍连接，公共 helper 仍被 `boundary_smoothing.py` 引用。
- [保存资产与源码漂移] → 必须运行节点资产构建，并执行相关节点与 operator 测试后检查旧接口引用。

