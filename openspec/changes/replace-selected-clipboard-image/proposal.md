## Why

已有 Image Empty、图片节点或贴图笔刷需要换图时，当前粘贴会创建新对象、节点或纹理，增加重新绑定和清理的工作。让单选目标直接接收剪贴板图片，可保留现有场景结构和名称。

## What Changes

- `Ctrl+Shift+V`（macOS 为 `Cmd+Shift+V`）优先替换当前单选 Image Empty、图片节点或当前已配置图片纹理的笔刷。
- 沿用图片编辑的引用原则：最后一个实际使用者原地更新 Image 并保留名称；仍有其他使用者时新建 Image，只更新当前目标，保留其他使用者的原图。
- 保留物体、节点、Brush 和现有设置；笔刷共用 Texture 时为当前笔刷分离 Texture。
- 清理操作自有临时数据，不生成备份；仍被其他使用者引用的原图继续保留。
- 物体或节点多选、无适用目标时沿用原有新建粘贴；笔刷按当前活动笔刷判断。
- Texture Paint 替换后刷新笔刷预览，保留现有预览失败提示行为。

## Capabilities

### New Capabilities

- `clipboard-image-replacement`: 单选目标解析、按实际引用替换图片、数据生命周期和容器状态保留。

### Modified Capabilities

- `clipboard-image-shortcut`: 受支持上下文中的粘贴优先替换单选目标，其余沿用创建行为。
- `clipboard-image-cache`: 按引用规则处理独占或共享目标、输入缓存与目标重合及结果缓存标记。

## Impact

- `operators/clipboard_image/actions.py` 与 `operators.py`：目标解析、替换分支、重做面板和结果提示。
- 复用 `common/image.py` 的内容读写与刷新机制，以及现有笔刷颜色处理、预览更新逻辑。
- 更新剪贴板行为、缓存、笔刷预览及必要的 Blender 集成测试，检查既有 Operator 注册关系。
- 与进行中的 `normalize-uncompensated-image-colors` 共用笔刷颜色与缓存路径，实现时保留其有效修改。
