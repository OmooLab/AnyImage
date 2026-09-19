## Why

`O Image Relief Plane` 当前允许远于参考深度的采样把浮雕面压到 `Thickness` 高度以下，只在接近固定底面时停止，导致基础厚度同时承担浮雕零点和防穿透边界，深度整体位置也无法独立调节。需要明确浮雕深度零点，使缩放、钳制与整体偏移各自表达单一职责。

## What Changes

- 将 `Thickness` 所在高度定义为浮雕 depth 0，并把采样深度产生的向内位移钳制在该高度，不再让深度结果进入基础厚度区域。
- 为 `O Image Relief Plane` 新增默认值为 `1` 的公开 `Depth Offset` 距离参数，作为 `Reference Depth` 的附加矫正，在方向换算和 `Depth Scale` 之前参与相对深度计算。
- 将 `Depth Direction` 和 `Depth Offset` 移到主界面，并在 `Thickness` 后按 `Depth Direction`、`Depth Offset`、`Depth Scale` 排列。
- 创建 Relief Plane 时从完整深度图拟合近似深度平面，并用其法向初始化 `Depth Direction`。
- `Depth Scale` 以 `Thickness` 所在的 depth 0 为位移基准，并缩放包含 `Depth Offset` 矫正的相对深度；`Thickness` 高度本身不参与缩放。
- 更新节点组行为测试、接口清单与发布 `.blend` 节点资产。

## Capabilities

### New Capabilities

- `relief-plane-depth-controls`: 定义 Relief Plane 的 depth 0、钳制、缩放和整体偏移行为。

### Modified Capabilities

无。

## Impact

影响 `tools/nodes/groups/image_relief_plane.py`、`src/anyimage/common/depth.py`、Plane 创建逻辑、相关测试、节点资产接口清单，以及 `src/anyimage/assets/O_AnyImage.blend`。不增加依赖，也不改变 AI 深度产物；已有 Modifier 会获得新的节点组输入，原先依赖负向深度进入基础厚度区域的结果将发生变化。
