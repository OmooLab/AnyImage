## ADDED Requirements

### Requirement: Baked materials replace image layer outputs

Bake Mesh SHALL 从结果材质移除 O Image Layer 实例，按原输出的全部消费者重接标准节点，保留组外结构、其他连线和参数。Color SHALL 使用统一后的 0–1 sRGB 图片，Alpha SHALL 保留 Alpha Fix 曲线效果，Specular SHALL 将当前输出固化为独立 Non-Color PNG，使用最终 Color 经 RGB to BW 的求值结果。可编辑对象 SHALL 继续使用原节点资产。

#### Scenario: Flatten a generated material
- **WHEN** 用户烘焙使用 O Image Layer 的受支持对象
- **THEN** 结果材质没有该组实例，Color、Roughness、Alpha、Normal、Specular 的原连接目标均得到对应结果
- **AND** IOR、Emission Strength、组外处理及 Material Output 连接保持原值

#### Scenario: Preserve alpha and HDR specular
- **WHEN** 原组使用非零 Alpha Fix 或输入颜色含大于 1 的 HDR 分量
- **THEN** 标准 Float Curve 保留 Alpha 修正，Specular 根据统一后的 Color 计算灰度，Color 归一化至 0–1 sRGB

### Requirement: Roughness is a static data texture

系统 SHALL 将被消费的 Roughness 输出烘焙为0–1 的 8-bit Non-Color PNG 图片，使用最终 UV、Color 对应区域分辨率并打包保存。烘焙 SHALL 求值统一后的 sRGB Color 与实际曲线。

#### Scenario: Bake roughness for one or multiple regions
- **WHEN** 单区对象或 Cutout Atlas 材质的 Roughness 被消费
- **THEN** 生成 `_roughness` 图片并连接原消费者；有效 UV 内部采样相对原 Roughness 的绝对误差 95% 分位小于 0.02
- **AND** 保存重载后数据解释及像素保持一致

### Requirement: Final tangent normals include bump

系统 SHALL 将 Normal Map、当前 Normal Scale、几何属性适配及 Bump 的最终效果固化为一张浮点 Non-Color Tangent Normal 图片，通过 Strength=1 的标准 Normal Map 接入原消费者。结果 SHALL 只应用一次 Bump。

#### Scenario: Bake normal and bump together
- **WHEN** 源材质有法线图、非单位 Normal Scale 及正或负 Bump Scale
- **THEN** 结果包含全部组合效果，移除协议属性后有效 UV 表面内部的法线编码 RGB 向量误差 95% 分位小于 0.04，固定光照线性 RGB 对应误差小于 0.06

#### Scenario: Bake bump without a normal image
- **WHEN** 源材质没有 Normal 图片但 Bump Scale 非零
- **THEN** 系统按 Color 对应区域分辨率创建并打包 `_normal` 图片，保留 Bump 效果

#### Scenario: No normal detail is present
- **WHEN** 原组无 Normal 图片、使用默认法线输入且 Bump Scale 为零
- **THEN** 使用标准 Geometry Normal 承接消费者，省去法线图片

### Requirement: Flattening is isolated and transactional

系统 SHALL 保留其他使用者的材质和图片外观，对共享资源进行隔离；无共享时保留既有材质及图片身份。所有结果 SHALL 在准备完成后提交，失败 SHALL 恢复图片、节点和连线及对象数据并释放临时资源。

#### Scenario: Another object shares the material
- **WHEN** 烘焙对象与可编辑对象共享材质或图片
- **THEN** 其他对象保持原材质、贴图内容及 O Image Layer，烘焙对象使用隔离结果

#### Scenario: Failure occurs during commit
- **WHEN** Roughness 或 Normal 烘焙、图片写入或节点重接失败
- **THEN** 原对象、图片、材质节点及连接恢复，新增的未提交图片和临时数据释放

#### Scenario: Undo and redo
- **WHEN** 用户对成功烘焙执行 Undo / Redo
- **THEN** 原几何节点、O Image Layer、图片与连接和静态结果可以完整往返恢复


### Requirement: Specular is a static data texture

系统 SHALL 将最终 Color 经 RGB to BW 得到的灰度烘焙为独立的 0–1、8-bit Non-Color PNG，尺寸及布局与 Roughness 一致。图片 SHALL 保持线性标量语义并 pack。

#### Scenario: Bake scalar texture outputs
- **WHEN** 用户执行 Bake Mesh
- **THEN** Roughness 和 Specular 使用独立 PNG 图片连接原消费者，量化误差在 8-bit 精度范围内

### Requirement: Emission follows the original strength

系统 SHALL 在原强度为 0 时移除 Emission Color 连接且不生成发光图片；强度大于 0 时复制最终 Color 为独立 `_emissioncolor` 图片，保留内容、颜色空间、Alpha、精度及强度。

#### Scenario: Export a non-emissive material
- **WHEN** 原材质发光强度为 0，烘焙后导出 GLB
- **THEN** GLB 没有发光贴图，导入后仍不发光

#### Scenario: Strong emission has an independent color image
- **WHEN** 原材质发光强度大于 0
- **THEN** Emission Color 使用独立 `_emissioncolor` 图片，修改该图不影响 Base Color，发光强度不重复烘入图片

### Requirement: Texture nodes follow material input order

结果图片节点 SHALL 按 Principled BSDF 输入顺序从上到下排列，宽度一致、列对齐、行间距足够，Normal Map 与对应图片同排。失败 SHALL 恢复原布局。

#### Scenario: Arrange the flattened material
- **WHEN** 结果包含 Color、Roughness、Normal、Specular 和 Emission Color
- **THEN** 图片依次排列为 Color、Roughness、Normal、Specular、Emission Color


### Requirement: Baked colors use a preference-independent sRGB domain

Bake Mesh SHALL 将所有静态 Color 统一为 0–1 sRGB，保留 Alpha，独立于颜色补偿偏好。inverse 与 HDR 输入 SHALL 先按实际颜色空间求得线性 RGB，再复用按通道截断至 0–4、除以 4、Gamma 0.75、编码 sRGB 的固定归一化。普通 byte sRGB 与已归一化图片 SHALL 保持编码值。所有派生贴图 SHALL 使用统一后的 Color；Specular SHALL 使用 RGB to BW，绕过可编辑节点组的 Clamp。可编辑材质 SHALL 保留现有节点组。

#### Scenario: Both preference states produce the same baked maps
- **WHEN** 对同一原图分别使用开启和关闭颜色补偿的材质执行 Bake Mesh
- **THEN** Color、Roughness、Specular、含 Bump 的 Normal 和 Emission Color 的结果像素一致

#### Scenario: HDR and inverse inputs become bounded colors
- **WHEN** 输入包含 inverse 颜色空间或超出 0–1 的 HDR 值
- **THEN** 输出为已打包的 sRGB PNG、颜色范围 0–1，Alpha 在量化容差内保持不变；失败恢复原图及解释

#### Scenario: Normalized colors are not transformed twice
- **WHEN** 输入已使用普通 byte sRGB 或带归一化标记
- **THEN** 保持编码颜色值，结果记录归一化标记
