# 实施验收

验收日期：2026-10-06。任务组沿用审查编号 1–15，第 16 组记录整体验证。

| 任务组 | 核对结果 |
| --- | --- |
| 1 | Bake 成功移除 `o_image_object`，对象菜单和图片目标识别退出，Undo/Redo 恢复及清除标记；贴图节点入口与参考候选类别过滤保持原有行为 |
| 2、6、7 | Scene 参考按实际引用释放，公共数据与属性协调分层，长期缓存仅保留摘要、签名、色板与缩略图；连续编辑、跨 Scene、删除、load、Undo/Redo 和注销覆盖通过 |
| 3 | 色板控件交互保留，匹配算法输入保持原有约定；只读交互继续暂缓 |
| 4、8 | Bake 按纯几何、Color 拼接和 Normal 烘焙验证，临时 Color 图片复用公共创建能力；动画 Color 采样保留、数值与渲染、共享数据、保存重载和失败回滚覆盖通过 |
| 5、12 | UI 本地安装检查和缓存快照读取通过；同尺寸损坏文件在 Session 创建前失败，可重新下载；模型 key、档位与枚举编号统一由目录声明 |
| 9、10、11 | 去背景收拢到业务包，颜色匹配按业务命名，Polygon 暴露明确公共接口；旧源码路径和 Viewport 转发访问已清理 |
| 13、14 | 参考测试按职责拆分，跨测试文件辅助能力移到 `tests/support`；节点无用定义和无效状态参数已清理 |
| 15、16 | 内部文档链接与源码路径、Python 语法、旧引用、差异空白和 OpenSpec 严格校验通过 |

## 自动化验证

- `uv run --no-sync --group blender --group ai pytest -q`：1099 passed、105 subtests passed，160.31 秒，退出码 0。
- `uv run --no-sync --group blender node-group build`：生成并校验 10 个保存节点组；169 项节点与工具测试通过，108.92 秒；退出码 0。生成资产位于项目约定的本地构建路径，Capture Attribute 校验通过。
- `openspec validate refine-image-workflow-boundaries --strict`：通过。
- `git diff --check`：通过。内部文档的相对链接及源码路径检查通过。

## 真实 GPU 验证

`tests/support/image_preview_gpu.py` 在独立前台 Blender 图形上下文中加载实际颜色转换、GPUTexture 和共享预览 Shader，绘制非对称中灰、彩色和半透明像素，并读取 framebuffer。验证普通 RGBA8 与 SRGB8_A8 两条显示编码路径，RGB 容差为 `2/255`。

| Blender | RGBA8 最大误差 | SRGB8_A8 最大误差 | 结果 |
| --- | --- | --- | --- |
| 4.5.14 LTS | 0.001961 | 0.001389 | 通过 |
| 5.2.2 LTS | 0.001961 | 0.001389 | 通过 |

验证入口：`blender --factory-startup --python tests/support/image_preview_gpu.py -- temp/gpu.json`。脚本写入 JSON 结果后关闭本次验证实例。pytest 中的 Mock 测试继续验证上传参数、绘制调用和错误清理，GPU 数值验证独立执行。
