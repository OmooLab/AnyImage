## Context

当前工具栏以 Mesh Detail 枚举映射像素间距，Operator 按裁切像素长边和 Maximum Cutout Mesh Resolution 限制间距。普通几何随后将像素间距换算到世界度量，Fine Outline 在像素空间生成网格。两条路径需要统一为物理长度驱动。

## Goals / Non-Goals

本变更负责 Cutout 的目标采样长度、场景单位换算、相对密度限制，以及普通轮廓和 Fine Outline 的一致性。实施范围为工具属性、偏好、几何采样链和相关测试。

## Decisions

### 参数与单位

工具栏使用 `cutout_edge_length`，标签 Edge Length，正值 FloatProperty，使用 Blender 长度单位显示；通过公共属性工厂提供一致的 Operator 参数。初始物理默认值为 0.1 m。内部明确区分 Blender 世界单位与米：世界长度乘 `scene.unit_settings.scale_length` 得到米。场景属性以米存储，通过读写回调转换 Blender 世界单位；Operator 使用原生长度属性接收菜单传入的世界单位值，确保 Blender 复制参数时保留输入。属性初始化和显示遵循 Blender 的长度属性语义，避免重复换算；用实际 Blender 测试覆盖非默认 Unit Scale 下的初始值与输入值。无单位场景按 Unit Scale 换算，默认比例 1。

### 有效间距

在裁切内容确定后，使用参与建网的内容范围计算局部包围盒，将其图像平面两条轴向边向量应用世界变换，取较长者作为 L。该定义包含非均匀缩放，旋转前后保持一致；多块内容共用整体包围盒，孔洞不改变外部范围。范围依据有效 Alpha 与选区的交集；透明留白不扩大基准。

Preferences 增加 `min_cutout_relative_edge_length`，标签 Minimum Relative Edge Length，百分比显示，Blender 百分比属性保存百分数（默认 1，范围 0.001 到 100），preferences.py 读取入口换算为比例（默认 0.01）。

以相同长度单位计算 `effective_edge_length = max(edge_length, L * min_relative_edge_length)`。这里限制的是目标点间距；相对限制生效时，界面可见反馈使用场景长度格式显示 Effective Edge Length。操作前尚无有效内容范围时，在执行得到范围后通过 Operator 报告显示有效值。用户请求值和实际值分别保存，避免执行改写工具参数。

### 采样链

普通轮廓与 Fine Outline 共用同一有效世界间距和世界平面度量。轮廓读取继续使用 Alpha 数据；基础内部采样、边界重采样及相关容差统一从有效间距派生。Fine Outline 将轮廓变换到世界平面度量后，按有效间距归一化为目标间距 32 的计算坐标，统一既有轮廓容差和约束采样尺度。非均匀缩放下距离判断保持一致；Alpha 宽度样本使用最小奇异值保守换算，仅辅助细枝支撑判断，输出映射回像素坐标用于 UV。沿现有真实调用链检查清理容差等间距消费者。

同步与 AI 异步路径使用相同解析入口，在 Blender 主线程读取场景和对象数据，后台参数保持普通可序列化值。AI 内容返回后根据实际建网内容范围解析最终有效间距。

### 替换与验证

删除旧 Mesh Detail 枚举、档位映射、以源像素为单位的 Operator 间距参数，以及 Maximum Cutout Mesh Resolution 属性和读取函数。相关保存属性直接使用新默认值，不保留转发或兼容层。更新注册清单检查与相关测试。

## Risks / Trade-offs

- 相对限制生效后，放大对象可能提高实际间距 → 展示有效长度，并测试限制两侧的行为。
- Fine Outline 和三角剖分会产生短边，1% 不等同于严格顶点预算 → 保留细轮廓语义，验证整体采样密度与细小部件存活。
- Alpha 像素化使不同分辨率的边界略有差异 → 分辨率不影响目标间距，测试比较几何密度容差而非要求任意图片顶点完全相同。
- 单位换算或非均匀缩放可能导致两条采样路径分歧 → 使用不同 Unit Scale、旋转和非均匀缩放的几何用例验证。
