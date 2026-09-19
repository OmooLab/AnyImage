## 验收记录

- Blender 4.5.10 LTS：三套节点资产验证脚本通过，进程正常退出。
- 最终 Cutout 定向测试：62 项通过，进程正常退出。
- 全量回归：649 项通过、2 项预期失败、59 项子测试通过；开发环境 bpy 在解释器退出阶段仍使进程返回 1。正式 Blender 的构建、求值及重新打开检查均正常退出。
- 三张图片各 High/Low，Split 为 0、0.5、1，Thickness 为 0、0.02，共 36 组求值：零厚度保留全部原始面；正厚度所有面边均成对连接，无开口边或非流形边。
- 六个物体共用正式 `O Image Cutout` 及其 Depth Surface 子组。重新打开保存文件后，图像数据有效，零厚度顶点坐标与保存前一致；Split 0.5、Thickness 0.02、Smooth Iterations 2 时仍全部闭合。
- Blender 节点编辑器实际尺寸检查无节点重叠，Repeat 区域内无无关节点；已保存总览、面判别和 Repeat 局部预览。
- 阶段布局复核：参照 OmooNodes 的四个节点组后，图宽从 27550 缩至 8580 个节点编辑器单位。主轴横排，字段按局部阶段展开；实际节点尺寸检查通过。重排前后全部节点运算、默认输入和穿过 Reroute 后的实际连接完全一致，58 项定向测试与 36 组样例求值通过。

## 视觉结果

蜘蛛与蛛丝、甲虫右侧腿和噬菌体左下交叉腿的 High/Low 对比均已保存，包含关闭、中点、最大强度和中点加厚。

中点能分离主要深度连接，最大强度进一步增加局部分离。High/Low 的三角形布局与深度采样不同，切口位置和碎片形状仍有差异；例如甲虫右侧末端在 High 中点已断开，Low 到最大值才断开。厚度沿各自区域形成连续侧壁，闭合结论同时由完整网格拓扑检查支持。

合成用例覆盖默认投影、控制阈值、规则斜坡重采样、等比缩放、零跨度、拆后清理、单段与多段厚度、重合独立区域及外层平滑。接口和依赖检查覆盖其他 Shape 不受 Split 影响。

审阅文件位于本机：`C:/Users/icrdr/.codex/visualizations/2026/09/06/01a076f5-7f13-7083-84cd-f624eeeb4c30/corrected-depth-surface/`，其中 `cutout-depth-surface.blend` 为共享正式节点的六物体场景，`*-comparison.png` 为三张对比图，`node-layout-*.png` 为节点预览，`validation.json` 为 36 组完整网格检查记录。

最新阶段布局及六物体审阅文件位于同级 `compact-depth-surface/`，节点预览为 `layout-overview.png`、`layout-split.png`、`layout-projection.png`、`layout-thickness.png`。参考资产截图及连接一致性检查位于同级 `layout-study/`。

## 命名属性与阶段留白复核

- FACE、CORNER、POINT 暂存值已改为 `o_depth_*` 命名属性，8 项属性在输出前按启用分支逐项移除。4 组 Split/Thickness 组合验证无残留且保留 UVMap 和 `o_user_weight`；Blender 修改器界面不再出现关闭厚度时的缺失属性清理警告。
- 与上一版 `compact-depth-surface/` 的 24 份样例数据对比，面索引完全相同，顶点坐标绝对误差不超过 `1e-6`；36 组完整求值及六个平滑后闭合实体复核通过。
- 大步骤之间保留至少 500 个节点编辑器单位的空白，6 个 String 节点显示阶段说明。计算树从局部 Named Attribute 和 Group Input 展开，几何起点位于部分计算节点右侧。实际节点尺寸检查无重叠，Repeat 区域未遮挡其他节点。
- 最新六物体场景位于同级 `named-depth-surface/cutout-depth-surface.blend`；`layout-*.png` 为总览、Split、投影、厚度、位置恢复和属性清理预览。重新打开后图片数据、共享节点与厚度闭合均通过。

## 双侧支线与 Wildcard 复核

