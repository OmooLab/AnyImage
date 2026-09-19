## Why

WorkspaceTool 声明散落在 Operator 模块中，Tool 注册和快捷键生命周期也分别由顶层入口与具体功能模块管理，使新增 Tool 或快捷键时需要修改多个位置。需要建立两个简单、统一且按 Blender 类型划分的入口，同时保持现有用户行为不变。

## What Changes

- 新增 `src/anyimage/tools.py`，集中定义 Frame、Mask、Rectify、Cutout 四个 WorkspaceTool，并通过一个有序清单统一注册和逆序注销。
- 保持 `operators/` 的目录、Operator 和业务实现位置不变；Operator 模块不再定义或导出 WorkspaceTool。
- 新增 `src/anyimage/keymaps.py`，以常量完整描述功能、按键、事件和所属 Blender 面板，再通过统一循环注册和清理扩展快捷键。
- 将现有剪贴板快捷键定义迁移到统一 keymap 常量，保留平台修饰键，删除功能模块内旧的 keymap 注册入口和特殊可用性分支。
- 暂不增加 Cutout 或其他新快捷键；后续快捷键直接在统一模块中声明。
- 更新相关测试和内部架构文档，不新增只复述注册参数的测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `maintainable-project-structure`: 按 Blender 类型集中 WorkspaceTool 声明，并为全部扩展快捷键建立单一、直接的注册生命周期。

## Impact

- 影响四个 WorkspaceTool 的定义与导入位置、扩展顶层注册入口、剪贴板 keymap 注册代码及相关测试。
- `operators/` 的业务模块路径、Operator ID、工具 ID、快捷键和用户行为保持不变。
- 不新增依赖，不修改 Cutout 快捷键、节点资产、Server 协议或模型逻辑。
