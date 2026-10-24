## 1. 统一匹配像素约定

- [x] 1.1 检查颜色转换入口的真实调用者，在 common 统一 Rectify 与 Match Color 的 byte sRGB / float linear Rec.709 解码与编码，替换对应旧入口。
- [x] 1.2 将目标、参考准备、色板和参考图标接入同一约定，保留 Alpha、缓存失效与现有算法参数。
- [x] 1.3 验证相同 byte 像素在 sRGB、AgX Base sRGB、Non-Color 设置下得到等价结果，以及 float 值和零调节行为。

## 2. 固定 sRGB 浮层

- [x] 2.1 核实 Blender 4.5 与 5.x 的 GPU 纹理创建、更新和普通绘制 API，在 common/image_preview.py 提供共享纹理与绘制入口，替换两种工具的临时 Image。
- [x] 2.2 将线性预览 RGB 编码为显示范围内的 sRGB，复用布局与刷新限制，验证方向、Alpha 混合及只进行一次显示编码。
- [x] 2.3 统一初始化、刷新、确认、取消和失败路径的纹理、handler、timer 清理，验证重复刷新资源数量有界。
- [x] 2.4 Rectify 预览和最终透视重采样接入共享线性转换，保留预乘 Alpha 插值、输出尺寸限制、trim、placement 和宽高比交互；清理无调用的旧预览入口。

## 3. 保留设置与验证

- [x] 3.1 记录并校验预览期间目标 color space 和 Alpha 模式，保留已有目标、参考与像素有效性检查。
- [x] 3.2 验证直接执行和交互确认按相同存储约定编码，并保留原设置、共享隔离及 Undo；取消和错误路径保留源图状态。
- [x] 3.3 在缺少 sRGB 条目的自定义 OCIO 配置中验证预览启动与刷新，并在实际 GPU 上检查中灰、彩色色块、不对称图案和半透明边缘。
- [x] 3.4 更新并运行相关 common 与 Operator 测试，确认正常退出；检查旧预览引用与最终差异。
- [x] 3.5 补充 Rectify 黑白线性插值、float 预览及输出编码、半透明边缘、返回选点与异常清理覆盖，运行相关 projective、Rectify 与共享 preview 测试。
