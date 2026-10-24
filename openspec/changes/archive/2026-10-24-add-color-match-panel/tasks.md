## 1. Color Reference Selection

- [x] 1.1 为 Color Reference 增加可复用的静态图片与 `_normal`、`_depth`、`_color` 逻辑名称过滤，并覆盖大小写及 Blender 数字重名后缀测试
- [x] 1.2 以动态 Enum 代理现有 Image PointerProperty，验证缩略图候选、默认空值、允许选择、拒绝候选、替换和清空

## 2. Color Match Panel

- [x] 2.1 使用 `template_icon_view` 绘制 Color Reference 缩略图画廊，并将 `Color Match` Panel 排在侧边栏第二位
- [x] 2.2 更新 Panel 绘制、顺序和类型注册测试

## 3. Menu and Operator Cleanup

- [x] 3.1 从共享 Image Empty、AnyImage Mesh 和 Image Texture 菜单移除 `Set Color Reference`，保留 `Match Color Reference`
- [x] 3.2 删除 `SetColorReference` Operator 的实现、导出和注册，不保留旧 ID 或兼容入口
- [x] 3.3 更新颜色参考、图片菜单、对象图片操作和节点图片操作测试，确认匹配仍读取 Panel 对应的 Scene 引用

## 4. Verification

- [x] 4.1 运行 Color Match Panel、颜色参考、菜单、对象目标、节点目标和扩展注册相关测试
- [x] 4.2 检查 `set_color_reference` 旧引用与最终差异，并运行 OpenSpec 校验

## 5. Reference Palette

- [x] 5.1 从参考图可见像素确定性提取五个代表色，并在参考变化时更新派生显示值
- [x] 5.2 在 Color Match Panel 的参考选择器下绘制只读色块并补充 UI、透明像素和更新测试
- [x] 5.3 运行 Panel 与颜色匹配相关测试并检查最终差异
