## Purpose

规定 Cutout 网格细节与源图像素之间的稳定关系，并让性能上限约束实际生成的网格采样数量而不是输入图片尺寸。

## ADDED Requirements

### Requirement: Mesh Detail preserves source-pixel spacing
系统 SHALL 将 Cutout 的 Low、Medium、High、Ultra 分别解释为相邻网格采样点之间 32、16、8、4 个源图像素，并在未触及网格上限时保持该间距。

#### Scenario: Low samples every 32 source pixels
- **WHEN** 用户以 Low 创建一个未触及网格上限的 Cutout
- **THEN** 系统按每 32 个源图像素一次的间距构建网格

#### Scenario: Upscale increases linear mesh density
- **WHEN** 同一图片内容在线性宽高各 Upscale 4 倍后，以相同 Mesh Detail、相同相对 Selection 和相同显示尺寸创建 Cutout，且两次均未触及网格上限
- **THEN** Upscale 结果在同一线性内容范围内获得约 4 倍网格采样密度

### Requirement: Cutout mesh limit caps actual sampling resolution
系统 SHALL 仅在 Cutout 实际几何范围的预期采样长边超过 **Maximum Cutout Mesh Resolution** 时增大采样间距，并 SHALL NOT 按 Selection bounds 的原始像素长边直接缩放已经由 Mesh Detail 得到的密度。

#### Scenario: Large pixel bounds remain below the sampling limit
- **WHEN** Selection bounds 的像素长边超过配置值，但按当前 Mesh Detail 计算的实际采样长边没有超过配置值
- **THEN** 系统保持该 Mesh Detail 对应的源像素采样间距

#### Scenario: Actual sampling reaches the configured limit
- **WHEN** Cutout 实际几何范围按当前 Mesh Detail 计算的采样长边超过配置值
- **THEN** 系统等比增大网格采样间距，使实际采样长边不超过配置值

