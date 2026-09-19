## 1. 锁定回归行为

- [x] 1.1 为 Cutout 增加按源像素间距和实际 Selection 采样长边计算的测试，覆盖 Low 的 32 px、Upscale x4 的 4 倍线性密度、bounds 像素超过上限但采样数未超限、实际采样数触及上限，并运行 `uv run pytest tests/test_cutout_interaction.py tests/test_cutout_geometry.py`
- [x] 1.2 为 Image 编辑结果增加真实 Blender 数据块测试，覆盖完整 `.png` 名称、共享源或 Keep Original 产生的 Blender 数字后缀、非共享源恢复准确原名，并运行对应 `tests/test_cutout_objects.py` 用例
- [x] 1.3 为 Remove Background、Upscale、Selection Crop 本地与 Refine 路径、Crop Perspective 增加调用边界测试，确认它们统一请求 Image 编辑结果而不使用 `_color` 或基础名，并运行对应 `tests/test_blender_addon.py` 用例

## 2. 修正 Cutout 网格采样

- [x] 2.1 将 Mesh Detail 的 32、16、8、4 px 间距直接保留到 Cutout 执行阶段，移除交互阶段受整图 1024 限制的提前换算，并运行 Cutout 交互测试验证四档参数
- [x] 2.2 根据 Selection bounds 的预期网格采样长边应用 **Maximum Cutout Mesh Resolution**，把最终有效像素间距换算为世界空间 spacing，删除复用图片输入尺寸限制的错误路径，并运行 Cutout 几何测试验证密度比例和上限
- [x] 2.3 更新同步创建与异步 AI 响应的参数传递，使四种 Cutout Shape 使用同一有效间距，并运行 `uv run pytest tests/test_cutout_interaction.py tests/test_cutout_geometry.py tests/test_cutout_objects.py tests/test_blender_addon.py`

## 3. 统一 Image 编辑结果命名

- [x] 3.1 在 `common/image.py` 建立分别面向像素编辑结果和 Job 编辑结果的共享入口，两者都请求源 Image 完整名称并复用 Pack、颜色空间、动画与错误清理；保留独立材质 Color 加载入口，并运行 Image 数据测试
- [x] 3.2 将 Remove Background 与 Upscale 迁移到共享 Job 编辑结果入口，删除调用方命名修补，并运行对应 Operator 响应测试验证共享与非共享 Image
- [x] 3.3 将 Selection Crop、Refine Crop 和 Crop Perspective 迁移到共享像素编辑结果入口，移除默认 `image_base_name()` 命名，并运行本地、Refine、Perspective 与 Keep Original 测试
- [x] 3.4 删除旧的错误 Image 添加入口、可选后缀参数、重复赋名、无用导入与失去调用者的 helper，不保留别名、转发函数或兼容层，并用 `rg` 确认纯 Image 编辑 Operator 只调用新的共享入口
- [x] 3.5 补充 Plane、Depth Plane 与 Cutout Shape 的材质命名回归断言，确认 `_color.png`、`_depth.exr`、`_normal.png` 不受 Image 编辑结果重构影响，并运行 `uv run pytest tests/test_image_data.py tests/test_cutout_objects.py tests/test_blender_addon.py`

## 4. 文档与完整验证

- [x] 4.1 更新 `docs/internals/common.md`、Crop Tool、Cutout Tool 与相关运行时说明，正面描述 Image 编辑结果完整源名、Blender 自动数字后缀和实际 Cutout 采样上限，并用 `rg` 核对代码与文档术语一致
- [x] 4.2 运行 `uv run pytest`，确认全部测试通过且没有恢复旧命名入口、兼容层或图片尺寸限制胶水代码
