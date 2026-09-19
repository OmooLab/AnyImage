# 实施验证

## 基线与入口

开始实施时 `git status --short` 仅有本 change 未跟踪，生产代码无已有未提交修改。

- Geometry：Operator → Geometry Job → ModelManager → MoGe-2 / MoGe-3 ONNX；保留 MoGe-3 三步细化。
- Upscale：Operator → Upscale Job → `models/upscale.py` → ONNX 分块 → Lanczos 2× 与源 Alpha 合成。
- 背景移除：Operator 当前硬编码 BEN2；Job 调用 `models/ben2.py`，HDR 已使用 Alpha-only 返回，输入准备复用 `common`。
- 模型入口：`preferences.py`、`properties.py`、`server/model_catalog.py`、`server/model_manager.py`；背景资源分类当前为 `ben2`。
- 资产入口：`uv run model prepare` / `uv run model sync` → `tools/models/cli.py`；上传为逐文件 `rclone copyto`。
- 当前生产源码未发现 DA3 实现；本地及 R2 残余仍需枚举。历史 OpenSpec 记录不作为现行调用链。

衔接 `add-moge3-model`、`add-pisa-sr-two-times-upscale`、`add-ben2-hdr-support`、`organize-tool-cli`，模型成员以本 change 为准。

## BiRefNet 来源

| 模型 | 官方权重与源码仓库 | 固定 revision |
|---|---|---|
| Lite | ZhengPeng7/BiRefNet_lite | aa62cd87eafb9cc43056d08ef3615a14628b831d |
| HR-matting | ZhengPeng7/BiRefNet_HR-matting | 5d6b6f8adcb5b417c871b1d84ceaae9871355b7f |

两款模型卡标注 MIT，正式导出结构检查通过，许可证随模型发布。

Lite 固定权重 SHA-256：`4417d89795250e698c3cb0ae8df15743810065f646f48a694fdfa7ca052d0815`；HR：`a5a4de698739ea5e0e8bbab28e1b293dde95092b87a442d566cbc585c53cef55`。许可证固定到 BiRefNet revision `ebcc0bc8ec7fe919cec829f2dea656b3078acddc`，1,066 bytes，SHA-256 `92a7089e0915fc32bc40067560b398f1e6a7a5958abd7d04eda393629a5acefb`。

数值测试开始前固定 Alpha 容差（激活后、浮点范围 0–1）：FP32 ONNX 对原始 FP32 实现的 MAE ≤ 0.0002、P99 ≤ 0.002、Max ≤ 0.01；压缩权重资产 MAE ≤ 0.002、P99 ≤ 0.02、Max ≤ 0.1。所有输出必须有限、尺寸准确、处于 0–1。容差不得根据测得误差放宽。

固定样图使用作者官方演示中的 Helicopter、Jewelry、My_Love、My_MiSheng、Windmill，另补发丝、毛绒及薄纱覆盖；记录来源与逐图结果。性能测量使用同一批源图、同一 Runtime/设备并分开运行模型。

补充 Alpha Matting Evaluation 官方测试集中的 `net.png`（薄网纱）和 `plasticbag.png`（透明塑料）；来源 `https://www.alphamatting.com/datasets.php`，仅用于本地评估。

Lite 通过七图 CPU / DirectML 对照的正式资产：112,968,598 bytes，SHA-256 `6e2a9844c57b080e95a402722ddcae5660e6f254a04d3e003347f06f587b71fe`。FP16 权重存储与完全无损的静态常量压缩，FP32 运算。最大误差 0.041951，符合预设门槛。CPU 热推理约 2.85 秒；同输入 BEN2 CPU 约 3.84–3.90 秒，Lite 下载成本更低且 CPU 更快。正式 DirectML 与端到端结果见下表。

HR 的 DirectML 最后一层解码器有稳定偏差；用户于 2026-09-10 确认保留 HR，暂时仅支持 CPU。正式资产使用原始 GridSample 结构和 FP16 权重存储，不采用失败的分块或混合精度实验。HR 选项、实际 Job 设备和缓存键均明确使用 CPU。

