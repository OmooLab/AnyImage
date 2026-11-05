# AnyImage 项目规范

## 总则

**不管是代码还是文档，遵循 KISS 原则，以好理解为首要要求**

- 说明性内容以中文为主，专有名词和约定俗成的表达可使用英文
- 修改代码、依赖或执行方式后，
  - 不保留旧路径、转发函数、兼容层或胶水代码
  - 仅更新并运行相关测试，但不主动同步说明文档、构建文档或打包扩展
- 优先选择依赖少、直接、易验证的实现
- 简单直写优先于消除重复；不得仅为合并相似流程引入管理类、工厂、策略或回调配置。只有真实共享的业务逻辑才提取为职责明确的函数。
- 复用来自 `common` 的函数，避免重复造轮子
- 确保文件名/文件夹名和内容边界一致

## 项目结构

```text
.codex/                      项目 Codex 配置与技能
.github/                     GitHub 工作流与仓库配置
.tmp/                        项目临时输出
.venv/                       Python 开发环境
dist/                        扩展包与节点资产构建产物
docs/                        用户文档与开发文档
models/                      本地 ONNX 模型
nodes/                       Blender 节点资产源码
openspec/                    功能规范与变更记录
site/                        文档站点构建产物
src/anyimage/
  assets/                    插件资源与生成的节点资产
  common/                    插件公共函数
  operators/                 Blender Operator 与功能包
  server/                    BlendJob 后端
  licenses/                  依赖许可证
  wheels/                    插件随包依赖
tests/                       自动化测试与测试辅助代码
tools/                       构建、打包、文档与模型管理工具
```

- 项目可控的临时文件、缓存、日志与验收产物统一放在 `.tmp/`，内部按任务或用途命名。
- 一次性排查脚本、截图、测试报告及中间数据放在 `.tmp/`；需要长期维护的工具和测试分别放在 `tools/`、`tests/`。
- `.tmp/` 由 Git 忽略，任务结束后清理本次创建且已无用途的文件；需保留供验收的产物在交付时说明路径。
- 正式构建产物使用上方约定的目录，工具自动管理的环境与缓存沿用其既有配置。

## 整理代码

当用户说「整理代码」时，对全局或局部执行：

- 检查并确保代码符合本文提到的所有开发规范。
- 保留已有的其他修改和有效功能，沿真实调用链清理无用代码。
- 同步整理文档，使名称、说明与实际实现一致。
- 精简测试，保留有效行为覆盖，运行全量测试并确认正常退出。

## 查询文档

下列是重要文档

- [总览](docs/develop/index.md)：内部实现的总览
- [程序架构](docs/develop/architecture.md)：进程边界、职责与调用主链
- [Operator 索引](docs/develop/operators/index.md)：Operator 实现功能和对应源码
- [节点资产](docs/develop/node-assets.md)：节点组的构建与验证（节点组不在运行时新建）

## 常见命令

