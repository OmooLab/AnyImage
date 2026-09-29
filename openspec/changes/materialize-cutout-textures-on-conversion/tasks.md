## 本轮修订：简单拼接与同步执行

- [x] 镜像组在背面翻转基础上再水平翻转一次，保持四区位置，验证 UV、Color 与法线烘焙。

- [x] 背面 UV 与 Color 同步水平翻转，静态 Normal 按最终 UV 烘焙。
- [x] 固定上正下背、左本体右镜像的布局；覆盖单区、正反双区、镜像双区、完整四区及缺失组合。

- [x] 移除 Smart UV Project 与颜色三角形重采样；原 UV 仅按区域缩放和平移，颜色整图复制到上下或 2×2 布局。
- [x] 移除 modal、timer、生成器和取消入口，改为同步构建及提交，保留失败资源清理。
- [x] 保留用户确认的简单 UV 效果：有效 UV 表面继续使用原误差阈值；退化侧壁检查几何覆盖一致、UV 关系和渲染数值有效性。
- [x] 根据简单 UV 决策修订验收任务与 design/specs，补充异常资源清理、byte 图片重载及同步菜单调用测试。

## 1. 验证静态法线与布局方案

- [x] 1.1 建立小型 Blender 原型，验证从 Bump 之前的实际材质法线烘焙到最终 UV 的 Tangent Normal，覆盖 Object/Tangent、非默认 Normal Scale、Depth Scale 和位置相关衰减。
- [x] 1.2 验证薄壳 Front/Rear、symmetry mirrored、Side 和 fill 的确定性源面对应；确定源 UV 的简单拼接、翻转、目标尺寸及退化侧壁近似规则。
- [x] 1.3 对比法线通道、固定光照渲染和非零 Bump，记录有效 UV 表面的像素精度与退化 UV 覆盖，将可执行的验收阈值和选定烘焙策略写入 design.md。

## 2. 替换可编辑 Cutout 协议

- [x] 2.1 移除旧创建期图片拼接模块和全部调用，恢复基础 0–1 UV 与单区 Color/Normal，保留单区 Boundary Padding。
- [x] 2.2 删除节点中的 Rear 下区映射、Atlas Depth 还原及仅服务旧布局的节点/拓扑，保留仍有几何职责的侧环和必要采样保护。
- [x] 2.3 在普通 Cutout、Depth Cutout 及 Symmetry 构造位置输出 FACE/INT 来源区域，验证 Front/Rear、Side、retained/mirrored 和 fill 继承。
- [x] 2.4 替换旧双区测试，覆盖单图像素和尺寸、实时正背法线、Depth 标定、Balloon/Shell、零厚度、Split 与一次 symmetry 的行为。

## 3. 实现转换与静态图片

- [x] 3.1 建立转换模块与输入校验，识别支持的 Cutout 节点栈和材质连接，隔离求值 Mesh、材质及图片；未知输入在提交前明确失败。
- [x] 3.2 按实际存在的来源区域生成最终 Corner UV，保留源 UV 形状和退化/重叠关系，实现 Color/Normal 的一致区域布局及翻转。
- [x] 3.3 实现 Color 逐像素拼接及水平翻转，验证 Alpha、透明 RGB、byte/float/HDR、颜色空间及打包保存重载。
- [x] 3.4 按原型方案实现静态 Tangent Normal 生成，固化全部法线适配与衰减，保持 Bump 只应用一次，同步执行并清理失败资源。
- [x] 3.5 保留目标材质结构与共享 O Image Layer，更新独立图片引用、Tangent 模式及单位 Normal Scale，验证共享数据隔离。

## 4. 提交与属性清理

- [x] 4.1 建立完整的 AnyImage 形状/法线/区域/中间属性清理清单，删除已消费协议、临时 UV 和程序化元数据；保留最终 UV、必要网格数据、用户属性及图片操作能力标记。
- [x] 4.2 实现原位事务提交及 Undo/Redo，保留对象身份、变换和集合，验证失败后源数据与场景设置恢复、临时资源释放。
- [x] 4.3 注册 ConvertToMesh 并接入 AnyImage 对象菜单，补充可用性、重复转换、注册和逆序注销测试。

## 5. 验收与完整清理

- [x] 5.1 运行相关图片、Operator、注册、节点求值和渲染测试，按原型阈值验证 1/2/4 区、薄壳、非默认 symmetry、无 Normal、HDR、共享材质及保存重载。
- [x] 5.2 检查转换结果没有任何被消费的 AnyImage 形状、法线、区域或中间属性，并验证清理后的渲染与用户数据保留。
- [x] 5.3 运行 `uv run --group blender node-group build`，验证生成资产、来源协议、单图 UV、Capture Attribute 为零及旧 Atlas 节点消失。
- [x] 5.4 沿真实调用链检查旧拼接代码、旧节点、旧测试及引用全部清除，检查最终差异并保留其他已有修改；不构建文档或打包扩展。
- [x] 5.5 准备 split-cutout-front-back-uv 之后应用的规格 delta，废止旧双区要求并恢复创建期单图规格，记录归档先后顺序并校验；实施阶段不自动归档。
