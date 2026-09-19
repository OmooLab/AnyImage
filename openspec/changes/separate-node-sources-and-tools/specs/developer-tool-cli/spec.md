## MODIFIED Requirements

### Requirement: Build and check node groups

`node-group build` SHALL 使用当前 Python 环境中的 `bpy`，通过独立 Python 子进程依次构建资产、校验保存的资产、运行 `tests/nodes` 与 `tests/tools/nodes`；`node-group check` SHALL 仅执行后两步。两者 SHALL 支持 `--skip-tests` 仅跳过节点相关 pytest，且 SHALL 不查找或启动外部 Blender 可执行程序。

#### Scenario: Build assets
- **WHEN** 用户运行 `uv run --group blender node-group build`
- **THEN** 使用固定 bpy 环境更新 O_AnyImage.blend，并在独立进程的资产校验和节点相关测试成功后成功退出

#### Scenario: Check existing assets
- **WHEN** 用户运行 `uv run --group blender node-group check`
- **THEN** 使用固定 bpy 环境检查已有资产并运行节点相关测试，资产文件内容保持原样

#### Scenario: Skip Python tests
- **WHEN** build 或 check 指定 `--skip-tests`
- **THEN** 仍执行独立进程的资产校验，跳过 pytest

#### Scenario: Stop after failure
- **WHEN** 构建、校验或测试任一步失败
- **THEN** 命令非零退出且不执行后续步骤

#### Scenario: Missing bpy environment
- **WHEN** 当前 Python 环境无法导入 bpy
- **THEN** 命令非零退出并提示使用 `--group blender`，不尝试查找外部 Blender

### Requirement: Preview node groups

`node-group preview` SHALL 使用当前 Python 环境中的 `bpy`，从当前源码在独立 Python 子进程中构建并排列几何节点组，生成 HTML，输出绝对路径并默认打开浏览器，保持资产文件内容原样。默认文件 SHALL 保存于系统临时目录并在命令退出后可供查看。命令 SHALL 支持 `--output PATH`、`--no-open` 和 `--fragment`，不支持选择外部 Blender 可执行程序。

#### Scenario: Preview current source
- **WHEN** 用户运行 `uv run --group blender node-group preview`
- **THEN** 生成当前源码的可查看 HTML 并尝试打开浏览器

#### Scenario: Save without opening
- **WHEN** 用户指定 `--output PATH --no-open`
- **THEN** HTML 写入指定路径且不启动浏览器

#### Scenario: Export fragment
- **WHEN** 用户指定 `--fragment`
- **THEN** 输出 HTML 片段及其路径，不自动打开浏览器
