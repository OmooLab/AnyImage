## Why

参考深度现在有两条互不相干的算法：服务端按「源图 Alpha 阈值」取中位数写进 `depth.json`，Cutout 又按「选区透明比例」决定用 95 分位还是固定值 `8.0`。同一个深度场在不同目标下得到不同基准，历史补偿（`Depth Offset = 1`、固定兜底）也在互相抵消。深度纹理的 Alpha 已经同时携带源图 Alpha 与模型有效性，足以单独作为有效性判据。

## What Changes

- **BREAKING**：服务端不再计算参考深度，`depth.json` 只保留 `image_size` 与 `intrinsics`。
- 在 `common/depth.py` 提供唯一的参考深度计算：以 `depth.exr` 的 Alpha 大于 `0.95`、深度有限且为正为有效域，取相机 Z 的 95 百分位。
- 统计前丢弃距离超过中位数 `REFERENCE_DEPTH_RANGE_FACTOR`（`1.1`）倍的样本，避免远景把参考深度与整个重建尺度拖到远处；完全没有有效像素时参考深度取 `REFERENCE_DEPTH_BASELINE`（`8` 米），不报错也不提示。
- 深度方向拟合没有可用样本时返回无倾斜方向，Relief Plane 与 Depth Symmetry 的 `Direction` 一律回退为 `(0, 0, 1)`，不再报错，也不在调用点各自兜底。
- Depth Plane、Relief Plane、Depth Solid、Depth Symmetry 共用同一实现与同一统计量，不再区分「服务端基准」与「标定基准」；Cutout 把选区作为可选参考域传入，Plane 转换使用整幅深度图。
- **BREAKING**：参考深度从内容中位数改为上分位，基准平面移动到场景后端，Depth Plane 与 Relief Plane 的几何结果随之变化。
- 删除 Cutout 的透明比例闸门与固定基准兜底，并停止向服务端透传 Alpha Threshold；Alpha Threshold 只保留控制轮廓的既有职责。
- 把 Relief Plane 的 `Depth Offset` 默认值从 `1` 改为 `0`，让基准由参考深度本身决定。

## Capabilities

### New Capabilities

- `reference-depth-calibration`: 定义参考深度的唯一来源、有效性判据、统计量，以及它作为深度几何与 `Uniform Scale` 归一化基准的职责。

### Modified Capabilities

无。

## Impact

影响 `src/anyimage/server/geometry/depth_texture.py`、`geometry/prediction_artifacts.py`、`jobs/cutout.py`、`src/anyimage/common/depth.py`、Plane 转换与 Cutout 的对象创建逻辑、`tools/nodes/groups/image_relief_plane.py`、相关测试与 `src/anyimage/assets/O_AnyImage.blend`。不新增依赖、不改变 AI 推理与节点组接口；已有场景中保存的 Modifier 数值不变，但重新生成深度几何的结果会变化。
