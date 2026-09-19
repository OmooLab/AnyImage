## Context

节点组的可维护源码位于 `tools/nodes/groups` 和 `tools/nodes/common`，构建入口、布局、校验与预览也位于同一包中。生成后的 `src/anyimage/assets/O_AnyImage.blend` 被扩展运行时读取并进入发布包，但它同时作为 Git LFS 文件提交，历史中已累积多个 1–10 MB 的版本。

项目通过 `blender` dependency group 安装 `bpy==4.5.3`，现有测试也使用该 wheel 创建节点、求值几何及写入 `.blend`。因此本地和 CI 都不需要额外安装或定位完整 Blender 应用程序。

## Goals / Non-Goals

**Goals:**

- 根目录 `nodes/` 只表达节点组及共用节点构建定义。
- `tools/nodes/` 只表达构建、布局、校验和预览工具。
- 干净 CI 从源码生成、验证并打包节点资产。
- 本地与 CI 使用同一个 `node-group` 执行路径，不需要 `.env` 或 `BLENDER_BIN`。
- Git 当前树不再包含生成的 `.blend` 或对应 LFS pointer。
- 节点组的接口、默认值、求值和最终发布包保持不变。

**Non-Goals:**

- 不在本变更中重写 Git 历史或清理远程 LFS 对象。
- 不改变节点组业务名称和实现逻辑。
- 不把节点资产改为扩展运行时动态创建。
- 不提供选择其他 Blender 可执行程序或版本的兼容路径。

## Decisions

### 节点定义成为独立顶层包

建立 `nodes/` Python package：

```text
nodes/
├── common/
└── groups/

tools/nodes/
├── arrangement/
├── preview/
├── build.py
├── check.py
└── cli.py
```

`nodes/groups` 保存各命名节点组定义，`nodes/common` 保存这些定义共享的节点图构建逻辑。布局属于产物呈现和构建工具，继续位于 `tools/nodes/arrangement`。旧 `tools.nodes.groups` 与 `tools.nodes.common` 路径直接删除，不提供转发模块。

Hatch 的工具 wheel同时包含 `tools` 和 `nodes`，确保安装后的 `node-group` 入口能导入节点定义。相应测试按同一职责拆分：节点行为测试进入 `tests/nodes`，工具入口、布局、保存资产和校验测试保留在 `tests/tools/nodes`。

### `.blend` 是构建产物而不是源码

`src/anyimage/assets/O_AnyImage.blend` 加入 `.gitignore` 并从 Git 索引移除。源码检出不承诺该文件存在；开发者使用 `node-group build` 生成它。扩展运行时仍只通过 `load_node_group` 加载生成资产，不在用户运行时创建节点组。

保留 `.gitattributes` 的通用 Blender LFS 规则，因为它可能服务其他手工资产；忽略规则确保本生成物不再加入 Git。删除当前文件只影响未来提交，历史容量将在后续仓库历史整理时处理。

### node-group 统一使用 bpy wheel

`node-group build`、`check` 和 `preview` 都在 `uv run --group blender` 提供的 Python 环境中工作。CLI 不再解析 `--blender`，也不再读取 `BLENDER_BIN`、项目 `.env` 或系统 `PATH`。

为保持构建与保存后检查的进程隔离，CLI 使用 `sys.executable -m` 顺序启动模块：

```text
node-group build
├── python -m tools.nodes.build
├── python -m tools.nodes.check
└── python -m pytest tests/nodes tests/tools/nodes
```

`check` 只运行后两步，`preview` 使用同一 Python 运行预览导出模块。节点命令只运行与节点定义和工具直接相关的测试；项目常规与 AI 测试由各自命令负责。缺少 `bpy` 时命令明确提示使用 `uv run --group blender node-group ...`，不回退到外部 Blender。

相比保留完整 Blender 启动器，这一方案删除了路径发现、`.env` 解析、wheel 解压和 `--python-expr` bootstrap，且让本地与 CI 覆盖同一入口。

### CI 通过 node-group 构建

测试工作流在 pytest 前执行：

```bash
uv run --group blender node-group build --skip-tests
```

该命令使用 CI 已安装的 `bpy==4.5.3`，顺序生成并检查资产。随后运行常规测试目录，节点资产测试读取刚生成的文件。

发布工作流采用同样顺序，在测试成功后执行 `uv run pack`。生成文件留在 job 工作区，由打包器收入扩展压缩包，不作为工作流 artifact 单独传递。

备选方案是在本地或 CI 查找完整 Blender。它下载更大、存在第二套 Python 和依赖 bootstrap，且现有 bpy wheel 已覆盖所需 API，因此删除而不是保留兼容路径。

### 缺失资产时打包明确失败

打包器在创建任何平台包前检查生成资产存在且为普通文件；缺失时给出先构建节点资产的错误。打包测试既验证缺失失败，也验证每个平台归档包含 `assets/O_AnyImage.blend`。

这避免生成步骤遗漏后发布一个运行时才报错的不完整扩展。

## Risks / Trade-offs

- [bpy wheel 的资产兼容性发生变化] → 固定 `bpy==4.5.3`，构建后在独立 Python 进程运行资产检查和现有求值测试。
- [开发者从源码直接启用扩展时缺少资产] → `node-group build` 成为源码使用和打包前置步骤，缺失资产由工具给出明确错误。
- [测试路径重组造成覆盖遗漏] → 沿真实导入路径迁移测试并运行节点构建、常规测试和全量测试。
- [生成文件被误提交] → `.gitignore` 固定忽略具体资产路径，并增加版本控制边界测试。
- [从 Git 删除文件不会立即释放现有远程 LFS 容量] → 本变更只阻止继续增长；后续创建精简根历史时排除旧 LFS 对象。

## Migration Plan

1. 移动节点定义及对应测试，更新全部导入与 wheel 包清单。
2. 将 `node-group` 改为通过当前 Python 的独立子进程运行构建、检查和预览，删除完整 Blender 定位与 bootstrap。
3. 在保留现有资产的情况下构建并验证，确认重组没有改变节点行为。
4. 为测试和发布工作流加入统一的 `node-group` 生成步骤，补充缺失资产打包测试。
5. 将生成资产加入 `.gitignore` 并从 Git 索引移除。
6. 从无节点资产的干净状态执行 CI 等价流程，确认最终发布包包含重新生成的资产。

回滚时恢复节点定义路径、工作流和已提交资产即可；Git 历史清理不属于本变更，因此回滚不需要恢复远程历史。

## Open Questions

无。
