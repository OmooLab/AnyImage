## 1. 固定轴向契约

- [x] 1.1 补充 BaseShape 与对象放置测试，验证原始 Mesh 位于局部 XY、正面为 `+Z`、裁切区域世界空间位置不变
- [x] 1.2 补充 Cutout 属性、交互和对象测试，验证 `Inward Axis` 继续显示和传递，且 `-Z` 为默认值
- [x] 1.3 扩展节点结构与真实 Blender 求值测试，分别固定四种 Shape 的 XY 输入、Z 轴形变、Face winding，以及外层 `-Z`/`+X` 配对转换
- [x] 1.4 补充 Object Space Normal 的 Server 编码与 Blender 加载测试，验证 `+Z` 中性值、默认原样加载和 `+X` 单次通道转换

## 2. 统一 BaseShape 与对象坐标

- [x] 2.1 让 `build_base_shape()` 直接保留三角化的 `(x, y, 0)` 顶点，删除 X 轴顶点转换及其遗留测试
- [x] 2.2 让默认 `-Z` 对象矩阵只使用源矩阵与裁切中心平移，并为 `+X` 保留从原生 Z 轴到 X 轴输出的配对矩阵补偿
- [x] 2.3 保持 Scene Settings、工具面板、交互编码、Operator Property 和对象创建调用链的 `Inward Axis` 接口，清理只服务旧 X 轴内部默认的逻辑

## 3. 迁移 Cutout Geometry Nodes

- [x] 3.1 将 Cutout 节点构建辅助函数从 X 轴厚度/偏移改为 Z 轴，并按最终职责重命名，不保留旧函数转发
- [x] 3.2 将 Surface、Balloon、Depth Balloon 与 Depth Surface 的平面坐标、厚度、深度投影和向量运算统一迁移到 XY / Z 坐标
- [x] 3.3 保留 `O Image Cutout` 的 `Inward Axis` socket 与 Menu Switch，让 `-Z` 直通原生 Shape、`+X` 执行 Z 到 X 的最终 Transform，并更新节点布局验证
- [x] 3.4 更新 Cutout 与既有 Plane 的节点资产验证，重建并验证 `src/anyimage/assets/O_AnyImage.blend`

## 4. 对齐 Object Space Normal

- [x] 4.1 修改 Server 的 Object Space Normal 通道映射和不可见像素值，使 Artifact 直接使用最终 XY / Z Cutout 对象空间
- [x] 4.2 调整 Blender 端 Object Space Normal 转换方向：默认 `-Z` 原样消费 Artifact，仅 `+X` 在响应阶段执行一次 Z 到 X 的通道变换

## 5. 文档与完整验证

- [x] 5.1 更新 Cutout Tool 与节点资产内部文档，用从上到下的流程说明统一 XY / Z 坐标和四种 Shape 的 `-Z` 内向语义
- [x] 5.2 搜索并清理 Shape 子组以 X 轴为内部默认的实现和说明，同时确认 `Inward Axis`、`CutoutInwardAxis` 与外层转换只承担可选输出轴职责
- [x] 5.3 运行 Cutout、Server、Blender 与节点资产定向测试，再运行 `uv run pytest`；仅修复本 change 引入的回归，不构建其他文档或发布产物
