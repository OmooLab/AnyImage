## 1. 统一 GeometryFrame 边界

- [x] 1.1 按单帧 MoGe-2 数据重建 `GeometryFrame`：定义 Depth、Normal、Validity、Intrinsics、Points 字段及 dtype/shape 校验，删除 `mask`、`confidence`、`valid_mask`、`model_mask` 多重状态并补充单元测试。
- [x] 1.2 让 MoGe-2 生产推理直接返回 `GeometryFrame` 序列，在适配器中完成 batch 拆分、Mask 到 `0/1` Validity 的转换和内参像素化；删除旧 `Prediction` 与二次转换入口，并验证每个字段忠实来自原始预测。
- [x] 1.3 为 DA3 保留原始调试推理并实现 `GeometryFrame` 适配器，验证 `normal=None`、派生 Points、Intrinsics 和由 Confidence 提供的连续 Validity，保持该参考路径可用。

## 2. 统一 MoGe-2 输入

- [x] 2.1 将模型输入准备改为始终读取最终 Region RGBA、按输入上限缩放并以 `RGB × Alpha` 合成到黑底；用像素测试验证 Alpha 为 `0`、`0.5`、`1` 的输出。
- [x] 2.2 增加不同隐藏 RGB 的工作流等价测试，验证可见 RGB 与 Alpha 相同时生成完全一致的 MoGe-2 RGB 输入；运行相关 Server Job 测试。

## 3. 让几何产物只消费 GeometryFrame

- [x] 3.1 修改 Vector/Z Depth Writer，使其只接收 `GeometryFrame`，完整写入有限的 Points/Depth RGB，并把 `frame.validity` 单独写入 Alpha；用 EXR 回读测试验证 Validity 为零时 Field 仍保留。
- [x] 3.2 为 Depth Writer 增加缺少 Points、NaN/Inf 失败测试，验证错误明确区分 Point Field 与 Depth Field，且失败时不生成 EXR。
- [x] 3.3 修改 Normal Writer 只从 `GeometryFrame.normal` 读取预测，保留业务 Region Mask 的可见性处理，并增加缺少 Normal 与非有限值测试。
- [x] 3.4 修改 Metadata Writer 从 `GeometryFrame` 按需计算正 Validity、正且有限 Depth、业务 Region Mask 的校准交集；迁移 Artifact 编排层，使其不再读取 MoGe-2 专用预测字段，并运行 Server Job/Runtime 测试。

## 4. Depth Surface 回归与文档

- [x] 4.1 增加边缘 Mask 为假但 XYZ 连续的 Depth Surface 测试，验证求值网格不会聚集到相机原点；运行 `uv run pytest tests/test_cutout_objects.py tests/test_node_assets.py`。
- [x] 4.2 更新 GeometryFrame、模型适配、MoGe 输入、Depth/Normal/Metadata Artifact 语义及 Cutout Runtime 文档；运行 `uv run pytest tests/test_docs.py`，不构建文档产物。
- [x] 4.3 运行 `uv run pytest` 完成全量回归，确认两条前景工作流、Depth Plane、Depth Surface、打包和文档检查全部通过。
