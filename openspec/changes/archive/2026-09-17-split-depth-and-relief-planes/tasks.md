## 1. 补齐 Alpha 规则

- [x] 1.1 获取用户节点连接参考图，记录 Alpha 采样、阈值、字段域、删除模式和宽松边界结果，补齐 design 与 Alpha 规格；本项完成后实施第 4 组任务。

## 2. 转换入口与法线

- [x] 2.1 新增 ConvertToReliefPlane、菜单项与注册清单，ConvertToDepthPlane 改为相机投影语义，复用整图任务调度函数。
- [x] 2.2 为整图 Job 增加可序列化转换类型参数，Depth 生成 object_normal，Relief 生成 tangent_normal，验证各自产物键与深度协议。
- [x] 2.3 按转换类型加载节点组和法线，绑定 OBJECT / TANGENT 材质空间，保持对象替换、Undo 与失败清理行为。

## 3. 独立节点资产

- [x] 3.1 将相机投影与浮雕分别整理为 O Image Depth Plane 和 O Image Relief Plane 构建脚本，删除 Mode 与跨模式接口、旧连接及无用引用。
- [x] 3.2 整理两组布局与验证脚本，确认接口顺序、参数默认值、未使用输出隐藏，以及独立 Thickness 和 Normal Smooth 的归属。

## 4. 节点内 Alpha 剔除

- [x] 4.1 为 Depth Plane 添加默认开启的 Valid Only ，复用现有 Depth Image 输入读取 depth.exr 的有效性 Alpha。
- [x] 4.2 按已确认参考图在细分后、投影前连接宽松剔除，关闭开关时旁路完整网格，保留 UV 并衔接厚度计算。
- [x] 4.3 验证全无效、全有效、中间有效性、混合边界与细窄区域，检查 Subdivide 改变后重新求值及零厚度、正厚度结果。

## 5. 测试与接口说明

- [x] 5.1 更新入口、注册注销、Job 产物、对象创建与材质测试，覆盖 Object Normal 轴向和 Relief 行为。
- [x] 5.2 更新节点结构与几何求值测试，按参考图检查运算、默认值、域及连接，覆盖开关和动态细分。
- [x] 5.3 同步节点资产文档中的两个资产接口与处理流程，检查当前源码和资产脚本中的旧模式引用。
- [x] 5.4 完成最终全量测试并确认正常退出。节点资产与转换相关 69 项测试通过，退出码 0。

## 6. 后续节点资产更新阶段

- [x] 6.1 已按用户授权构建 src/anyimage/assets/O_AnyImage.blend，Blender 4.5.10 的资产清单、接口、布局与几何验证通过。
- [x] 6.2 在 Blender 中按实际节点尺寸检查总览与局部布局，并以风景透明图检查剔除轮廓、厚度、细分调节和对象旋转后的法线表现。


## 7. 复用 Cutout Smooth

- [x] 7.1 在 Depth Plane 最终几何上复用 expand_smooth，沿用 Smooth 与 Smooth Weight 的默认值、范围及接口归属。
- [x] 7.2 覆盖零厚度和正厚度的平滑、关闭平滑、面连接与 UV 保持，并同步节点资产说明。
- [x] 7.3 节点资产已重建，Blender 资产验证和 69 项相关测试通过。
