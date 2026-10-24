## Context

当前 Match Color 用 `image_rgba_to_linear()` 准备目标和参考；该函数仅在 byte 图片的 color space 名称为 `sRGB` 时解码。预览又通过 `linear_rgba_to_image()` 按目标设置编码，并创建继承目标 color space 的临时 Image，交由 `gpu.texture.from_image()` 绘制。因此材质用的 `AgX Base sRGB` 等设置同时影响算法输入与预览显示。

Match Color 已有独立浮层和图片编辑事务。此次调整围绕当前源码保留交互参数、代理尺寸及匹配算法。

Rectify 目前在原业务像素上执行透视重采样，然后将结果直接写入标为 `sRGB`、`STRAIGHT` 的 byte 临时 Image；float 输入也走此预览入口。两者已共享 `common/image_preview.py` 的布局、边框、文字与 Image 纹理绘制选项。

## Goals / Non-Goals

**Goals:**

- 固定 sRGB 预览，并统一参考、色板、代理与最终结果的像素解释。
- 保留原图设置、共享用户与取消行为。
- 自定义 OCIO 缺少名为 `sRGB` 的色彩空间时仍可显示预览。
- Rectify 与 Match Color 共用 linear Rec.709 处理、sRGB 显示及存储类型编码规则。

**Non-Goals:**

- 任意 OCIO 色彩空间到 linear Rec.709 的色彩转换。
- 匹配算法及交互参数调整。

## Decisions

### 用存储类型定义 Match Color 的像素约定

通过 `common/color_space.py` 中职责明确的共享入口转换图片编辑像素：byte 图片当前业务 RGB 一律按 sRGB 解码到 linear Rec.709，float 图片当前业务 RGB 按 linear Rec.709 使用；Alpha 原样传递。参考准备、参考图标与色板、代理匹配、全分辨率匹配以及 Rectify 透视重采样均使用该约定。

结果写回采用对应逆过程：byte RGB 编码为 sRGB，float RGB 保留线性值。以原图类型控制算法已有的输出范围策略。像素来自现有 `image_rgba()`，保留其 Alpha 与读取完整性语义。

选择此约定是为了将 `_color` 等图片的材质解释与匹配工具的颜色操作分开。仅修改预览 Image 的设置仍会留下输入与提交编码的不一致。实现时检查转换函数全部调用者；仅服务颜色匹配的旧入口直接替换，并同步相关测试。

Rectify 在调用 `warp_projective_pixels()` 前解码，在预览和最终重采样后分别进行显示编码与存储编码。`warp_projective_pixels()` 继续负责几何采样、预乘插值和还原 straight Alpha，颜色转换放在调用边界；确认时沿用现有尺寸限制、Alpha trim 与 placement。零处理的原图缓冲与线性处理缓冲职责明确，避免重复解码或把线性值直接写回 byte 图片。

### 用独立 GPU 纹理显示已编码的 sRGB

预览从匹配得到的线性数组生成 sRGB RGBA，RGB 限制在显示范围内，Alpha 保持现有透明混合语义。使用 Blender GPU Buffer/GPUTexture 创建普通 RGBA 纹理；上传前按现有预览方向处理数组。

纹理不经过 Image 色彩空间解释，也不启用 scene-linear 到 sRGB 的额外绘制转换。共享 shader 通过 Blender 自动设置的 `srgbTarget` 内建 uniform 识别当前 framebuffer 的编码：硬件会编码为 sRGB 时先解码显示 RGB，其他 framebuffer 直接输出显示 RGB。此转换保证显示值只编码一次。无需查询、猜测或设置 OCIO 的 `sRGB` 名称。复用现有布局、边框与文字绘制，刷新频率沿用当前限制。每次刷新替换纹理引用，保持同时存活资源有界。

直接创建 GPU 纹理比临时 Image 更直接地表达已准备好的显示像素，同时避免 OCIO 命名回退与数据块管理。

### 两种工具共用小型预览入口

在 `common/image_preview.py` 提供共享纹理创建或替换、绘制入口，以 top-down、straight-alpha 的线性 RGBA 为输入，集中完成 sRGB 显示编码、显示裁剪、纹理方向及透明混合。颜色数学函数仍归属 `common/color_space.py`。两种 Operator 仅负责提供预览数组、目标 bounds、HUD 和自身资源引用。

Rectify 保留固定 512×512 预览纹理和通过 bounds 调整宽高比的交互；Match Color 保留自己的代理比例与刷新节奏。退出时各自释放引用，handler 和 timer 由所属 Operator 清理。删除两套临时 Image 创建入口；检查 `preview_texture_draw_options()` 和临时预览标记的全部消费者，仅清理已无调用的代码。采用函数级共享，避免引入通用 Modal 基类。

### 原设置贯穿操作，结果只替换内容

预览的任何呈现转换与最终图片 color space、Alpha 设置相互独立；操作不会为了预览更改原设置，也无需在结束时恢复设置。输出编码仅表示写回像素时的数值转换。

预览始终保留源 Image 的 color space、Alpha 模式、像素与绑定。确认时按 Match Color 像素约定生成全分辨率结果，继续通过 `create_image_edit_result()` 和 `ImageEditTarget.commit()` 保留原设置、共享隔离与 Undo。取消、确认或异常退出移除 handler、timer 并释放纹理引用。

启动时记录目标 color space 与 Alpha 模式；提交时连同现有像素、目标与参考有效性校验进行检查。用户在预览期间更改解释设置时安全取消，保留用户的外部修改。

## Risks / Trade-offs

- [自定义 OCIO 的源图可能实际采用其他编码或色域] → 明确 Match Color 的 byte sRGB / float linear Rec.709 约定；预览一致性不代表任意源空间转换能力。
- [GPU API、像素方向与透明混合在不同 Blender 版本下存在差异] → 在真实 `POST_PIXEL` 回调中比较预览与 Blender 原生色块，覆盖 Blender 4.5 与 5.x 的 framebuffer 编码差异，同时检查离屏绘制。
- [byte 非 sRGB 图片的匹配结果随新解释改变] → 用相同存储像素、不同 color space 的对照测试验证确定性与结果编码，并覆盖 `_color` 图片。
- [Rectify 线性插值会改变高反差区域的中间亮度] → 用黑白插值与半透明边缘测试明确正确结果，预览和最终重采样使用同一线性输入。
- [旧 OpenSpec 变更含与当前源码不同的算法及参数描述] → 实施以本提案的颜色契约与当前源码为准，检查相关未归档规范对临时 Image 的描述，在归档时保持预览资源约定一致。
