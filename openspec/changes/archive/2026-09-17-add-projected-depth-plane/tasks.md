## 1. 删除 Cutout 双击整图入口

- [x] 1.1 删除 Cutout 的 DOUBLE_CLICK 整图绑定、full_image Property、整图 Selection 分支及失去用途的 import，保留共享套索交互。
- [x] 1.2 调整交互和注册测试，验证图片内外双击均不打开 Shape 菜单或提交任务，有效套索继续生成 Shape。

## 2. 新增整图 Depth Surface 转换

- [x] 2.1 增加 ConvertToDepthSurface、菜单入口和正逆序注册，验证静态图片、AI 环境及忙碌状态检查。
- [x] 2.2 扩展共用整图 Job 的 Z/VECTOR 产物选择及 Blender 响应分派，保持普通 Depth Plane 的 Z 路径；验证 VECTOR Depth 和 Tangent Normal 来自一次推理。
- [x] 2.3 复用 common 的图片、深度、材质及对象收尾函数创建 Depth Surface；共用 Plane 的基础 Mesh 和中心矩阵，初始化四项参数及隐藏深度数据。
- [x] 2.4 验证完整颜色、材质槽、深度与法线 Pack、源对象替换、失败清理和单步 Undo。

## 3. 构建定义与几何验证

- [x] 3.1 按业务职责提取共用相机投影和均匀厚度构建步骤，新增 O Image Depth Surface 构建定义，并接入节点组构建和验证索引。
- [x] 3.2 以 O Mesh Plane 的零厚度输出生成完整矩形基础网格，设置 Subdivide、Thickness、Depth Scale、Reference Depth 以及隐藏数据接口，检查 SINGLE 与 socket subtype。
- [x] 3.3 增加合成纹理几何测试：同级 Plane 拓扑与 UV 对照、Depth Scale 0/0.5/1/>1、Reference Depth、相机 Y 方向和非中心主点。
- [x] 3.4 增加零厚度单层、正厚度闭合、透明区域完整矩形、深度跳变连接、材质和临时属性清理验证。
- [x] 3.5 编排新节点组布局与验证入口，覆盖未用输出隐藏、主链及支线间距；记录发布准备时所需的实际绘制尺寸视觉验收项目。

## 4. 回归与交付检查

- [x] 4.1 运行相关转换、交互、注册、Server Job 和节点构建定义测试，修复回归；检查现有 Depth Plane 和圈选 Cutout 的行为。
- [x] 4.2 运行 uv run pytest，记录测试结果及需要 Blender 或已构建新资产才能完成的验收项。按项目总则，代码实施只运行测试，资产构建、二进制产物和节点资产文档同步留给发布准备。


发布准备验收：构建节点资产后，在 Blender 节点编辑器按实际绘制尺寸检查新组总览、投影支线、厚度分支及旁路；检查修改器四项参数的实际显示，并对已发布资产运行几何验证。本次不生成资产或文档产物。

测试记录：全量测试两次均为 723 passed、2 xfailed、62 subtests passed；显式调用 pytest.main 返回 0。两次完整进程均在 pytest 返回后以退出码 1 结束，退出阶段异常尚未定位。新曲面几何、接口、对象定位及失败清理测试全部通过。OpenSpec strict 校验通过。

资产更新记录：已按用户要求运行 build_node --skip-tests，Blender 4.5.10 LTS 构建及三项资产验证均成功。更新后资产与转换回归 53 passed；构建定义和磁盘发布资产使用相同几何用例验证，31 passed，命令退出码均为 0。已同步节点资产说明。Computer Use 应用授权超时，实际节点编辑器视觉验收仍待完成。
