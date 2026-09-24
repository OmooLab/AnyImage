## Context

`common/smoothing.py::pinned_smooth` 是边界与接缝位置松弛的唯一共享实现，由 Depth Cutout、Depth Plane、Depth Panorama 和 Cutout Symmetry 调用。它在 repeat zone 中逐轮更新 Geometry，但 `UVMap` 作为既有 Face Corner 属性原样穿过，因此受力带内的纹理参数化不会跟随已经平滑的表面。

UV 不能简单转换到 Point 域处理：Panorama 等网格可在同一空间顶点上保存不同的 Face Corner UV，Point 域平均会跨 seam 混合。实现还必须保持项目对临时属性、Capture Attribute 和资产重建的现有约束。

## Goals / Non-Goals

**Goals:**

- 让 `pinned_smooth` 每轮同步松弛 Position 与已有 `UVMap`。
- 两种数据使用相同的迭代次数、作用范围、权重和 pin 选择。
- 保持 Face Corner UV、UV seam 与彼此不连通的 UV island。
- 让全部既有调用方通过共享实现获得一致行为。
- 保持零迭代和范围外点的精确旁路。

**Non-Goals:**

- 不改变未调用 `pinned_smooth` 的深度、法线、掩码、统计或 smooth shading。
- 不新增 modifier 输入或为调用方提供是否同步 UV 的开关。
- 不重新展开 UV，也不从变形后的三维位置反投影纹理坐标。
- 不为旧节点组保留兼容路径。

## Decisions

### 1. UV 随动属于 `pinned_smooth` 的固定语义

共享函数在 Position repeat state 之外维护 UV repeat state。每轮先从当前状态计算位置目标与 UV 目标，再用同一最终权重混合；`pin_boundary` 选择边界自身目标时，对两者作相同选择。

采用固定语义而不是调用方参数，是因为所有调用点表达的都是同一种表面松弛。由调用方选择会产生几何相同、纹理语义不同的分支，并重复连接逻辑。

### 2. UV 在 Face Corner 拓扑内独立松弛

读取 `UVMap` 时保留 `FLOAT2/CORNER` 域。UV 邻域只连接属于同一连续 UV island 的 Face Corner；几何邻接但 UV 不连续的 corners 不互相贡献。边界目标同样只从对应 UV 边界条带计算，随后把结果写回 `UVMap`。

不采用 Point 域 Blur，因为它会合并同一顶点上的 seam 值。不采用最终位置反投影，因为各调用方包含平面、透视深度、球面和对称几何，缺少统一可逆映射。

### 3. `UVMap` 是共享平滑的输入协议

全部现有调用方都处理带图像 UV 的表面，`pinned_smooth` 因此默认输入几何具有 `UVMap`，不增加运行时属性存在性判断。`iterations = 0` 时直接返回输入 Geometry，避免即使数值相同也重建属性。

### 4. 只保存最少的临时映射

若 seam-aware corner 邻接需要跨 repeat zone 保存索引或 island 标记，使用 `_o_` 前缀的最少命名属性，并在最后消费者之后通过现有属性清理协议删除。实现保持 Capture Attribute 为零，不改变用户属性和 `UVMap` 之外的属性。

### 5. 以共享行为测试覆盖所有调用形态

测试分别覆盖有 pin 的边界松弛、无 boundary pin 的 Fill Smooth、Panorama seam、范围外区域和零迭代。调用方测试不再断言全部 UV 恒定，而断言受力带内 UV 与 Position 一致发生松弛、受力带外及 seam 两侧保持隔离。

## Risks / Trade-offs

- [Face Corner 邻域比 Point Blur 更复杂] → 把构建逻辑封装在 `common/smoothing.py`，调用方继续只传现有参数。
- [UV 平滑会在受力带内产生局部纹理拉伸] → 这是纹理轮廓追随平滑几何的预期结果，并继续受既有 influence 衰减限制。
- [Panorama 的 0/1 经度 seam 可能被错误平均] → 使用 UV 连续性划分邻域，并增加跨 seam 的专门行为测试。
- [Fill 生成的新 corners 可能没有稳定 UV] → 仅对输入中有效存在的 UV island 传播值，验证结果有限且不反向污染已有 island。
