## Context

当前 Scene 已通过 `AnyImageSettings.color_reference` 保存一个 `Image` 指针，但用户只能从图片上下文执行 `Set Color Reference`，侧边栏无法确认或修改该状态。相同设置入口出现在 Image Empty、AnyImage Mesh 和 Shader Image Texture 菜单中。

这次变更跨越 Property、Panel、菜单和 Operator 注册，但不改变颜色迁移与结果提交实现。实现需遵循 Blender 声明式 UI，并让 Scene 指针继续随 `.blend` 保存。

## Goals / Non-Goals

**Goals:**

- 用一个侧边栏图片选择框完成 Color Reference 的显示、选择、替换和清空。
- 在参考变化时显示五个代表性色块，让用户看到参考统计关注的颜色。
- 只向用户列出适合作为颜色参考的静态颜色图片。
- 精简所有图片右键菜单并删除失去用途的 Set Operator。
- 保持现有匹配条件、预览、Undo 和目标隔离行为。

**Non-Goals:**

- 不在 Panel 中增加 `Match Color Reference` 按钮或颜色匹配参数。
- 不改变图片生成命名、颜色匹配算法或图片结果事务。
- 不根据材质连接、图片用户数或当前选择自动推断参考。

## Decisions

### 使用 Image PointerProperty 保存状态并以缩略图 Enum 呈现

保留 `AnyImageSettings.color_reference` 作为可为空的 `PointerProperty(type=bpy.types.Image)`，并增加一个动态 Enum UI 代理。Enum 从允许的 Image 生成带预览图标的候选，并通过自定义 get/set 直接读取和更新 Image 指针；`None` 作为首个候选和默认值。

Panel 使用与 BioxelNodes Layer Library 相同的 `template_icon_view` 画廊呈现 Enum。Image 指针继续负责持久状态，Enum 不另存一份选择，从而避免两个状态失配。

### 候选过滤复用颜色参考有效性并增加名称分类

候选必须通过现有静态图片有效性检查：尺寸有效且不是 Movie、Sequence 等动画来源。另按不区分大小写的逻辑名称过滤 `_normal`、`_depth`、`_color` 结尾；判断时忽略 Blender 为重名数据块追加的 `.001` 一类数字后缀。

名称规则集中为一个可单测函数，并由动态 Enum 候选构建使用。它只控制候选列表，不扫描材质或删除任何 Image 数据。

### 新增独立 Color Match Panel

在 `VIEW_3D` 的 `UI` Region、`AnyImage` Category 注册 `ColorMatchPanel`，标题为 `Color Match`，排列在 `Job Server` 之后。Panel 绘制 Color Reference 缩略图画廊和五个只读参考色块，与 `Job Server`、`Danger Zone` 保持职责分离。

色板在 Image 指针更新时从可见像素确定性提取并保存为 Scene 的派生显示值；透明像素不参与，候选少于五类时以最后一个代表色补齐。色板只解释算法关注的参考颜色，不作为离散颜色约束。

### 删除 Set Operator 和全部菜单入口

从共享图片动作菜单删除 `SetColorReference`，仅保留 `MatchColorReference`。同时从颜色参考 Operator 注册清单中删除 Set 类型及其实现，不保留转发或隐藏入口。Image Empty、对象和节点菜单共用该菜单函数，因此一次调整覆盖三种入口。

## Risks / Trade-offs

- [用户创建的普通图片恰好以保留后缀命名，因而不会出现在候选中] → 后缀是明确的辅助图分类协议；用户可重命名图片后选择。
- [数据块重名数字后缀绕过过滤] → 先剥离末尾 `.数字` 再判断保留后缀，并覆盖测试。
- [动态 Enum 候选重建后索引变化] → Enum 的 get 每次从当前 Image 指针计算索引，set 立即将所选索引解析回 Image，Enum 本身不保存独立状态。
- [色板被误解为精确的五色迁移] → 标记为 Reference Palette，实际匹配继续使用连续像素统计。
- [已有文件保存了现在会被过滤的参考] → 当前功能仍在变更阶段，不增加迁移或兼容层；用户可在 Panel 中清空或改选。
