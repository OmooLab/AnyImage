## 1. 双向桥接

- [x] 1.1 移除中值收拢与两圈 seam influence，保留 Front / Rear 原始 leaf positions
- [x] 1.2 按 `_o_leaf_source_index` 计算 Front / Rear 对应点中值并存入两张 leaf
- [x] 1.3 从 Front 与 pre-flipped Rear 的全部边界分别 Edges Extrude，将两侧 Top points 重定位到共同中间环

## 2. Side UV

- [x] 2.1 以局部 UV Blur 的 `blurred - original` 表达内侧方向
- [x] 2.2 将 leaf 边缘 UV 沿内侧方向移动，通过边界 influence 渐变到零
- [x] 2.3 让 Side base 继承调整后的 boundary UV，并为 Side top 保存目标 UV

## 3. 闭合与验证

- [x] 3.1 Join Front、Rear 与两半 Side，使用单次固定 `1e-6` ALL Merge by Distance 焊接基座和中间环
- [x] 3.2 更新结构与拓扑测试，验证两个 Extrude、共同中间环、face 数、方向、闭合性、多边界和高密度输入
- [x] 3.3 更新 UV 测试，验证 leaf 边缘影响带参与过渡、带外 UV 不变及 Side UV，并覆盖 `Boundary Smooth = 0` 和零厚度旁路
- [x] 3.4 运行 Depth Cutout 相关测试并修正失败

## 4. 节点资产

- [x] 4.1 运行 `uv run --group blender node-group build`，生成并验证 `O Image Depth Cutout` 资产
- [x] 4.2 复查 UV 方向、影响范围、最终差异与相关测试结果

## 5. 实图反馈修正

- [x] 5.1 将 Side top UV 固定为 original boundary UV，并把局部 UV Blur 改为四次
- [x] 5.2 以实际最大位移的 Smoothstep 控制 leaf UV pull 与 Front Normal Reduction
- [x] 5.3 更新对应结构预期并重新生成节点资产，不运行测试

## 6. 渐变调参与节点精简

- [x] 6.1 将厚度 Smoothstep 范围改为 `0～1`，并把 leaf UV pull 改为 `0.5`
- [x] 6.2 将 Bridge UV 的 U/V 两次 Point-domain 转换精简为一次 FLOAT_VECTOR 转换
- [x] 6.3 将 Bridge UV 的 boundary influence 从两圈扩展到四圈，保持 Boundary Smooth 原规则
- [x] 6.4 同步结构预期并重新生成节点资产，不运行测试

## 7. 低厚度响应

- [x] 7.1 在厚度 Smoothstep 后应用 `Pow 0.5`，同步 UV pull 与 Front Normal Reduction
- [x] 7.2 重新生成节点资产，不运行测试

## 8. 共享边界范围与 Side Roundness

- [x] 8.1 在 leaf 分离前计算四圈 `_o_boundary_falloff`，供 Boundary Smooth 与 Top UV 共用
- [x] 8.2 新增 `Side Roundness` 0～1 参数，以法线约束的外移目标调节共同 Side ring
- [x] 8.3 让 Rear 按 source index 采样 Front 计算的唯一 Side ring target，精简重复 lookup
- [x] 8.4 同步接口、属性与结构预期，重新生成节点资产，不运行测试

## 9. Side Roundness 定稿与验证

- [x] 9.1 将 `Side Roundness = 1` 缩放为旧范围 `0.5` 的效果，并将默认值设为 `0.5`
- [x] 9.2 运行相关测试并修正失败
- [x] 9.3 运行完整节点资产构建与验证
