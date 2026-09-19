## Why

材质的 Image Texture 节点目前无法直接使用 AnyImage 去背景和放大。用户需要在节点右键菜单中完成处理，并像 Empty Image 一样在当前位置使用结果。

## What Changes

- 在材质 Shader Editor 的有效 Image Texture 节点右键菜单增加 AnyImage 菜单，提供 Remove Background 和 Upscale。
- 复用现有 AI 环境准备、模型配置、输入限制、任务进度和图片处理流程。
- 处理成功后原位更新目标节点图片，保留节点、连线及设置；单独使用的图片保留 Image 身份，共享图片仅替换当前节点的绑定。
- 为异步目标校验、失败恢复、撤销重做和菜单注册增加覆盖。

## Capabilities

### New Capabilities

- `texture-node-image-actions`: 材质 Image Texture 节点的 AI 图片操作入口及原位提交语义。

### Modified Capabilities

无。

## Impact

涉及 `src/anyimage/menu.py`、扩展注册入口、Remove Background / Upscale Operator、`common` 图片输入与提交逻辑及对应测试。服务端沿用现有 Job 协议，依赖和节点资产保持现状。
