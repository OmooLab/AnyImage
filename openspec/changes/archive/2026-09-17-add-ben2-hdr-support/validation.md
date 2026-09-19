## 验证环境

2026-09-10，Windows，项目 uv 环境，Blender Python 4.5.3 LTS，BEN2 本地 `models/BEN2-ONNX/onnx/model_fp16.onnx`，ONNX Runtime CPU。

## 浮点与编辑事务

- 真实 Blender 验证外部 EXR、packed、generated、未保存像素，覆盖 Image Empty 与材质 Image Texture，以及共享和独占图片。
- RGBA 样本包含大于 1 的颜色、有限负值、零 alpha 与部分透明像素；32-bit ZIP EXR 保存、打包、载入和 blend 保存重开均通过数值检查。
- 单独验证 STRAIGHT EXR 解码后的预乘缓冲语义，处理后解关联颜色在 `rtol=1e-6` 内保持一致。
- 已验证 Radiance `.hdr` 实际文件读取与识别预览生成，源浮点像素保持不变。
- 原生 Operator 的撤销、重做、取消、提交异常和资源释放通过测试；未保存的独占浮点源图采用内嵌 EXR 撤销基线。
- 纹理节点删除重建测试覆盖独立身份字段，防止 RNA 地址复用造成异步目标误认。

## 实际 BEN2 推理

Cycles 渲染 320×320 金属 Suzanne，16 samples，两盏面光源，原始 RGB 峰值约 112.432。用渲染 alpha 作为轮廓参考，构造三档曝光的灰底 HDR 图，以及保留原始软 alpha 的透明图。四组均执行真实 BEN2 Job、浮点 alpha 读回、Blender 合成及 EXR 持久化。

| 输入 | 原始 RGB 峰值 | 输出预乘 RGB 峰值 | 轮廓 IoU |
| --- | ---: | ---: | ---: |
| 正常亮度 | 112.4321 | 112.4235 | 0.9822 |
| 16 倍亮度 | 1798.9137 | 1796.3881 | 0.9874 |
| 0.05 倍亮度 | 5.6216 | 5.6176 | 0.9757 |
| 原始透明度 | 112.4321 | 112.4292 | 0.9656 |

IoU 使用预测 alpha 与渲染 alpha 的 0.5 阈值轮廓计算。四组 EXR 读回值相对于 `source_rgba × predicted_alpha` 的最大绝对误差均为 0。已目视检查高亮预览、低亮度预览与预测轮廓。该结果验证当前渲染样例的识别效果；不同实图的抠图质量取决于模型预测。

## 自动检查

- OpenSpec 严格校验通过。
- BEN2 的旧 `infer` 入口及旧节点使用者检查名称已清理，相关调用者和测试已更新。
- 最终 `uv run pytest -q`：1074 passed、2 xfailed、52 subtests passed，175.71 秒，退出码 0。两项 xfail 为已有的浮点图片显示色彩空间适配测试。
- `git diff --check` 通过。
