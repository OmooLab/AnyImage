## ADDED Requirements

### Requirement: Editable Cutouts use source images and source UVs

系统 SHALL 为可编辑 Cutout 保留单区 Color、Normal、Depth 和完整 0–1 源 UV。创建阶段 MUST 不生成前后 Atlas，Depth 采样 MUST 不依赖材质 Atlas 逆变换。共享源采样的实时材质 SHALL 保持厚度、正背及 symmetry 的当前默认外观。

#### Scenario: Create and adjust a Cutout
- **WHEN** 用户创建 Flat、Solid、Depth Solid 或 Depth Symmetry 并调整厚度
- **THEN** Color 与 Normal 保持各自单区产物尺寸，Depth 与相机标定使用单区语义
- **AND** Boundary Padding 在单区 Color 与 Depth 上执行，UV 不带 Atlas 偏移

### Requirement: Conversion materializes actual surface regions

`anyimage.convert_to_mesh` SHALL 从支持的 Cutout 求值结果生成静态 Mesh 和独立纹理地址。区域 SHALL 来源于构造时的面身份；布局 SHALL 保持源 UV 形状，仅进行缩放、偏移与背面/镜像水平翻转；纵轴为正反面，横轴为本体与镜像。

#### Scenario: Thickness and symmetry produce four regions
- **WHEN** 求值结果同时含 Front、Rear 及其 mirrored 副本
- **THEN** 左上为本体正面、左下为本体背面、右上为镜像正面、右下为镜像背面
- **AND** 背面和镜像体各叠加一次 UV 与 Color 的水平翻转：本体正面及镜像背面保持原方向，本体背面及镜像正面水平翻转；Normal 按最终 UV 烘焙

#### Scenario: Fewer regions survive evaluation
- **WHEN** 零厚度、无 symmetry 或裁切使部分组合不存在
- **THEN** 省略完全缺失的行或列，局部缺失组合留空；只有正反面时上下排列，只有本体与镜像正面时左右排列

#### Scenario: Source UVs overlap on side walls
- **WHEN** 不同表面的源 UV 重叠或退化且需要不同法线结果
- **THEN** 目标 UV 保留这些表面的原有退化或重叠关系，静态侧壁法线允许由该限制引起的近似
- **AND** Color 与 Normal 使用一致的归一化布局

### Requirement: Converted normal maps are static

转换 SHALL 把当前法线图经过旋转、镜像、正背适配、Normal Scale、Depth Scale、位置相关衰减与 wall 禁用后的效果固化为最终 UV 下的 Tangent Normal。结果 MUST 不依赖 AnyImage 法线属性；有效网格法线、平滑和锐边 SHALL 保留。

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
- **THEN** 当前 Normal Scale 固化到贴图，目标 Normal Scale 为 1 且 Object Space 为 false
- **AND** Bump Scale 与既有 Bump 连接保留且效果只应用一次

#### Scenario: Normal maps are disabled on a surface
- **WHEN** 原材质在具有有效 UV 面积的 Rear、Side、wall 或接缝位置关闭或衰减法线细节
- **THEN** 静态图在相应位置保留该效果，清除衰减属性后不会重新出现细节

### Requirement: Material structure and image interpretation are preserved

转换 SHALL 保留材质结构及共享 `O Image Layer`，只更新目标图片和静态法线所需输入。Color SHALL 保持 Alpha、颜色解释和源精度，HDR SHALL 保留浮点动态范围。共享数据 SHALL 在修改前隔离。

#### Scenario: Material and images have other users
- **WHEN** 活动 Cutout 与其他对象共享材质或图片
- **THEN** 转换只更新活动对象的独立结果，其他对象及共享节点组不变

#### Scenario: Save a converted HDR object
- **WHEN** 转换 HDR Cutout 并保存重载文件
- **THEN** 打包后的 Color 与 Normal 可用，颜色与法线符合各自数据解释和精度要求

### Requirement: Conversion commits atomically and supports undo

转换 SHALL 同步阻塞执行并原位处理活动的受支持 Cutout，保留对象身份、变换与用户数据。成功 SHALL 支持 Undo / Redo；失败或不支持的输入 SHALL 保留原对象并释放本次临时资源及烘焙设置。

#### Scenario: Undo and redo conversion
- **WHEN** 成功转换后撤销再重做
- **THEN** 撤销恢复可编辑节点栈与原图引用，重做恢复静态网格、图片和材质

#### Scenario: Baking fails or input is unsupported
- **WHEN** 烘焙失败、输入有未知修改器/材质连接或缺少来源协议
- **THEN** 操作明确结束并报告原因，原 Mesh、Modifier、材质与图片保持原值，临时数据释放

### Requirement: Old creation-time atlas implementation is removed

实现 MUST 删除旧创建期双区图片函数、调用、基础上区 UV、Rear 下区变换、Atlas Depth 还原、仅服务旧布局的构造和过时测试；MUST 不保留旧路径、转发函数、布局兼容层或开关。转换期纹理布局 SHALL 集中于新转换职责。

#### Scenario: Inspect source and rebuilt assets
- **WHEN** 检查最终生产源码、相关测试及重建节点资产
- **THEN** 不存在旧创建期 Atlas 的可执行路径或悬空引用
- **AND** 可编辑 Cutout 使用单区协议，纹理布局只在 Convert to Mesh 执行
