## Why

用户需要以一张图片作为持续使用的颜色参考，将其整体色调快速统一到多张目标图片，同时保持操作简单、结果确定且不改变图片结构。现有图片操作没有可复用的颜色参考状态，也不能从 Image Empty、AnyImage Mesh 或材质 Image Texture 发起这种直接编辑。

## What Changes

- 新增 `Set Color Reference`，将当前可编辑静态图片设置为持续使用的颜色参考并预先分析其颜色特征。
- 新增 `Match Color Reference`，以固定 100% 强度将当前参考的色调迁移到当前目标图片；未设置有效参考时不可执行。
- 设置参考时仅从 Alpha 可见部分提取颜色特征；匹配目标时无论是否包含 Alpha 都迁移整图 RGB，并原样保留目标 Alpha，不增加背景识别或特殊化路径。
- 迁移采用确定性的平滑颜色变换，抑制压缩噪声与新增色阶，保持目标结构、尺寸和细节。
- 在 Image Empty、可解析 Color Image 的 AnyImage Mesh 和材质 Image Texture 菜单中提供这两个操作，并沿用现有图片目标隔离、Undo、失败恢复与名称规则。

## Capabilities

### New Capabilities

- `color-reference-matching`: 定义颜色参考的设置、有效期、匹配可用性、固定强度、Alpha 语义、颜色迁移质量与结果提交行为。

### Modified Capabilities

- `object-image-actions`: AnyImage Mesh 图片菜单新增设置颜色参考与匹配颜色参考，并沿用唯一 Color 目标解析。
- `texture-node-image-actions`: 材质 Image Texture 菜单新增设置颜色参考与匹配颜色参考。
- `image-edit-results`: 颜色匹配纳入直接图片编辑的命名、共享 Image 隔离和结果替换规则。

## Impact

- Blender 侧菜单、Operator 注册、Scene 颜色参考状态与图片目标解析。
- 颜色参考分析、平滑色调迁移、Alpha 处理、色域压缩与量化抖动。
- Image Empty、AnyImage Mesh Color Image 和 Shader Image Texture 的结果提交及 Undo。
- 相关单元测试、Blender 集成测试与 Server/本地执行边界；不引入 AI 模型、背景分割或用户可调强度。