```bash
# 安装或同步开发依赖
uv sync

# 本地 BlendJob wheel 内容变化后刷新锁文件
uv lock --refresh

# 运行全部测试
uv run --group blender --group ai pytest

# 为 Windows x64 同步本地插件 wheel 与 Manifest
uv run pack -l -p windows-x64

# 构建 Windows、macOS、Linux 扩展包到 dist/
uv run pack

# 本地构建多版本静态页面（只提交到本地 gh-pages 分支，不推送）
uv run --group docs docs build

# 本地热更新预览当前文档
uv run --group docs docs dev

# 用 pyproject.toml 中的 major.minor.x 发布文档并让 latest 指向它
uv run --group docs docs deploy

# 构建并验证 Blender 节点资产
uv run --group blender omoonodes build
mkdir -p src/anyimage/assets
cp dist/b45/O_AnyImage/O_AnyImage.blend src/anyimage/assets/O_AnyImage.blend
uv run --group blender pytest tests/nodes

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
- Menu、Panel、AddonPreferences、PropertyGroup 分别使用实际类型后缀，如 `ImageMenu`、`ServerPanel`、`Preferences`、`Settings`
- 偏好设置类分别命名为 `PreferencesBase` 和 `Preferences`，直接导入真实类名，不使用旧名或别名。
- 场景设置类分别命名为 `SettingsBase` 和 `Settings`，直接导入真实类名；公共属性仍使用 `Scene.anyimage_settings`。
- 菜单类按职责命名为 `ImageMenu`、`ObjectMenu`、`TextureNodeMenu`；基础版使用 `Base` 后缀，独立定义，不继承完整版或反向继承。菜单挂接函数放在两个入口。对外显示的产品名称统一为 `Any Image`。
- `bl_idname` 使用 `anyimage` 项目前缀：
  - Operator 如 `anyimage.convert_to_depth_plane`
  - Menu 如 `ANYIMAGE_MT_image_context`
  - Panel 如 `ANYIMAGE_PT_server`
  - 公共 Property 如 `Scene.anyimage_settings`
- Operator 自身 Property 不加项目前缀，使用业务名称，如 `input_path`、`process_res`、`resolution_level`
- 产品显示名使用 `Any Image`；文件名中的品牌名使用去掉空格的大驼峰 `AnyImage`，不写成 `Any_Image`。扩展包名为 `AnyImage.v<version>.<platform>.zip`，基础版为 `AnyImage_Base.v<version>.<platform>.zip`；打包、校验和发布流程保持一致。节点组名称沿用资产中的 `O DA3 Depth Plane`、`O MoGe2 Surface` 等既有名称

## 文档规范

- `README.md` 面向用户，不在其中堆叠内部细节。实现原理放入 `docs/develop` 对应主题
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
- `__init__.py` 与 `__init_base__.py` 的注册和注销流程有意重复，分别在各自入口直接实现和维护；不得抽成共享注册类、注册函数、Mixin 或生命周期框架（如 `AnyImageRegistration`）。公共类型可按业务模块导出复用。
- 两个入口分别直接导入并在 `CLASSES` 中逐项列出本版的全部静态注册类型，按设置、Operator、Menu、Panel 分组，保持必要注册顺序。不得使用 `base.CLASSES`、`*XXX_CLASSES`、替换映射或动态收集；下级模块不再维护 `CLASSES`。注册直接遍历 `CLASSES`、`TOOLS`、`MENUS`，注销反序遍历同一清单；不维护 `_registered`、`_registered_*` 状态，不添加失败回滚。BlendJob 的动态类型仍由 Runtime 注册。
- `TOOLS`、`MENUS` 也分别在两个入口显式汇总，由入口选择 AI 或非 AI 类型；下级模块只定义类型，不提供注册清单或清单生成函数。
- 翻译模块提供分组数据，`translations.py` 提供 `build_translations()`；两个入口显式选择本版分组并构建 `TRANSLATIONS`。
- 依赖版本、wheel 或 Manifest 改变时同步检查 `pyproject.toml`、`uv.lock`、`blender_manifest.toml` 和打包测试
- `server/` 是 blendjob 后端代码，无法引用来自它上级文件夹的内容。共享函数需单独实现。
- 按业务职责梳理代码结构与命名；简单功能用单文件，复杂 Operator 功能包统一以 `operators.py` 为入口，功能包的 `__init__.py` 只导出实际使用的类型。

## Blender 节点组规范

- 节点资产由 PyPI 的 `omoonodes` 管理，版本锁定在 `blender` dependency group；使用默认源码目录 `nodes/`、目标 `b45` 及默认 Blender 版本，无需额外配置。
- 资产库位于 `nodes/O_AnyImage/`，`collection.json` 将 `O_AnyImage.blend` 映射到库内的 `O_AnyImage/` 源码目录；节点源码使用 `omoonodes dump` 导出的 nodebpy 写法。
- 首次 dump 前必须将待导出的节点组标记为 Asset 并保存；在 Blender 中编辑时，先用 `omoonodes dev nodes/O_AnyImage` 生成开发库，再用 `omoonodes dev nodes/O_AnyImage --sync workspaces` 同步源码。命令均通过 `uv run --group blender` 执行。
- `src/anyimage/assets/O_AnyImage.blend` 是发布构建产物，由节点源码生成且不得提交到 Git。
- 插件运行时必须使用 `load_node_group(group_name)` 从资产加载，禁止调用 `bpy.data.node_groups.new()` 创建节点组。
- `nodes/` 构建代码和节点测试允许通过代码创建节点组。
- 字段默认直接连接，按消费位置的几何、域、类型及输入属性版本验证求值等价性；多个消费者可复用同一输出。
- 所有几何节点、嵌套组及测试辅助图禁止使用 Capture Attribute。域转换显式表达；跨几何变化优先调整消费顺序或在明确源几何上采样。
- Store Named Attribute 仅用于实际命名协议或经论证仍需跨几何变化保存的最少数据；明确名称、类型、域、Selection、写入阶段及消费者。多个消费者或跨区域连线不构成存值理由。
- 内部临时命名属性使用专用名称，在最后消费者之后精确清理，保留用户属性；源码和保存资产均检查 Capture 为零。
- 节点布局通过区域内输入、字段排列和必要的 Reroute 保持可读；存储须有数据生命周期依据，构建阶段通过明确的节点或 socket 引用接线。
- 修改节点组的逻辑、接口或布局后，必须运行 `uv run --group blender omoonodes build`，将 `dist/b45/O_AnyImage/O_AnyImage.blend` 复制到 `src/anyimage/assets/O_AnyImage.blend`，并运行相关节点测试，无需另行确认；生成资产并验证通过才算完成。
- 具体构建规范与操作步骤见[节点资产](docs/develop/node-assets.md)。
