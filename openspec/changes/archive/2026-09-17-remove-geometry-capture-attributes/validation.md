# 几何节点核查

## 实施基线

- 基线采用实施开始时工作区源码，保留已有无效点清理、边界平滑、模型目录与粘贴预览等修改。
- 节点基线测试：295 项通过，正常退出。
- 保存 41 个场景、236 组数组，包含 Balloon/Uniform、Split、零与正厚度、法线平滑、膨胀、四边面与三角面边界平滑、Depth/Relief Plane、Panorama 有效性及重叠表面。
- 本地核查文件：build/attributes-capture-before.json、build/geometry-capture-before.npz；实现后的对应文件以 capture-after 命名。

## 存储决策

| 范围 | 最终实现与必要性 |
| --- | --- |
| 原边界 | Depth Plane 直接消费 UV 矩形边缘，Panorama 使用闭合源面的 False；Depth Cutout 的任意输入轮廓跨切分后无法从当前拓扑恢复，保留一个 POINT/BOOLEAN 标记 |
| 平滑 Boundary、Influence | 直接由不变拓扑和受保护轮廓计算，不保存字段 |
| 平滑 SourceIndex、BoundaryIndex | 分别分离源边界与当前边界，保持相同紧凑索引顺序；用原网格按 Index 采样的位置查询源边界，再按结果索引消费当前边界位置，不保存索引 |
| 切分 Camera | 面相机采样在当前面直接求值，保持显式 FACE 域，不保存 Camera |
| 切分 Cut | 原顶点受切分影响的标记跨分裂及删面使用，每个深度组保留一个 CORNER/BOOLEAN 标记；完成投影后精确删除 |
| 厚度 Position、Vertex、Normal | 将源索引编码进构造网格坐标后再挤出，按整数解码后的索引从独立源表面采样位置、厚度与法线，不保存字段；保留独立重叠表面身份 |
| Depth Cutout 中心、结构、圆化、膨胀字段 | 直接在投影源表面求值并按壳体源索引采样；仅厚度构建需要的圆化厚度额外在对应前表面索引上求值 |
| 材质 Source | 按输入网格顶点数量和 Join 的实际输入顺序识别待删除范围，不保存标记；验证空输入、多材质槽与排列前后结果 |
| UVMap | Image Plane 两个分支、Panorama 各有实际输出 UV 写入，共 3 次，CORNER/FLOAT2，材质按名称消费 |
| o_normal_scale | Image Cutout、Depth Balloon 各一次 POINT/FLOAT；Depth Cutout 原面 1、合并背面与侧壁后 0 两次 FACE/FLOAT，共 4 次；形状和材质按名称消费 |

所有保留 Store 的 Selection 均为 True。新增临时名称为 `.o_anyimage_depth_cut`、`.o_anyimage_original_boundary`，清理按完整名称执行；用户的其他属性，包括同前缀属性，保留原行为。

## 数量

| 节点组 | Capture 前 → 后 | Store 前 → 后 |
| --- | --- | --- |
| O Image Plane | 1 → 0 | 2 → 2 |
| O Image Depth Plane | 6 → 0 | 0 → 1 |
| O Image Relief Plane | 0 → 0 | 0 → 0 |
| O Image Cutout | 0 → 0 | 1 → 1 |
| O Image Depth Cutout | 8 → 0 | 3 → 4 |
| O Image Depth Balloon | 0 → 0 | 1 → 1 |
| O Image Depth Panorama | 6 → 0 | 1 → 2 |
| 合计 | 21 → 0 | 8 → 11 |

按节点组自身计数，嵌套 Image Plane 在递归结构检查中去重。11 次 Store 由 7 次实际输出协议写入和 4 次必要拓扑标记写入组成。

## 验证结果

- 41 个场景的顶点位置、带方向的面、角 UV、材质索引和法线掩码与基线一致；面按顶点坐标及角 UV 对应比较，允许输出索引重排。
- 源码和保存资产递归检查 Capture 为零；相关测试辅助图中已无 Capture。
- 已修正全量测试发现的旧模型名称断言，匹配工作区当前模型名称。
- 已刷新本地 BlendJob 0.1.17 wheel 的锁文件哈希；版本、依赖声明及 Manifest 保持一致。
- uv run node-group build 成功且正常退出：Blender 4.5.10 LTS 重建资产，独立进程重新加载并验证全部 10 个节点组，递归几何组 Capture 为零。
- 构建命令串行调用的全量 pytest：1237 项通过，耗时 221.33 秒，正常退出；覆盖新增跨 4096 索引行的厚度采样、临时属性精确清理、多材质继承、空输入和排列前后求值。
- 逐组检查最终布局、字段连接与共享源几何路径，7 个几何组均无节点重叠，排列前后行为及保存布局稳定性测试通过；交互预览位于 build/capture-nodes.html。
- git diff --check 与 OpenSpec 严格校验通过。源码检索中的 GeometryNodeCaptureAttribute 仅存在于禁止该节点的检查断言。
- 源码、规范、测试与资产同步完成，未构建文档或打包扩展。
