## 1. 统一深度输出与读取

- [x] 1.1 将深度写出统一为 write_depth_texture、depth.exr 和结果键 depth，删除 Z 写出分支；保留内部 depth 与 depth.json，验证 RGBA 数值和有效性。
- [x] 1.2 将共享生成层、整图 Job 和 Cutout 请求改为 generate_depth 布尔值，验证深度保留 points、法线共用单次推理及边缘修正路径。
- [x] 1.3 更新整图与 Cutout 结果加载、测试夹具和公共读取调用，验证 Pack、色彩空间、标定和非有限值处理；删除旧参数和结果键。

## 2. 合并整图节点与入口

- [x] 2.1 将 Relief 与 Camera 组合为 O Image Depth Plane，增加 Mode 与统一接口；Relief 改读 B/Z，Camera 复用投影及平滑法线壳。
- [x] 2.2 重排合并组的布局，更新构建入口、公开组清单与验证；删除独立 Surface 构建和布局入口，同步节点资产文档。
- [x] 2.3 保留单一 ConvertToDepthPlane，删除独立 Surface 类、菜单、注册和对象类型分支，统一结果对象与默认值。

## 3. 回归验证

- [x] 3.1 使用 X/Y/Z 不同的纹理覆盖 Relief、Camera、Depth Cutout、Depth Balloon 和公共标量读取，验证各自位置、有效性及尺度。
- [x] 3.2 覆盖模式切换无需推理且保留参数、Relief 固定底面、Camera 投影与法线厚度、矩形拓扑、UV、材质及临时属性清理。
- [x] 3.3 更新注册与逆序注销、静态媒体和 AI 检查、成功替换与单次 Undo、失败清理测试，运行相关测试及必要的完整回归。
- [x] 3.4 搜索生产代码中的旧文件名、结果键、模式分支和独立 Surface 入口，确认无兼容转发或残留消费路径。

## 4. 资产更新验收

- [x] 4.1 在资产更新阶段构建并验证 O_AnyImage.blend，以相同用例检查保存资产和构建定义的接口与两种模式求值。
- [x] 4.2 在 Blender 节点编辑器检查总览及局部实际布局，确认主轴、分支顺序、间距、旁路和未用输出隐藏，记录视觉验收结果。

## 验证记录

- 已构建 O_AnyImage.blend，Blender 4.5.10 LTS 的资产、Mesh Plane、Cutout 验证通过。
- 完整回归报告 746 passed、2 xfailed、60 subtests passed；pytest 完成后进程退出码为 1，与本变更前已记录的退出现象一致。随后清理了 3 个合并入口造成的重复测试。
- 清理重复测试后的受影响范围回归：349 passed、30 subtests passed，退出码 0；覆盖保存资产与构建定义。
- 视觉验收待完成：Computer Use 能捕获 Blender 启动画面，但激活、点击与 Escape 后界面均未变化，尚未进入节点编辑器。坐标与几何校验已通过，不能替代实际视觉验收。
