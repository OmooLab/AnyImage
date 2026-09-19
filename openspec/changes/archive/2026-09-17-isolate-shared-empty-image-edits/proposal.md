## Why

图片编辑目前通过旧 Image 的总引用数决定是否保留旧数据，无法直接表达用户关心的其他 Empty Image 是否共用原图。需要以真实物体引用关系决定图片分离，使编辑当前 Empty 时其他共用原图的 Empty 保持原样。

## What Changes

- 在整个文件中查找引用同一 Image 的其他 Empty Image，以此决定编辑结果是否需要独立数据块。
- 存在其他 Empty Image 时，仅将当前物体切换到结果 Image；不存在时更新当前 Image，保留身份与完整名称。
- 隐藏物体和其他场景中的 Empty Image 同样参与判断；Frame 按合并后仍保留的物体判断共享。
- 统一本地像素编辑与 Job 结果提交，保留成功、取消和失败时的图片及物体状态约定。

## Capabilities

### New Capabilities

- `empty-image-edit-isolation`: 定义以 Empty Image 引用关系为依据的编辑分离、单独使用时的更新、Frame 合并及失败恢复规则。

### Modified Capabilities

无。当前 `openspec/specs/` 为空；本能力承接已有 change 中的图片编辑命名与替换约定。

## Impact

- `src/anyimage/common/image.py`：共享判断与统一结果提交入口。
- `src/anyimage/operators/image_edit_tool/` 及调用图片替换入口的 Job 响应：结果提交与 Frame 合并。
- `tests/test_image_data.py`、`tests/test_alpha_presentation.py`、`tests/test_blender_addon.py` 及相关图片编辑测试。
