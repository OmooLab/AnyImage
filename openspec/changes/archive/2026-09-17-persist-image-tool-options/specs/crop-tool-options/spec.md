## Purpose

规定四合一 Crop Tool 的工具栏结构、裁切工具命名和独立编辑选项，以及相邻 Cutout Tool 成品相对源图片平面的局部向内轴约定。

## ADDED Requirements

### Requirement: Crop Tool is one four-tool toolbar group
系统 SHALL 在 3D Viewport 工具栏中提供两个独立 AnyImage 入口：一个 **Crop Tool** 工具组和一个普通单项 **Cutout Tool**。Crop Tool SHALL 按 **Crop Box**、**Crop Lasso**、**Crop Polyline**、**Crop Perspective** 的顺序包含四个子工具；Cutout Tool SHALL 不属于任何工具组，并紧接在 Crop Tool 组之后。

#### Scenario: User opens the Crop Tool group
- **WHEN** 用户展开 Crop Tool
- **THEN** 工具组只显示 Crop Box、Crop Lasso、Crop Polyline 与 Crop Perspective
- **AND** Crop Box 是该组的首个子工具

#### Scenario: User views adjacent AnyImage tools
- **WHEN** Crop Tool 组和 Cutout Tool 已注册到 3D Viewport
- **THEN** 工具栏显示 Crop Tool 组与 Cutout Tool 两个独立入口
- **AND** Cutout Tool 紧接在 Crop Tool 组之后
- **AND** Cutout Tool 是单个 WorkSpaceTool，不是单项工具组
- **AND** 两个入口之间没有分割线
- **AND** Cutout Tool 使用 Add UV Sphere 图标

### Requirement: Crop terminology replaces Image Tool terminology
系统 SHALL 对四个裁切子工具、激活入口、Tool ID、Operator、设置属性、源码边界和文档统一使用 Crop 术语，不得保留旧 Image Tool 或独立 Perspective Tool 的兼容名称和转发入口。

#### Scenario: User activates the crop entry
- **WHEN** 用户从 AnyImage 入口激活图片裁切功能
- **THEN** 系统激活 Crop Box 并以 Crop Tool 命名该功能

#### Scenario: Extension registers crop tools
- **WHEN** AnyImage 扩展完成注册
- **THEN** 四个 Crop 子工具使用 `anyimage` 前缀的 Crop Tool ID 注册为同一组
- **AND** 旧 Image Tool 与独立 Perspective Tool ID 不再注册

### Requirement: Image Line is removed
系统 SHALL 删除 Image Line 及其按直线划分图片半平面的裁切行为，不得在 Crop Tool、菜单、快捷入口或公开 Operator 中提供该工具。

#### Scenario: User opens Crop Tool
- **WHEN** 用户查看 Crop Tool 的子工具
- **THEN** 列表中没有 Image Line 或 Crop Line

### Requirement: Crop options persist independently per sub-tool
系统 SHALL 为 Crop Box、Crop Lasso、Crop Polyline 与 Crop Perspective 分别保存彼此独立的 **Keep Original**，并为前三个 Selection Crop Tool 分别保存彼此独立的 **Invert**；所有选项默认关闭，切换一个子工具的值不得改变其他子工具的值，Crop Perspective SHALL NOT 提供 Invert。

#### Scenario: User returns to a Crop sub-tool
- **WHEN** 用户修改一个子工具支持的 Invert 或 Keep Original，切换到其他 Crop 子工具后再返回
- **THEN** 该子工具恢复自己上次保存的选项值

#### Scenario: User uses a Crop sub-tool for the first time
- **WHEN** 当前文件尚未修改该子工具支持的 Invert 或 Keep Original
- **THEN** 该子工具支持的选项均为关闭

#### Scenario: User opens Crop Perspective settings
- **WHEN** 用户激活 Crop Perspective
- **THEN** 工具设置提供独立的 Keep Original
- **AND** 工具设置不提供 Invert 或 Refine Selection

### Requirement: Invert follows the persistent Crop sub-tool option
Crop Box、Crop Lasso 与 Crop Polyline SHALL 使用当前子工具保存的 **Invert** 值决定保留 Selection 内部还是外部，并只通过工具选项修改该值；Crop Perspective 不参与该行为，Crop Tool 的 keymap 与 modal 交互 SHALL NOT 将 `F` 或其他字母键绑定为选项快捷键。

