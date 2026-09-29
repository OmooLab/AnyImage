## REMOVED Requirements

### Requirement: Cutout 厚度模式共享双区 UV 协议
**Reason**: 创建期上下双区布局由单图编辑和静态转换取代。
**Migration**: Balloon、Shell 与零厚度使用源 UV，在生成面的位置保留来源身份，专用 Convert to Mesh 再生成独立区域。
