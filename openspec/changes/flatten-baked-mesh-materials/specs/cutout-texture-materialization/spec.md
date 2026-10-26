## MODIFIED Requirements

### Requirement: Convert To results support static mesh conversion

系统 SHALL 为 Plane、Depth Plane、Relief Plane、Panorama 提供同一个 Convert to Mesh 入口，保留求值几何、单区 UV、Color 内容与材质身份。法线存在时 SHALL 将其当前空间及属性处理固化到原 Normal 图片，再清除已消费属性；Normal Scale 与 Bump SHALL 固化到最终法线图；结果材质 SHALL 使用标准节点承接 O Image Layer 输出。

#### Scenario: Convert a depth or relief plane
- **WHEN** 用户转换带 Object Space 法线的 Depth Plane 或带 Depth Scale、边缘衰减的 Relief Plane
- **THEN** 法线烘焙到现有单区 UV，使用 Strength=1 的标准 Tangent Normal Map，删除协议属性后有效表面的法线编码误差 95% 分位小于 0.04

#### Scenario: Convert an ordinary plane or panorama
- **WHEN** 用户转换没有 Normal 的 Plane 或自发光 Panorama
- **THEN** 固化几何，保持 Color；Shadeless 保持材质及采样设置，含 O Image Layer 的材质按静态输出规则替换；仅在无源法线且无 Bump 时跳过法线烘焙

### Requirement: Converted normal maps are static

转换 SHALL 把当前法线图经过旋转、镜像、正背适配、Depth Scale、位置相关衰减与 wall 禁用后的效果，连同当前 Normal Scale 和 Bump，固化为最终 UV 下的 Tangent Normal。结果 MUST 不依赖 AnyImage 法线属性；有效网格法线、平滑和锐边 SHALL 保留。

#### Scenario: Convert a rotated symmetric depth object
- **WHEN** 对带非平坦法线图、非默认 symmetry 方向与接缝衰减的 Cutout 执行转换
- **THEN** 清理全部法线协议属性后，具有有效 UV 面积的可见表面内部像素，其法线编码 RGB 向量误差的 95% 分位小于 0.04；固定光照线性 RGB 的对应阈值为 0.06
- **AND** Normal 图作为 Non-Color 数据保存、打包和重载

#### Scenario: A side wall has degenerate UVs
- **WHEN** 侧壁原 UV 面积为零，无法独立承载每个表面位置的法线
- **THEN** 转换保持其几何、退化 UV 及区域归属，允许静态法线近似且渲染数值必须有限
- **AND** 测试依据几何 UV 面积与可见面分类区分这些像素，验证转换前后的分类覆盖一致；正常 UV 表面的误差阈值保持不变

#### Scenario: Normal strength and bump are both customized
- **WHEN** 用户修改 Normal Scale 和 Bump Scale 后执行转换
- **THEN** Normal Scale 与 Bump 均烘入最终图片，标准 Normal Map 使用 Tangent Space 和 Strength=1
- **AND** 结果移除组内实时 Bump 路径，Bump 效果只应用一次

#### Scenario: Normal maps are disabled on a surface
- **WHEN** 原材质在具有有效 UV 面积的 Rear、Side、wall 或接缝位置关闭或衰减法线细节
- **THEN** 静态图在相应位置保留该效果，清除衰减属性后不会重新出现细节

### Requirement: Material structure and image interpretation are preserved

转换 SHALL 按原消费者替换 O Image Layer 的全部输出并移除该实例，保留组外结构和其他参数。Color SHALL 统一为 0–1 sRGB PNG 并在量化容差内保留 Alpha；HDR SHALL 使用固定颜色归一化。无共享时既有材质与图片 SHALL 保持身份、名称和路径；有共享时 SHALL 隔离结果。Roughness 和缺失的 Normal SHALL 按需新建并打包。

#### Scenario: Material and images have other users
- **WHEN** 活动对象与其他对象共享材质或图片
- **THEN** 结果隔离共享资源，其他对象继续使用原节点组及图片内容

#### Scenario: Static normals have no independent image destination
- **WHEN** 没有源 Normal 图片但 Bump 非零
- **THEN** 新建独立 Normal 图片并固化最终法线
- **AND** Color 与 Normal 输入共用图片等不支持的输入在写入前明确拒绝，保留源数据

#### Scenario: Save a converted HDR object
- **WHEN** 转换 HDR Cutout 并保存重载文件
- **THEN** 打包后的 Color、Roughness 和存在的 Normal 可用，符合各自数据解释和精度要求
