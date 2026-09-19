## Why

`Smooth Weight` 在三个深度节点组中始终以 `1` 参与边界平滑，单独暴露只会增加接口与实现复杂度；`Reference Depth` 是标定值，用户极少调整，却占据 Options 的首位。

## What Changes

- **BREAKING**：从 `O Image Depth Plane`、`O Image Depth Cutout`、`O Image Depth Panorama` 的公开接口移除 `Smooth Weight`，边界平滑固定使用完整强度。
- 删除共享 smoothing 中只为 `Smooth Weight` 与 `pin_sharp` 服务的分支和节点。
- 将 `O Image Depth Plane`、`O Image Depth Cutout`、`O Image Relief Plane` 的 Options 中 `Reference Depth` 移到面板最后一项。
- 重建并验证 `O_AnyImage.blend`，同步节点接口清单与相关测试。

## Capabilities

### New Capabilities

- `depth-node-options`: 规定深度与浮雕几何节点组 Options 面板的公开控制项集合与排列顺序。

### Modified Capabilities

无。

## Impact

- 影响 `O Image Depth Plane`、`O Image Depth Cutout`、`O Image Depth Panorama`、`O Image Relief Plane` 的公开 modifier 接口。
- 影响 `tools/nodes/groups`、`tools/nodes/common` 的边界平滑构建代码、节点资产与节点相关测试。
- 现有依赖 `Smooth Weight` socket identifier 的 modifier 配置或调用方需要停止写入该输入；默认值下的几何结果保持不变。
