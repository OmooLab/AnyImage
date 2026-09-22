## 1. 修正方案与基线

- [x] 1.1 以真实图像和不对称网格复核 Rear 轮廓问题，确认共同平滑本身不削弱 Rear，并撤销 `Pin Sharp` 是核心原因的错误归因。
- [x] 1.2 明确投影阶段 CONNECTED Merge by Distance 的退化清理职责、极小相对容差和非流型风险边界。
- [x] 1.3 将提案、设计和规范固定为“同源 raw Front/Rear、Rear 预先 Flip、一次共同 Boundary Smooth、之后桥接”的唯一实现顺序。

## 2. 共同平滑叶片

- [x] 2.1 删除投影阶段的 Front-only Boundary Smooth，由同一最终投影拓扑生成 Front 与 Face-domain Rear。
- [x] 2.2 Rear 依次执行位移、Rear Smooth、Flip Faces，再与 Front 写入 leaf id 并 Join。
- [x] 2.3 按厚度选择 Front-only 或 joined leaves，执行唯一一次 Boundary Smooth Repeat，再按 leaf id 分离。

## 3. 稳定桥接

- [x] 3.1 保留分支前保存的 source index，平滑后按 source index 建立 Rear Position lookup。
- [x] 3.2 以完整 Front 的 boundary edges 执行 Edges Extrude，并用 Top selection 重定位到同源 Rear target。
- [x] 3.3 Join Front、Rear、Side 后只焊接已重合端点，并清理 `_o_*` 临时属性；零厚度只输出 Front。

## 4. 验证与资产

- [x] 4.1 把错误的不同顺序对照替换为相同 raw leaf 输入的共同/独立平滑等价测试。
- [x] 4.2 增加单 Repeat、Rear 预先 Flip、source-index 对应、投影 merge 退化和零厚度路径检查。
- [x] 4.3 运行相关测试与 `uv run --group blender node-group build`，更新验证记录并严格校验 change。

## 5. 冻结边界平滑权重

- [x] 5.1 在最终单层 projection topology 上计算 Outline 0.1、Split / Depth Limit 1.0 及两圈 falloff，保存最终 Point-domain smoothing weight。
- [x] 5.2 Front / Rear 与共同 Repeat 只直接读取最终 smoothing weight；临时 cut marker 保留其惰性依赖，并由最终 `_o_*` 清理删除。
- [x] 5.3 增加属性生命周期与单 Repeat 消费检查，重建并验证节点资产。
- [x] 5.4 修正字段惰性求值生命周期：取消 smoothing weight 与共同 Repeat 之间的 cut marker 删除，仅在最终 `_o_*` 清理中移除。
- [x] 5.5 将 `project_depth_surface()` 的清理范围从 `_o_*` 收窄为其自身拥有的 `_o_depth_*`，确保调用方 cut marker 穿过 projection。

## 6. Rear 控件调整

- [x] 6.1 将 `Back Smooth` 重命名为 `Rear Smooth`，其 `o_balloon` 强度系数使用 exponent `0.5`，并将 `Edge Turn` 默认值改为 `1`。
- [x] 6.2 将强边界平滑的拓扑门槛固定为无双边界边三角形，不再以局部面朝向变化判定失败。
