## ADDED Requirements

### Requirement: Inverse colors use a fixed per-channel cap and gamma

关闭 Compensate Image Colors 且普通 byte 颜色图匹配可用 inverse 空间时，系统 SHALL 按该空间将 straight RGB 解码为工作线性 RGB，对各通道分别执行 `(clamp(L, 0, 4) / 4) ** 0.75`，再进行 sRGB 编码。Alpha 数值 SHALL 保持不变。

#### Scenario: Channels exceed the fixed cap

- **WHEN** 解码后的线性 RGB 为 `(8, 2, 1)`
- **THEN** 截断并除以 4 后 SHALL 为 `(1, 0.5, 0.25)`
- **AND** 每个分量 SHALL 应用 Gamma 0.75 后编码为 sRGB
- **AND** 最终图像 SHALL 使用 sRGB 解释，解码 RGB 位于 0～1

#### Scenario: Image contents or bounds change

- **WHEN** 图像被裁切、其他像素出现极端值，或像素 Alpha 改变
- **THEN** 同一输入 RGB SHALL 得到相同输出 RGB
- **AND** 透明区域隐藏 RGB SHALL 使用相同固定变换，Alpha 保持原值

#### Scenario: Dark and negative channels are handled

- **WHEN** 某分量为零或负值
- **THEN** 该分量 SHALL 输出零，其他分量 SHALL 按固定规则独立处理

#### Scenario: Nonfinite color data is encountered

- **WHEN** 输入或 inverse 转换结果含 NaN 或 Inf
- **THEN** 处理 SHALL 明确报错，并恢复图像原内容与配置

### Requirement: Color conversion agrees with Blender texture evaluation

系统 SHALL 使用当前 Blender 提供的 inverse 色彩变换，在浮点线性空间执行归一化，并只进行一次最终 sRGB 编码。

#### Scenario: A mapped inverse space is available

- **WHEN** 使用 AgX、ACES、Filmic 或 Khronos PBR Neutral 对应的可用 inverse 空间处理 byte 图
- **THEN** 归一化前 RGB SHALL 与 Blender 直接按该 inverse 空间采样的结果在浮点容差内一致
- **AND** 该计算 SHALL 独立于场景灯光、曝光及 Look

### Requirement: Normalized images are updated in place and remain stable

归一化 SHALL 保留目标 Image 的身份、名称、尺寸和已有绑定，原地提交新像素并打包。系统 SHALL 记录已处理状态，重复配置或重新加载相同内容时保持已归一化像素，且不产生额外交付贴图。

#### Scenario: The same image is configured repeatedly

- **WHEN** 已归一化 Image 被再次配置、绑定或保存重载，或偏好随后改变
- **THEN** 其颜色 SHALL 继续按 sRGB 读取，像素 SHALL 不再次进行 inverse 解码或归一化

#### Scenario: A normalized image is edited or used as a source

- **WHEN** 用户编辑归一化图，或以此图准备新的材质 `_color`
- **THEN** 结果 SHALL 保留已归一化状态，并在后续配置时保持当前 sRGB 内容

#### Scenario: Fresh source content replaces the image

- **WHEN** 图像内容被全新未处理的原始输入替换
- **THEN** 已归一化状态 SHALL 清除，新内容 SHALL 按当前偏好处理一次

#### Scenario: An update fails

- **WHEN** 颜色求值、编码、写回、打包或笔刷交付失败
- **THEN** 系统 SHALL 恢复原像素、颜色空间、Alpha 模式、打包内容和处理状态，并释放临时资源
