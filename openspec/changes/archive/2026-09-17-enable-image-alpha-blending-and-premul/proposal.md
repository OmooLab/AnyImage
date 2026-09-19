## Why

用户已验证 Empty 开启 Alpha Blending 能改善渐变显示，并确认希望 AnyImage 处理后的图片及 Mesh Color 图片默认使用 Premultiplied。目前本地编辑、Job 结果与材质图片采用不同 Alpha 模式，需要统一这些交付入口并验证重复编辑和保存行为。

Frame 当前按像素中心判断图片投射覆盖，倾斜边缘存在阶梯；需要在 RGB 和 Alpha 中共同保留子像素覆盖信息，使 Mask Add 恢复后的图层边界也能平滑过渡。

## What Changes

- AnyImage 新建或成功替换图片的 Image Empty 默认开启 `use_empty_image_alpha`，保留原有对象不透明度和深度设置。
- Mask、Frame、Rectify 及 Remove Background 等公共图片编辑结果默认设置 `Image.alpha_mode = 'PREMUL'`。
- Plane、Depth Plane 和 Cutout 的 Color 图片默认使用 `PREMUL`；共享普通 Color 结果加载入口的图片采用同一约定。
- 将用户要求落实为 Blender Alpha 解释模式策略，保留既有 RGB/Alpha 像素编辑算法与透明 RGB；不额外永久执行 RGB 乘 Alpha。
- 验证 Mask Add、重复 Frame、实际 Packed Image、保存重载及 Mesh 材质采样，避免模式切换改变可恢复的颜色数据。
- Frame 几何边界采用 4×4 子像素覆盖采样，逐样本完成深度与图层合成，再汇总 RGB/Alpha；内部区域保留现有中心采样，输出尺寸不变。

## Capabilities

### New Capabilities

- `image-alpha-presentation`: AnyImage 图片与 Image Empty 的 Alpha 展示默认值、Color 材质图片策略及数据保留约束。
- `frame-edge-antialiasing`: Frame 投射轮廓与图层边界抗锯齿，包含恢复 Alpha 后的 RGB 过渡和源外颜色保护。

### Modified Capabilities

无。

## Impact

- `src/anyimage/common/image.py`：公共图片创建、加载、替换入口和像素保留验证。
- `src/anyimage/operators/image_edit_tool/frame.py`：边界子像素覆盖、逐样本排序合成及分块汇总。
- `src/anyimage/common/material.py`：Mesh Color 图片进入材质时的统一 Alpha 模式。
- `src/anyimage/operators/clipboard_image/actions.py`：新建 Image Empty 的 Alpha Blending。
- `src/anyimage/operators/convert_to_plane/object.py`、`src/anyimage/operators/cutout_tool/object.py`：复制或裁剪创建的 Color 图片。
- 相应 Blender 单元与集成测试。沿用现有依赖、节点资产和编辑算法；实施阶段不同步修改产品文档，不构建产物。
