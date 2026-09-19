## 1. 公共媒体校验

- [x] 1.1 在 server/media/input.py 统一路径、图片/视频扩展名与格式消息，保持标准库预检及后端独立加载；补充大小写、无扩展名和缺失路径测试。
- [x] 1.2 让 prepare_input 与 BEN2 单帧校验复用公共规则；验证直接后端请求与前端提示一致，图片子集限制有效。
- [x] 1.3 在实际图片/视频读取边界统一解码失败提示并保留异常原因；覆盖损坏内容，确认推理异常保留自身语义。

## 2. Blender 输入准备

- [x] 2.1 将 require_input_path 接入公共预检，移除 require_background_input_path 和 BEN2 重复常量；覆盖 Remove BG/Upscale 同一无效输入的消息及未提交 Job 行为。
- [x] 2.2 统一 source image/video 路径提示，覆盖 Image Empty 和材质 Image Texture；回归其他公共校验消费者。
- [x] 2.3 在 Blender 序列复制前校验图片格式；验证不支持序列、混合目录、无有效帧目录、帧排序与范围。
- [x] 2.4 修复输入准备失败的临时目录释放，验证 packed 导出与序列复制失败；覆盖普通原文件和导出 PNG 的不同实际输入路径。

## 3. Operator 失败边界

- [x] 3.1 修复 Remove BG、Depth/Relief Plane 的嵌套调用异常出口，规范错误前缀并处理同步失败/CANCELLED 的临时输入清理。
- [x] 3.2 补齐公共 AI setup 入口及 AI Environment 安装/下载嵌套调用的预期失败处理；回归 Panorama 已有错误边界。
- [x] 3.3 补充准备失败、同步取消、异步成功/失败/取消的生命周期测试，确认原文件、源图片引用和 Undo 行为保持有效。

## 4. 验证

- [x] 4.1 运行相关测试，再运行 uv run pytest 并确认正常退出；检查旧校验名称、重复格式列表与最终差异。
- [x] 4.2 在真实 Blender UI 从 Remove BG、Depth/Relief Plane 及 AI setup 入口触发同步失败，确认普通提示无重复前缀、无未捕获 traceback，并检查临时输入已释放。
- [x] 4.3 验证有效 PNG、视频、序列与材质贴图入口，记录测试结果及实际验证限制。

## 验证记录

- `uv run pytest -q`：1025 passed、2 xfailed、52 subtests passed，退出码 0。随后新增的 4 项原生 Operator 测试通过；最终相关新增测试合计 24 项通过。
- Blender 4.5.10 LTS 独立场景：UI 主循环依次调用 Remove BG、Upscale、Depth、Relief 和 AI setup；前四者格式错误完全一致，所有入口仅一层 Error 前缀且没有未捕获 traceback。原生回归另行验证同步失败后的临时输入清理。
- 有效图片、视频帧、序列、材质贴图、异步完成/取消/失败和 Undo 由全量回归覆盖；本次验证使用模拟推理与安装失败，不下载模型或执行真实模型推理。