## 公共背景编排

`models/background.py`、`get_background` / `release_background` 与资源分类 `background` 已统一。保留 `onnx_ben2.py` 专用适配器。三款模型已通过静态、多帧、连续 Alpha、源 Alpha 合成和缓存切换测试；既有 HDR RGB 保持、取消和失败清理测试通过。

## 正式背景模型验收

正式导出命令：`uv run --script tools/models/birefnet_export.py --variant lite --destination models/birefnet-lite`；HR 使用 `--variant hr-matting --destination models/birefnet-hr-matting`。导出器固定上游代码、权重与许可证。Lite 重复导出哈希完全相同。

| 模型 | ONNX bytes | SHA-256 |
|---|---:|---|
| Lite | 112968598 | `6e2a9844c57b080e95a402722ddcae5660e6f254a04d3e003347f06f587b71fe` |
| HR-matting | 529467341 | `b3abc34843a4d96f669ca9fb1a2a16b3417ab8b91c987573fdbda36d20514133` |

ORT 1.24.4；DirectML 使用 RTX 5070 Ti。Lite 正式资产的七图 CPU / DirectML 误差通过既定门槛；最终 DirectML 记录确认实际加载 DmlExecutionProvider。HR 七图 CPU 与原始 FP32 对照全部通过，最差 MAE 0.000001987、P99 0.000020504、Max 0.000103504；输出均为有限的 2048×2048 连续 Alpha，生产适配器恢复源图尺寸。

| 模型 / 设备 | 加载秒 | 七图热推理秒 | 峰值工作集 GB | 峰值进程提交 GB |
|---|---:|---:|---:|---:|
| Lite / DirectML | 2.728 | 0.05895–0.05961 | 0.802 | 6.729 |
| BEN2 / DirectML | 1.154 | 0.11591–0.11801 | 0.604 | 6.519 |
| HR / CPU | 4.318 | 21.718–23.437 | 19.278 | 22.596 |

Lite 与 BEN2 用同一七图、同一 Runtime 配置串行运行，每图三次，表中取每图最后一次。HR 每图两次，CPU 配置为八线程。工作集与提交量来自 Windows 进程计数器，不将其表述为独立显存测量。Lite 满足体积更小且热推理更快的默认门槛；其加载和峰值内存并不全面优于 BEN2。

视觉检查 `.model-cache/birefnet/quality-1.png`、`quality-2.png`：三款均能提取人物、猫、直升机和风车细杆；HR 更明显保留薄网纱和透明塑料的中间透明度，猫须细节更完整。普通珠宝场景 HR 会残留叶片背景，Lite / BEN2 的主体分离更干净。第三档表示高分辨率 matting 用途，不保证对所有主体都更好。源图与逐图 Alpha/PNG、耗时/误差 JSON 保存在 `.model-cache/birefnet`。

## 集成与回归

- 三类各三款，共九款；默认集合为 MoGe S、Lite、WDN。默认值由目录统一提供，偏好读取集中于 `preferences.py`。保留模型沿用原 Blender 枚举编号，有效 BEN2 / x4plus / MoGe 选择保留，退役偏好归一到默认，直接提交退役 Job 键报错。
- `uv run model prepare` 成功，九款模型共 13 文件全部通过大小和 SHA-256 校验。
- 真实 JobServer：Lite 连续两次、BEN2、HR CPU、HAT 连续两次全部成功，Alpha 源尺寸/有限范围及 HAT RGBA 准确 2× 输出检查通过。Lite 第二次加载 0 ms；HR 完整 Job 24.08 秒；HAT 两次完整 Job 3.41 / 0.60 秒。服务关闭后全部资源键为空。记录：`.model-cache/tier-job-validation/results.json`。
- `uv run pytest -q --tb=short`：1227 passed，51 subtests passed，178.55 秒，正常退出。随后补齐退役偏好持久化归一，对应偏好与初始化测试再次通过：23 passed、2 subtests passed。曾因本地 bpy 安装缺少资源而失败，重新安装锁定的 bpy 4.5.3 后通过；渲染测试明确启用 Cycles。`pyproject.toml`、`uv.lock`、Manifest 未改变，新增模型导出依赖位于隔离脚本，正式 Runtime 无新增依赖。
- 实施过程中另有节点源文件、节点测试和 `.blend` 资产并行修改；保留这些变化，本任务未修改对应节点逻辑。

