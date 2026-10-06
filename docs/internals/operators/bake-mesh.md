# Bake Mesh

`operators/bake_mesh/operators.py` 实现 `BakeMesh`，同步固化 Plane、Depth Plane、Relief Plane、Panorama 及受支持 Cutout 节点栈。`materialization.py` 管理求值网格、UV、Normal 烘焙和原位图片事务，`textures.py` 根据来源区域拼接 Color。

单区无 Normal 路径固化几何，保留 Color 图片与采样设置。多区 Color 路径按来源区域缩放和平移 UV、复制及翻转整张图片；Normal 路径用单位 Normal Scale 烘焙最终 UV 的 Tangent Normal。校验根据实际读写和采样依赖执行。

成功保留对象、材质与图片身份、图片名称和路径及用户属性，清理被消费的协议属性、修改器和 `o_image_object`。结果以普通 Mesh 使用，Shader Editor 节点入口按活动贴图逻辑继续提供图片操作。共享图片与材质沿用原位更新行为。

失败恢复图片与材质输入并清理本次资源；Undo/Redo 恢复或固化网格、贴图和对象能力。零引用 Depth 图片在成功后释放。
