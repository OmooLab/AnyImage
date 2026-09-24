## Context

`O Image Depth Cutout` 先将相机 XYZ 投影为规范对象坐标，再生成 Balloon / Shell 厚度。投影后的局部深度轴是 Y，位置公式为：

`object_y = (sampled_depth × uniform_scale − reference_depth) × depth_scale`

当前流程没有在投影后排除远处几何的阶段。参考深度会忽略远于有效深度中位数一定比例的尾部，但这些像素仍参与几何投影，因而可能把 Cutout 拉向远端。

## Goals / Non-Goals

**Goals:**

- 用 Blender 对象空间距离表达远端裁切，而不是向用户暴露模型原始深度单位。
- 让 `Reference Depth`、`Uniform Scale` 与 `Depth Scale` 的现有投影公式自然决定哪些点越过阈值。
- 在投影前以面中心深度分类远端面，并让新边界进入 Depth Split 的完整成形链。
- 为新建 Depth Cutout 提供基于当前选区深度分布的有效初值。

**Non-Goals:**

- 不为 Depth Plane、Relief Plane、Depth Balloon 增加相同控制。
- 不做阈值处的精确插值切面或重拓扑；边界精度沿用输入网格分辨率。
- 不改变参考深度的 95 百分位算法及其离群尾部过滤。

## Decisions

### 1. 公开物体空间 `Depth Limit`

在 `O Image Depth Cutout` 的主输入区把 `Depth Limit` 作为 `DISTANCE` 输入暴露，最小值为 `-1`。它表示参考平面沿对象局部 +Y 方向允许保留的最大距离；`1 m` 表示删除局部 Y 大于 `1 m` 的部分，负值允许裁切进入参考平面之前。

选择最终对象空间阈值，而不是相机原始深度阈值，是因为 Modifier 面板显示的值可直接对应场景单位，且无需在裁切分支重复 `Reference Depth` 与 `Depth Scale` 的换算逻辑。

### 2. 按面采样并复用 Depth Split 边界协议

Depth Limit 与 Depth Split 共用 `sample_face_camera()` 得到的面中心相机坐标。系统按投影公式计算每个面的对象空间 Y，选择 `face_y > Depth Limit` 的面；相邻两面的选择状态不同时，其公共边写入现有 `_o_depth_cut` 切边标记。Depth Split 完成自身的边界三角清理后删除远端面，随后 Depth Limit 边与 Depth Split 边共同进入 `taper_split_profile()`、边界平滑、法线和 Balloon / Shell 厚度流程。

采用面中心采样与整面删除，与 Depth Split 现有的面采样拓扑一致，也避免点采样在同一面内产生不完整的厚度边界。裁切边界仍落在现有网格边上，不做阈值处的插值切割。

### 3. 创建默认值对应相机深度中位数的 1.2 倍

新增共用深度统计入口，在与 `reference_depth()` 相同的有效条件和 Cutout 选区内取得中位深度。创建时先把相机深度阈值 `1.2 × median_depth` 换算为 `Depth Scale = 1` 时的对象空间距离：

`depth_limit = max((1.2 × median_depth − reference_model_depth) × uniform_scale, 0)`

该值写入主 `O Image Depth Cutout` Modifier。后续调整 `Reference Depth` 或 `Depth Scale` 会改变投影后的 Y 位置，裁切仍使用固定的真实对象距离，因此结果自然反映两项控制。无有效样本时，中位深度与参考深度共同回退到既有 baseline，使对象仍可创建。


## Risks / Trade-offs

- [裁切边界受网格密度限制] → 用几何行为测试固定点域删除语义，不引入高成本精确切割。
- [调整 Depth Scale 会让更多或更少几何越过固定阈值] → 这是对象空间距离的预期行为，并通过参数联动测试明确。
- [旧内嵌节点组没有新 socket] → 不增加兼容层；重新构建资产后，新创建对象使用当前接口。
