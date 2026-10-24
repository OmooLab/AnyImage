## REMOVED Requirements

### Requirement: Cutout 服务端保持单区 Depth 与 Normal 产物
**Reason**: 该条包含 Blender 将 Normal 转成双区的旧契约。
**Migration**: 服务端单区推理保持既有行为，Blender 编辑阶段同样保持单区；静态转换遵循 cutout-texture-materialization。

### Requirement: Cutout Depth Metadata 描述单个 Front tile
**Reason**: Atlas Front tile 的相机坐标逆变换被删除。
**Migration**: Depth Metadata 继续描述单张图片；几何直接使用完整源 UV 采样。
