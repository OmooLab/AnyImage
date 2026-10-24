## Context

AnyImage 已通过 `image_edit_owner()` 与 `ImageEditTarget` 统一解析和提交 Image Empty、AnyImage Mesh 的 Color Image Texture 与 Shader Editor 活动 Image Texture。现有直接图片编辑要么在 Blender 主线程内处理像素，要么提交 AI Job；颜色参考匹配不需要模型，且原型在普通图片上可由 NumPy 在交互可接受的时间内完成。

本功能有两个连续操作：先记录一个场景级颜色参考，再对任意有效目标执行确定性颜色匹配。交互必须保持两个按钮、没有强度或背景处理选项；固定的完整效果由算法内部负责稳定性。设置参考时 Alpha 限定颜色特征提取范围；匹配目标时所有 RGB 像素统一迁移，目标 Alpha 仅被保留而不控制处理范围。

## Goals / Non-Goals

**Goals:**

- 在当前 Scene 中持续保存一个静态 Image 作为颜色参考。
- 从三种现有图片上下文设置参考，并在相同上下文一键匹配当前目标。
- 以固定完整强度产生平滑、确定、结构不变的结果。
- 抑制 JPEG 压缩误差放大、新增色阶、硬裁剪和色域越界。
- 复用现有目标验证、共享数据隔离、失败恢复和 Undo 行为。
- 不依赖 AI 环境、模型下载或新第三方依赖。

**Non-Goals:**

- 不提供 Strength、Tone、Color 或算法模式选项。
- 不提取或编辑可见色板。
- 不检测、分割、保留或重建无 Alpha 图片的背景。
- 不按物体语义建立局部颜色对应，也不生成或修改图片结构。
- 不支持 Movie、Sequence 或逐帧颜色参考。

## Decisions

### Scene 保存 Image 参考，匹配时读取当前像素

在 `AnyImageSettings` 中保存一个 `bpy.types.Image` 指针。`Set Color Reference` 仅验证并更新该指针；同一 Scene 后续目标共享它，保存 `.blend` 后仍可恢复。匹配时重新读取参考图当前像素，避免维护容易失效的像素缓存，并确保用户修改参考 Image 后得到当前内容。

备选方案是保存提炼后的颜色 profile。它能减少少量重复分析，但需要定义图片内容变更、文件重载与 Undo 后的缓存失效；当前图片规模下收益不足以抵消状态复杂度。

### 两个 Operator 共用现有图片目标解析

新增 `SetColorReference` 与 `MatchColorReference`。两者都通过 `image_edit_owner()` 取得 Image Empty、AnyImage Mesh Color Texture 或 Shader Editor Image Texture；匹配通过 `ImageEditTarget` 捕获和提交目标，从而沿用共享 Image、共享 Material、节点身份与对象材质槽验证。

设置参考只要求当前 Image 静态且可读。匹配还要求当前 Scene 存在有效静态参考、目标有效，并且参考与目标不是同一 Image。参考被移除或失效时，`Match Color Reference` 的 `poll` 返回 false。

### Blender 侧执行确定性 NumPy 颜色匹配

颜色匹配在 Blender 侧读取参考与目标像素并生成结果，不启动 Job Server。这样没有环境准备和文件往返，也不会把非 AI 功能绑定到模型状态。

算法在统一的线性颜色解释上转换到感知颜色表示，并分别构建亮度与色度变换：

- 亮度使用少量分位锚点形成单调平滑曲线；
- 色度使用带正则和增益上限的协方差映射；
- 在低频颜色基底上计算调整量，再叠回目标原始细节，避免放大 JPEG 块与边缘振铃；
- 完整应用校准后的变换，不再与原图做用户可调强度混合；
- 超出输出色域时压缩色度而非直接裁剪 RGB；
- byte 输出在最后一次量化前加入确定性高频抖动，float 输出保持浮点精度。

备选的完整直方图匹配更贴近参考分布，但会放大 8-bit 阶梯和压缩噪声；生成式或参考条件 AI 会增加模型、等待时间与结构变化风险。

### Alpha 只控制参考特征提取

参考统计按 Alpha 加权并忽略完全透明像素；没有有效 Alpha 的参考使用全部 RGB。匹配目标时无论 Alpha 是否存在或取值如何，颜色变换 SHALL 应用于整张图的全部 RGB，包括完全透明像素下的隐藏 RGB，目标 Alpha 原样提交。系统不增加背景识别或按目标可见度分流的处理路径。

### 使用直接图片编辑事务提交

算法先生成独立结果 Image，再由 `ImageEditTarget.commit()` 提交。独占 Image 原地恢复结果内容；共享 Image 或共享对象 Material 按现有规则隔离。成功操作作为一次 Undo，失败时释放结果并保持参考和目标不变。

## Risks / Trade-offs

- [无 Alpha 的白底 JPG 在强迁移后可能显露原有压缩块] → 通过平滑调整场、增益限制和抖动减轻；明确不增加背景识别特殊路径。
- [固定完整强度对部分图片可能过强] → 将稳定性、亮度保护与色域约束纳入校准后的默认算法，而不是暴露用户参数。
- [大图同步处理可能短暂阻塞 Blender] → 使用缩小采样分析参考分布、向量化全分辨率应用并控制中间数组数量；以代表性分辨率建立性能测试。
- [Scene 引用的 Image 被移除或变为动画] → 每次绘制与执行时重新验证，失效时禁用匹配且不回退到其他图片。
- [参考图本身随后被编辑] → 匹配明确读取当前参考 Image；需要冻结旧外观时用户重新复制或保留该 Image。
