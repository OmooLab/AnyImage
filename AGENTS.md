# AnyImage 项目规范

## 总则

**不管是代码还是文档，遵循「少就是多」的原则，以好理解为首要要求**

- 说明性内容以中文为主，专有名词和约定俗成的表达可使用英文
- 修改代码、依赖或执行方式后，
  - 不保留旧路径、转发函数、兼容层或胶水代码
  - 仅更新并运行相关测试，但不主动同步说明文档、构建文档或打包扩展
- 优先选择依赖少、直接、易验证的实现
- 复用来自 `common` 的函数，避免重复造轮子
- 确保文件名/文件夹名和内容边界一致

## 全面整理代码

当用户说「全面整理代码」时，依据本文件规范，直接执行以下整理：

- 按业务职责梳理代码结构与命名；简单功能用单文件，复杂 Operator 功能包统一以 `operators.py` 为入口，`__init__.py` 负责导出与注册清单。
- 沿真实调用链清理无用代码，不把仅有测试引用当作业务用途；查证动态调用、框架回调和注册入口后再删除。
- 精简测试，保留有效行为覆盖，使测试名称、归属与功能对应，并检查状态隔离。
- 同步整理 `tools/nodes`、`docs/internals` 和相关引用，使名称、说明与实际实现一致。本触发指令包含内部文档整理。
- 保留已有的其他修改和有效功能，运行全量测试并确认正常退出，检查旧引用与最终差异，简要报告调整及验证结果；不构建文档或打包扩展。

## 查询文档

下列是重要文档

- [总览](docs/internals/index.md)：内部实现的总揽
- [程序架构](docs/internals/architecture.md)：进程边界、职责与调用主链
- [Operator 索引](docs/internals/operators/index.md)：Operator 实现功能和对应源码
- [节点资产](docs/internals/node-assets.md)：节点组的构建与验证（节点组不在运行时新建）

## 常见命令

```bash
# 安装或同步开发依赖
uv sync

# 本地 BlendJob wheel 内容变化后刷新锁文件
uv lock --refresh

# 运行全部测试
uv run --group blender --group ai pytest

# 构建 Windows、macOS、Linux 扩展包到 dist/
uv run pack

# 本地构建多版本静态页面（只提交到本地 gh-pages 分支，不推送）
uv run --group docs docs build

# 本地热更新预览当前文档
uv run --group docs docs dev

# 用 pyproject.toml 中的 major.minor.x 发布文档并让 latest 指向它
uv run --group docs docs deploy

# 构建并验证 Blender 节点资产
uv run --group blender node-group build

# 准备、校验并同步 ONNX 模型到 R2
uv run --group models model sync
```

## 命名规范

- 变量、函数、Docstring 必须使用英文；同一概念在代码和文档中使用统一表达
- 函数的动作前缀应表达产物边界：`generate_*` 表示 AI 生成。`build_*` 表示代码层构建。`create_*` 表示 Blender 内创建
- 名称应说明业务职责，并与用户概念、公开协议和界面术语保持一致；不要使用脱离上下文后无法判断用途的宽泛名称
- 文件和目录名应表达稳定的业务分类和模块职责，不直接沿用函数名，也不按临时执行步骤命名
- 集合层使用复数，单项分类使用单数

- Operator Class 使用动宾结构，如 `ConvertToDepthPlane`、`RemoveImageBackground`
- Menu、Panel、AddonPreferences、PropertyGroup 分别使用实际类型后缀，如 `AnyImageImageMenu`、`ServerPanel`、`AnyImagePreferences`、`AnyImageSettings`
- `bl_idname` 使用 `anyimage` 项目前缀：
  - Operator 如 `anyimage.convert_to_depth_plane`
  - Menu 如 `ANYIMAGE_MT_image_context`
  - Panel 如 `ANYIMAGE_PT_server`
  - 公共 Property 如 `Scene.anyimage_settings`
