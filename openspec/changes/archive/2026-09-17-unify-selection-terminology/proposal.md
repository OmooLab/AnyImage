## Why

当前代码把用户圈定的图像选区称为 `region`，容易与 Blender 的 Viewport Region 混淆，也与界面中的选择概念不完全对应；Cutout 还直接暴露像素采样间距，用户难以判断数值与细节的关系。统一业务术语并改用 Mesh Detail 后，代码、公开协议和界面可以使用更直观且彼此对应的表达。

## What Changes

- **BREAKING**：将表示图像选区的模块、类型、函数、属性、Operator、Job 参数、返回字段和文件名从 `region` 重命名为 `selection`，不保留兼容别名或转发入口。
- 保留 Blender API 固有的 `context.region`、`region_data`、`mouse_region_x` 等名称，以及与选区业务无关的普通空间区域表达。
- 将界面选项 **Fit to Foreground** 恢复为 **Refine Selection**，并同步对应的代码标识。
- 将界面选项 **Generate Normal Map** 缩写为 **Normal Map**；其布尔语义和生成行为不变。
- **BREAKING**：将 Cutout 的连续整数选项 **Mesh Sampling Spacing** 改为四档 **Mesh Detail**；Low、Medium、High、Ultra 分别使用 32、16、8、4 px 的采样间距。
- 同步测试和内部文档，使术语、界面名称与当前实现一致。

## Capabilities

### New Capabilities

- `image-selection`: 规定图像工具和 Cutout 工具对选区的统一表达，以及选区细化、Normal Map 与 Cutout Mesh Detail 选项。

### Modified Capabilities

无。

## Impact

- 影响 `common` 的选区数据与 Viewport 交互、Image Tool、Cutout Tool、Server Job、属性定义、注册入口和相关文件布局。
- 影响 Blender 内部 Operator ID、Job 类型、序列化参数与结果字段；旧名称不再可用。
- 需要同步相关测试与 `docs/internals` 文档；不新增依赖，不改变选区栅格化、AI 细化、Normal Map 生成或既有四种网格采样密度。
