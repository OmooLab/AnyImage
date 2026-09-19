# production-only-ai-workflows Specification

## Purpose
TBD - created by archiving change remove-debug-workflows. Update Purpose after archive.
## Requirements
### Requirement: Blender exposes production AI workflows

扩展 MUST 移除 Debug 主面板、DA3 / MoGe-2 / BEN2 / Upscale 子面板及四个 `anyimage.debug_*` Operator，并保持正式类型注册和逆序注销完整。

#### Scenario: Extension registration lifecycle
- **WHEN** 扩展注册、注销并重新注册
- **THEN** Debug 面板和 Operator 均不在注册清单中，正式面板与 Operator 正常可用

### Requirement: Server registers production jobs only

Server MUST 移除 `debug-da3`、`debug-moge2`、`debug-ben2` 和 `debug-upscale` Job 及其处理实现，不提供兼容入口。

#### Scenario: Registered jobs
- **WHEN** Server 加载 Job 注册清单
- **THEN** 四个 Debug Job 均缺席，正式 Job 保持已注册且可执行

### Requirement: Debug implementation is removed completely

源码和扩展文件选择 MUST 移除 Debug 专用模块、Scene 参数、UI 辅助函数、参数组装、原始预测序列化、帧复制及相应导入和导出。

#### Scenario: Source and packaging boundaries
- **WHEN** 检查模块引用与扩展打包文件清单
- **THEN** `operators/debug.py`、`server/jobs/debug_predictions.py`、`server/outputs/` 和 Debug 专用辅助实现均缺席，保留模块可正常导入

#### Scenario: Scene settings
- **WHEN** 读取 `AnyImageSettings` 的属性声明
- **THEN** Debug 专用属性已删除，正式使用的 `video_frames`、Cutout 和 Mask 属性保持可用

#### Scenario: Debug-only model dependencies
- **WHEN** 加载模型目录与缓存 Resource
- **THEN** DA3 模型声明、推理模块与缓存分支均已移除，正式 MoGe-2、BEN2 和 Upscale 模型保持可用

### Requirement: Shared production inference remains available

系统 SHALL 保持正式深度处理、Cutout、Remove Background 和 Upscale 所需的模型、输入校验、设备选择、多帧处理及内存释放行为。

#### Scenario: Production model requests
- **WHEN** 正式 Operator 组装并提交 AI 请求
- **THEN** 请求使用正式模型参数及 Add-on Preferences 设备设置，输入校验和视频帧数传递保持有效

#### Scenario: Production output and memory lifecycle
- **WHEN** 正式 Job 完成单帧或多帧模型推理
- **THEN** 生成对应正式产物，并按既有最终推理边界请求内存释放

