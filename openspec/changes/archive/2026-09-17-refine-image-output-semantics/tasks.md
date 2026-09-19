## 1. Refine Server 输出协议

- [x] 1.1 修改通用 BEN2 Refine，使其保存与输入同尺寸的 `Source Alpha × BEN2 Alpha` RGBA，删除 Alpha 紧裁切与局部 bounds 计算；用像素和尺寸测试验证透明、半透明与前景局部输出。
- [x] 1.2 修改 `refine-image-selection` 与 Cutout artifact Job，只返回完整 Refine 图片并删除 `selection_bounds` 文件和结果 key；更新 Job 协议测试并确认 request 不包含 Selection Mask。
- [x] 1.3 验证 Cutout Refine 后的 Color、Normal 可见区域、MoGe-2 黑底输入和 Depth Metadata 都消费完整 Refine Alpha，同时 Depth EXR 继续保留连续 RGB Field 与模型 Validity Alpha。

## 2. Crop 与 Cutout 最终 Selection 约束

- [x] 2.1 为 Crop Refine 准备与 Bounds 输入同生命周期的本地 Selection Mask sidecar，确保 Job request 不发送该路径且 cleanup 能完整删除临时容器。
- [x] 2.2 修改 Crop Refine 响应，沿用提交前 bounds，在 Blender 中计算 `Refine Alpha × Selection Mask` 并创建完整 bounds 结果；用圈外 BEN2 内容、空交集、Keep Original 和一次栅格化测试验证。
- [x] 2.3 修改 Cutout Job 响应，让启用 Refine 与仅生成 Normal/Depth 两条路径都以“贴图 Alpha × 原 Selection Mask”构建网格，同时保持颜色及 AI 贴图未乘 Selection；用圈外内容、抗锯齿 Mask、空交集和标定测试验证。
- [x] 2.4 删除 Blender 端 Refine 局部 bounds 偏移与结果读取逻辑，验证 Crop 和 Cutout 的图片尺寸、placement bounds、颜色资产复用和异常清理。

## 3. 生成材质 IOR Level

- [x] 3.1 将 `O Image Layer` Color 直接连接到 Plane、Depth Plane 与 Cutout 生成材质的 Principled BSDF IOR Level，保留既有 IOR 和其他材质连接。
- [x] 3.2 增加材质节点测试，验证 Color-to-IOR-Level 直连、Cutout/Depth Plane IOR `1.2`、普通 Plane 覆盖以及 Shadeless 分支不回归。

## 4. Reference Depth 节点接口

- [x] 4.1 将 Depth Plane、Cutout、Depth Balloon 与 Depth Surface 构建脚本中的 `Base Plane Depth` 一次性改名为 `Reference Depth`，同步 Group Input 可见项、子组连线和面板顺序。
- [x] 4.2 更新 Depth Plane 与 Cutout 对 Modifier 输入的初始化、查找和测试，确保元数据与标定值只写入 `Reference Depth` 且几何公式不变。
- [x] 4.3 更新节点资产验证脚本和结构断言，确认所有相关接口、依赖集合与功能验证不再包含旧名称。
- [x] 4.4 运行 `uv run build_node` 重建并验证 `assets/O_AnyImage.blend`，检查 socket 顺序、节点布局、几何求值和未使用输出隐藏。

## 5. 文档与验证

- [x] 5.1 更新 Crop Tool、Cutout Tool、Convert to Plane、Runtime、Outputs 与节点资产内部文档，说明稳定 Refine bounds、贴图与网格 Mask 边界、IOR Level 连接和 `Reference Depth`。
- [x] 5.2 搜索并删除当前实现和文档中的 `Base Plane Depth`、Refine 局部 bounds 协议及“BEN2 圈外内容直接进入最终网格”的残留描述。
- [x] 5.3 运行相关 Server、Blender、Cutout、材质和节点资产测试，再运行 `uv run pytest` 完整测试；仅修复本 change 引入的回归，不构建其他文档或发布产物。
