## 1. AI 与业务模块命名

- [x] 1.1 将 `ai_job.py` 迁移为 `ai.py`，并从 `image_interaction.py` 迁入 `draw_ai_setup()` 与 `draw_ai_property()`；运行相关 Operator 导入测试并用 `rg` 确认 AI 公共函数只定义于 `ai.py`。
- [x] 1.2 将 `image_data.py`、`image_region.py`、`depth_data.py` 分别迁移为 `image.py`、`region.py`、`depth.py`，保持函数体和签名不变；运行 `uv run pytest tests/test_image_data.py tests/test_cutout_geometry.py tests/test_cutout_objects.py` 验证行为。
- [x] 1.3 将移除 AI UI 后的 `image_interaction.py` 迁移为 `viewport.py`，集中 View3D 坐标投影、点击解析、工具设置、手势与 Overlay 绘制；运行 `uv run pytest tests/test_cutout_interaction.py tests/test_blender_addon.py` 验证视口交互函数和模块导入。

## 2. Material 与 Object 边界

- [x] 2.1 建立 `material.py`，从 `object.py` 迁移材质颜色空间、Node Group、材质构建和 Displacement 配置函数；运行 `uv run pytest tests/test_image_data.py tests/test_cutout_objects.py` 验证材质结果。
- [x] 2.2 收窄 `object.py` 为 Object 与 Modifier 构建收尾，并保持 `node.py` 不变；运行 Object、Convert to Plane 与 Cutout 相关测试验证 Modifier 输入和结果 Object。

## 3. 调用方、文档与验证

- [x] 3.1 更新 `operators/`、`menu.py` 和测试的全部直接导入，删除 `ai_job.py`、`image_data.py`、`image_region.py`、`image_interaction.py` 与 `depth_data.py`；使用 `rg` 确认不存在旧模块导入、重导出或兼容转发。
- [x] 3.2 更新 Common 模块结构测试，验证八个目标模块可导入、AI UI 定义位置唯一且 `common/__init__.py` 不重导出；运行该测试确认边界规则生效。
- [x] 3.3 按八个业务模块更新 `docs/internals/common.md` 和 `docs/internals/architecture.md`；人工核对文档索引与生产源码一致，不构建文档产物。
- [x] 3.4 运行 `uv run pytest` 完成全量回归，确认所有 Operator、Job、节点资产、打包和文档检查通过。
