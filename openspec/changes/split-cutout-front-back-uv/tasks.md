## 1. 双区图片协议

- [x] 1.1 在 Cutout 结果阶段生成 Front 与水平镜像 Rear 颜色区，保持 byte、float、Alpha、透明 RGB、颜色空间和非 Cutout 默认行为
- [x] 1.2 让 Cutout AI 始终直接分析未复制的正面图，并补充颜色尺寸、像素一致性及单片分析输入测试
- [x] 1.3 保持 Cutout Job 输出单张 Normal 与 Depth，在 Blender 中只为 Normal 建立镜像后片，Depth 与 `depth.json` 保持单区协议
- [x] 1.4 让 CPU 侧 Alpha、参考深度、中位深度和方向拟合直接读取 Atlas 之前的单区 Color 或单区 Depth，不保留双区 Depth 兼容参数
- [x] 1.5 保持既有 Boundary Padding 只处理单区 Color 与 Depth，再生成 Color、Normal 镜像后片；增加真实像素顺序、float packed 重载、单区 Depth 与非 Cutout 单区尺寸测试

## 2. 基础与普通 Cutout UV

- [x] 2.1 将 Cutout BaseShape 的 `UVMap` 从 0–1 映射到 Atlas 上半区，并验证零厚度 Flat、Solid 只使用 Front 区域
- [x] 2.2 在 `O Image Cutout` Balloon 路径中保持 Front UV、将 Rear Corner UV 下移 `0.5`，并让重合轮廓保持 Face Corner seam
- [x] 2.3 在 `O Image Cutout` Shell 分段挤出路径中建立相同的 Front、Rear 和分侧 Side 所有权，确保没有单张 Side face 跨越上下 tile
- [x] 2.4 增加普通 Cutout 的 Balloon、Shell、零厚度、正厚度及厚度切换 UV 求值测试，验证 Rear 与 Side seam 不被焊接合并且可见外形不变

## 3. Depth 与对称 Cutout UV

- [x] 3.1 调整 `O Image Depth Cutout`，在既有叶片 UV 平滑之后将 Rear Corner UV 下移 `0.5`，并保持 Front 位于上半区
- [x] 3.2 覆盖 Depth Cutout 的双叶片桥接 UV，使 Front-side 使用上半区、Rear-side 使用下半区，并在共享 Side ring 保持 Face Corner seam
- [x] 3.3 调整后置 Cutout Symmetry，使 Retained side 与 Mirrored side 完整保留输入的 Front/Rear tile，并阻止焊接后 UV 跨 seam 平滑
- [x] 3.4 增加 Depth Cutout Balloon、Shell、零厚度、Split、Boundary Smooth 与 Depth Symmetry 的 UV 测试，并验证 Cutout 单区 Depth 映射不会泄漏到共享的 Depth Plane 采样

## 4. 集成验证与节点资产

- [x] 4.1 更新 Cutout 对象与材质集成测试，验证 Color、Normal 使用双区布局、Depth 保持单区且单一材质正确采样 Front 和 Rear
- [x] 4.2 运行相关 Python 与 Blender 测试，修复双区尺寸或 UV 协议引起的回归
- [x] 4.3 运行 `uv run --group blender node-group build` 重建并验证节点资产，确认 Capture Attribute 为零且无临时 `_o_*` 属性泄漏
- [x] 4.4 检查最终差异和旧重叠 UV 假设，确认未新增兼容路径、材质槽、公开节点输入或非 Cutout 行为变化
