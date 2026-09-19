# 节点属性核查与验证

## 存取清单

核查入口为 `tools/nodes/build.py` 的全部七个几何组和三个材质组。以下覆盖原有 44 次 Store 写入；其 Selection 均为常量 True。重复名称按几何阶段区分版本，表中标明重复写入次数。

| 属性 | 原域 / 类型 | 生产、消费与处理 |
| --- | --- | --- |
| `o_depth_face_center`（3 组） | FACE / FLOAT_VECTOR | Depth Plane、Depth Cutout、Panorama 分裂前的面中心，供相邻面距离采样；直接由 FACE 域的 Sample Index 求值 |
| `o_depth_face_camera`（3 组） | FACE / FLOAT_VECTOR | 面中心 UV 采样结果供断层判断及角值捕获；改为 FACE Evaluate on Domain 后直连 |
| `o_depth_corner_camera`（3 组） | CORNER / FLOAT_VECTOR | 分裂、删面前的各面相机值，供切分后投影；与切分标记一起捕获 |
| `o_depth_cut_vertex`（3 组） | CORNER / BOOLEAN | 分裂前 EDGE→POINT 标记，供分裂后的射线调整；在 CORNER 域捕获，保持原转换顺序 |
| `o_depth_camera`（3 组） | POINT / FLOAT_VECTOR | 射线调整结果紧接投影使用；改为 POINT Evaluate on Domain 后直连 |
| `o_depth_surface_position`（2 组） | POINT / FLOAT_VECTOR | Depth Plane、Depth Cutout 展平前的位置，供合并后恢复；与顶点身份一起捕获 |
| `o_depth_source_vertex`（2 组） | POINT / INT | 挤出前身份，供前后盖和侧壁合并；与位置在同拓扑下捕获 |
| `o_depth_surface_normal` | POINT / FLOAT_VECTOR | Depth Plane 的源面平滑法线，供恢复壳体厚度；合并到源几何捕获 |
| `o_panorama_direction` | POINT / FLOAT_VECTOR | 球面方向供 UV、面中心和径向投影；消费前位置保持不变，直接用 Position |
| `o_panorama_uv` | POINT / FLOAT_VECTOR | 球面采样坐标供深度与有效性采样；POINT 域直接求值 |
| `o_panorama_distance` | POINT / FLOAT_VECTOR | 采样距离供分裂后投影；删面与 Split Edges 保持球面坐标，POINT 域直接求值 |
| `o_panorama_invalid` | POINT / FLOAT_VECTOR | 有效性分类供面删除及无效距离选择；改为 POINT/FLOAT 字段，面消费者保留聚合语义 |
| `o_balloon_surface_rim` | POINT / FLOAT | 源面边界供中心和结构 Blur 权重；显式 POINT/FLOAT 字段直连 |
| `o_balloon_surface_center`（2 次） | POINT / FLOAT | 第一版 seed 只供 Blur，直接连接；第二版平滑中心跨表面变形，捕获最终值 |
| `o_balloon_surface_front_normal` | POINT / FLOAT_VECTOR | 源表面法线供 Uniform 厚度及前向平滑；POINT 求值后捕获 |
| `o_balloon_surface_structure` | POINT / FLOAT | 原表面结构幅度供壳体膨胀；在壳体构建前捕获 |
| `o_balloon_surface_inflation_normal` | POINT / FLOAT_VECTOR | 原表面平滑方向供最终膨胀；与结构幅度一起捕获 |
| `o_balloon_surface_thickness`（3 次） | POINT / FLOAT | Balloon 基础厚度、Uniform 控件厚度、Balloon 圆化后厚度三个版本；基础计算直接连接，模式选择后的最终厚度在变形前捕获 |
| `o_balloon_surface_edge_weight` | POINT / FLOAT | 圆化权重供壳体前后表面；在圆化前捕获 |
| `o_balloon_surface_front_delta` | POINT / FLOAT | 圆化位移供当前 Set Position 和后续壳体；在圆化前捕获 |
| `o_balloon_surface_normal` | POINT / FLOAT_VECTOR | 在独立中心表面求值并按顶点采样的法线，供最终壳体；保留采样源并捕获 |
| `UVMap`（3 次） | CORNER / FLOAT2 | Image Plane 的 Grid/Cube 两分支及 Panorama，供材质与输出使用；保留命名属性 |
| `o_normal_scale`（5 次） | FLOAT；Cutout/Balloon 为 POINT，Depth Cutout 为 FACE | 两类 Cutout 输出掩码、Depth Cutout 原面值 1 与背面/侧壁值 0；供 `cutout_tool/object.py` 材质读取，保留全部写入 |

`o_balloon` 由 `cutout_tool/object.py` 写入输入网格，作为形状协议继续按名称读取。Relief Plane 使用 UVMap 读取；Image Layer、Shadeless 通过接口消费材质数据；Depth Layer 的位移属性读取保持原协议。以上外部消费者均已检查。

## 数量变化

表中为 Store / Named Attribute 读取 / Capture 节点数量，包含组内共用构建函数展开后的节点。

| 节点组 | 调整前 | 调整后 |
| --- | --- | --- |
| Depth Panorama | 10 / 14 / 1 | 1 / 0 / 2 |
| Image Plane | 2 / 0 / 1 | 2 / 0 / 1 |
| Depth Plane | 8 / 12 / 0 | 0 / 2 / 2 |
| Relief Plane | 0 / 1 / 0 | 0 / 1 / 0 |
| Image Cutout | 1 / 2 / 0 | 1 / 2 / 0 |
| Depth Cutout | 22 / 36 / 0 | 3 / 7 / 4 |
| Depth Balloon | 1 / 3 / 0 | 1 / 3 / 0 |
| 三个材质组 | 0 / 0 / 0 | 0 / 0 / 0 |
| 合计 | 44 / 68 / 2 | 8 / 15 / 9 |

移除的内部命名空间不再参与清理；输入网格中自行携带的同前缀属性得以保留。快照经匿名属性传播，最终输出不新增内部命名属性。

## 求值验证

- 基线节点测试首次受环境同步文件锁影响：248 通过，2 个材质测试因 Cycles 未能注册失败。恢复完整 bpy 安装后，相关 5 个材质测试全部通过。
- 保存并对比 28 个场景、164 组数组：覆盖 Balloon/Uniform、Split 关闭/开启、零/正厚度、Normal Smooth 0/50、Front Inflation、Panorama 非均匀深度与无效像素。
- 28 个场景的实际顶点位置完全一致。按空间位置对应比较，面的方向、角 UV、材质索引和法线掩码完全一致；Merge by Distance 的部分输出编号顺序发生变化。
- 重构后的 Depth Cutout 与分裂测试：56 通过；其余投影与 Panorama 首轮测试通过，旧临时属性测试已迁移为字段输出验证。
- `uv run node-group build` 成功退出：使用 Blender 4.5.10 LTS 重建 `.blend`，在独立进程中重新加载并验证全部 10 个节点组。
- 同一构建入口调用项目环境的 `python -m pytest`：1182 项全部通过，耗时 217.79 秒，正常退出；包含排列前后行为、保存布局稳定性、材质与 Operator 回归验证。
- 七个几何组的节点边界检查均为零重叠，现有排列器无需调整；已导出本地交互预览 `build/node-attributes.html`。
- `git diff --check` 与 OpenSpec 严格校验通过；节点源代码中已无本次移除的临时命名属性与旧存取入口引用。
