## 1. 拆分节点源码与工具

- [x] 1.1 创建顶层 `nodes` package，将 `tools/nodes/groups` 和 `tools/nodes/common` 移入并删除旧路径
- [x] 1.2 更新构建、布局、预览、测试和辅助代码的导入，使节点定义只从 `nodes.groups` 与 `nodes.common` 加载
- [x] 1.3 将 `nodes` 加入 Hatch wheel 包清单，验证安装后的 `node-group` 入口可加载节点定义
- [x] 1.4 将节点定义行为测试移动到 `tests/nodes`，仅将构建、布局、校验和预览工具测试保留在 `tests/tools/nodes`

## 2. 将节点资产改为构建产物

- [x] 2.1 将 `src/anyimage/assets/O_AnyImage.blend` 加入 `.gitignore` 并从 Git 索引移除，不改变扩展运行时资产路径
- [x] 2.2 为打包器增加节点资产存在性检查，并覆盖缺失失败与归档包含资产的行为
- [x] 2.3 增加版本控制边界测试，确认生成的节点资产不会再次进入 Git

## 3. 统一节点工具运行环境

- [x] 3.1 删除 `--blender`、`BLENDER_BIN`、`.env` 读取、Blender 路径发现及外部进程 bootstrap
- [x] 3.2 让 build、check 和 preview 通过当前 Python 的独立子进程运行，让 build/check 只运行节点相关测试，并在缺少 bpy 时给出 `--group blender` 提示
- [x] 3.3 更新节点 CLI 测试，覆盖命令顺序、参数传递、失败停止和不再支持外部 Blender 配置

## 4. 接入 CI 构建

- [x] 4.1 修改测试工作流，通过统一的 `node-group` 入口从干净源码生成并校验节点资产后再运行常规测试
- [x] 4.2 修改发布工作流，在测试和打包前生成并校验节点资产，确保生成文件进入全部平台归档
- [x] 4.3 更新工作流测试，验证 CI 不要求 `BLENDER_BIN` 或额外下载完整 Blender

## 5. 同步规范与文档

- [x] 5.1 更新 `AGENTS.md`，将节点资产定义为必须由源码构建、不得提交的发布构建产物，并删除外部 Blender 配置规则
- [x] 5.2 更新 `docs/internals/node-assets.md` 及相关内部引用，说明 `nodes/`、`tools/nodes/`、bpy 环境和 CI 生成链

## 6. 验证

- [x] 6.1 从不存在 `O_AnyImage.blend` 的状态运行统一的节点资产构建与独立检查
- [x] 6.2 运行节点定义、节点工具、常规及全量测试，确认重组前后节点行为一致
- [x] 6.3 运行打包相关测试并检查生成归档，确认包含节点资产且源码树未重新跟踪该文件
- [x] 6.4 搜索旧导入、外部 Blender 配置和路径引用，检查最终差异并严格验证 OpenSpec 变更
