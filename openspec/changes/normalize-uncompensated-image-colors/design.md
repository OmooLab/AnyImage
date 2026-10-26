## Context

材质与笔刷共用 `configure_material_color_image()`。材质准备流程生成独立 `_color`，笔刷直接使用传入 Image。普通 sRGB 贴图需要将 inverse 解码后的高值压入 0～1；鳄鱼对比确认采用固定 T＝4、各通道分别截断、Gamma 0.75。

## Decisions

### 1. 在共用入口选择颜色策略

通过 `preferences.py` 读取默认开启的 Compensate Image Colors。

| 输入 | 补偿开启 | 补偿关闭 |
|---|---|---|
| 普通 byte 图，inverse 空间可用 | inverse + STRAIGHT，保留业务像素 | inverse 解码 → 固定归一化 → sRGB + PREMUL，原地改值 |
| 场景解析为 sRGB 或 inverse 不可用 | sRGB + PREMUL | sRGB + PREMUL |
| float/HDR 或保留源解释的非 sRGB Shadeless 分支 | 沿用源解释 | 沿用源解释 |

inverse 映射覆盖运行中 Blender 支持的 ACES 1.3、ACES 2.0、AgX、Filmic 和 Khronos PBR Neutral。已归一化 Image 直接保留当前 sRGB 内容。

### 2. 固定各通道映射

对 inverse 解码得到的线性 RGB `L` 执行：

```text
normalized = (clamp(L, 0, 4) / 4) ** 0.75
encoded = linear_rgb_to_srgb(normalized)
```

R、G、B 分别计算：超过 4 的分量截断到 4，负数归零，除以 4 后应用 Gamma 0.75。最后复用 `common/color_space.py` 的 sRGB 编码函数。T 和 Gamma 是固定规则。

全部像素（含透明区域的隐藏 RGB）使用相同变换，Alpha 原样保留。同一颜色的结果独立于裁切、透明度和其他像素。输入或解码结果含 NaN / Inf 时明确失败并恢复原内容。

### 3. 通过 Blender 求值 inverse 颜色

`decode_color_image()` 使用运行中 Blender 的 OCIO 配置：将 byte RGB 写入所选 inverse 空间的临时图，以 float32 线性 EXR 保存并回读。临时图的 Alpha 设为 1，避免 EXR 预乘改变 RGB；业务 Alpha 单独保留。求值结果用 Blender 直接纹理采样交叉验证。

数组映射位于 `common/color_space.py`；Blender 图像求值位于 `common/color_image.py`；配置、写回和打包由现有 common 入口完成。Blender 数据操作在主线程执行，临时图、场景和文件在结束时释放。

### 4. 原地提交与处理状态

材质直接更新已准备的独立 `_color`，保留原始 Empty 图。笔刷更新传入 Image，共享该 Image 的引用看到相同结果。

成功后设置 `anyimage_color_normalized`。重复配置、打包重载、编辑及以该图准备新颜色图时保留状态；替换为全新原始内容时清除状态。偏好变化影响后续未处理输入，需要重新处理时从原始来源准备颜色图。

使用 `image_content_state()` / `restore_image_content()` 保存和恢复像素、颜色空间、Alpha 模式、打包内容及处理状态。写回后重新打包；笔刷交付失败也回滚图像和绑定。原地修改后，剪贴板缓存通过既有内容哈希识别变化，再次粘贴原始内容时重新准备。

## Validation

- 已知颜色覆盖各通道截断、Gamma、sRGB 编码、Alpha、负值及非有限值；裁切和极端像素验证固定映射。
- byte、generated、dirty、packed 来源覆盖重复配置、编辑、保存重载、真实纹理采样和失败恢复。
- 材质和三种笔刷模式覆盖入口一致性、图像身份及缓存失效。
- 鳄鱼正式入口输出与认可的 T4、Gamma 0.75 对比贴图逐像素核对；对比场景共用 HDRI 和环境光，以原始 Empty 为参照。

## Trade-offs

独立截断和 Gamma 会改变部分 RGB 比例，高于 4 的亮部细节会丢失。这是对比实验选定的亮度与对比折中。运算保持浮点精度，最终 sRGB byte 存储存在量化误差。场景光照由用户调整，配置函数保持场景设置不变。
