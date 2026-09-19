## 1. 节点组实现

- [x] 1.1 从 Cutout、Depth Cutout、Depth Plane、Depth Panorama 与 Relief Plane 删除 `Smooth` 接口及末端整体 `expand_smooth()` 调用，直接连接原有着色或输出阶段
- [x] 1.2 从 Cutout 与 Relief Plane 删除仅服务整体 smooth 的 `Smooth Weight`，并确认三个深度节点组继续以 `Smooth Weight` 驱动边界平滑
- [x] 1.3 检查共享 smoothing 构建函数的剩余调用，保留边界平滑所需实现并清理仅随末端整体 smooth 产生的无用代码

## 2. 调用方与测试

- [x] 2.1 清理 operator、节点检查工具和测试中对已删除 `Smooth` 及相应 `Smooth Weight` 的赋值与接口预期
- [x] 2.2 更新节点组库存与布局测试，验证五个节点组不再暴露 `Smooth`，且仅三个深度节点组保留 `Smooth Weight`
- [x] 2.3 精简整体 smooth 行为测试，并保留或补充边界平滑、法线平滑、Fill Smooth 与 smooth shading 不变的有效覆盖

## 3. 资产与验证

- [x] 3.1 同步 `tools/nodes` 与 `docs/internals` 中相关接口和实现说明，检查仓库内不存在失效的整体 `Smooth` 引用
- [x] 3.2 运行 `uv run node-group build`，更新并验证 `src/anyimage/assets/O_AnyImage.blend`
- [x] 3.3 运行相关节点与 operator 测试，检查最终差异并确认专用平滑路径仍正常
