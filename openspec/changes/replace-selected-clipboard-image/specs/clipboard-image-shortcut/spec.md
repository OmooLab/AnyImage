## MODIFIED Requirements

### Requirement: Image paste only participates in supported contexts

系统 SHALL 仅在 3D View 的 Object Mode、受支持画笔纹理模式以及受支持 Node Editor 节点树中提供图片粘贴；其他上下文 MUST 使图片粘贴 Operator 不可执行，以保留 Blender 对相同组合键的处理。受支持上下文 SHALL 优先替换符合条件的单选已有图片目标；物体或节点多选、没有适用目标时 SHALL 沿用原有创建或首次配置行为。

#### Scenario: Paste an image in Object Mode
- **WHEN** 3D View 处于 Object Mode 且用户触发图片粘贴
- **THEN** 系统 SHALL 替换唯一选中的已有 Image Empty 图片；没有适用目标或多选时允许创建 Reference Image 或 Plane

#### Scenario: Paste an image as a brush texture
- **WHEN** 3D View 处于 `SCULPT`、`PAINT_TEXTURE` 或 `PAINT_VERTEX` 且用户触发图片粘贴
- **THEN** 系统 SHALL 替换当前笔刷已有图片纹理的 Image；没有已有图片纹理时允许把图片配置为当前画笔纹理

#### Scenario: Preserve Pose paste behavior
- **WHEN** 3D View 处于 Pose Mode 且用户按下 `Shift+Ctrl/Cmd+V`
- **THEN** 图片粘贴 Operator 不可执行，AnyImage 不阻止 Blender 的镜像姿势粘贴

#### Scenario: Preserve Grease Pencil paste behavior
- **WHEN** 3D View 处于 Grease Pencil 编辑或绘制模式且用户按下 `Shift+Ctrl/Cmd+V`
- **THEN** 图片粘贴 Operator 不可执行，AnyImage 不阻止 Blender 的 Grease Pencil 粘贴

#### Scenario: Paste an image node
- **WHEN** Node Editor 使用受支持的 Shader、Compositor 或 Geometry 节点树且用户触发图片粘贴
- **THEN** 系统 SHALL 替换唯一选中且持有直接 Image 的受支持图片节点内容；没有适用目标或多选时允许创建对应图片节点

#### Scenario: Use an unsupported context
- **WHEN** 当前模式或节点树不属于图片粘贴支持范围
- **THEN** 图片粘贴 Operator 不可执行，AnyImage 不接管该快捷键
