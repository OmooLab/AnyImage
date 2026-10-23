# 节点资产

## 源码与资产清单

节点资产由 PyPI 的 `omoonodes` 管理，依赖版本锁定在 `blender` dependency group。`nodes/O_AnyImage/` 是资产库目录，`collection.json` 将 `O_AnyImage.blend` 映射到库内的 `O_AnyImage/` 源码目录。

源码采用 `omoonodes dump` 导出的 nodebpy 写法，通过 `TreeBuilder`、节点类型和 socket 引用定义接口与连线。

| 节点组 | 源码（相对于 `nodes/O_AnyImage/O_AnyImage/`） |
| --- | --- |
| `O Image Plane` | `geometry/o_image_plane.py` |
| `O Image Depth Plane` | `geometry/o_image_depth_plane.py` |
| `O Image Relief Plane` | `geometry/o_image_relief_plane.py` |
| `O Image Cutout` | `geometry/o_image_cutout.py` |
| `O Image Depth Cutout` | `geometry/o_image_depth_cutout.py` |
| `O Image Cutout Symmetry` | `geometry/o_image_cutout_symmetry.py` |
| `O Image Depth Panorama` | `geometry/o_image_depth_panorama.py` |
| `O Image Layer` | `shader/o_image_layer.py` |
| `O Shadeless` | `shader/o_shadeless.py` |

## 构建与验证

在项目根目录执行以下命令（Git Bash）：

```bash
uv run --group blender omoonodes build
mkdir -p src/anyimage/assets
cp dist/b45/O_AnyImage/O_AnyImage.blend src/anyimage/assets/O_AnyImage.blend
uv run --group blender pytest tests/nodes
```

OmooNodes 默认读取 `nodes/`，目标为 `b45`，由工具包准备默认版本的隔离 Blender 环境；项目直接使用这些默认值，无需配置 `[tool.omoonodes]`。

构建与校验成功后，资产库输出到 `dist/b45/O_AnyImage/`。CI 使用同样的构建和复制步骤，再运行测试与打包。`src/anyimage/assets/O_AnyImage.blend` 是 Git 忽略的发布产物；插件运行时通过 `load_node_group(group_name)` 加载其中的节点组。

`tests/nodes/` 覆盖节点求值、接口、布局和属性协议；`test_inventory.py` 重新加载保存资产，检查资产清单、接口一致性和几何行为。修改节点逻辑、接口或布局后，应重新构建、复制资产并运行相关测试。

## 在 Blender 中编辑

先从源码生成开发库：

```bash
uv run --group blender omoonodes dev nodes/O_AnyImage
```

在 Blender 中打开 `workspaces/b45/O_AnyImage/O_AnyImage.blend`，编辑并保存节点资产，再同步回源码：

```bash
uv run --group blender omoonodes dev nodes/O_AnyImage --sync workspaces
```

同步后检查源码差异，再按上面的构建与验证步骤更新发布资产。

## 首次导入

导入现有 `.blend` 前，先将需要导出的节点组标记为 Asset 并保存。`dump` 将资产节点组导出为 nodebpy 源码，同时生成 `collection.json` 并验证往返构建。目标目录必须尚不存在：

```bash
uv run --group blender omoonodes dump path/to/O_Library.blend -o nodes/O_Library
```

已有资产库通过 `dev --sync` 同步 Blender 中的修改。

## 节点规则

- 字段默认直接连接，多个消费者可复用同一输出；按消费位置的几何、域、类型和输入属性版本验证求值等价性。
- 所有几何节点、嵌套组及测试辅助图禁止使用 Capture Attribute；源码构建和保存资产均检查 Capture 为零。
- 域转换使用 Evaluate on Domain 或明确域的采样节点表达；跨几何变化优先调整消费顺序或在源几何上采样，明确索引对应关系。
- Store Named Attribute 仅用于实际命名协议或跨几何变化必需的最少数据，明确名称、类型、域、Selection、写入阶段及消费者。内部临时属性使用 `_o_` 前缀，在最后消费者之后用 Remove Named Attribute 的 Wildcard 模式清理 `_o_*`，保留 UV、用户属性和外部协议属性。
- 通过区域内输入、字段排列和必要的 Reroute 保持连线可读；存储须有数据生命周期依据，构建阶段通过明确的节点或 socket 引用接线。
- 保留节点默认 `name` 和标题，不用 `label` 覆盖，不用 String 节点注解；Frame 节点仅用于确有包裹语义的区域。
- 全接线的简单数学运算可折叠；需要阅读的常数、运算域和模式保持可见。
- 几何树比较使用 Compare，布尔运算使用 Boolean Math；材质树使用 Math。
- 修改器 Geometry Nodes 的输入 socket 默认使用 `SINGLE`；socket `subtype` 按语义设置，长度用 `DISTANCE`，比例用 `FACTOR`，百分比用 `PERCENTAGE`。
- 接口或布局变更须验证 socket 顺序与结构及几何求值；纯布局变更比较运算、默认值和实际连接，确认功能不变。
