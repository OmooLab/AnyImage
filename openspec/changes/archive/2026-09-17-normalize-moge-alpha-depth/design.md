## Context

Cutout Job 会把最终 Region 图像交给 MoGe-2。Remove Background 路径会清除全透明像素下的 RGB，Fit to Foreground 路径则可能保留隐藏 RGB；MoGe-2 只读取 RGB，因此两条业务路径当前并不等价。

几何预测的另一处边界也不统一：MoGe-2 先返回专用 `Prediction`，Normal Writer 直接读取它，Depth Writer 才临时转换为 `GeometryFrame`；DA3 则有另一套转换入口。这样 `GeometryFrame` 没有真正成为模型预测与几何产物之间的稳定协议。

MoGe-2 返回连续的 Depth/Points Field 和原始 Mask。当前 Depth Writer 会按有效性 Mask 清零 RGB，而 Depth Surface 线性采样 RGB、不读取 Alpha，因此 Mask 边界的零坐标会把网格拉向相机原点。

## Goals / Non-Goals

**Goals:**

- 以 MoGe-2 单帧预测的数据类型重建 `GeometryFrame`，并让 MoGe-2 与 DA3 都通过模型适配器产出该类型。
- 让 Depth EXR、Normal Texture 和 `depth.json` 只消费 `GeometryFrame`，不直接依赖模型专用预测结构。
- 让所有 MoGe-2 调用在同一个 Server 边界获得确定的黑底 RGB 输入。
- 让 Depth EXR 分别表达连续数值场与原始模型 Mask，两者互不改写。
- 保留严格的 Metadata 校准筛选，并阻止非有限数值进入 Blender。

**Non-Goals:**

- 不修改 BEN2、MoGe-2 或 DA3 模型实现及其推理分辨率。
- 不改变 Depth EXR 文件名、尺寸、RGBA 通道布局或节点组接口。
- 不用输入 Alpha 覆盖模型 Mask，也不在本次变更中让 Geometry Nodes 按 Alpha 丢弃点。
- 不把 DA3 恢复为当前生产路径；仅保持其适配器与统一协议可用、可测试。

## Decisions

### 1. `GeometryFrame` 是单帧几何预测协议

`GeometryFrame` 按 MoGe-2 单帧结果定义：

- `depth: ndarray[H, W]`，必需的 `float32` 深度场；
- `normal: ndarray[H, W, 3] | None`，MoGe-2 提供，DA3 可为空；
- `validity: ndarray[H, W]`，必需的 `float32` 模型有效性信号；MoGe-2 的原始 Mask 转换为 `0/1`，DA3 保存原始连续 Confidence；
- `intrinsics: ndarray[3, 3]`，必需的 `float32` 像素坐标内参；
- `points: ndarray[H, W, 3] | None`，可选的 `float32` 相机空间点场；

构造时校验 dtype、维度和同帧空间尺寸，但不在容器内改写预测值。`validity` 是唯一存储的模型有效性信号；不再同时保存 `mask`、`confidence` 和派生的 `valid_mask`，避免相同职责出现多个可漂移来源。

MoGe-2 的生产推理入口直接返回一组 `GeometryFrame`，在适配器内完成 batch 拆分、Mask 到 Validity 的转换和内参像素化。用于调试 NPZ 的原始单次推理入口继续返回模型原始字典，因为它不是 Artifact 生产边界。DA3 保留原始调试推理，并提供同样的逐帧适配器：`normal=None`，从深度和内参生成 Points，并把 Confidence 作为连续 Validity。

不选择在通用层保留 MoGe-2 `Prediction` 再二次转换，因为这会继续允许 Writer 绕过统一协议。也不把 `GeometryFrame` 限定为 MoGe-2 类型，避免 DA3 和后续模型各自复制 Artifact 逻辑。

### 2. 所有几何 Artifact Writer 只消费 `GeometryFrame`

Vector Depth Writer 从 `frame.points` 和 `frame.validity` 写 EXR；Z Depth Writer 从 `frame.depth` 和 `frame.validity` 写 EXR；Normal Writer 从 `frame.normal` 生成贴图；Metadata Writer 从 `frame.depth`、`frame.intrinsics` 和调用方提供的业务 Region Mask 计算 `depth.json`。

