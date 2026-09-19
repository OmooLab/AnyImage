## Why

Texture Paint 模式粘贴图片后，笔刷已使用该图片作为纹理，但图标仍显示原有预览，难以直接识别绘制内容。将笔刷图标同步为粘贴图片，让选择笔刷时的视觉提示与实际纹理一致。

## What Changes

- Texture Paint 模式绑定粘贴图片后，同步更新当前可编辑笔刷的自定义预览。
- 预览保持图片比例，支持已打包的剪贴板图片及重复粘贴更新。
- 验证预览即时刷新，以及保存并重新打开文件后的保留效果。

## Capabilities

### New Capabilities

- `pasted-brush-preview`: Texture Paint 粘贴图片与笔刷预览同步。

### Modified Capabilities

## Impact

- `src/anyimage/operators/clipboard_image/actions.py`：笔刷纹理绑定与预览更新。
- `src/anyimage/common/image.py`：复用现有图片读取或导出能力。
- `tests/anyimage/operators/test_clipboard_image.py`：增加预览行为覆盖。
- 使用 Blender 自定义预览 API，沿用现有依赖。