- Remove Named Attribute 使用 `pattern_mode = WILDCARD`，一个节点匹配 `o_depth_*`。删除逐项清理与条件分支，移除全部 String 注解。测试额外注入 `o_depth_probe`，确认前缀匹配生效且保留 `o_user_weight`、UVMap。
- 计算分支在主轴上下交错展开；面判别与厚度分段算式横向延伸，厚度统计从主链向左引用几何。验证仅要求几何主轴向右，辅助引用允许回接；实际节点尺寸无重叠，Repeat 区域未遮挡其他节点。
- 62 项 Cutout 定向测试、三套 Blender 资产验证通过。36 组真实样例求值和六个平滑实体保持闭合；与命名属性版的 24 份数据比较，面索引相同，坐标绝对误差不超过 `1e-6`。
- 最新审阅场景为同级 `tree-depth-surface/cutout-depth-surface.blend`，六个物体共用正式节点。`layout-*.png` 保存总览和局部节点编辑器预览；重新打开检查及 OpenSpec 严格校验通过。

## 全部几何资产布局复核

- 七个几何节点组均按主轴与双侧计算分支整理，局部重复 Group Input；基础平面在 UV 和网格尺寸区域分别计算相同的源包围盒尺寸。深度表面的厚度统计直接向左引用几何，支线末端移近使用位置，前向旁路仅保留少量转接。
- 将重复的输入与尺寸计算归一化后，全部资产的运算、默认值和实际连接与重排前一致。24 份真实样例的面索引完全相同，顶点坐标绝对误差不超过 `1e-6`；36 组求值、六个平滑闭合实体和重新打开检查通过。
- Blender 4.5.10 LTS 中逐组检查总览和实际绘制边界，七组均无节点重叠；Depth Surface 的投影、厚度等阶段另保存局部预览，Repeat 区域检查通过。所有组保留默认标题、隐藏未使用输出且无 String 注解。
- 三套 Blender 资产验证正常退出。完整回归为 650 项通过、2 项预期失败、59 项子测试通过；开发环境 bpy 在测试完成后的退出阶段仍返回 1。
- 布局规则已写入 AGENTS.md。最新预览与六物体审阅场景位于同级 `all-geometry-layout/`，七组总览分别按节点组名称保存为 PNG，`drawn-layouts.json` 记录实际尺寸，`semantics.json` 与 `geometry-comparison.json` 记录比较结果。

## 紧凑布局与同级输入复核

- 全部七组按实际绘制边界比较，布局宽度减少约 13–26%，高度减少约 30–37%。同一目的的计算、正背面汇合与局部输入进一步聚拢，四个 Shape 在菜单前按输入顺序排成一列。
- 验证独立同级来源的输出端对齐，并保留共享上游与后续处理的主轴关系。实际节点边界与厚度 Repeat 区域检查通过，运算、默认值和实际连接与本轮重排前一致。
- 65 项相关测试及三套 Blender 4.5.10 LTS 资产验证全部通过，进程正常退出。预览位于同级 `compact-peers-layout/`，`*-peers.png` 为汇合局部，`layout-*.png` 为 Depth Surface 阶段预览。

## 用途分组与 XYZ 同级输入复核

- Depth Plane 的深度偏移与厚度权重计算收在主轴同一侧；Depth Surface 的 Split 判别和投影支线内部收紧，主轴与不同用途之间保留更大间距。
- Combine XYZ 的独立输入分支末端对齐，供多个部分使用的共享上游保留在公共位置。几何主轴、同级来源、未使用输出、实际节点边界与 Repeat 区域检查通过，七个几何节点组均在 Blender 中检查总览和相关局部。
- 与本轮修改前资产比较，全部十个节点组的运算、默认值和实际连接相同。65 项相关测试、三套 Blender 4.5.10 LTS 资产验证通过，进程正常退出。
- 本轮预览位于同级 `branch-clusters-layout/`，`O Image Depth Surface-selection.png` 为选边判别，两个 `*-projection.png` 为置换计算，`*-xyz.png` 为 XYZ 汇合；`drawn-layouts.json` 和 `semantics.json` 保存实际边界与一致性记录。

