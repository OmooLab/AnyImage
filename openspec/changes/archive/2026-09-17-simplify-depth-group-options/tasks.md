## 1. 共享平滑收敛

- [x] 1.1 将 `expand_smooth()` 收敛为影响场形态，删除 `weight_name`、`pin_sharp` 与无影响场分支
- [x] 1.2 更新 `smooth_cut_boundary()` 调用并确认影响带、保护规则与轮廓权重不变

## 2. 节点组接口

- [x] 2.1 从 Depth Plane、Depth Cutout、Depth Panorama 删除 `Smooth Weight` 输入
- [x] 2.2 将 Depth Plane、Depth Cutout、Relief Plane 的 `Reference Depth` 移到 Options 最后一项

## 3. 测试与资产

- [x] 3.1 更新节点库存、Options 排列与边界平滑行为测试，移除 `Smooth Weight` 依赖
- [x] 3.2 运行 `uv run node-group build` 重建并验证节点资产
- [x] 3.3 运行节点与 Operator 相关测试，检查残留引用与最终差异
