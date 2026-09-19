# 内部实现总览

AnyImage 在 Blender 主线程处理交互、像素编辑和数据创建，通过 BlendJob 把模型推理交给独立 Job Server。

| 主题 | 对应职责 |
| --- | --- |
| [程序架构](architecture.md) | 进程、注册、配置与主线程边界 |
| [Common](common.md) | Blender 侧图像、手势、几何与 AI 公共能力 |
| [Runtime 与 Server](runtime.md) | Environment、Job、模型下载与 Session 生命周期 |
| [Job 产物](outputs.md) | 文件协议、相机坐标和 Blender 消费方式 |
| [Operator 索引](operators/index.md) | 按实际用户功能查找实现 |
| [节点资产](node-assets.md) | 资产、源码职责、构建和验证 |
| [开发与发布](development.md) | 测试组织、工具命令与发布流程 |

源码位于 `src/anyimage/`，开发工具位于 `tools/`，自动化测试位于 `tests/`。扩展级设置由 `preferences.py` 定义，运行时资源由 `runtime.py` 接入 BlendJob。
