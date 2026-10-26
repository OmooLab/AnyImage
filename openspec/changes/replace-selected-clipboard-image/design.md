## Context

`PasteClipboardImage` 读取剪贴板并获取打包 Image，再按编辑器创建 Empty、Plane、节点或配置笔刷。`common/image.py` 已有 `image_content_state()`、`restore_image_content()`，可保留目标 Image ID 更新内容并通知预览缓存。

本功能沿用现有图片编辑的引用原则，复用 `common/image_target.py` 的实际引用判断。Fake User 和编辑器显示引用不构成其他使用者。

## Goals

单选已有图片载体时替换其图片，独占 Image 原地覆盖，共享 Image 分离给当前目标。保留载体、连接和设置，多选按原有粘贴行为处理。

## Decisions

### 1. 按当前编辑器解析唯一目标

| 上下文 | 替换条件 | 保留内容 |
| --- | --- | --- |
| Object Mode | `selected_objects` 恰好一个，且为持有 Image 的 Image Empty | 物体身份、名称、变换、显示设置 |
| Node Editor | 当前编辑树恰好一个节点被选中，且是受支持的图片节点并持有直接 Image | 节点身份、名称、位置、连线、参数 |
| Sculpt / Texture Paint / Vertex Paint | 当前活动笔刷具有 Image 类型 Texture，且已绑定 Image | Brush 身份与名称，纹理槽设置、颜色、映射及 stencil 设置 |

节点范围包括 `ShaderNodeTexImage`、`ShaderNodeTexEnvironment`、`CompositorNodeImage`、`GeometryNodeImageTexture` 和 `GeometryNodeInputImage`。几何节点的 Image 输入仅在未连接且持有默认 Image 时命中；已连接输入按原有新建路径处理。以当前编辑树的全部选中节点计数，不能先过滤图片节点再计数。

绘制模式的目标是当前活动笔刷，场景物体选择数量不代表笔刷多选。已有贴图笔刷包含用户自行创建的笔刷，不依赖 AnyImage 标记。无已有图片时沿用首次粘贴配置行为。

命中目标后检查目标及必要容器可编辑、Image 为静态 `FILE` 或 `GENERATED`；不符合时取消并提示。替换分支保持本地数据身份，因此只读库目标不能通过复制笔刷绕过检查。

### 2. 按实际引用提交已准备好的新内容

在主线程先解析目标，再解码、校验剪贴板内容。复用 `has_other_image_user()` 判断 Empty、图片节点及 Texture 的实际引用，补全几何节点 Image 输入与同树多个引用的识别。独占时写入原 Image；共享时复制 Image 并写入新内容，只重新绑定当前目标。新图沿用原名称基名，由 Blender 分配唯一后缀。

笔刷 Texture 若被其他使用者或当前笔刷的遮罩纹理槽引用，同时复制 Texture，保留其参数并只绑定当前笔刷的主纹理槽。独占 Texture 保留身份。Image 写入与预览刷新复用 `common/image.py`；笔刷内容沿用现有归一化规则。

独占 Image 名称、ID、Fake User 和用户自定义属性保持；共享原图及其元数据保持。新图继承自定义属性且关闭 Fake User。仅清除结果图的旧剪贴板缓存标记，颜色归一化标记按新内容更新。结果使用新内容的内嵌数据和路径状态，不覆盖或删除用户原始磁盘图片。

提交成功后清理操作自有临时 Image、归一化结果和临时文件。原图仅因其他实际使用者继续保留，不创建备份。失败时恢复原内容或绑定，释放新建 Image 与 Texture；保留 Operator 既有 Blender Undo 行为。

### 3. 区分输入缓存与替换目标

`acquire_packed_image()` 返回的缓存 Image 只是输入。独占目标保留 Image ID，共享目标获得独立 Image。缓存输入与原图相同时仍按实际引用决定覆盖或分离；借用缓存保持只读。仅清除结果图上的剪贴板哈希与内容基线，共享原图的缓存状态保持。

这样可以同时保留显式替换的身份语义和已有缓存的复用行为。实现时与 `normalize-uncompensated-image-colors` 的缓存规范合并，保持笔刷归一化仅执行一次。

### 4. 替换只更新内容与预览

替换分支按引用关系提交 Image，保持选择、位置、笔刷颜色及 stencil 尺寸。Texture 仅在共享时分离，新图片比例由现有容器按自身设置显示。

Texture Paint 成功提交后复用现有笔刷预览更新和界面刷新逻辑；预览失败提示警告，已提交内容保持可用。其他绘制模式保持既有预览规则。

Operator 在本次执行中明确区分创建和替换，替换的重做面板不展示 `Import As` / `Shadeless`，结果提示使用原 Image 名称。核查注册、逆序注销和快捷键测试。

## Risks / Trade-offs

- 同树多个图片引用或多个笔刷共用 Texture → 验证当前目标分离、其他引用及原图内容保持，后续独占替换保持新图身份。
- 解码、打包或写入失败可能留下半成品 → 先准备新内容，提交失败恢复原内容并清理自有临时数据；命中目标后的失败直接取消。
- 输入缓存与目标重合、颜色归一化可能误改其他 Image → 显式区分输入所有权，对同一 ID、共享缓存和不同尺寸分别验证。
- 图片格式和颜色空间写入涉及 Blender 实际解码 → 以真实 Blender 集成测试验证像素、尺寸、打包数据与保存后重开结果。
