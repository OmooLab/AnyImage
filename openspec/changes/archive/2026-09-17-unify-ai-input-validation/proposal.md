## Why

Remove BG 与 Upscale 对同一种输入给出不同的格式提示，Remove BG 的普通校验错误还会经嵌套 Operator 调用变成 Python traceback。检查发现格式规则重复、序列过滤、路径提示和临时输入清理也存在同一调用链上的不一致，需要建立统一的输入与失败处理契约。

## What Changes

- AI 文件输入使用同一套格式规则与错误文案，前端提前校验，后端独立复核；错误说明实际扩展名及支持的图片、视频格式。
- 区分路径缺失、格式不支持、目录无有效帧和文件无法解码，路径提示统一使用 source image/video，适用于 Image Empty 和材质 Image Texture。
- Blender 图片序列在复制前验证格式，避免不支持的序列被当成空目录；通用帧目录明确过滤规则。
- Remove BG、Depth/Relief Plane 与 AI Environment 的嵌套调用按普通错误取消操作，并统一资源释放；审查 Panorama 既有处理作为回归范围。
- 保留静态图、尺寸、比例等功能专属限制，统一其异常出口；格式能力以当前实际提交文件为准。

## Capabilities

### New Capabilities

- `ai-input-validation`: AI 文件、帧目录与 Blender 图片序列的公共校验、错误分类及文案。
- `ai-operator-failure-handling`: AI Operator 的失败展示、取消状态与临时输入所有权。

### Modified Capabilities

无。当前 `openspec/specs/` 为空。本提案与现有 `add-texture-node-image-actions`、`add-panorama-conversion` 变更共同验收相关入口。

## Impact

- `src/anyimage/server/media/input.py`、`server/media/__init__.py`、`server/models/ben2.py`：公共格式契约、目录处理与模型输入校验。
- `src/anyimage/common/ai.py`、`common/image.py`：前置校验、源路径与序列准备、临时资源释放。
- `operators/remove_background.py`、`upscale.py`、`convert_to_plane/operators.py`、`ai_setup.py` 及其他公共入口消费者：错误传播与回归。
- 更新相关行为测试，运行全量 pytest，并用 Blender 验证嵌套调用的实际报错。依赖与节点资产沿用当前版本。
