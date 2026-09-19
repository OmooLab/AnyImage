## Context

参考深度是深度几何的零点，同时是 `Uniform Scale` 的归一化基准：`depth_uniform_scale()` 用 `参考深度 × fx / (宽度 - 1)` 把模型相机单位换算成 Image Empty 的局部距离。同一张深度图因此只能有一个基准，否则投影尺度与位移零点会互相矛盾。

当前有两个算法。服务端 `write_depth_metadata()` 以「模型有效性 ∧ 深度有限为正 ∧ 源图 Alpha ≥ 阈值」取中位数写入 `depth.json`；Cutout 的 `metric_depth_reference()` 以「选区 ∩ 源图 Alpha ≥ 阈值」取 95 百分位，并在选区透明像素不足 5% 时改用固定值 `8.0`。Depth Plane 与 Relief Plane 用前者，Depth Solid 与 Depth Symmetry 用后者，Relief Plane 又用 `Depth Offset = 1` 把中位数基准向后补偿。

`depth.exr` 的 Alpha 是「源图 Alpha × 模型有效性」，随深度纹理一起被 Blender 读入，`camera_depth_values()` 已经在读它的 Alpha 与相机 Z，服务端那次计算没有额外信息可用。

## Goals / Non-Goals

**Goals:**

- 参考深度只有一处实现、一条有效性判据、一个统计量。
- 服务端只提供相机内参和图像尺寸，不再判断参考区域。
- 删除 Cutout 的透明比例闸门与固定基准兜底。
- 让 Relief Plane 的基准平面由参考深度决定，而不是由 `Depth Offset` 的默认值补偿。

**Non-Goals:**

- 不改变 AI 推理、深度纹理协议、节点组接口与 Depth Symmetry 的方向拟合行为。
- 不为旧 `depth.json` 字段保留兼容读取或转发函数。
- 不把参考深度暴露成新的用户参数。

## Decisions

### 参考深度在 Blender 侧由深度纹理计算

`common/depth.py` 新增 `reference_depth(image, mask=None)`，读取 `camera_depth_values()` 的相机 Z 与 Alpha，在 `Alpha > 0.5 且深度有限且为正` 的像素上取 95 百分位，返回模型单位。调用方再乘 `Uniform Scale`。服务端删除参考深度写入，`depth.json` 只保留 `image_size` 与 `intrinsics`。

服务端没有选区信息，也无法在加载时知道几何目标的意图；把判据放在读取深度纹理的一侧，才能让「有效性」只有 Alpha 一个来源。备选是保留服务端字段作为默认值，但这会让同一张深度图继续存在两个基准。

### 有效性只由 Alpha 与深度值决定

Alpha 已经包含源图 Alpha 与模型有效性两个条件，因此不再需要 `alpha_threshold` 参与参考深度，也不再需要 `validity` 与 Alpha 双重过滤。有效性阈值取 `0.95`：模型的有效性信号接近二值，抬高阈值主要排除源图 Alpha 的半透明边缘，让参考深度只统计完全不透明且模型判定有效的像素。代价是毛发、玻璃等本身就半透明的主体可能没有可用像素，此时几何创建明确失败而不是回退到固定基准。非有限与非正深度仍被排除，因为它们无法参与深度换算。

### 统计量统一为 95 百分位

基准平面取有效深度的上分位，主体整体落在基准之前：Depth Solid、Depth Symmetry 与 Relief Plane 的位移与厚度归一化因此都从「内容后端」起算，Depth Plane 与 Relief Plane 不再需要靠 `Depth Offset` 人工后移。作为 `Uniform Scale` 的锚点，这个取值同时决定近处内容相对源图轮廓的缩进量，属于可见的行为变化，由几何测试与人工检查确认。

备选是统一取中位数：实现同样简单，但 Depth Solid 与 Depth Symmetry 会有一半内容被钳制在深度零点，厚度归一化也随之改变。

### 参考深度丢弃超出中位数倍数的样本

参考深度同时是 `Uniform Scale` 的锚点，`Uniform Scale` 与参考深度成反比，所以远景会把整个重建结果缩小并整体推向基准之前。风景图没有主体，中位数与上分位都落在远景上，这个效应最明显。因此统计前丢弃距离超过 `REFERENCE_DEPTH_RANGE_FACTOR`（`1.1`）倍中位数的样本，让基准由主要内容的距离决定；被丢弃的内容仍保留在深度纹理里，只影响几何投影，不影响标定。

上限取中位数的倍数而不是固定米数，因为固定米数假设「主要内容在多少米以内」，一旦主体整体在固定上限之外，基准会落到主体之前，`reference − depth` 全为负而被钳制，几何直接消失。倍数上限随内容尺度变化：中位数永远落在上限之内，所以只要存在有效像素，统计集合一定非空，也不会因为题材远近而失效。代价是风景图的上限随内容放大，远景被推后的力度比固定小上限时轻。

### 参考域可选，Cutout 传入选区

`reference_depth(image, mask=None)` 的 `mask` 由目标自己决定：Cutout 传入当前选区，Plane 转换不传。选区只是参考深度的作用域，不再参与透明度比例判断。

全幅照片没有透明区域时，若忽略选区，参考深度会落在背景深度上，投影归一化会让被套索的主体缩小并与源图轮廓错开。备选是完全按整幅深度图计算，但会破坏套索全幅照片这一既有用法。

### 计算函数返回模型单位

`depth_uniform_scale()` 需要未缩放的参考深度才能求出 `uniform_scale`，因此 `reference_depth()` 返回模型单位，由调用方乘以尺度后写入 Modifier。

### Relief Plane 的 Depth Offset 默认值改为 0

基准平面已由 95 百分位放到内容后端，`Depth Offset` 恢复为纯粹的微调参数。默认值属于节点组接口，修改构建脚本后重新生成 `O_AnyImage.blend`。

### 删除 Cutout 标定模块

`depth_calibration.py` 的参考深度计算与透明比例闸门被 `reference_depth()` 取代；其中的基础形状 UV 采样与平面方向拟合下沉到 `common/depth.py` 的 `fit_symmetry_depth_direction()`，与 `fit_depth_direction()` 同处。`geometry.py` 的 `selection_calibration()` 只服务于旧标定，随之删除。

### 方向拟合沿用同一条选择规则

`fit_depth_direction()` 在没有可用样本时返回无倾斜的规范方向 `(0, 1, 0)`，而不是报错；Relief Plane 与 Depth Symmetry 因此都得到 `(0, 0, 1)` 的 `Direction`。兜底放在拟合函数里而不是调用点，是因为「有效像素选不出来」对参考深度和方向是同一个问题，放在一处可以删掉 Plane 转换里原有的 `try/except`，也让两个深度目标行为一致。

## Risks / Trade-offs

- [Depth Plane 与 Relief Plane 的基准从内容中位数移到上分位，几何尺度变化明显] → 这是本次明确要求的行为变化，用几何测试锁定 `Reference Depth` 与投影结果，不增加兼容分支。
- [套索选区在源图全不透明时决定参考深度] → 保留可选 `mask` 参数，让 Cutout 继续以选区为参考域。
- [节点组默认值与发布资产不一致] → 修改构建脚本后运行 `uv run node-group build`。
- [已有场景保存的 Modifier 仍带旧 `Reference Depth` 与 `Depth Offset`] → 已保存数值按原样保留，只有重新生成深度几何时才使用新基准。
