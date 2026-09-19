## Why

Mask、Rectify 与 Cutout 当前把空白点击交给带 `deselect_all` 的 Blender 原生选择，导致透明像素或 Viewport 空白会清除 active Image Empty，后续手势只能从可拾取的可见像素开始。图片操作的起始坐标不应同时承担维持源对象选择的职责。

## What Changes

- 保留 Blender 原生对象拾取：命中另一对象时正常切换 active，本次不启动图片操作。
- Mask、Rectify 与 Cutout 在没有命中对象时保留当前 active Image Empty，使手势可从透明区域或 Viewport 空白开始。
- 继续由各工具在提交阶段判断手势是否与图片画布或可见内容有效相交。
- Frame 保持现有空白点击取消选择的行为；不建立只允许 Image Empty 的自定义 Picker，也不自动撤销非 Image Empty 的原生选择结果。

## Capabilities

### New Capabilities

- `image-tool-interaction`: 定义图片工具的原生对象选择、空白起始和源对象有效性规则。

### Modified Capabilities


## Impact

- 修改 `common/viewport.py` 中图片工具点击解析与 selection keymap 的空白点击策略。
- 调整 Mask、Rectify、Cutout 的交互测试与 Image Edit、Cutout、Common 内部文档。
- 不改变图片、SelectionMask、Cutout Shape、Job 协议、依赖或 Blender 数据结构。
