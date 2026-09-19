## Why

整图 Depth Plane 与 Depth Surface 共用图片、网格和深度预测，只在几何模式上不同，独立入口使选择与切换复杂。相机 XYZ 已包含标量 Z 深度，统一产物可以消除生成和读取中的格式分支。

## What Changes

- 合并为一个 Convert to Depth Plane 入口与 `O Image Depth Plane` 节点组，提供 Relief（固定底面浮雕）和 Camera（相机投影曲面）模式，默认 Relief；切换模式复用已加载深度。
- Camera 保留沿平滑法线的 Thickness 与 Normal Smooth（默认 50，范围 0–50），整图保持连续矩形网格。
- **BREAKING**：删除独立 Depth Surface Operator、菜单项和公开资产组，直接使用合并接口。
- **BREAKING**：删除 `z-depth.exr` 输出，将 `vector-depth.exr` 更名为 `depth.exr`，结果键统一为 `depth`。RGB 为相机 XYZ，Alpha 为有效性。
- 所有整图和 Cutout 深度消费者统一读取该产物；标量深度读取 B/Z 通道。内部 `GeometryFrame.depth` 与 `depth.json` 继续承担计算和标定职责。

## Capabilities

### New Capabilities

- `unified-depth-plane`: 一个整图转换入口与节点组中的 Relief / Camera 模式、接口及几何行为。
- `depth-artifact-contract`: 统一深度文件、结果键、通道约定及全部消费者的读取契约。

### Modified Capabilities

无。当前 `openspec/specs/` 为空；本变更承接已实现但未归档的 `add-projected-depth-plane`，以本次契约定义合并后的行为。

## Impact

涉及整图转换 Operator、菜单与注册、对象创建与结果加载、Cutout 请求与响应、Server Job 与预测产物层、深度纹理写出、节点构建与验证及相关测试。节点资产文档随节点接口同步；本次只创建提案，资产构建和 Blender 视觉验收在实现后的资产更新阶段执行。无需新增依赖。
