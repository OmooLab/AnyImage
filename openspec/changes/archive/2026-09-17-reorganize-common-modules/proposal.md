## Why

`common/` 当前以功能演进过程形成分类，部分模块同时容纳数据、I/O、UI、交互与绘制职责，导致公共函数的位置不能由名称直接判断；例如通用 AI UI 函数 `draw_ai_setup()` 位于 `image_interaction.py`。重新建立稳定、可预测的模块边界，可以降低新增功能复用公共能力时的查找与依赖成本。

## What Changes

- 将 `common/` 收敛为八个稳定业务模块：`ai`、`image`、`region`、`viewport`、`depth`、`material`、`object` 和 `node`。
- 将 `draw_ai_setup()`、`draw_ai_property()` 从 Image 交互分类移至 `ai.py`，与 AI 环境、模型检查和 Job 参数准备形成统一入口。
- 保留完整的 Image 生命周期于 `image.py`，将 View3D 坐标、手势和 Overlay 绘制统一归入 `viewport.py`，避免把视口交互误称为图片编辑。
- 仅从 `object.py` 独立出体量较大、职责明确的材质构建函数；Modifier 和结果 Object 处理继续归入 Object 分类。
- 更新所有 Operator 与测试的直接导入，同时同步 `docs/internals/common.md` 和架构索引。
- **BREAKING**：删除被替代的旧模块路径，不提供重导出、转发函数或兼容层；这是仅面向项目内部源码的导入变更，不改变扩展的用户功能与公开 Blender 标识符。

## Capabilities

### New Capabilities

无。本变更只重构 Blender 侧内部公共函数的模块边界，不新增用户可观察行为。

### Modified Capabilities

无。现有功能、Operator 协议、Job 参数和结果保持不变。

## Impact

- 主要影响 `src/anyimage/common/` 及所有直接导入这些模块的 `operators/`、`menu.py` 和测试。
- `src/anyimage/server/` 的进程边界、Job 协议、模型实现和依赖均不改变。
- 不新增依赖，不改变 Blender 类型注册、`bl_idname`、节点组名称或扩展打包内容。