- Operator 自身 Property 不加项目前缀，使用业务名称，如 `input_path`、`process_res`、`resolution_level`
- 扩展包名使用 Manifest 中的真实名称、版本和平台，例如 `AnyImage.v0.11.2.windows-x64.zip`；节点组名称沿用资产中的 `O DA3 Depth Plane`、`O MoGe2 Surface` 等既有名称

## 文档规范

- `README.md` 面向用户，不在其中堆叠内部细节。实现原理放入 `docs/internals` 对应主题
- 文档只正面描述当前主题的职责与实现，不记录无关模块、未采用路径、历史差异、边界辩解、“不做什么”的排除性信息。
- 根据内容选择最清晰的表达方式，优先简洁文字；复杂流程或关系在有助于理解时使用图表。Mermaid 流程图默认从上到下。
- 文档版本只使用 `pyproject.toml` 中的 major.minor，写成 `x.y.x` 系列标识，不写具体 patch；`uv run docs build` 和 `uv run docs deploy` 都构建到该版本并更新 `latest`
- mike 默认只提交不推送，`--push` 不能省；内容没有变化时 mike 会跳过提交并连带跳过推送，所以 `uv run docs deploy` 额外带 `--allow-empty`；mike 默认推送到 `origin`，本仓库的远端名是 `omoolab`

## Blender 开发规范

- 扩展级设置及其读取入口统一放在 `preferences.py`；使用 `addon_preferences()` 读取
- Blender 类型的 `bl_idname` 和 `bl_label` 在类型定义处直接声明；共享协议确有循环依赖时可由定义和消费者共同引用单一常量
- `layout.operator`、keymap、`WorkSpaceTool.bl_operator`、注册关系等声明式消费者应引用项目类型的 `bl_idname`，不重复写项目内 ID 字符串
- UI 使用目标类型的默认名称时省略 `text`，由 Blender 读取 `bl_label`；仅在动态名称、上下文简称或语义不同时显式设置 `text`
- `bpy.ops` 执行调用保持原生命名空间写法；外部依赖或运行时动态生成且无可引用类型的 Operator 使用字符串 ID
- Job 参数使用可序列化的普通字典；Blender 数据只能在主线程的 Operator 响应阶段读写
- 新增或修改 Blender 类型时同步检查 `src/anyimage/__init__.py` 的注册与逆序注销，并补充对应测试
- 依赖版本、wheel 或 Manifest 改变时同步检查 `pyproject.toml`、`uv.lock`、`blender_manifest.toml` 和打包测试
- `server/` 是 blendjob 后端代码，无法引用来自它上级文件夹的内容。共享函数需单独实现。

## Blender 节点组规范

- 节点组源码位于顶层 `nodes/`，`tools/nodes` 只负责构建、校验、布局和预览。
- `src/anyimage/assets/O_AnyImage.blend` 是发布构建产物，由节点源码生成且不得提交到 Git。
- 插件运行时必须使用 `load_node_group(group_name)` 从资产加载，禁止调用 `bpy.data.node_groups.new()` 创建节点组。
- `nodes/` 构建代码和节点测试允许通过代码创建节点组。
- 字段默认直接连接，按消费位置的几何、域、类型及输入属性版本验证求值等价性；多个消费者可复用同一输出。
- 所有几何节点、嵌套组及测试辅助图禁止使用 Capture Attribute。域转换显式表达；跨几何变化优先调整消费顺序或在明确源几何上采样。
- Store Named Attribute 仅用于实际命名协议或经论证仍需跨几何变化保存的最少数据；明确名称、类型、域、Selection、写入阶段及消费者。多个消费者或跨区域连线不构成存值理由。
- 内部临时命名属性使用专用名称，在最后消费者之后精确清理，保留用户属性；源码和保存资产均检查 Capture 为零。
- 节点布局通过区域内输入、字段排列和必要的 Reroute 保持可读；存储须有数据生命周期依据，构建阶段通过明确的节点或 socket 引用接线。
- 修改节点组的逻辑、接口、布局或共用构建函数后，必须运行 `uv run --group blender node-group build`，无需另行确认；生成资产并验证通过才算完成。
- 具体构建规范与操作步骤见[节点资产](docs/internals/node-assets.md)。
