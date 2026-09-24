## Context

Depth Cutout 的 Front 初始轮廓同样锯齿，但开放边界上的 `smooth_cut_boundary()` 可以有效消除阶梯。Rear 的问题不是法线陡峭或 `Pin Sharp` 天生更弱，而是旧结构在 Faces Extrude 生成并闭合侧壁后，Rear 已不再是开放边界。

真实图像和不对称网格实验确认：从同一份未平滑投影拓扑生成 Front 与 Rear，Rear 先完成 Face-domain 位移、Rear Smooth 和 Flip Faces，再将两个断开的 leaf Join 后共同平滑，Front 与 Rear 的轮廓衰减对称；共同执行与对相同两张 leaf 分别执行在浮点容差内等价。此前所谓“共同平滑变弱”来自错误对照：独立路径先平滑 Front，再由已平滑 Front 生成 Rear，比较的不是相同输入。`Pin Sharp` 开关在真实样本上只造成约 4–6% 位移差，不是 Rear 锯齿的核心原因。

投影后的 CONNECTED Merge by Distance 使用平均边长的 `1e-6` 容差，用于清理 Depth Limit 或投影把相邻点压到完全相同位置时产生的零长度边和退化面。它保留，但必须保持极小相对容差，不能承担叶片配对或最终闭合职责。

## Goals / Non-Goals

**Goals:**

- Front 与 Rear 从同一份最终投影拓扑生成，并在 Wall 生成前共同执行一次 Boundary Smooth。
- Rear 在共同平滑前完成 Face-domain 位移、Rear Smooth 和 Flip Faces。
- 以保存的 source index 对应 Front/Rear 边界点，逐点生成 Wall。
- 保留 Balloon / Shell、Depth Split、Depth Limit、UV 和现有属性语义。
- 通过相同输入的共同/独立对照验证平滑没有偏向 Rear。

**Non-Goals:**

- 不新增公开输入或桥接模式。
- 不修改 Cutout 源网格、Depth Split 或 Depth Limit 的拓扑算法。
- 不使用 Capture Attribute，不用更大的 Merge by Distance 容差掩盖对应错误。

## Decisions

### 1. 固定叶片生成与平滑顺序

最终投影拓扑在分支前保存 Point-domain `_o_leaf_source_index`。Front 只应用现有 Front 位移；Rear 从同一原始投影分支，位移向量先以 `Evaluate on Domain(FACE, FLOAT_VECTOR)` 固定，再执行 Rear Smooth 和 Flip Faces。Rear Smooth 的 profile 系数使用 `pow(o_balloon, 0.5)`，使中低权重区域过渡更平。

Front/Rear 分别写入临时 leaf id 后 Join。正厚度把两张 leaf 输入唯一一次 `smooth_cut_boundary()`；零厚度通过同一入口只输入 Front。共同平滑之后再按 leaf id Separate，避免前后生成顺序不同，也避免两条 Repeat Zone 的成本。

共同平滑不会把断开的 mesh island 互相连接。等价测试必须以完全相同的 raw Front 与 pre-flipped Rear 为输入，比较“一次 Join 后平滑”与“两张 leaf 分别平滑”；禁止再用“先平滑 Front、再生成 Rear”的旧顺序作为参考。

### 2. Source index 是桥接协议

保存的 source index 必须穿过 Set Position、Rear Smooth、Flip Faces、Join、Boundary Smooth 和 Separate Geometry。Rear lookup 按该属性 Sort Elements，使 Sample Index 的 lookup index 与 source index 一致；当前动态 `Index` 不能直接充当跨几何键。

任何会删除、复制或合并 leaf 点的节点都必须位于 source index 建立之前，或显式重建协议。最终 Merge 只焊接已通过 lookup 放到同一位置的端点。

### 3. Wall 使用边界 Edges Extrude 加 Top 重定位

Edges Extrude 接收完整 Front mesh，以 Mesh Boundary Edges 作为 Selection，保留相邻 Front faces 提供的边绕向。Extrude Offset 只创建拓扑；Top selection 随后由 Set Position 按 source index 查到的 Rear Position 重定位。最后只保留 Side faces。

不能把逐点 offset 直接接到 Edges Extrude，因为它在 Edge domain 求值并会平均共享点的相邻边值；也不能回退到 Faces Extrude 的 Face-domain Offset。

### 4. Rear 先 Flip，最终只做精确焊接

Rear 在共同平滑前 Flip Faces，使 leaf 阶段已具有最终绕向。Front、Rear 与 Wall Join 后使用极小相对容差 Merge by Distance。Merge 前 Wall 两端必须已经与对应 leaf 重合；Merge 不参与寻找配对。

投影阶段的 CONNECTED merge 与最终实体 weld 职责不同：前者清理投影退化，后者只合并桥接产生的共点副本。两者都不得扩大到可能误焊窄缝的范围。

### 5. 在单层最终拓扑上冻结平滑权重

Split / Depth Limit cut marker 只用于区分完整权重切口与 `0.1` 权重原始 Outline。它以 Boolean Point attribute 穿过 projection 与 CONNECTED merge；在最终单层 projection topology 上计算两圈 falloff 和最终 Boundary Smooth weight。由于 Geometry Nodes 字段惰性求值，marker 必须保留到共同 Repeat 消费最终权重之后，再由输出端 `_o_*` wildcard 统一删除。

`project_depth_surface()` 只清理自己拥有的 `_o_depth_*`，不得使用 `_o_*` 删除调用方属性。Depth Cutout 的 `_o_cut_boundary` 因此能够穿过 projection；节点组最终输出仍用 `_o_*` 清理所有内部属性。

Front / Rear 的共同 Repeat 只直接读取最终 `_o_boundary_smooth_weight`，不得在 Join 后重新推导 influence；保留的 raw marker 仅维持该权重字段的惰性依赖，不作为 Repeat 的直接输入。

## Risks / Trade-offs

- **source index 经拓扑节点失效**：索引只在投影拓扑稳定后建立，并测试每张 leaf 的完整唯一集合。
- **Edges Extrude 域适配改变目标**：固定使用 Top selection + Set Position，不直接消费逐点 Offset。
- **Wall 绕向错误**：Extrude 接收完整 Front，测试闭合体每条边的有向使用次数。
- **Merge 误焊窄缝**：保持相对极小容差，并增加投影 merge 的定向退化用例。
- **错误性能结论**：只比较相同 raw leaf 输入；最终节点中正厚度只允许一个 Boundary Smooth Repeat Zone。

## Migration Plan

1. 删除投影阶段的 Front-only Boundary Smooth 和 Rear 独立 Boundary Smooth。
2. 从同一投影生成 Front 与 pre-flipped Rear，按厚度选择 Front 或 joined leaves，共同平滑一次。
3. 平滑后按 leaf id 分离，按 source index lookup Rear target，生成 Wall 并精确焊接。
4. 用相同输入等价测试和结构检查验证顺序与单 Repeat。
5. 运行相关测试与 `node-group build`，保存并验证资产。
