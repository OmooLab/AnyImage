## Purpose

保证图片编辑与网格生成取得当前有效的业务像素，同时保护 Blender 源图片的未保存内容、透明颜色、呈现模式与共享引用，使连续编辑和保存重开具有一致的数据结果。

## ADDED Requirements

### Requirement: Reading business pixels preserves source state
系统 SHALL 在读取业务 RGBA 时保留源 Image 的像素缓存、Alpha 模式、脏状态、Packed 内容和对象引用。读取 SHALL NOT 通过重载源图片覆盖当前有效内容。

#### Scenario: Dirty packed image is read
- **WHEN** 用户修改 Packed Image 像素但尚未重新 Pack，图片编辑工具读取该图片
- **THEN** 读取结果包含最近修改的 RGB/Alpha
- **AND** 源像素、脏状态及原 Packed 内容保持读取前状态

#### Scenario: Shared source is read before an edit is cancelled
- **WHEN** 两个对象共享同一 PREMUL Image，其中一个工具读取图片后取消或报错
- **THEN** 两个对象仍引用相同源数据，源像素缓存与呈现设置保持不变

### Requirement: Business pixel interpretation survives persistence
系统 SHALL 保留既有 PREMUL 结果默认值，并在即时读取、Pack 和 blend 保存重开后取得相同业务 RGB/Alpha。误差 SHALL 仅来自既有编码精度，完全透明 RGB SHALL 可以通过 Mask Add 恢复。

#### Scenario: Edited image is reopened and read repeatedly
- **WHEN** 含透明及半透明像素的编辑结果保存重开并被多次读取
- **THEN** 每次返回相同业务像素，结果 Alpha 模式保持 PREMUL
- **AND** 读取不会改变源缓存或产生累计颜色变化

#### Scenario: Floating point source is consumed
- **WHEN** 工具读取生成或加载的浮点图片，包括原生预乘 Alpha 数据
- **THEN** 返回值符合源编码的业务 RGBA 语义并保留当前有效精度
- **AND** 源图片的像素及模式保持不变

### Requirement: Temporary decoding data has bounded lifetime
系统 SHALL 在单次业务读取结束或失败时释放该读取拥有的临时图片数据。

#### Scenario: Repeated read or decode failure
- **WHEN** 用户重复触发读取，或读取中的解码发生错误
- **THEN** 不留下额外 Image 数据块，原图片及共享引用保持不变
