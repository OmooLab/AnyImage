# 节点资产

## 资产清单

节点组由 `nodes/groups/` 中的构建模块定义，共用构建逻辑位于 `nodes/common/`。

| 节点组                    | 构建模块                    |
| ------------------------- | --------------------------- |
| `O Image Plane`           | `image_plane.py`            |
| `O Image Depth Plane`     | `image_depth_plane.py`      |
| `O Image Relief Plane`    | `image_relief_plane.py`     |
| `O Image Cutout`          | `image_cutout.py`           |
| `O Image Depth Cutout`    | `image_depth_cutout.py`     |
| `O Image Cutout Symmetry` | `image_cutout_symmetry.py`  |
| `O Image Layer`           | `image_layer.py`            |
| `O Image Depth Layer`     | `image_depth_layer.py`      |
| `O Shadeless`             | `shadeless.py`              |
| `O Image Depth Panorama`  | `image_depth_panorama.py`   |

## 构建节点资产

生产节点组由 `uv run --group blender node-group build` 构建到 `src/anyimage/assets/O_AnyImage.blend`。该文件是 Git 忽略的发布构建产物；CI 与本地发布都从节点源码重新生成。

节点组规则：

- 字段默认直接连接，多个消费者可复用同一输出；按消费位置的几何、域、类型和输入属性版本验证求值等价性
- 所有几何节点、嵌套组及测试辅助图禁止使用 Capture Attribute；构建定义和保存资产递归检查 Capture 为零
- 域转换使用 Evaluate on Domain 或明确域的采样节点表达；跨几何变化优先调整消费顺序或在源几何上采样，明确索引对应关系
- Store Named Attribute 用于实际命名协议或仍需跨几何变化保存的最少数据，逐项明确名称、类型、域、Selection、写入阶段、消费者及必要性；内部临时属性使用 `_o_` 前缀，在最后消费者之后用通配符 `_o_*` 清理，保留 UV、用户属性和外部协议属性。清理必须走 `remove_attribute_pattern`：按精确名称删除时，若某个几何分支从未写入该属性，Remove Named Attribute 会报出缺失警告
- Group Input 按区域重复放置，通过字段排列和必要的 Reroute 保持连线可读，隐藏未使用输出；存储须有数据生命周期依据
- 构建阶段通过明确的节点或 socket 引用接线
- 保留节点默认 `name` 和标题，不用 `label` 覆盖，不用 String 节点注解。Frame 仅用于确有包裹语义的区域
- 全接线的简单数学运算可折叠；需要阅读的常数、运算域和模式保持可见
- 比较统一用 Compare 节点并按操作数数据类型选择输入，布尔运算统一用 Boolean Math，不用 Math 节点做比较、也不用数值乘法代替布尔运算；材质树不支持这两个节点，仍用 Math
- 修改器 Geometry Nodes 的输入 socket 默认使用 `SINGLE`
- socket `subtype` 按业务语义设置：长度用 `DISTANCE`，`0–1` 比例用 `FACTOR`，`0–100` 用 `PERCENTAGE`；无对应范围语义时保留默认
- 接口或布局变更须验证 socket 顺序与结构、未使用输出隐藏及几何求值；纯布局变更比较运算、默认值和实际连接，确认功能不变

## 构建资产脚本

`tools/nodes/build.py` 按依赖顺序加载 `nodes/groups/` 的定义，调用 `arrangement/` 统一排列几何节点组后保存。`nodes/common/` 提供共用构建函数：`nodes.py` 创建接口与节点，`depth_surface.py`、`cutout.py` 等组装几何，`shader.py` 构建材质着色节点，`material_slots.py` 继承几何材质槽；`tools/nodes/preview/` 导出交互预览。

命令通过当前 uv Python 的独立子进程执行构建、检查和预览，`bpy` 由 `blender` dependency group 提供。保存后，`check.py` 重新加载资产并做基本几何求值；`tests/nodes/` 覆盖节点定义行为，`tests/tools/nodes/` 覆盖工具行为。CI 使用同一入口先生成资产，再运行常规测试和打包。

```bash
uv run --group blender node-group build
uv run --group blender node-group build --skip-tests
uv run --group blender node-group check
uv run --group blender node-group preview
```
