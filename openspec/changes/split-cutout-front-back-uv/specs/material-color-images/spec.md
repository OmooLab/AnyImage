## MODIFIED Requirements

### Requirement: Material color uses the requested source bounds

所有材质生成入口 SHALL 按本次准备时的源图像素和范围生成颜色图。Cutout SHALL 使用裁切范围，将原内容放在上方 Front，并将其水平镜像放在下方 Rear；四种 Convert To 与剪贴板 Plane SHALL 使用整图范围和既有单区尺寸。AI 的参与 SHALL 保持相同颜色来源、单张正面分析内容及正面颜色分辨率。

#### Scenario: Cutout uses or omits AI

- **WHEN** 同一源图和裁切范围分别执行普通 Cutout 和需要 AI 的 Cutout
- **THEN** 两者的颜色图 SHALL 对应同一裁切内容、原有 Alpha 与透明区域 RGB
- **AND** 两者均生成相同尺寸的 Front 与水平镜像 Rear 区域

#### Scenario: Cutout analysis uses one front image

- **WHEN** Cutout 准备 AI 分析输入
- **THEN** AI 输入 SHALL 直接使用一张原始裁切正面
- **AND** 双区材质颜色图 SHALL 在结果阶段生成

#### Scenario: A full image is converted

- **WHEN** 执行 Plane、Depth Plane、Relief Plane、Panorama 或剪贴板 Plane
- **THEN** 颜色图 SHALL 对应完整源图片，保持原始尺寸和当前像素
