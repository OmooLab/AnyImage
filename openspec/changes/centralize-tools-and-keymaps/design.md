## Context

AnyImage 目前有四个 WorkspaceTool。它们的类声明分别位于 Frame、Mask、Rectify、Cutout 的 Operator 模块中，而具体注册顺序和参数直接写在扩展顶层 `__init__.py`。现有快捷键只有剪贴板功能使用的四个 keymap item，其定义、注册记录和清理函数都位于剪贴板 Operator 模块。

WorkspaceTool 和 keymap 都是扩展级注册资源。新增同类资源时，应当只进入对应类型模块，而不是继续扩展顶层入口或在业务 Operator 中重复生命周期代码。

## Goals / Non-Goals

**Goals:**

- 按 Blender 类型集中 WorkspaceTool 声明和生命周期。
- 为全部扩展快捷键建立一个可直接阅读和维护的常量清单与注册入口。
- 让新增 Tool 或快捷键只需在对应模块中添加普通代码。
- 保持现有 Operator、工具顺序和剪贴板快捷键行为。

**Non-Goals:**

- 不移动或重命名现有 Operator 与业务辅助模块。
- 不新增 Cutout 快捷键，也不决定未来 Cutout 使用哪个键位。
- 不建立 keymap dataclass、通用配置 schema、插件式 provider、回调协议或兼容转发层。
- 不为未来尚未出现的 keymap 属性、条件组合或冲突处理提前抽象。

## Decisions

### 1. WorkspaceTool 使用单一 `tools.py`

`src/anyimage/tools.py` 直接定义 `FrameTool`、`MaskTool`、`RectifyTool` 和 `CutoutTool`。这些类只包含 Blender 工具元数据、关联 Operator、工具内 keymap 和设置绘制，规模适合单文件。

`TOOLS` 按工具栏顺序保存 `(tool, options)`：

```python
TOOLS = (
    (FrameTool, {"separator": True, "group": True}),
    (MaskTool, {"after": {FrameTool.bl_idname}, "separator": False}),
    (RectifyTool, {"after": {MaskTool.bl_idname}, "separator": False}),
    (CutoutTool, {}),
)
```

`register()` 顺序遍历，`unregister()` 逆序遍历。顶层入口只调用这两个函数。Operator 模块继续拥有 Operator ID 常量、执行状态和业务实现，不反向导入 `tools.py`。

### 2. Keymap 信息先声明为常量

`src/anyimage/keymaps.py` 包含：

- `_PRIMARY_MODIFIER`：当前平台的主快捷键修饰键。
- `CLIPBOARD_SHORTCUTS`：剪贴板功能使用的 Operator、按键、事件和修饰键。
- `KEYMAPS`：每个 Blender keymap 的名称、`space_type` 和快捷键集合。
- `_items`：记录本模块实际创建的 `(keymap, item)`。
- `_add()`：消费一项快捷键定义，调用 `keymap.keymap_items.new(...)` 并记录结果。
- `register()`：获取 addon keyconfig，只遍历 `KEYMAPS` 和其中的快捷键定义。
- `unregister()`：移除 `_items` 中的项目并清空列表。

常量使用普通 tuple 和 dict，字段名直接对应 Blender 概念，不引入 dataclass 或配置解析层。维护者无需阅读 `register()` 的控制流程即可看到所有功能绑定及其生效面板。

`register()` 不包含 `clipboard_image_supported()` 等功能特殊判断。Operator 自身的 `poll()` 继续决定功能在当前平台和上下文是否可执行。后续新增快捷键时，只扩展快捷键常量和 `KEYMAPS`；只有出现真实需求后才增加新的字段或抽象。

### 3. 删除旧入口而非兼容它

剪贴板 Operator 模块删除 `_keymap_items`、`register_keymaps()` 和 `unregister_keymaps()`，其包入口也不再导出这些名称。顶层扩展入口改为直接调用 `keymaps.register()` 和 `keymaps.unregister()`，不保留旧函数作为转发层。

原生复制跟踪 token 属于剪贴板行为状态，而不是 keymap 注册资源；迁移后不为旧注销函数的 token 清空副作用建立额外 hook。该状态只有在复制跟踪 Operator 执行后才产生，并继续由剪贴板 Operator 自身读写。

### 4. 测试验证生命周期，不复制实现

现有扩展注册测试改为从 `tools.py` 读取 Tool，并继续验证顺序、参数和逆序清理。现有剪贴板快捷键测试改为调用统一 keymap 模块，继续验证平台修饰键、上下文和清理。

不新增针对内部 `_add()` 的测试，也不增加没有用户行为的新用例。内部文档只同步模块职责和注册路径，不构建文档。

## Risks / Trade-offs

- [Tool 抽取时遗漏 UI 依赖] → 保持类内容不变，仅调整导入，并运行现有 Tool 设置与交互测试。
- [keymap 迁移后遗留旧入口] → 使用 `rg` 检查 `register_keymaps`、`unregister_keymaps` 和 `_keymap_items`。
- [集中模块直接依赖具体 Operator] → 这是扩展注册层的预期依赖方向；Operator 不反向依赖注册层，因此不会形成循环。
- [不在注册阶段过滤平台能力] → 保持 keymap 清单完整一致，由 Operator `poll()` 处理平台和上下文可用性。
