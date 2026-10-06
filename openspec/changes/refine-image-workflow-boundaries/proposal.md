## Why

图片编辑、Bake Mesh、颜色参考和模型安装的状态边界需要统一梳理，避免跨 Scene 缓存清理、重复图片生命周期实现和职责分散。将已确认的审查项拆成可独立核对的任务，明确 Bake 完成后的对象身份和模型快速检查与完整校验的分工。

## What Changes

- Bake 成功后移除对象的 AnyImage 能力标记，使结果成为普通 Mesh；Shader Editor 的贴图节点操作沿用现有逻辑，`_color`、`_normal`、`_depth` 图片沿用现有参考候选过滤。
- 按图片拼接、法线烘焙及几何固化的实际操作设置输入校验条件。
- 隔离各 Scene 的参考选择与缓存释放，明确公共参考数据、Scene 同步和预览资源的职责，限制全尺寸参考快照的长期保留。
- UI 通过本地文件信息快速判断模型是否已安装；服务端首次加载时完整校验文件并复用校验缓存，提供校验失败后的重新下载入口。
- 复用公共图片创建能力；按业务职责收拢去背景、颜色匹配、Polygon 接口和相关测试，删除旧路径及无用实现。
- 模型目录统一声明档位，服务端状态以稳定模型 key 表达身份。
- 整理相关测试、真实 GPU 预览验证和内部文档；色板只读交互暂缓，当前控件行为保留。

## Capabilities

### New Capabilities

- `mesh-bake-boundaries`: 定义 Bake 完成后的普通 Mesh 身份、分支校验与事务保留要求。
- `color-reference-lifecycle`: 定义 Scene 参考隔离、缓存保留范围及恢复行为。
- `model-installation-validation`: 定义本地安装检查、服务端完整校验与修复入口。

### Modified Capabilities

- `object-image-actions`: Bake 后移除对象图片操作能力并支持 Undo/Redo 恢复。
- `server-cache-display`: 加载状态使用模型 key，并按目录声明展示档位。
- `maintainable-project-structure`: 明确公共模块、复杂 Operator 包、测试及内部文档的职责归属和引用清理。

## Impact

- Blender 侧：`common/`、`operators/`、`properties.py`、`panel.py`、`preferences.py`、菜单及扩展注册入口。
- 服务端：模型目录、Session 缓存、首次加载校验和模型下载流程。
- 维护：相关 `tests/`、`nodes/common/cutout.py`、节点资产校验及 `docs/internals/`。
- 本次交付为提案、设计、规格和未完成任务清单。实施时保持模型、图片、材质与节点组的现有有效功能，按任务核对；依赖与发布方式沿用当前配置。
