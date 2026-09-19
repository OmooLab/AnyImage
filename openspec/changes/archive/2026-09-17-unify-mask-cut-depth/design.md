## Context

`common/depth_surface.py` 的 `build_surface_camera` 负责把「点的相机采样」换成「面的相机采样」：保持点自身的射线方向，只沿射线把深度缩放到相邻面的采样值（`projected = original × separated.z / original.z`）。`separated` 是 FACE 域的采样，消费到 POINT 域时按该点的保留相邻面取平均。

三个调用点的接入方式不一致：

| 组 | 切口来源 | 面深覆盖范围 |
| --- | --- | --- |
| `O Image Depth Cutout` | `Depth Split` 切边、网格轮廓 | `cut_vertex` + `always_vertex=outline`（全部自由边界点） |
| `O Image Depth Plane` | `Depth Mask` 删点、`Depth Split` 切边 | 仅 `cut_vertex` |
| `O Image Depth Panorama` | `Depth Mask` 删点、`Depth Split` 切边 | 仅 `cut_vertex` |

Plane 的矩形网格另有一条始终存在的自由边界：原画幅外框（UV 边距 0）。它以 `original_boundary` 的形式被 `smooth_boundary_camera` 与 `smooth_cut_boundary` 的 `protected` 参数排除在平滑之外。Panorama 的球面是闭合流形，Depth Mask 打开时唯一的自由边界就是删除产生的切口。

`Depth Mask` 删点后，切口点的深度仍取该点自身的纹理采样。Plane 的深度纹理使用 Linear + EXTEND 采样，外框行或无效区旁的像素被 clamp 或跨断裂混合时，切口点会顶出尖刺；Panorama 的点采样已有 nearest 保护，但切口与 Depth Split 切边仍走两套深度来源。

`common/validity.py` 的删点用 POINT 域的 Delete Geometry：无效顶点连同所有相邻面一起消失，切口因此比阈值轮廓多退一圈，剩下的悬空边还要再删一次。Panorama 的无效判定链先经 `evaluate_field(..., "POINT")` 固定到点域，Plane 的判定链则直接由 UV 属性与纹理采样组成。

## Goals / Non-Goals

**Goals:** Depth Plane 与 Panorama 的 mask 切口与 Depth Split 切边遵循同一条深度规则，并与 Depth Cutout 的既有约定一致；规则内建在共享 helper 里，调用方不再枚举哪些点用面深，切口规则本身不带例外。

**Non-Goals:** Panorama 点采样的 nearest 保护、`Boundary Smooth` 与位置平滑的语义（含原画幅外框在边界带平滑中的保护）、`O Image Depth Cutout` 与 `O Image Relief Plane` 的行为。

## Decisions

### 切口边界内建，删除 `always_vertex` 参数

规则统一后三个调用点都要它，参数只剩「要不要这条规则」一个含义，而三处答案相同，因此把它移进 `build_surface_camera`：helper 内部用 `edge_boundary_field` 求值边界点，再与 `cut_vertex` 一起接入既有的 `OR → Switch`。`always_vertex` 参数删除，不留兼容分支。代价是将来若有调用方需要退出这条规则，得重新引入参数——目前看不出这样的调用方。

### 切口 = 全部自由边界，不设例外

`build_surface_camera` 内部把自由边界直接当作切口，不接受调用方给定的点集合，也不接受排除字段。Plane 的原画幅外框因此与 mask 切口同规则，Depth Mask 关闭时外框也会取相邻面采样。

曾做过一版「外框例外」：以 UV 边距为零排除外框，并把被 mask 判为无效的外框点并回切口。实际结果是外框上仍会剩下一两个自身采样有效、又紧贴 mask 边界的点按点采样，边界上出现个别不合规则的深度；判据还多出「外框 ∧ 自身采样是否有效」这层状态。相比之下，把全部自由边界当作切口既符合规则本身，也少一层例外，因此取消。

外框在边界带平滑（`smooth_boundary_camera`、`smooth_cut_boundary` 的 `protected`）中的保护保持不变，与深度规则互不影响。

### 深度替换沿用射线方向不变的比率法

切口点保持自身的射线方向，只取相邻保留面的深度。替代方案是整点改用面采样（方向与深度都换），那会把切口点拉离它所在的行列，破坏 Plane 的规则网格与 Panorama 的等距经纬投影；比率法只改深度分量，是既有 Depth Split 与 Cutout 轮廓已验证的形式。

### 平滑顺序保持不变

```
删除面（切口成为自由边界）
        │
        ▼
build_surface_camera（切口点取相邻面深）
        │
        ▼
切口带内深度模糊，沿射线重建（Plane）／径向重建（Panorama）
        │
        ▼
切口带内位置平滑
```

面深决定切口点贴在哪张面上，带内模糊决定切口附近怎么过渡，两者职责不同，先锚定再过渡，与 Depth Cutout 一致。可观测后果是切口点的最终深度等于「面深在切口带内与邻点模糊一次」的结果，而不是相邻面深的精确值。要让切口严格等于面深，只能把替换挪到模糊之后或把切口点也排除出模糊，两者都会在切口与第二圈之间留出台阶，不采用。

### Depth Mask 按面删除

删除改用 FACE 域，并去掉随后的残留边清理。理由是节点链按消费域求值：Plane 的判定链没有固定到点域，切到 FACE 后 UV 属性取该面四角平均，等于在面中心采样深度，因此面中心仍有效的面保留下来，切口不再比阈值轮廓多退一圈；点删除遗留的悬空边也随面删除一并消失，不需要第二次 Delete Geometry。

Panorama 的判定链同样改在面心求值：无效采样用面中心经纬（`combine(face_u, face_v)`）取 Closest 纹理，再固定到 FACE 域供删面使用。面心经纬由面中心位置反算，不经过点域经度的平均，因此不会在 seam 处折返。判据统一后 Panorama 的切口与 Plane 一样落在面中心轮廓上，不再比阈值轮廓多退一圈，无效判定也只剩这一处，不再有过渡带删面或按深度通道判无效的第二套规则。

面心判定让切口点可能落在无效侧：自身采样无效、但所属面中心有效。这些点由切口规则取相邻面深，不会被当成无效区。Depth Mask 关闭时被保留的无效面则整片落到 `Dome Radius`，它同时是 Depth Scale 为 0 时的球半径：`radius = Dome Radius + Depth Scale × (d − Dome Radius)`。两个作用共用同一个值，无效面拿到的就是同一次 `alpha < Mask Threshold` 的结果。

## Risks / Trade-offs

- 推翻「Depth Mask 只删点、不改位置」的既有契约 → 重写相关断言为「切口取相邻面深」，并保留 Depth Mask 关闭时结果逐位不变的断言。
- 没有相邻保留面的点参与面深替换时 FACE→POINT 求值为 0，比率会塌到原点 → `edge_boundary_field` 只标记开口边界与残留边端点，不标记孤立点，并加断言兜住。
- 外框改按面深后，Depth Mask 关闭时外框的深度也随之变化 → 由切口规则测试覆盖；外框在边界带平滑中的保护保持不变。
- 源码与 `.blend` 资产不同步 → 修改后运行 `uv run node-group build`，源码、测试与资产一并更新。

## Migration Plan

直接替换构建函数、两个组的接入与相关测试，不保留旧参数或开关；重新构建节点资产。回滚时恢复 `build_surface_camera`、两个组与测试并重建资产。用户工程中已保存的节点实例沿用保存时的接口，不做迁移。

## Open Questions

无。
