# Validation

## Root Cause

- Rear 边界锯齿不是由 Rear 法线陡峭或 `Pin Sharp` 天生削弱导致。Front 的原始边界同样锯齿，关键差异是旧 Rear 在 Faces Extrude 后已与 Wall 闭合，失去了开放边界平滑条件。
- 先前“共同平滑较弱”的实验比较了不同输入：参考路径先平滑 Front，再从平滑后的 Front 生成 Rear；候选路径则从 raw Front/Rear 共同平滑。该对照不能说明 Join 或单 Repeat 会降低效果。
- 真实图像上关闭 `Pin Sharp` 只使 Front/Rear 边界位移变化约 4–6%，不能解释观察到的显著差异。

## Corrected Smoothing Experiment

- 两条路径均从相同 raw Front 和已经位移、Rear Smooth、Flip Faces 的 raw Rear 开始。
- “Join 后一次共同平滑”与“两张 leaf 分别平滑后 Join”的 Front 和 Rear 位置均在 `1e-6` 容差内一致。
- 真实图像在 Thickness 0.35、Boundary Smooth 16、Rear Smooth 8 时，归一化边界弯折由 Front 0.1668、Rear 0.1508 衰减到强平滑下的 0.0732、0.0728，未出现 Rear 系统性偏弱。
- 默认型 Thickness 1、Boundary Smooth 4、Rear Smooth 0 时，Front/Rear 的归一化弯折分别为 0.26083、0.28098；强平滑下为 0.11041、0.11065，响应基本对称。

## Geometry Decisions

- Rear offset 经 `Evaluate on Domain(FACE, FLOAT_VECTOR)` 后 Set Position，随后 Rear Smooth 和 Flip Faces，最后才与 Front 进入共同 Boundary Smooth。
- source index 在投影拓扑完成和 CONNECTED merge 后保存，穿过两张 leaf 的位置修改、Flip、Join、Repeat 和 Separate。
- Edges Extrude 只负责 Wall 拓扑；逐点 Rear target 通过 source-index lookup 得到，并以 Top selection 的 Set Position 重定位。
- 投影阶段 CONNECTED Merge by Distance 保留 `mean edge length × 1e-6`，只清理投影产生的连接点精确重合；最终 ALL merge 使用独立的小容差，只焊接已经重合的桥接端点。
- raw cut marker 以 Boolean Point attribute 穿过 projection merge，并在单层最终 topology 上生成 `_o_boundary_smooth_weight`。由于 Store Value 字段惰性求值，marker 保留到共同 Repeat 完成后，再由最终 `_o_*` wildcard 清理；Front / Rear 与共同 Repeat 不再存储或读取 `_o_leaf_cut`。
- `project_depth_surface()` 的中间清理由 `_o_*` 收窄为 `_o_depth_*`；此前该节点会提前删除调用方 `_o_cut_boundary`，是权重退化为灰色 Outline 路径的直接原因。

## Integrated Matrix

- Balloon 和 Shell 模式。
- Boundary Smooth 0、4、16；Rear Smooth 0、8。
- 原始 Outline、孔洞、Depth Split、Depth Limit 和超过 4096 source points 的输入。
- 所有聚焦用例坐标有限，正厚度输出闭合且有向边成对，面面积为正，UV 与公开属性保留，输出无 `_o_*` 临时属性。
- 节点结构检查确认只有一个 Boundary Smooth Repeat Zone，Rear Flip 在 Repeat 之前，Repeat 之后才 Separate 和 Extrude；两个 Merge 分别为投影 `CONNECTED` 与最终 `ALL`。
- 属性生命周期检查确认共同 Repeat 只直接读取冻结的最终 smoothing weight；raw cut marker 不在中途删除，输出仍无 `_o_*` 临时属性。

## Final Verification

- `uv run --group blender pytest tests/nodes/test_depth_cutout_leaf_bridge.py -q` — 21 passed。
- `uv run --group blender pytest tests/tools/nodes/test_inventory.py -q` — 4 passed。
- `uv run --group blender node-group build` — 成功生成资产并重载检查 Blender 4.5.3 LTS 中的 10 个节点组；节点与节点工具测试 151 passed。
- 本次权重冻结调整后的 `uv run --group blender node-group build` — 151 passed，保存资产无缺失属性警告。
- 移除中途 cut marker 删除后的 `uv run --group blender node-group build` — 151 passed；最终输出属性测试确认 `_o_cut_boundary` 与 `_o_boundary_smooth_weight` 均未泄漏。
- 收窄 projection 清理范围、启用完整 cut weight，并完成 Rear Smooth / profile exponent / Edge Turn 调整后的 `uv run --group blender node-group build` — 151 passed。强平滑验证采用无双边界边三角形的拓扑门槛。
