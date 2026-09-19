## Context

`O Image Depth Balloon` 当前以原始 Cutout 网格作为对称平面上的轮廓，通过 `o_balloon` 和深度差构建两侧。新需求已经用用户提供的小车图完成独立实验：正面投射后截留正 Z 区域，两侧围绕固定 XY 平面镜像，并以直壁连接对应外边界。

实验文件位于 `C:/Users/icrdr/AppData/Local/Temp/anyimage-car-symmetry/`：`car-depth-balloon-fast-modes.blend`、`fast_balloon.py`、`performance-results.json`、`mode-validation.json`。这些是可复核的实验材料，正式实现和测试自行提供所需资源。

## Goals / Non-Goals

**Goals:** 双模式、手势预设、完整对称网格、独立且可复用的节点构建、统一命名。

**Non-Goals:** 本变更不包含旧资产兼容层、AI 模型调整或自动推断最佳车身对称方向。

## Decisions

### 名称与手势

| 对象 | 名称 |
|---|---|
| 功能与菜单 | `Depth Symmetry` |
| 节点组 | `O Image Depth Symmetry` |
| 构建模块与入口 | `image_depth_symmetry.py` / `build_image_depth_symmetry_group()` |
| Shape 标识 | `DEPTH_SYMMETRY` |
| Mode 顺序 | `Balloon`、`Projected` |

`Balloon` 描述原有鼓起方式；`Projected` 描述新模式的投射轮廓。功能名称表达两者共同的对称职责，避免用其中一个模式命名整个节点组。

| 手势 | Depth Cutout（现有） | Depth Symmetry |
|---|---|---|
| Lasso | Balloon | Balloon |
| Polyline | Shell | Projected |

在 Cutout 对象创建阶段按 gesture 设置 Mode。预设只影响初值，用户仍可直接切换节点 Mode。裸节点默认 Balloon，保持原有入口的默认行为。

### 直接构建 Projected 正面

复用 `_position_field` 读取 Depth Image 的相机 XYZ，乘以 Uniform Scale，将 Y 转为现有 Cutout 坐标约定，以 `Reference Depth − metric depth` 构建 Z。Depth Scale 沿用已验证的平面坐标与相机坐标插值，并缩放深度差。

将 Depth Direction 对应的方向对齐到局部 Z 轴，输出成形坐标中的正面。Reference Depth 和 Depth Direction 共同改变位移与投射后的轮廓；最终镜像面固定在成形坐标 `Z=0`，不把镜像结果转回倾斜平面。既有 Depth Axis 作为统一的最终坐标变换保留。

复用公共边界平滑，随后在 POINT 域判断负 Z，并在 FACE 域判断是否包含越界顶点。删除包含越界顶点的整面及其失去面的边线、孤点。仅保留正 Z 面，不产生压扁在对称平面上的外围裙边。平面附近使用与几何尺度相适应的小容差处理零厚度退化。

采用整面删除，因为它只依赖现有网格与字段求值；相较精确裁切，边界具有网格分辨率级别的近似。新分支不使用 Mesh Boolean，也不嵌套 Depth Plane、Depth Cutout 节点组。

### 镜像与直壁

先完成正面和平滑，再镜像到负 Z，避免封闭后的全网格平滑破坏直壁。以边的面邻接数识别正面外边界，将每个边界点 `(x,y,z)` 与 `(x,y,-z)` 连接；生成的侧壁沿 Z 轴延伸，其法线垂直于 Z 轴。保留正背面平滑着色，侧壁使用平面着色。

合并对应顶点，正确处理对称平面上的零厚度边。Double Sided 打开时生成完整封闭网格；关闭时沿用已验证原型的正面预览行为。Balloon 分支原有 Double Sided、Thickness、平滑等语义保持不变。Thickness 继续控制 Balloon 轮廓；Projected 的形体由 Depth Scale、Reference Depth、Depth Direction 控制，不引入未经验证的厚度推断。

### 复用与模式分派

复用公共节点接口、深度采样、岛清理、边界平滑、普通平滑和属性函数。节点内部保留直接构建的两条几何分支，通过 Mode 选择；共享最终输出和坐标约定，不通过嵌套节点组包装旧实现。

Projected 需要局部辅助函数时放在该业务模块；只有确有其他消费者的函数才进入 common。UV 和现有命名属性继续随拓扑传递，新增临时属性需要明确生命周期；源码与保存资产中 Capture Attribute 数量均为零。

### 性能与验证

同一小车输入、相同参数与 3 次边界平滑，预热 4 次后连续修改 Reference Depth，记录 24 次依赖图求值的中位数。外部实验的双模式 Projected 分支结果如下：

| 输入顶点 | 布尔原型 | 双模式直接构建 | 提速 |
|---|---:|---:|---:|
| 27,860 | 174.9 ms | 30.9 ms | 约 5.7 倍 |
| 165,771 | 960.7 ms | 135.6 ms | 约 7.1 倍 |

这些数值是当前机器的对比证据，不作为跨机器测试断言。正式验证保留同输入、同平滑、同参数的对照，并分别记录 Reference Depth 与 Depth Direction 调整耗时。几何测试覆盖封闭性、顶点流形性、面绕序、XY 镜像、直壁法线、越界删除、空结果及模式切换；Balloon 分支与变更前的基准几何比较。

## Risks / Trade-offs

- 整面删除使切口随网格密度离散变化 → 使用已有采样密度控制，比较多个密度与连续参数变化，明确其为近似边界。
- 深度噪声可能形成小岛或点接触 → 复用岛清理，测试连通性与顶点流形性，退化处删除无效拓扑。
- 在补壁后平滑可能令侧壁弯曲 → Projected 的平滑在正面阶段完成，再镜像和补壁。
- 只在中等网格测量可能掩盖扩展成本 → 同时验证普通与加密输入，记录求值而非渲染耗时。
- 资产与代码名称失配 → 同步重命名 Shape 标识、模块、校准函数、构建/校验清单和界面文本，构建保存资产后检查旧引用。

## Migration Plan

实现时整体替换旧名称并更新相关代码、测试和节点资产，不保留旧路径或别名。通过 `uv run node-group build` 构建并验证 `O_AnyImage.blend`，检查新组存在、旧组不再由构建产出。已保存在用户工程中的旧节点组不执行自动扫描或重写。
