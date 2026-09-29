## REMOVED Requirements

### Requirement: Cutout 图片使用固定上下双区布局
**Reason**: 可编辑 Cutout 使用单区图，静态转换按实际表面布局。
**Migration**: 使用 cutout-texture-materialization，创建期双区路径删除。

### Requirement: Boundary Padding 先于材质 Atlas
**Reason**: 创建期不再构建 Atlas。
**Migration**: Boundary Padding 保留单图处理，Atlas 在 Convert to Mesh 时生成。

### Requirement: Cutout 正片与后片使用独立 UV 区域
**Reason**: 独立纹理空间推迟到静态转换。
**Migration**: 编辑阶段共享源 UV，转换消费表面来源并建立最终 Corner UV。

### Requirement: Cutout 侧壁按叶片来源分区
**Reason**: 独立区域的 UV 映射在静态转换时完成。
**Migration**: Side 保留来源身份和源 UV，在 Convert to Mesh 中随所属区域缩放、偏移及翻转。

### Requirement: 双区布局不改变几何语义
**Reason**: 固定双区协议退出创建阶段。
**Migration**: 几何节点维持形状职责，静态转换使用当前求值几何。
