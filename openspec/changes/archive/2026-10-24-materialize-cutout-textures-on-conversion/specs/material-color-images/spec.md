## MODIFIED Requirements

### Requirement: Material color uses the requested source bounds

所有材质生成入口 SHALL 按本次准备时的源图像素和范围生成颜色图。可编辑 Cutout SHALL 使用单区裁切内容，四种 Convert To 与剪贴板 Plane SHALL 使用整图范围。AI 的参与 SHALL 保持相同颜色来源及颜色分辨率。独立表面纹理布局 SHALL 由专用 Convert to Mesh 生成。

#### Scenario: Cutout uses or omits AI

- **WHEN** 同一源图和裁切范围分别执行普通 Cutout 和需要 AI 的 Cutout
- **THEN** 两者的颜色图 SHALL 对应同一裁切内容、单区尺寸和原有 Alpha，包含透明区域 RGB

#### Scenario: A full image is converted

- **WHEN** 执行 Plane、Depth Plane、Relief Plane、Panorama 或剪贴板 Plane
- **THEN** 颜色图 SHALL 对应完整源图片，保持原始尺寸和当前像素
