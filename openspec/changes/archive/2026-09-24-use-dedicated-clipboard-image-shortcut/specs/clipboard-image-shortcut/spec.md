## ADDED Requirements

### Requirement: Clipboard image paste uses a dedicated shortcut

系统 MUST 在 3D View 与 Node Editor 中以 `Shift+Ctrl+V` 触发 Windows/Linux 图片粘贴，并以 `Shift+Cmd+V` 触发 macOS 图片粘贴。AnyImage MUST NOT 为该功能绑定 `Ctrl/Cmd+C` 或不带 Shift 的 `Ctrl/Cmd+V`。

#### Scenario: Invoke image paste on Windows or Linux
- **WHEN** 用户在受支持上下文按下 `Shift+Ctrl+V`
- **THEN** 系统调用图片粘贴 Operator

#### Scenario: Invoke image paste on macOS
- **WHEN** 用户在受支持上下文按下 `Shift+Cmd+V`
- **THEN** 系统调用图片粘贴 Operator

#### Scenario: Use native Blender copy and paste
- **WHEN** 用户按下 `Ctrl/Cmd+C` 或 `Ctrl/Cmd+V`
- **THEN** AnyImage MUST NOT 处理该按键，Blender 原生复制粘贴保持可用

### Requirement: Image paste only participates in supported contexts

系统 SHALL 仅在 3D View 的 Object Mode、受支持画笔纹理模式以及受支持 Node Editor 节点树中提供图片粘贴；其他上下文 MUST 使图片粘贴 Operator 不可执行，以保留 Blender 对相同组合键的处理。

#### Scenario: Paste an image in Object Mode
- **WHEN** 3D View 处于 Object Mode 且用户触发图片粘贴
- **THEN** 系统允许创建 Reference Image 或 Plane

#### Scenario: Paste an image as a brush texture
- **WHEN** 3D View 处于 `SCULPT`、`PAINT_TEXTURE` 或 `PAINT_VERTEX` 且用户触发图片粘贴
- **THEN** 系统允许把图片配置为当前画笔纹理

#### Scenario: Preserve Pose paste behavior
- **WHEN** 3D View 处于 Pose Mode 且用户按下 `Shift+Ctrl/Cmd+V`
- **THEN** 图片粘贴 Operator 不可执行，AnyImage 不阻止 Blender 的镜像姿势粘贴

#### Scenario: Preserve Grease Pencil paste behavior
- **WHEN** 3D View 处于 Grease Pencil 编辑或绘制模式且用户按下 `Shift+Ctrl/Cmd+V`
- **THEN** 图片粘贴 Operator 不可执行，AnyImage 不阻止 Blender 的 Grease Pencil 粘贴

#### Scenario: Paste an image node
- **WHEN** Node Editor 使用受支持的 Shader、Compositor 或 Geometry 节点树且用户触发图片粘贴
- **THEN** 系统允许创建对应的图片节点

#### Scenario: Use an unsupported context
- **WHEN** 当前模式或节点树不属于图片粘贴支持范围
- **THEN** 图片粘贴 Operator 不可执行，AnyImage 不接管该快捷键

### Requirement: Image paste does not track native copy state

系统 MUST 根据独立图片粘贴快捷键直接尝试读取系统剪贴板，并 MUST NOT 注册原生复制跟踪 Operator、保存原生复制 token 或依赖平台剪贴板变更序列决定粘贴类型。

#### Scenario: Paste across Blender instances
- **WHEN** 用户在一个 Blender 实例复制对象或节点，并在另一个实例按下原生 `Ctrl/Cmd+V`
- **THEN** AnyImage 不参与复制状态判断或粘贴处理

#### Scenario: Dedicated shortcut has no image
- **WHEN** 用户触发图片粘贴但系统剪贴板没有可读取图片
- **THEN** 图片粘贴 Operator 返回 `PASS_THROUGH` 且不创建 Blender 数据
