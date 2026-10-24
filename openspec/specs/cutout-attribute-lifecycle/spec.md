# cutout-attribute-lifecycle Specification

## Purpose
TBD - created by archiving change optimize-cutout-geometry-nodes. Update Purpose after archive.
## Requirements

### Requirement: Internal Cutout attributes use the `_o_` prefix

Attributes that exist only inside the Cutout geometry node lifecycle and are removed before output SHALL use the `_o_` prefix. The system SHALL NOT use the previous `.o_anyimage_*` prefix for new internal attributes.

#### Scenario: Split marker is stored as an internal attribute

- **WHEN** Depth Cutout or another depth surface stores the split marker during edge separation
- **THEN** the stored name starts with `_o_` and is removed before the node group output

#### Scenario: Old internal marker names are not emitted

- **WHEN** a Cutout node group is evaluated
- **THEN** no `.o_anyimage_depth_cut` or `.o_anyimage_original_boundary` attribute remains on the output geometry

### Requirement: Public Cutout attributes keep the `o_` prefix

可编辑 Cutout 的形状、法线、材质和转换来源协议属性 SHALL 使用 `o_` 前缀，并保留到真实消费者执行完成。专用 Convert to Mesh SHALL 在完成静态纹理与法线生成后清除全部 AnyImage 形状、法线、来源与中间协议属性。

#### Scenario: Public shape and normal attributes survive cleanup
- **WHEN** 可编辑 Cutout 或 Depth Cutout 节点输出几何
- **THEN** `o_balloon`、`o_normal_reduction` 和 `o_depth_*` 按现有实时消费者契约保留
- **AND** FACE/INT `o_image_region` 在 Front/Rear、Side 及 symmetry 分支中保持可供转换使用的来源身份

#### Scenario: UVMap and user attributes survive cleanup
- **WHEN** 输入几何含 UVMap 和用户自有属性
- **THEN** 节点内部清理及静态转换保留必要 UV 和用户数据，不按宽泛前缀误删

#### Scenario: Static conversion removes all consumed protocol data
- **WHEN** Convert to Mesh 成功提交静态结果
- **THEN** 结果不含 `o_balloon`、`o_normal_reduction`、`o_depth_rotation`、`o_depth_face`、`o_depth_axis`、`o_image_region` 或 AnyImage 中间属性
- **AND** 已消费的临时 UV、烘焙标记与程序化对象/Mesh 元数据被清除
- **AND** 最终 UV、网格必要数据、用户属性及图片操作能力标记 `o_image_object` 保留，结果着色不再依赖被删除的数据

### Requirement: Internal attributes are removed by a single wildcard operation

Each depth surface group SHALL remove its `_o_*` internal attributes with one `Remove Named Attribute` node using wildcard mode before output. It SHALL NOT remove internal attributes one by one.

#### Scenario: Wildcard cleanup removes all internal attributes

- **WHEN** a depth surface group evaluates with Split or Thickness enabled
- **THEN** every `_o_*` attribute is absent from the output geometry

#### Scenario: Wildcard cleanup is safe when no internal attribute exists

- **WHEN** a depth surface group evaluates with the corresponding internal path disabled
- **THEN** the wildcard removal produces no missing-attribute warning and leaves public attributes unchanged
