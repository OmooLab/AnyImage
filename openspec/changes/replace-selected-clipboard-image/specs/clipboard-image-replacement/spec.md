## ADDED Requirements

### Requirement: Paste resolves a single existing image target

系统 SHALL 在原有支持的粘贴上下文中优先解析已有图片目标。Object Mode MUST 恰好选中一个持有 Image 的 Image Empty；Node Editor MUST 在当前编辑树恰好选中一个持有直接 Image 的受支持图片节点；绘制模式 SHALL 使用当前活动笔刷已有图片纹理。物体和节点选择计数 MUST 包括非图片项。

#### Scenario: Select one Image Empty
- **WHEN** 用户仅选中一个持有 Image 的 Image Empty 并粘贴有效图片
- **THEN** 系统 SHALL 按实际引用关系更新该目标的图片，保持原物体

#### Scenario: Select one image node
- **WHEN** 当前编辑树仅选中一个持有直接 Image 的 `ShaderNodeTexImage`、`ShaderNodeTexEnvironment`、`CompositorNodeImage`、`GeometryNodeImageTexture` 或 `GeometryNodeInputImage`
- **THEN** 粘贴 SHALL 按实际引用关系更新该节点的图片，并保留节点、参数、位置及全部连线

#### Scenario: Geometry image input is linked
- **WHEN** 单选几何图片节点的 Image 输入已有连线，图片由上游提供
- **THEN** 粘贴 SHALL 按当前编辑器原有新建行为执行

#### Scenario: Multiple items are selected
- **WHEN** 当前物体选择或当前编辑树节点选择超过一个，包括一个图片项与一个非图片项的混合选择
- **THEN** 系统 SHALL 沿用原有新建粘贴行为，所有既有 Image 内容保持

#### Scenario: No existing image is available
- **WHEN** 没有选中适用项，或选中项尚未绑定 Image，或活动笔刷尚无图片纹理
- **THEN** 系统 SHALL 沿用当前上下文原有创建或首次配置行为

#### Scenario: An existing textured brush is active
- **WHEN** 用户在 Sculpt、Texture Paint 或 Vertex Paint 使用已绑定图片纹理的活动笔刷并粘贴有效图片
- **THEN** 系统 SHALL 按实际引用关系更新其图片，保留 Brush 与纹理设置；共享 Texture 时只为当前笔刷分离 Texture
- **AND** 系统 SHALL 以活动笔刷为唯一目标，独立于场景物体选择数量以及 AnyImage 创建标记

### Requirement: Replacement follows actual image references

替换 SHALL 复用现有图片编辑的实际引用判断。仅剩当前使用者时 SHALL 原地更新 Image，保留其 ID、名称、Fake User 和用户自定义属性；还有其他使用者时 SHALL 创建独立 Image，仅重新绑定当前目标，并保留原图内容、名称、元数据及其他引用。新 Image SHALL 使用原名称基名和 Blender 唯一后缀。Fake User 和编辑器显示引用 MUST NOT 单独触发分离。物体、节点、Brush 的身份、名称和设置 MUST 保持；笔刷输入 SHALL 沿用现有颜色归一化规则。

#### Scenario: Replace with a different image size
- **WHEN** 目标 Image 仅由当前目标使用，新图片与原图尺寸或宽高比不同
- **THEN** 原 Image SHALL 使用新尺寸与完整像素，原名称和引用保持
- **AND** Empty 显示设置、物体变换、节点参数和笔刷映射、颜色、stencil 设置 SHALL 保持

#### Scenario: The image has shared users
- **WHEN** 待替换 Image 同时被其他 Empty、节点或笔刷纹理引用
- **THEN** 当前目标 SHALL 绑定持有新内容的独立 Image，其他使用者 SHALL 保持原引用与原内容

#### Scenario: Multiple image nodes share one tree
- **WHEN** 同一节点树内多个节点通过图片属性或 Image 输入默认值引用同一 Image，用户单选其中一个并粘贴
- **THEN** 系统 SHALL 为所选节点分离 Image，保留同树其他节点的原图

#### Scenario: Only display and Fake User remain
- **WHEN** 当前目标是唯一实际图片使用者，图片同时有 Fake User 或显示在 Image Editor 中
- **THEN** 系统 SHALL 原地更新 Image 并保留名称与 ID

#### Scenario: Brushes share a texture
- **WHEN** 当前笔刷的 Texture 也被其他笔刷或遮罩纹理槽引用
- **THEN** 系统 SHALL 为当前笔刷的主纹理槽创建独立 Texture 和 Image，保持原 Texture、原图及其他引用
- **AND** 新 Texture SHALL 继承原设置，当前 Brush 的身份、名称、颜色、映射与 stencil 设置保持

#### Scenario: Refresh a Texture Paint brush
- **WHEN** Texture Paint 中原图替换成功
- **THEN** 当前笔刷预览 SHALL 更新为新内容并刷新界面
- **AND** 预览失败时 SHALL 保留新内容与可用纹理，并提示预览失败

### Requirement: Replacement retains only the committed image content

替换成功后结果 Image SHALL 持有已打包的新内容。原图 SHALL 仅因其他实际使用者继续保留，系统 MUST NOT 生成备份 Image 或备份文件。操作自有临时数据 SHALL 清理。用户原始磁盘图片 SHALL 保持；Blender 原生 Undo SHALL 沿用现有 Operator 行为。

#### Scenario: Complete a replacement
- **WHEN** 替换成功且操作结束
- **THEN** 结果 Image SHALL 持有新 packed 数据，操作自有临时 Image 和文件全部释放
- **AND** 系统 MUST NOT 创建原图备份、额外物体、节点或 Brush；Texture SHALL 仅在共享时分离

#### Scenario: Save and reopen
- **WHEN** 替换后保存并重新打开 `.blend`，剪贴板临时文件已删除
- **THEN** 当前目标 SHALL 加载新内容，其他使用者 SHALL 加载原内容，原物体、节点和笔刷引用仍有效

### Requirement: Invalid replacement leaves the target intact

替换 SHALL 在修改前验证图片输入、目标可编辑性和静态图片类型（`FILE` / `GENERATED`）。命中目标后验证或提交失败 SHALL 取消、报告原因并保持原内容和绑定；短生命周期恢复状态 SHALL 在结束时释放。

#### Scenario: Target cannot be edited
- **WHEN** 已有目标或必要容器为只读，或 Image 是序列、电影、多瓦片等不支持类型
- **THEN** 系统 SHALL 取消并提示原因，保留原数据

#### Scenario: Input or commit fails
- **WHEN** 图片解码、校验或内容提交失败
- **THEN** 系统 SHALL 保持或恢复原 Image 内容与容器状态，清理操作自有临时数据并返回取消

#### Scenario: Clipboard contains no image
- **WHEN** 触发替换时剪贴板没有可读取图片
- **THEN** Operator SHALL 返回 `PASS_THROUGH` 且保持全部原数据
