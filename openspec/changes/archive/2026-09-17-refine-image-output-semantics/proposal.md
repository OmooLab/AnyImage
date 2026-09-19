## Why

Cutout 与 Plane 的材质高亮、Geometry Nodes 深度控制命名，以及 Refine Selection 的最终范围目前缺少一致语义。暗色区域仍会产生明显高亮，`Base Plane Depth` 暴露了多余的 Plane 概念，而 Refine 结果还会忽略用户圈选范围并改变提交前的 bounds。

## What Changes

- 将 `O Image Layer` 的 Color 输出连接到生成材质 Principled BSDF 的 IOR Level，使原图暗色区域同步降低高亮。
- 将所有 Geometry Nodes 接口中的 `Base Plane Depth` 统一改名为 `Reference Depth`，并同步 Modifier 初始化、节点资产验证和内部文档。
- Refine Selection 保留送入 BEN2 前的矩形尺寸与 bounds；Server 不接收 Selection Mask，也不按 BEN2 Alpha 紧裁切结果。
- Cutout 的 Color、Normal 与 Depth 统一基于 `Source Alpha × BEN2 Alpha` 的图片内容生成；Selection Mask 只在 Blender 中与该 Alpha 相乘，用于构建最终网格。
- Crop Refine 同样保留提交前 bounds，并在 Blender 中使用 `Source Alpha × BEN2 Alpha × Selection Mask` 生成最终图片结果。
- **BREAKING（内部 Job 产物协议）**：`refine-image-selection` 与 `generate-cutout-artifacts` 不再返回 Refine 后的局部 bounds 文件；调用方沿用提交前保存的 Selection bounds。

## Capabilities

### New Capabilities

- `image-result-materials`: 规定 Plane、Depth Plane 与 Cutout 生成材质的颜色驱动 IOR Level 行为。
- `geometry-depth-controls`: 规定 Depth Plane 与 Depth Cutout Geometry Nodes 的参考深度公开接口。
- `selection-content-processing`: 规定 Refine Selection 的稳定 bounds、AI 贴图内容范围，以及 Crop 图片和 Cutout 网格对 Selection Mask 的最终约束。

### Modified Capabilities

无。当前 `openspec/specs` 尚无已归档 capability；本 change 将相关行为建立为当前规格。

## Impact

- Blender 材质构建：`src/anyimage/common/material.py` 及材质测试。
- Geometry Nodes：Depth Plane、Cutout 构建与验证脚本，Modifier 输入设置，`O_AnyImage.blend` 节点资产及节点资产文档。
- Refine 数据流：Crop Tool、Cutout Tool、BEN2 Refine Job、Cutout artifact Job、结果加载与内容 Mask 组合。
- Job 结果：删除 Refine 局部 bounds 产物及对应读取逻辑。
- 测试与文档：更新与“BEN2 可保留圈外内容”和紧裁切 bounds 相反的既有断言。
- 不新增运行时依赖，不改变 SelectionPath JSON、BEN2/MoGe-2 模型或进程边界。
