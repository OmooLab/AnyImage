## Why

全景生成后需要手动添加和调整 Light Probe Volume。自动按求值后网格配置探针，可以减少布光准备操作，并通过原点各方向的距离上限控制大型全景的探针范围。

## What Changes

- Preferences 新增默认开启的全景 Volume 自动创建开关，以及默认 20 m 的单向距离上限。
- 全景生成成功时按世界空间网格边界创建一个 Volume，六个方向分别限制距离。
- 每轴分辨率按截限后长度的米数向下取整，尺寸向上取整到整米，并调整中心保证覆盖截限范围。
- 探针作为全景物体的子物体，关闭 Capture → Contributions → Indirect Light。
- 自动隔离其他物体和灯光，仅捕获全景并烘焙新建探针，结束后恢复场景状态。
- 探针与全景一起完成创建、烘焙、失败清理和撤销，结果网格保持活动选择。

## Capabilities

### New Capabilities
- `panorama-light-probe`: 全景探针偏好、边界计算、尺寸与采样配置，以及创建事务。

### Modified Capabilities

## Impact

- `preferences.py` 及翻译目录：配置定义、读取入口和界面。
- `operators/convert_to_panorama/`：结果求值、探针创建与清理。
- 对应 Preferences 和全景转换测试；使用 Blender 内置 LightProbe API。
