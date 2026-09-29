## Why

当前颜色匹配的签名提取增加启动耗时，独立色度与明度控制也让结果难以直观预测。参考色板需要保留鲜艳、小面积的代表色，同时让迁移算法和交互更直接、易验证。

## What Changes

- 使用 materialyoucolor 3.0.4 的 Celebi 与 Score 提取最多四个代表色，保留 Pillow 依赖，色板独立于迁移计算。
- 内置基于 color-matcher 0.6.0 的 NumPy HM–MKL–HM 实现，并对两次 HM 的映射曲线做连续平滑与斜率限制，保留来源与许可声明，移除 color-matcher 运行依赖。
- **BREAKING**：Modal 改为水平移动调整 0–100% Mix；0% 为原图，100% 为完整匹配结果，中间直接 RGB 混合；移除 Color / Lightness 双轴控制。
- 选择参考时准备参考统计和色板，后续匹配复用有效缓存；鼠标移动仅混合已计算的预览结果。
- 缩小侧边栏参考图画廊及弹出选择窗口，减少其对面板空间的占用。
- **BREAKING**：移除旧签名、锚点传输、独立亮度映射、抖动、色域压缩及其失效接口和测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `color-reference-matching`：固定 HM–MKL–HM、参考预处理缓存与依赖边界。
- `interactive-color-matching`：单轴 Mix、预览复用与提交语义。
- `color-match-panel`：独立 Material 代表色与面积权重。

上述能力目前位于已完成但未归档的颜色功能 changes 中；本提案以前序 change 的要求为基线，归档时先合并前序能力，再应用本次 delta。

## Impact

涉及 common 的颜色匹配与色板模块、颜色参考 Operator、参考属性更新与注销清理，以及对应测试。实施时同步检查 pyproject.toml、uv.lock、blender_manifest.toml 和打包测试，保留已有无关修改。仅生成本提案，实施另行开始；不构建文档或打包扩展。
