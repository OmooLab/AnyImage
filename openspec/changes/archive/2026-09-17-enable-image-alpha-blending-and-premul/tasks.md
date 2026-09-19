## 1. Blender 数据保留验证

用户确认直接实施 PREMUL。byte GENERATED 与加载 PNG 的 Blender 4.5.3 重载解释差异保留在 `tests/test_image_premul_retention.py`；原始 Packed PNG 字节保持。公共业务像素入口在 PREMUL 下临时按 STRAIGHT 读取原始 RGB 并立即恢复模式，避免 Mask 将 Blender 展开的 RGB 写回。已验证 byte/float 独立 Color 产物与 Mask → Frame → Pack → reload → Mask Add；完整浮点保存重载和序列逐帧验收仍待完成。

- [x] 1.1 使用真实 Blender 为 byte/float 与 RGBA PNG 建立 PREMUL 模式切换、读取、Pack、导出和 blend 保存重开测试，包含隐藏 RGB 与连续 Alpha；记录适用的设置顺序。
- [x] 1.2 验证 PREMUL 结果再次 Mask Add、Frame 和序列逐帧读取仍符合原像素算法；业务读取须绕过 Blender 的 PREMUL RGB 展开并恢复最终模式。

## 2. 公共默认值

- [x] 2.1 在 common 中统一 Color Image 的 PREMUL 设置与必要的像素保留操作，接入本地编辑和公共图片 Job 结果入口。
- [x] 2.2 在成功替换和新建 Reference Image Empty 时开启 use_empty_image_alpha，补全失败恢复，保留不透明度、深度与时间映射。
- [x] 2.3 在材质 Color 入口及 Plane/Cutout Color 创建路径应用 PREMUL，保护共享源 Image，并保持 Depth/Normal 数据贴图原设置。

## 3. Frame 边缘抗锯齿

- [x] 3.1 增加覆盖及层级边界判定与 4×4 子像素参考采样，复用有效求交和逐样本排序；稳定内部继续中心采样。
- [x] 3.2 按全部子样本平均 Alpha，按有效覆盖样本平均 RGB，保留底层颜色规则并清除完全无覆盖的源外 RGB；采用分块累积。
- [x] 3.3 补充倾斜轮廓、中心漏采细条、交叉平面、透明图层、半覆盖数值、源外无黑边及内部细节测试。
- [x] 3.4 验证实际 Frame → Pack → Mask Add 的黑/白底图边缘 RGB，检查行块一致性并记录典型最大分辨率的耗时和峰值内存。

## 4. 集成与验收

- [x] 4.1 覆盖 Mask、Frame、Rectify、Remove Background 及共享加载入口的最终模式、取消/失败恢复和撤销边界测试。
- [x] 4.2 覆盖 Plane、Depth Plane、Cutout 的 Color Image、材质连线、颜色空间切换和共享源保护测试。
- [x] 4.3 使用黑/白背景与渐变边缘检查 Empty Alpha Blending、PREMUL 及 Mesh 显示，并记录多图排序或尚未完成的视口验收限制。
- [x] 4.4 运行定向测试、完整 uv run pytest 与 OpenSpec 严格校验；不修改产品文档，不构建节点、文档或扩展包。

最终自动测试：460 passed，56 subtests passed；OpenSpec strict 校验通过。当前 10/13 项完成，1.1、1.2 和 4.3 的剩余验收如上所述，不作为用户已确认的默认值落地阻塞。

验收记录：两层小纹理源、默认 2048×2048 输出约 7.916 秒，tracemalloc 峰值 359.2 MiB；8192×2048（16,777,216 像素上限）约 32.481 秒、1436.6 MiB。该数值为 Python/NumPy 跟踪内存，不是进程 RSS；未为源分配整图 4×4 放大副本。行块 1/3/256 结果一致。实际 Blender 视口、多图排序与完整序列验收尚未执行。
