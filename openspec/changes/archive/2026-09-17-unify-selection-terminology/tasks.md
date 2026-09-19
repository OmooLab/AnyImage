## 1. 迁移 Selection 基础类型

- [x] 1.1 将 `common/region.py` 迁移为 `common/selection.py`，把图片选区类型、函数、参数与返回值统一重命名为 Selection，并运行 `uv run pytest tests/test_cutout_geometry.py tests/test_cutout_objects.py` 验证栅格化和几何行为不变
- [x] 1.2 更新 `common/image.py` 与 `common/viewport.py` 的选区输入、手势基类、设置辅助函数和所有调用方，同时保留 Blender Viewport Region API 名称，并运行相关 image data、clipboard 和手势测试验证交互与投影行为

## 2. 迁移 Blender 工具

- [x] 2.1 将属性工厂、三个工具设置和 Operator 参数统一为 `refine_selection`，把显示名改为 **Refine Selection**，把 Cutout 法线选项显示名改为 **Normal Map**，并运行属性与工具设置测试验证名称、独立设置和 AI 门控
- [x] 2.2 将 `cutout_point_spacing` 迁移为默认 Low 的 `cutout_mesh_detail` 四档枚举，在 Cutout 业务边界将 Low、Medium、High、Ultra 映射为 32、16、8、4 px，并用参数化测试验证全部映射及采样密度顺序
- [x] 2.3 将 Image Tool 的 Selection 数据流、细化 Operator、Operator ID、Job 类型和注册入口迁移到新名称，并运行 Image Tool 与注册测试验证本地和 AI 两条路径
- [x] 2.4 将 Cutout Tool 的 Selection Operator、交互传参、Mask/Contour 使用和结果读取迁移到新名称，并运行 `uv run pytest tests/test_cutout_interaction.py tests/test_cutout_geometry.py tests/test_cutout_objects.py` 验证 Shape 菜单、Mesh Detail 与对象构建行为

## 3. 迁移 Server 协议

- [x] 3.1 将 `server/region/` 与 Image Selection Job 文件迁移到 Selection 命名，更新 `refine-image-selection` 注册、参数、进度消息、结果字段和细化产物文件名，并运行 Server runtime 测试验证 Job 输出
- [x] 3.2 同步 Blender 与 Server 两端的 `selection_image`、`selection_bounds` 和 `refine_selection` 协议，更新打包断言，并运行 `uv run pytest tests/test_server_runtime.py tests/test_extension_packaging.py tests/test_blender_addon.py` 验证跨进程契约和扩展内容

## 4. 同步文档与完整验证

- [x] 4.1 更新 `docs/internals`、getting started 与相关索引，将图片业务范围正面描述为 Selection，并确认 **Refine Selection**、**Normal Map**、**Mesh Detail** 档位映射和新 Job/产物协议一致
- [x] 4.2 使用 `rg` 检查源码、测试和文档中的 `region`，逐项确认剩余结果仅为 Blender Viewport Region 或与图片选区无关的一般区域表达，且不存在旧模块、旧类型、旧 Operator、旧 Job、旧字段或兼容转发
- [x] 4.3 运行 `uv run pytest`，确认全部测试通过且 Selection 重命名未改变现有功能
