## Context

Cutout 客户端持有源图裁切结果、Selection Mask、最终 `content_values` 以及对象创建所需的全部图片。服务端目前在 MoGe 推理后按源图 Alpha 做 Cutout 专用深度延伸，但它不知道 Selection Mask，因此无法与最终 Cutout 轮廓一致。材质、Depth 和 Normal 共用 `UVMap`，移动 UV 会让所有采样发生位移。

## Goals / Non-Goals

**Goals:**

- 从最终 Cutout Mask 得到唯一、局部、结构向内的采样方向。
- 用同一 mapping 处理材质 RGBA 与 Depth，而不改变 MoGe 输入或 UV。
- 在客户端完成处理，使 Selection Mask、颜色图和深度结果处于同一数据边界。
- 只保留必要的尺寸、有限值和结构边界保护，不建立 donor 可靠性分级。

**Non-Goals:**

- 不使用 Alpha 0.95、最近可靠 donor、core/candidate/fallback 或跨方向候选比较。
- 不处理 Normal，也不修改源 Image、网格几何、UV 或节点组。
- 不让 padding 重新定义 MoGe 的整体深度标定。

## Decisions

### 从最终 Mask 构造结构 inward mapping

以 `content_values >= alpha_threshold` 得到最终二值 Mask。用有符号距离场的局部梯度取得指向 Mask 内部的单位法线；轮廓外目标通过其边界落点继承该法线，而不是搜索多个内部 donor。对边界位置 `b`，内部采样位置为 `q = b + inward * padding`，边界带像素沿同一法线使用 `q` 的值。

同一 `Boundary Padding` 同时定义向内采样距离与向外写入宽度。Mask 内超过该距离的像素不变；边界内侧带、边界和外侧带使用结构内向样本，从而把 UV 边界内缩的采样结果烘焙到纹理，而不改变 UV。薄结构中若 `q` 沿射线提前离开当前 Mask，则使用该射线最后一个内部位置。角点使用距离场给出的局部法线；零梯度位置保持原值。

该规则没有 Alpha 可靠阈值、最近 donor 或回退层。方向完全由 Cutout 结构决定，像素内容不参与方向选择。

### 客户端统一处理 Color 与 Depth

同步 Cutout 在独立 Color Image 创建后立即处理；AI Cutout 等服务端返回原始产物后，加载临时 Color 与 Depth 数据，在创建材质和对象之前处理。两条路径共用一个纯数组 mapping 入口。mapping 按各目标图片分辨率从同一 Mask 重建，padding 以材质图像素为基准同比缩放到 Depth。

材质对边界带搬运完整 RGBA。Depth 从内部采样 camera Z 与 A validity；目标 R/G 不复制 donor 的相机位置，而是按 Metadata 中的像素单位 intrinsics 和目标像素中心从新 Z 重建 camera X/Y。这样只延伸深度表面，不把 donor 的投影视线横向搬到边界。

处理后的 Blender Image 重新打包。原始 `reference_depth` 和 intrinsics 保持不变：padding 是采样保护，不参与全局尺度校准。Normal 使用服务端原始结果。

### 服务端恢复为原始产物生成器

Cutout Job 不再向 `generate_moge_artifacts` 请求 `extend_edge_depth`。若搜索确认没有其他调用方，移除通用生成器的延伸参数、导入、旧服务端算法和仅覆盖旧行为的测试；否则保留其他真实调用方所需的最小能力。MoGe 仍读取未 padding 的原始 RGB，Depth Metadata 由原始 Frame 生成。

### Preference 只影响新对象

Preferences 的 Cutout Tool 提供 `Boundary Padding` 浮点像素值，默认 2、范围 1–4。操作开始时捕获当前值，保证异步响应不受中途设置变化影响；已有 Cutout 不追溯更新。

## Risks / Trade-offs

- [薄结构不足以容纳完整内部距离] → 沿同一 inward ray 截止在最后一个内部采样点，不转向其他 donor。
- [距离场在尖角或对称轴出现零梯度] → 仅对应位置保持原值，避免引入任意方向。
- [Color 与 Depth 分辨率不同] → 从同一 Mask 按目标尺寸重建 mapping，并按统一比例缩放 padding。
- [Depth XYZ 被错误整体复制] → 只搬运 Z/A，使用目标像素与原 intrinsics 重建 X/Y。
- [修改 packed Image 后保存旧内容] → 在对象消费前 update 并重新 pack，覆盖保存重载与失败清理。
