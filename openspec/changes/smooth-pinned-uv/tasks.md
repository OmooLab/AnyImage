## 1. 共享 UV 松弛

- [x] 1.1 在 `common/smoothing.py` 中构建保持 Face Corner 与 UV island 边界的 UV 邻域和边界目标，不跨 seam 混合
- [x] 1.2 扩展 `pinned_smooth` repeat state，使 Position 与已有 `UVMap` 使用相同迭代、作用范围、权重和 pin 选择逐轮松弛
- [x] 1.3 为零迭代提供精确旁路，并按 `_o_*` 协议清理必要的临时属性

## 2. 行为测试

- [x] 2.1 更新 Depth Cutout、Depth Plane 与 Depth Panorama 的边界测试，验证作用带内 UV 平滑、作用带外 UV 不变
- [x] 2.2 增加 Panorama 经度 seam 与 UV island 隔离测试，验证不连续 Face Corner UV 不被混合
- [x] 2.3 更新 Cutout Symmetry 的 Seam Smooth 与 Fill Smooth 测试，验证 UV 随作用范围松弛且镜像焊接与闭合性不变
- [x] 2.4 增加零迭代测试，验证几何与 UV 精确旁路

## 3. 节点资产验证

- [x] 3.1 运行相关节点测试并检查所有 `pinned_smooth` 调用方的既有几何行为
- [x] 3.2 运行 `uv run --group blender node-group build`，验证生成资产、临时属性清理及 Capture Attribute 为零
- [x] 3.3 检查最终差异与旧的 UV 恒定断言，确认未改变其他 Smooth 路径
