# Frame 多图合成

`operators/frame_tool/operators.py` 定义 `FrameImages` 和 `FrameTool`。`projection.py` 负责视图投影、交叠和结果平面定位，`compositing.py` 负责像素深度排序与边界覆盖采样，`__init__.py` 导出类型及注册清单。Frame 将选中的静态 Image Empty 按当前视图合成为一张图片。

```mermaid
flowchart TD
    A[拖出屏幕矩形] --> B[冻结视图矩阵并收集选中静态图片]
    B --> C[检查矩形与 active 图片的有效投射交集]
    C --> D[按 Region 与 Maximum Frame Resolution 计算输出尺寸]
    D --> E[观察射线投影到各图片平面]
    E --> F[按样本深度从远到近合成，等深度 active 优先]
    F --> G[边界覆盖采样与独立 Alpha]
    G --> H[创建 Packed Image 并复用 active Object]
    H --> I[删除其他参与图片对象并提交 Undo]
```

正交视图接受有限深度，透视视图采样观察方向前方的交点。交叠检查采用连续投影范围；输出尺寸受 Region、最长边上限和总像素上限约束。

RGB 与 Alpha 分别累计，保留被 Mask 隐藏的有效颜色。边界使用覆盖采样，内部复用直接采样，避免黑边和不必要的模糊。结果平面朝向观察者，位置由 active 图片的有效深度确定。

Frame 保留 active 对象身份、名称和 Collection；图像替换复用 [Common](../common.md) 的共享数据与失败恢复逻辑。