## 镜像与退役清单

`uv run model sync` 正常完成。三款新模型共六个文件从 `https://models.omoolab.xyz` 实际地址回读，大小、SHA-256 和就绪检查全部通过；回读资产依次通过 Lite DirectML、HR CPU、HAT DirectML 生产适配器推理，关闭后缓存为空。完整 URL、大小、哈希与执行结果见 `mirror-validation.json`。

精确清理清单见 `retirement.json`：19 个本地模型/专用缓存目录、12 个 R2 对象。每个本地绝对路径已检查属于其声明的模型或缓存根目录。全部逐项删除并复查不存在，失败项为零；镜像保留的 13 文件大小与删除前一致，项目模型目录只剩九款。用户目录保留的 BEN2、WDN、x4plus 哈希复核通过。结果见 `retirement-results.json`。

清理后的 `uv run model prepare` 再次成功，九款模型共 13 文件大小和 SHA-256 全部通过。OpenSpec strict 校验通过，本次修改的 `git diff --check` 通过。

## HAT Sharper 正式导出

`uv run --script tools/models/hat_export.py --destination .model-cache/hat-sharper-export --checkpoint <已验证官方权重>` 成功退出。

- 上游：XPixelGroup/HAT，revision `1638a9a822581657811867bf670717f8371fc3e5`。
- Checkpoint SHA-256：`5800b67136006eb8cab3b4ed7c8d73b6a195bb18e6cc709b674f9aa069c00271`，严格加载 `params_ema`。
- ONNX：45,874,438 bytes，SHA-256 `032d8b03c704220a08d91465a822aca252c1d6e63db20c3cf23c5fb67f3d2366`，与原实验资产完全相同。
- Apache 2.0 许可证随资产保存，完整资产小于 60 MB。结构检查通过。
- 导出时去除 BasicSR 训练注册器，初始化使用等价 PyTorch 工具；官方 forward 保持不变。FP16 initializer 在 FP32 图计算前 Cast 恢复。

正式资产 ORT 1.24.4、CPU / DirectML 各 4 张 256×256 样图（bread、village、indoor、indoor_grain）逐图对照全部通过；每图执行两次。最差 MAE 0.000190、P99 0.000613、Max 0.007376，全部有限。CPU 加载 1.19 秒、热推理 14.43–14.90 秒；本次 DirectML 热推理 0.787–0.811 秒。性能为当前机器本次运行记录，不将历史不同负载下的耗时作为同条件对照。

详细记录：`.model-cache/hat-sharper-export/numerics.json`；复测脚本 `.model-cache/validate_hat_formal.py`；原始 PyTorch 参考与样图见 `.model-cache/hat-validation` 和原实验临时目录。

HAT 拼接验收：321×163 自然屋顶纹理、跨缝细线、渐变 Alpha，另有 7×5 和 1×1 小图。原始 PyTorch 整图使用与分块一致的反射边界，DirectML 用 256 tile / 48 border，均缩至最终 2×。检查整图参考、分块结果和 8 倍差异图，未见拼接直线。细线图接缝带 MAE 为 0.223（8-bit），与整图 MAE 0.213 接近。

对照图和逐图记录：`.model-cache/hat-sharper-export/seams/*-comparison.png`、`results.json`；脚本 `.model-cache/hat_seams.py`。参考图不是不同构图或不同缩放的替代品。
