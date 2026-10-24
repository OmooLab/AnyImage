## Why

将现有本地图像与建模工具发布为可提交 Blender Extensions 的 AnyImage Base，让用户独立使用基础功能。通过一份基础实现和同一次 CI 构建维护 Base 与完整版，保持版本边界清晰、维护简单。

## What Changes

- 新增显示名称 `AnyImage Base`、Manifest ID `anyimage_base` 的独立发行包；完整版继续使用 `AnyImage` 和 `anyimage`。
- Base 保留剪贴板导入、普通平面、Frame、Mask、Rectify、Cutout Flat/Solid 及本地 Balloon、调色和 Bake Mesh。
- Base 安装包彻底排除 AI 专用 Python 代码、Server、模型与下载配置、任务运行依赖、设置、UI 和翻译条目。两版使用完全相同的节点资产文件。
- 基础功能维护一份源码，拆开混合模块中的本地操作与 AI 操作，以明确文件清单和少量版本入口组装发行包。
- 两版共用现有 Blender 注册 ID、Scene 属性和快捷键，择一启用。先启用的保留，后启用的在产生注册副作用前报告冲突。
- 同一版本标签、同一次 CI 生成两版在三个现有平台上的六个 ZIP，并验证实际产物。

## Capabilities

### New Capabilities

- `base-edition`: Base 功能范围、产物纯净性、身份及两版互斥启用。
- `edition-packaging`: 两版共用源码、节点资产、版本号和发布流水线的打包与验证契约。

### Modified Capabilities

无。既有功能规格继续描述完整版；Base 的发行范围由新增规格明确。

## Impact

影响插件注册、偏好设置、属性、菜单、面板、工具栏、平面与 Cutout 入口及其共用模块，涉及 `tools/pack.py`、依赖声明、Manifest、Release CI 和相关测试。基础依赖按真实调用保留，完整版行为保持。节点资产沿用同一次构建产物。交付包含适合提交官方仓库的 Base 包及校验；仓库上传由发布者执行。
