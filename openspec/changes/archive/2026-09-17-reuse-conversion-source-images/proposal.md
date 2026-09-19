## Why

Convert To 当前复制或重新加载颜色贴图，产生额外的 `_color` Image 和后端颜色文件。统一采用图片编辑工具的共享 Empty 判断，可以直接复用原图，并保留材质所需的颜色空间与 Alpha 配置。

## What Changes

- Plane、Depth Plane、Relief Plane、Panorama 在没有其他 Image Empty 引用原图时直接复用原 Image；存在其他 Empty 引用时复制 Image 数据块。
- 原图保留名称和路径；副本沿用原名并使用 Blender 自动消歧命名。材质颜色直接取自原图。
- 由转换入口决定 Image 所有权，再应用现有颜色空间、Alpha 和 Panorama HDR 保留规则。
- 共享判断仅考虑其他 Image Empty；已有材质引用同一原图时同步看到配置变化。
- 清理 Depth / Relief 和 Panorama 的冗余后端颜色输出与对应加载路径，补充失败恢复和像素保留验证。

## Capabilities

### New Capabilities

- `conversion-source-images`: 四种 Convert To 的原图复用、共享隔离、材质配置与结果生命周期。

### Modified Capabilities

## Impact

涉及 `common/image.py`、`common/material.py`、两个转换 Operator 包、Server 的 depth_plane / panorama Job、颜色文件辅助函数及相关测试。复用现有依赖和节点资产。

当前 `openspec/specs` 尚无已归档规格。本变更明确细化 `configure-material-view-adaptation` 中转换入口的共享策略：其他材质用户可以共享配置变化，其他 Image Empty 必须隔离；实施时应协调相关测试预期。