Writer 只依赖通用 `GeometryFrame`，不导入 `moge2` 或 `da3`。缺少所需可选字段时明确失败，例如没有 `points` 不能写 Vector Depth，没有 `normal` 不能写 Normal Texture。Artifact 编排层从 MoGe-2 取得一帧 `GeometryFrame` 后，把同一对象传给各 Writer，不再读取模型专用属性。

Metadata 所需的校准有效性按使用点计算：正的 `frame.validity`、有限且为正的 Depth，以及业务 Region Mask 的交集。它不是 `GeometryFrame` 的第二个持久字段，也不反向影响 EXR Alpha 或 RGB。

### 3. 在最终 MoGe-2 输入边界统一黑底合成

读取最终 `region_image_path` 为 RGBA，按输入上限缩放，然后使用 `output_rgb = source_rgb * alpha` 合成到黑底，并始终写为 Job 内的 RGB PNG。即使无需缩放，也经过相同规范化步骤。

这会让半透明像素保留按 Alpha 衰减后的颜色，并彻底消除 Alpha 为零时隐藏 RGB 的差异。Metadata 和 Normal 输出所需的业务 Alpha 仍从原始 Region 图读取，不从已移除 Alpha 的模型输入读取。

不在 Blender 的 `prepare_region_input()` 提前处理，因为该入口还服务其他 Job，而且 Fit to Foreground 会在 Server 端重新生成 RGBA，无法形成唯一收口点。

### 4. Depth RGB 保留连续 Field，Alpha 只记录 `frame.validity`

Vector/Z Depth Writer 无条件把完整 Points/Depth Field 写入 RGB，并仅把 `frame.validity` 写入 Alpha。零 Validity 不再导致 RGB 清零，使 Depth Surface 在边缘线性采样时仍能得到连续坐标。

Writer 在创建文件前要求所需 Field 全部有限。Mask 为假不豁免该检查，因为 Geometry Nodes 仍会读取 Mask 外 RGB；NaN/Inf 会传播到网格。有限但非正的 Depth 仍忠实写入，正值条件只属于 Metadata 校准。

不把非有限值替换为零或最近有效值：前者会重新引入相机原点尖刺，后者不再忠实于模型结果。

### 5. 测试固定协议、工作流等价与连续性

测试分为四层：

1. `GeometryFrame` 校验，以及 MoGe-2/DA3 适配器的字段、形状、dtype、Validity 映射和批次拆分。
2. 模型输入验证 Alpha 为 `0`、`0.5`、`1` 的黑底合成，并验证不同隐藏 RGB 得到相同透明区输入。
3. Writer 验证只接收 `GeometryFrame`、Validity 为零时 RGB 保留原值、Alpha 等于 `frame.validity`、缺字段与 NaN/Inf 明确失败；Normal 和 Metadata 不再读取 MoGe-2 专用结果。
4. Depth Surface 使用边缘 Mask 为假但 XYZ 连续的 Vector Depth，验证求值网格不会聚集到相机原点。

## Risks / Trade-offs

- [MoGe-2 返回类型变化会影响调用方] → 生产调用集中在 Artifact 编排层；一次性迁移并删除旧 `Prediction`/转换入口，不保留兼容层。
- [GeometryFrame 严格 dtype 会暴露模型适配错误] → 在适配器边界显式转换并用模型级测试固定协议。
- [黑底输入会改变当前 Fit to Foreground 的预测] → 这是统一语义的预期行为，用像素级测试固定合成规则。
- [零 Validity 区域的有限 Field 可能精度较低] → Alpha 完整保留模型判断供消费者解释；连续 Field 用于避免几何塌缩。
- [完整 Field 中一个非有限值会使 Job 失败] → 失败优于生成被 NaN/Inf 污染的网格，错误信息区分 Depth、Point 和 Normal Field。

## Migration Plan

1. 重建 `GeometryFrame` 与两种模型适配器，迁移 MoGe-2 生产推理返回值并删除旧专用中间结构。
2. 将 Depth、Normal 和 Metadata Writer 改为只消费 `GeometryFrame`，再迁移 Artifact 编排层。
3. 建立统一的 MoGe-2 黑底输入准备，并补充像素与工作流等价测试。
4. 调整 EXR 通道写入与数值检查，增加 Depth Surface 回归测试。
5. 更新 GeometryFrame、Artifact 和 Cutout 内部文档并运行全量测试。

现有 Job 目录中的旧 EXR 不迁移；重新运行对应功能即可生成新语义 Artifact。回退时必须同时回退协议、适配器、Writer 与测试。
