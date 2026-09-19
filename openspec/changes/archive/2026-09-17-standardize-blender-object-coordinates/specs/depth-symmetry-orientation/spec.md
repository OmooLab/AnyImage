## ADDED Requirements

### Requirement: Depth Symmetry mirrors across the canonical Y axis

`O Image Cutout Symmetry` SHALL 在 canonical Blender 对象坐标中沿 Y 轴镜像，即镜像面为 `Y=0` 的 XZ 平面。镜像前后的几何 MUST 在最终旋转前保持 `(x, y, z)` 与 `(x, -y, z)` 的对应关系。

#### Scenario: Canonical mirroring

- **WHEN** 上游 Depth Cutout 输出 canonical 几何并连接 `O Image Cutout Symmetry`
- **THEN** 对称节点先按 Y 轴删除越界半侧并镜像到另一侧
- **AND** Fill Sides 开启时沿 Y 方向连接对应边界

### Requirement: Final symmetry axis is X with Z up

`O Image Cutout Symmetry` SHALL 在 canonical Y 镜像完成后执行绕 Z 的固定旋转，使对称轴从 +Y 变为 +X，并保持 +Z 为 up。最终结果 MUST 在本地坐标中关于 `X=0` 对称。

#### Scenario: Default Depth Symmetry result

- **WHEN** 用户通过 Depth Symmetry 入口生成对象
- **THEN** 最终 evaluated local geometry 关于 `X=0` 对称
- **AND** 最终 Z 范围反映图片 up 范围
- **AND** 对象保持 up=Z

### Requirement: Depth Symmetry final front direction may change

Depth Symmetry 的最终朝向 SHALL 允许 canonical front `-Y` 随最终 yaw 旋转变为 `-X`。系统 MUST 不要求 Depth Symmetry 最终继续满足 front=-Y。

#### Scenario: Final front direction

- **WHEN** 使用把 +Y 映射到 +X 的最终 yaw 旋转
- **THEN** canonical front 方向 -Y 映射为 -X
- **AND** up 方向 +Z 保持不变

### Requirement: Depth Symmetry path has no Cutout Depth Axis

Depth Symmetry 创建流程 SHALL 不设置或依赖 `O Image Depth Cutout` 的 `Depth Axis`。所有最终轴向语义 MUST 只由 `O Image Cutout Symmetry` 承担。

#### Scenario: Create Depth Symmetry modifiers

- **WHEN** 用户通过 Depth Symmetry 入口创建对象
- **THEN** 上游 `O Image Depth Cutout` 不包含 `Depth Axis` 输入
- **AND** 上游 Cutout 输出 canonical +Y 深度结果
- **AND** `O Image Cutout Symmetry` 决定最终 X 朝向
