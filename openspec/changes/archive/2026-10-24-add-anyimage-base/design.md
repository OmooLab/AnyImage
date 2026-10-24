## Context

当前只有 `src/anyimage` 一个插件入口，打包器将整个源码目录装入三个平台的 ZIP。普通平面与 AI 平面共用文件；Cutout 的本地和 AI 分支共用 JobOperatorBase；设置、属性和 UI 也直接导入 AI 模块。生成 Base 前需要先形成可独立导入的基础模块集合。

## Goals / Non-Goals

交付独立可用的 AnyImage Base，与完整版择一启用；基础行为由同一份源码实现，一次发布生成两版。AI 专用内容在文件组装时剥离，节点资产按约定完整共用。此次范围为发行边界、启用互斥和打包验证。

## Decisions

### 1. 按业务拆分，使用两个明确入口

基础模块不依赖 AI 模块。普通平面与深度平面分开；Cutout 的选择交互、Flat/Solid、本地 Balloon 和几何处理归入基础部分，AI 深度及法线生成使用独立 Operator。移除旧的混合入口，直接更新真实调用链。

两版分别组合注册清单、偏好设置、属性、菜单、面板和工具栏。基础算法与交互复用 `common` 和对应业务模块，AI 专用设置及 UI 留在完整版模块。少量版本组合代码明确维护，避免在基础执行路径中散布版本判断。扩展级设置及其读取入口统一由各发行包的 `preferences` 模块提供。

全部源码维护在 `src/anyimage`，完整版可直接从源码加载调试。基础算法、注册流程、菜单交互和工具排列各维护一份，AI 模块只追加相关功能。总 `__init_base__.py` 组合基础功能并维护唯一的注册、冲突检查和逆序清理实现；总 `__init__.py` 复用基础入口，选用 AI 扩展类型并追加 Runtime 生命周期。子包只导出基础功能，AI 消费者直接导入对应实现模块。打包器排除明确列出的 AI 文件及目录，仅将总 Base 入口映射为 `__init__.py`；不修改 Python 源码文本。

### 2. Base 是完整的本地工具集

保留剪贴板导入、普通平面、Frame、Mask、Rectify、Cutout Flat/Solid、本地 Balloon、颜色参考与调色、Bake Mesh。去背景、超分、深度/浮雕平面、Panorama、深度 Cutout、AI 法线生成及全部 Server 管理只进入完整版。

Base 清单排除 Server、AI Runtime、AI Operator、模型目录与下载配置、AI 专用辅助函数、设置和翻译。通用材质、图像与几何计算按实际消费者保留。清理按用途和依赖关系判断，避免将普通法线处理等本地能力误认成 AI。

依赖分为共享基础集合和完整版追加集合，版本声明维护单一来源；开发环境继续具备完整版依赖。Base 不携带 blendjob。SciPy、materialyoucolor 等本地功能所需依赖继续打包，其余依赖按调用审计确定。Manifest 为 Base 生成真实名称、ID、文件权限说明及实际 wheels，移除 AI 网络权限。

### 3. 两版身份独立，内部命名一致

完整版名称与 Manifest ID 为 `AnyImage` / `anyimage`，Base 为 `AnyImage Base` / `anyimage_base`。内部沿用 `anyimage.*`、`ANYIMAGE_*`、`Scene.anyimage_settings` 和现有快捷键。AddonPreferences 的 bl_idname 继续从实际包路径取得，两版偏好设置分别保存；场景属性沿用同一协议。

两个入口在注册类型、翻译、工具、菜单、属性、快捷键、回调以及启动 Runtime 前检查 `Scene.anyimage_settings` 是否已注册。该共享属性直接表示 AnyImage 已启用，不依赖扩展仓库或包路径。

已有版本启用时，后启用版本抛出清晰的注册错误，提示先禁用当前版本。已安装但未启用不构成冲突。失败入口不得注销或修改先启用版本；清理仅作用于本入口成功注册的内容。启用检测复用已有注册状态，保持实现局部、直接。

### 4. 共用同一次节点构建产物

两版装入完全相同的 `assets/O_AnyImage.blend`，保留现有节点组名称与加载方式。打包验证两版资产字节一致。这里的共享资产包括资产库现有全部节点组，Base 的 AI 内容剥离针对 Python、依赖、配置与界面。

### 5. 一次发布生成六个归档

`uv run pack` 默认构建两版、三个现有平台；`--platform` 仅限制平台，同样生成两版。增加简单的 `--edition full|base` 选项用于单版构建。`--local` 延续完整版本地依赖同步语义，仅接受完整版；Base 从组装产物安装验证。

使用 `pyproject.toml` 的同一个版本号，生成 `AnyImage.v<version>.<platform>.zip` 和 `AnyImage_Base.v<version>.<platform>.zip`，文件名采用各自 Manifest 名称，空格转换为下划线。节点构建在同一次打包中只执行一次，共享依赖下载可复用。Release CI 检查六个归档、两版身份和版本、Base 内容及共同资产，再一起上传现有草稿 Release。含空格的路径作为完整参数传递。

## Risks / Trade-offs

- 混合模块拆分可能遗漏基础依赖 → 用 Base 最终 ZIP 在不含完整版、blendjob 和 AI 环境的 Blender 中执行功能验证。
- 注册失败清理可能影响先启用版本 → 覆盖两种顺序、失败清理以及禁用后切换，检查类型、属性、菜单与快捷键仍属于当前版本。
- 开发环境会掩盖漏打包或残留导入 → 结合明确文件清单、导入关系检查、实际安装与官方扩展校验。
- 基础功能仍使用二进制 wheels → 保留现有平台和 Python ABI 打包支持，按目标运行时验证。

## Migration Plan

先拆开基础与 AI 实现并验证完整版行为，再增加 Base 入口和互斥检查，最后接入双版组装与 CI。用户在 Blender 中禁用当前版本后启用另一版；现有场景字段、节点资产和完整版配置保持原协议。正式发布前验证离线使用、只读安装目录和依赖许可证，准备官方仓库提交产物。

## Open Questions

产品边界已确定。实施时通过依赖审计确定 Base 的最小 wheels 清单，并以 Blender 实际启用失败行为验证局部清理。
