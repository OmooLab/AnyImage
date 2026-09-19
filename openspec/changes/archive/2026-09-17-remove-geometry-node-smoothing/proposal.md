## Why

几何节点组当前在主体几何构建完成后提供一轮可选的整体 mesh smooth，既增加节点接口与实现复杂度，也会软化已经确定的表面细节。应移除这类末端后处理，同时保留边界平滑、法线平滑等独立业务所需的控制与权重。

## What Changes

- **BREAKING**：从所有相关几何节点组公开接口移除 `Smooth` 输入，生成结果不再执行末端整体 mesh smooth。
- 删除仅服务于末端整体 smooth 的节点链、构建调用与测试约束。
- `Smooth Weight` 若仍被 `Boundary Smooth` 等独立处理使用则保留；若只控制已删除的末端 smooth，则连同接口与相关逻辑删除。
- 保留 `Boundary Smooth`、`Normal Smooth`、shade smooth，以及深度/轮廓生成过程中的其他专用平滑行为。
- 重建并验证 `O_AnyImage.blend`，同步节点组接口清单、布局预期及相关内部说明。

## Capabilities

### New Capabilities

- `geometry-node-smoothing`: 规定几何节点输出不得追加整体 mesh smooth，并明确专用平滑控制及共享权重的保留规则。

### Modified Capabilities

无。

## Impact

- 影响 `O Image Cutout`、`O Image Depth Cutout`、`O Image Depth Plane`、`O Image Depth Panorama`、`O Image Relief Plane` 的公开 modifier 接口与生成图。
- 影响 `tools/nodes/groups`、共享 smoothing 构建代码的实际引用、节点资产与节点相关测试。
- 现有依赖 `Smooth` socket identifier 的 modifier 配置或调用方需要停止写入该输入；`Smooth Weight` 只在没有其他消费者的节点组中移除。
