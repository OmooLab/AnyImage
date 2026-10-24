## Why

Cutout 的正片和生成后片目前共享同一块 UV，无法在保持单一材质的同时分别编辑正背纹理。Cutout 各厚度模式本来都会从一张输入正片生成后片，因此可以建立统一的上下双区贴图协议，而不增加材质或形态分支。

## What Changes

- Cutout 专用颜色图固定为上下双区：正片位于上半区，下半区为左右镜像的后片。
- Cutout 的可选法线图采用相同布局；Tangent Normal 的后片额外反转 X 分量。Depth 保持单张正面图片。
- Cutout 基础网格 UV 初始化到上半区；厚度路径将 Rear 移到下半区。后置对称完整保留输入已有的 Front/Rear UV，仅镜像几何。
- 零厚度单片继续只使用上半区；Front 叶片挤出的 Side 使用上半区，Rear 叶片挤出的 Side 使用下半区，两侧在共同中圈形成 UV seam，不在正背区域之间渐变。
- Depth Cutout 的相机标定、参考深度、Split 与其他几何计算继续直接使用单张正片 Depth。
- 不新增材质、材质参数、节点组公开输入或兼容路径。

## Capabilities

### New Capabilities

- `cutout-double-sided-textures`: 定义 Cutout 上下双区图片布局、正背面 UV 分配、侧壁映射及零厚度行为。

### Modified Capabilities

- `material-color-images`: Cutout 的独立颜色图从单张裁切内容改为上下重复的双区材质图，其他材质入口保持原行为。
- `depth-artifact-contract`: Cutout 的 Depth 与 Normal 服务端结果保持单区，Blender 仅为 Normal 建立上下双区材质图，并保留单张正片的推理和标定语义。
- `cutout-shape-presets`: 普通与深度 Cutout 的 Balloon、Shell 和零厚度输出采用统一的正片上区、后片下区 UV 规则。

## Impact

- 影响 Cutout 颜色图准备、AI 结果写出或加载、深度元数据消费、基础网格 UV 初始化，以及 `O Image Cutout`、`O Image Depth Cutout` 与后置对称的正背面和分侧 Side UV 构建。
- 需要更新颜色、法线、深度图片尺寸与像素测试，验证 Boundary Padding 在 Atlas 之前执行，并覆盖 Flat、Solid、Depth Solid、Depth Symmetry 的 Balloon、Shell、零厚度和正厚度结果。
- 节点组逻辑变化后需要重建并验证 `O_AnyImage.blend`；不新增依赖，也不改变非 Cutout 的 Plane、Panorama 或 Clipboard 图片协议。
