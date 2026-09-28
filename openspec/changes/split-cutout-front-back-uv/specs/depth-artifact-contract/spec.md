## ADDED Requirements

### Requirement: Cutout 服务端保持单区 Depth 与 Normal 产物

Cutout Job SHALL 对一张正面分析输入执行一次模型推理，并按既有协议返回 `W × H` 的 Depth 与 Normal。Blender SHALL 保持 Depth 单区，并仅把 Normal 组成上方 Front、下方镜像 Rear 的 `W × 2H` 图片。

#### Scenario: 同时生成 Cutout Depth 与 Normal
- **WHEN** Cutout 请求 Depth 和 Normal
- **THEN** 模型只执行一次 `W × H` 正面推理
- **AND** 服务端返回的 `depth` 与对应 Normal 图片均为 `W × H`
- **AND** Blender 加载后的 Normal 为 `W × 2H`，Depth 仍为 `W × H`

#### Scenario: 只生成 Cutout Normal
- **WHEN** 普通 Cutout 只请求 Normal
- **THEN** 服务端返回单区 Normal，Blender 加载后采用上下双区布局
- **AND** 不生成 Depth 或 Depth Metadata

### Requirement: Cutout Depth Metadata 描述单个 Front tile

Cutout `depth.json` SHALL 保留单张正面推理的 `W × H` image_size 与 intrinsics。Blender SHALL 使用上半区和该单 tile 标定执行参考深度、方向拟合及投影，不得把 Atlas 的 `2H` 解释为相机画幅。

#### Scenario: 加载单区 Depth
- **WHEN** Blender 加载尺寸为 `W × H` 的 Cutout `depth.exr` 和相同 image_size 的 metadata
- **THEN** 加载成功并保持 `W × H` 单区图片
- **AND** Geometry Nodes 将 Front 材质 UV 还原为 0–1 后采样该 Depth

#### Scenario: 非 Cutout Depth
- **WHEN** Plane 或 Panorama 消费统一 Depth 产物
- **THEN** 图片尺寸与 metadata 的既有单区关系保持不变