#### Scenario: User changes Invert in tool settings
- **WHEN** 用户在任一 Selection Crop Tool 的工具设置中修改 Invert
- **THEN** 系统保存当前子工具的 Invert，下一次裁切使用新值

#### Scenario: User operates a Crop tool with a letter key
- **WHEN** Crop Tool 空闲或正在执行 modal 交互
- **THEN** Crop Tool 不使用 `F` 或其他字母键切换 Invert、Keep Original 或 Refine Selection

### Requirement: Cutout has no letter option shortcuts
Cutout Tool 的 keymap 与 modal 交互 SHALL NOT 使用 `F` 或其他字母键切换选项。

#### Scenario: User presses F during Cutout selection
- **WHEN** Cutout Tool 正在执行 Selection modal 交互
- **THEN** `F` 不切换 Invert 或其他选项

### Requirement: Keep Original preserves the crop source
四个 Crop 子工具 SHALL 在各自的 **Keep Original** 关闭时以裁切结果替换源 Image Empty；开启时 SHALL 为本次裁切创建一个结果 Image Empty，并保留源 Image Empty 的对象、图片、变换和显示设置。

#### Scenario: User crops with Keep Original disabled
- **WHEN** 用户在 Keep Original 关闭时完成任一 Crop 操作
- **THEN** 裁切结果替换源 Image Empty，场景中不额外保留操作前的源对象

#### Scenario: User crops with Keep Original enabled
- **WHEN** 用户在 Keep Original 开启时完成任一 Crop 操作
- **THEN** 场景同时包含未改变的源 Image Empty 和本次裁切的结果 Image Empty
- **AND** 结果 Image Empty 被选中并作为 active object
- **AND** 源 Image Empty 不再保持选中

#### Scenario: User continues cropping the result
- **WHEN** 用户在 Keep Original 开启时完成一次裁切后继续操作当前 active object
- **THEN** 下一次裁切以刚创建的结果 Image Empty 作为输入
- **AND** 前一次源 Image Empty 仍保留在场景中

### Requirement: Cutout exposes the inward local axis
Cutout Tool SHALL 提供持久保存的 **Inward Axis** 选项，可选 `-Z` 与 `+X`，默认值 SHALL 为 `-Z`；该选项 SHALL 决定生成 Mesh Object 在局部坐标中从纸面指向内部的轴向。

#### Scenario: User creates a Cutout with the default axis
- **WHEN** 用户未修改 Inward Axis 并创建任一 Cutout Shape
- **THEN** 结果 Mesh 的纸面位于局部 XY 平面，向内方向为局部 `-Z`
- **AND** 结果的局部坐标轴与源 Image Empty 的局部坐标轴一致

#### Scenario: User chooses the legacy axis
- **WHEN** 用户把 Inward Axis 设为 `+X` 并创建任一 Cutout Shape
- **THEN** 结果 Mesh 的纸面位于局部 YZ 平面，向内方向为局部 `+X`
- **AND** 结果保持变更前的 Cutout 局部坐标约定

### Requirement: Cutout orientation preserves world-space output
Cutout SHALL 对 Surface、Balloon、Depth Balloon 与 Depth Surface 一致应用所选 Inward Axis，同时保持结果在源 Image Empty 图片平面上的世界空间位置、尺寸、纹理方向和纸面正反语义不变。

#### Scenario: Equivalent shapes use different local axes
- **WHEN** 用户从同一源 Image Empty 和 Selection 分别以 `-Z` 与 `+X` 创建相同 Shape
- **THEN** 两个结果的对应表面点在世界空间重合
- **AND** 两个结果只在 Mesh Object 的局部坐标与对象变换约定上不同

#### Scenario: Oriented Depth Surface uses an Object Space Normal Map
- **WHEN** 用户以任一 Inward Axis 创建启用 Normal Map 的 Depth Surface
- **THEN** Object Space Normal Map 按所选局部坐标约定着色
- **AND** 可见表面法线方向与对应几何法线一致
