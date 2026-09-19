## Why

Frame 当前先把 Image Empty 的四个角投影为有限凸四边形，并要求四角的视图深度全部为正。这个前置条件把正交视图错误地套入透视观察平面的限制，也会在倾斜图片靠近透视观察原点、仍有有效可见区域时取消操作。用户已经能在 Viewport 中看到的有效图片投射因此无法被重新取景。

## What Changes

- Frame 改以 Frame 像素对应的观察射线与各 Image Empty 平面求交，决定源像素坐标、有效性和几何深度，不再要求源图片四角全部位于观察平面前方。
- 正交视图接受任意有限深度的平面交点，只在图片平面与观察射线平行或投影退化时取消。
- 透视视图只采样观察方向前方的交点；Image Empty 穿过观察原点时，仍烘焙 Frame 内可稳定求交的前方部分，后方与平行射线对应区域保持透明。
- Frame 与 active Image Empty 的有效投射交叠改为按可求交区域判断，不再依赖完整凸四边形。
- 当 active 对象原点不在透视观察方向前方、但 active 图片仍有有效交叠时，结果平面使用 active 有效交叠区域的代表深度，保证结果仍位于观察方向前方并覆盖 Frame。
- 补充正交深度、极近透视、跨观察平面、平行视线、无有效交叠和结果放置测试，并同步 Frame 内部文档。

## Capabilities

### New Capabilities


### Modified Capabilities

- `frame-tool`: 放宽 Frame 的投影有效性边界，以逐射线平面求交支持正交视图和部分跨越透视观察平面的 Image Empty，并定义相应的结果深度。

## Impact

- 主要影响 `src/anyimage/operators/image_edit_tool/frame.py` 的源投影描述、有效区域判断、像素采样、深度合成和结果平面放置。
- 相关测试集中在 `tests/test_blender_addon.py`，内部说明同步到 `docs/internals/common.md` 与 Image Edit Tool 文档。
- 不改变 Frame 的工具入口、输出分辨率、Alpha 合成、Selection 输入集合、对象消费或 Undo 语义，不引入依赖，也不修改节点资产。

