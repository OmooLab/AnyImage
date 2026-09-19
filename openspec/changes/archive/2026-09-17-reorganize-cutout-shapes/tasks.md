## 1. 创建预设与参数协议

- [x] 1.1 将形态标识与入口文案统一为 FLAT / Flat、SOLID / Solid、DEPTH_SOLID / Depth Solid、DEPTH_BALLOON / Depth Balloon，默认 Solid，更新 Pie 与直接 Operator 调用测试。
- [x] 1.2 建立四预设到三资产的映射及默认值，删除旧 Shape 索引协议、旧名称与转发路径，覆盖对象命名和 AI 可用性门控。
- [x] 1.3 确定并实现两个 Cutout 的 Balloon / Uniform 厚度输入，验证默认顺序、倍率与距离语义、零厚度及模式切换；距离 socket 使用 DISTANCE，输入结构使用 SINGLE。

## 2. 三个独立几何节点资产

- [x] 2.1 将 O Image Cutout 构建为直接修改器，合并普通 Balloon 与等厚 Surface 行为；所有预设准备 o_balloon，保证 Flat 可直接增厚。
- [x] 2.2 将已验证的平滑中心场、背面厚度与闭合方法纳入正式构建函数，构建 O Image Depth Cutout 的 Balloon 分支并保留 Uniform 分支。
- [x] 2.3 将原型中防止轮廓耳三角形和内部零轮廓弦退化的处理纳入合适的正式网格模块，增加针对闭合退化的求值测试。
- [x] 2.4 复用公共 Cleanup、Smooth、轴向输出与暂存属性清理；保留 Depth Cutout 的前置 Cleanup、原始深度 Split 和 Edge Smooth 控制。
- [x] 2.5 将 O Image Depth Balloon 改为直接修改器并默认 Double Sided 开启，保留其塑形和单面开关行为。
- [x] 2.6 删除总 Shape 切换器和三个旧子组资产，更新构建清单、节点加载及结构验证；处理同名旧 O Image Cutout 已加载时的新资产识别，避免复用旧接口。

## 3. Normal Map 与材质

- [x] 3.1 在业务层统一法线策略：Flat / Solid 受勾选控制，Depth Solid 固定 OBJECT，Depth Balloon 固定 TANGENT；Job 参数与结果接收共用解析。
- [x] 3.2 更新 Normal Map 工具说明，保持用户勾选值不被深度创建改写，覆盖未就绪时遗留开启值和直接调用 Operator 的测试。
- [x] 3.3 调整 Flat / Solid 共用节点后的材质法线适配，验证从 Flat 增厚以及 Balloon / Uniform 切换时的连接。
- [x] 3.4 验证两个深度入口的法线结果加载、材质连接、双面着色与 Inward Axis 转换。

## 4. 求值与视觉验收

- [x] 4.1 更新接口、默认值、资产集合和几何测试，覆盖三资产直接输出、普通与深度零厚度、Uniform 等厚、Depth Balloon 默认双面。
- [x] 4.2 保留 Cleanup 在 Split 前和 Depth Scale 0 / 0.25 / 1 / 2 / 4 不改变切边拓扑的回归测试。
- [x] 4.3 用已知中心深度加 Balloon 轮廓与噪声的合成曲面验证平滑背面、正面保留及参考深度平移。
- [x] 4.4 复用五张缓存输入，在独立 Blender 脚本中检查 15 个平滑与分离组合的闭合、退化、属性保留和求值时间；渲染背面与侧面，对照已接受原型，不直接控制用户 Blender。
- [x] 4.5 在独立 Blender 节点编辑器按实际绘制尺寸检查三个节点组的总览与局部，验证主轴、重复区域、socket 顺序和未使用输出隐藏。
- [x] 4.6 同步节点资产说明，重建 O_AnyImage.blend，运行全部节点验证和项目测试，记录结果；核对相关未归档规范在后续归档时采用本提案的目标行为。
