# mesh-bake-modifier-prefix Specification

## Purpose
识别并烘焙对象的图片修改器前缀，仅求值该前缀对应的几何结果，保留后续修改器的数据，并支持操作失败后的恢复与撤销。

## Requirements

### Requirement: Bake identifies an image modifier prefix

系统 SHALL 在 Object Mode 中为带 `o_image_object` 标记的 Mesh 识别从首项开始的 AnyImage 烘焙前缀。支持的首项 SHALL 为 `O Image Plane`、`O Image Depth Plane`、`O Image Relief Plane`、`O Image Depth Panorama`、`O Image Cutout` 或 `O Image Depth Cutout` Geometry Nodes 修改器。紧接 `O Image Depth Cutout` 的 `O Image Cutout Symmetry` SHALL 一并纳入前缀。前缀所有修改器 SHALL 具有节点组且同时启用视口和渲染。菜单判断和执行 SHALL 使用同一前缀规则，后续修改器的类型、节点组和启用状态 SHALL 不影响前缀识别。

#### Scenario: Depth Symmetry has additional modifiers
- **WHEN** 对象栈为 `O Image Depth Cutout → O Image Cutout Symmetry → Smooth → 用户 Geometry Nodes`，前缀符合启用条件
- **THEN** Bake Mesh 可用，前两项为烘焙前缀

#### Scenario: Cutout or a single-region conversion has additional modifiers
- **WHEN** 支持的单项图片生成修改器后存在其他修改器，包含禁用项或节点组为空的 Geometry Nodes
- **THEN** Bake Mesh 的前缀识别通过，其他项均作为后续处理保留

#### Scenario: The image generation prefix is disabled or preceded by another modifier
- **WHEN** 栈首项不是支持的图片生成修改器，或烘焙前缀内任一项关闭视口或渲染
- **THEN** Bake Mesh 不可用

#### Scenario: Symmetry follows the flat Cutout group
- **WHEN** 栈为 `O Image Cutout → O Image Cutout Symmetry`
- **THEN** 仅首项属于烘焙前缀，Symmetry 作为后续修改器保留

### Requirement: Bake evaluates only the image modifier prefix

系统 SHALL 对烘焙前缀的输出生成静态 Mesh、拼接 Color 和烘焙 Normal，并沿用实际图片操作所需的材质、UV 与来源区域校验。后续修改器 SHALL 在静态 Mesh 求值期间被临时排除，并在求值结束时恢复原始状态。

#### Scenario: A trailing modifier changes geometry
- **WHEN** Depth Cutout 与 Symmetry 后接会移动顶点的修改器并执行 Bake
- **THEN** 静态 Mesh 的顶点位置和拓扑对应 Symmetry 输出
- **AND** 完成后的对象通过保留修改器执行一次该变形

#### Scenario: A trailing Geometry Nodes modifier changes topology
- **WHEN** Cutout 后接改变拓扑的用户 Geometry Nodes 并执行 Bake
- **THEN** 贴图布局和 Normal 烘焙依据 Cutout 前缀输出
- **AND** 用户节点的拓扑处理继续作用于烘焙后的 Mesh

### Requirement: Bake preserves subsequent modifier data

成功提交 SHALL 只移除烘焙前缀，保留后续修改器实例、相对顺序、名称、参数、节点组引用、图片引用、动画关联和原始视口／渲染状态。系统 SHALL 保持原对象身份、变换、集合及用户数据，沿用共享材质／图片隔离、最终 `UVMap` 和协议属性清理。成功后 SHALL 移除 `o_image_object`。Depth Image 清理 SHALL 只针对已烘焙部分的候选，并仅移除无用户的图片。

#### Scenario: Smooth and custom nodes remain configured
- **WHEN** 烘焙前缀后有带自定义参数、节点输入和动画关联的 Smooth 与 Geometry Nodes
- **THEN** 成功后两项按原顺序保留，数据关联及各项启用状态保持原值
- **AND** 对象已退出 AnyImage 图片对象流程

#### Scenario: A retained modifier references the Depth Image
- **WHEN** 前缀的 Depth Image 也被保留的 Geometry Nodes 引用
- **THEN** Bake 后图片和后续节点的引用仍然有效

### Requirement: Bake restores state on failure and supports undo

Bake 失败 SHALL 恢复原 Mesh、完整修改器栈及启用状态、图片、材质输入和对象能力标记，并释放临时资源。成功 SHALL 支持 Undo/Redo，恢复或重新提交烘焙前缀和对应静态数据。

#### Scenario: Mesh evaluation fails while subsequent modifiers are disabled
- **WHEN** 临时关闭后续修改器后网格求值异常
- **THEN** 所有修改器的原状态恢复，原 Mesh、图片、材质和能力标记保留

#### Scenario: Texture processing fails after mesh evaluation
- **WHEN** 静态 Mesh 已准备，但贴图或法线处理失败
- **THEN** 恢复原图片和材质输入，保留完整修改器栈与原 Mesh，临时资源释放

#### Scenario: Undo and redo a bake with subsequent modifiers
- **WHEN** 用户成功 Bake 后执行 Undo，再执行 Redo
- **THEN** Undo 恢复原 Mesh、完整栈、贴图与能力标记
- **AND** Redo 恢复静态 Mesh 和仅保留后续修改器的结果，各项参数与状态保持一致
