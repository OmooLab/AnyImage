## 1. 统一 AI 设置绘制

- [x] 1.1 在共享图像交互模块中提取可复用的 AI 设置入口和 AI 依赖属性绘制函数，单次绘制复用同一状态
- [x] 1.2 调整 Image Box、Image Lasso 及其区域 operator 设置，使未就绪时的 AI 设置按钮位于依赖属性之前
- [x] 1.3 调整 Cutout 工具设置顺序，使 AI 设置入口开头只出现一次，并分别门控 `Fit to Foreground` 与 `Generate Normal Map`，保持 mesh spacing 可用

## 2. 门控 Cutout 交互

- [x] 2.1 根据 `ai_ready()` 在 Cutout shape pie 中选择两个本地 shape 或完整四个 shape
- [x] 2.2 在 Cutout 交互读取边界忽略 AI 未就绪时遗留的 `Generate Normal Map` 真值，并保持 `Fit to Foreground` 的既有门控

## 3. 验证行为

- [x] 3.1 补充共享工具设置测试，验证 AI 设置按钮顺序、依赖属性启用状态以及 Cutout 非 AI 属性可用性
- [x] 3.2 补充 Cutout pie 测试，验证 AI 未就绪时两个 shape、就绪时四个 shape及遗留 AI 设置不会传入 operator
- [x] 3.3 运行相关 Blender addon 与 Cutout interaction 测试并确认通过

## 4. Blender 5.2 Enum Compatibility

- [x] 4.1 Convert integer menu indices to string enum identifiers for runtime RNA modifier inputs while preserving the legacy ID property path
- [x] 4.2 Add regression tests for runtime enum and non-enum modifier inputs, then run the related test suite
