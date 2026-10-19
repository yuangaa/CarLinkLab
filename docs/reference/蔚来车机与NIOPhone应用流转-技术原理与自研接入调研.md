> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](../PUBLICATION-NOTES.md)。

# 蔚来车机 × NIO Phone 应用流转 —— 技术原理与自研应用接入路径（充分调研版）

> 目的：彻底搞清楚「蔚来车机与 NIO Phone 之间的应用流转是怎么实现的」，并回答一个核心问题——
> **在 NIO Phone 团队已收缩、新应用只能靠我们自己开发的前提下，我们自研的应用还能不能上到车机屏、以什么方式上、代价是什么。**
>
> 调研方法：① 通读本仓库全部既有实测文档（主文档 §4.13–4.16、白名单台账、可行路径等，全部为代码级反编译证据）；
> ② 补挖本仓库尚未分析过的 `nio-link-sdk.jar`（NIO 官方跨端 SDK）与 SkyLink 清单；
> ③ 网络调研（官方 Tech Talk / 百科 / 媒体报道 / ICCOA 对标 / NIO 手机业务现状）。
> 日期：2026-10-07
> 关联文档：`项目上下文与成果备忘.md`（实测底座）、`NIO-Link调研报告.md`、`NIO-Link白名单与触发机制.md`、`NIO-Link原生级体验-可行路径.md`

---

## 0. 结论速览（TL;DR）

1. **应用流转的本质**：不是传统投屏，而是「**车机造屏、手机算**」——车机（SkyUI）通知手机侧系统服务 SkyLink **在手机上创建一块虚拟显示器**（id=90000005），应用照常在手机上运行（算力/网络都在手机），这块虚拟屏的画面经 **SkyBus 协议**（自研多车道传输，官方称时延 50ms）编码传给车机显示，车机的触摸再回传注入。双向都是**系统级**通道，普通应用对整个过程无感知。
2. **"原生级 16:9" 与 "9:16 镜像" 的分野**由两点决定：
   - **白名单**（`supportPkgList`，按包名匹配 + `minVer` 门槛）决定应用是否进入"跨端应用"流程；
   - **`mWindowType`（2=镜像 / 6=原生级）由车机经 databus protobuf（`CastScreenProto.ScreenInfo.windowType`）下发**，手机只回显——**手机侧（含应用本身）没有任何"自己决定"的接口**（本仓库 §4.13 反编译铁证）。
3. **官方生态通道对我们实质关闭**：上架 NIO 应用商店 + NIO 云端白名单推送是官方唯一正道，但 NIO 手机团队 2025 年已并入数字座舱、业务收缩、无三代机计划，白名单预期不会再新增第三方应用。
4. **SDK 通路也走不通**（本次新查证）：系统里确有官方跨端 SDK `nio-link-sdk.jar`（`com.skyui.nms.link.*` / `com.skyui.dlink.*`，Nearby-Connections 风格的连接/Payload/投影接口），但其服务入口 `com.nio.nio_link_device.NioLinkService` 虽 `exported=true`，却挂了 `com.skylink.coreservice.permission` **系统签名级权限守卫**——第三方应用绑定不了，该 SDK 是给 NIO 自己的系统组件（如智能车控卡）用的。
5. **自研应用上车，现实中只有三条路**（详见 §6）：
   - **路 A｜系统杠杆**（零改动，待车内验证）：`wm set-ignore-orientation-request` / `allPackagesFullscreen` 等让任意应用在车机屏 16:9，脚本已就绪 `tools/car-orientation-test.sh（已作废，勿运行）`；
   - **路 B｜白名单精简壳**（自研 UI + 借白名单包名当门票）：设计条件已完全摸清（包名 + versionCode≥minVer + 只留一个 launcher Activity），风险已知可回滚；
   - **路 C｜接收端形态**（复用 NioPlay 已验证的通道）：把自研应用做成"被投到车机屏的那个界面"，等价于 CarPlay 接收端模式。
   - 三条路的共同天花板：**车机侧不认我们，就拿不到 6（原生级）**；路 A 若成功可绕过这一点。

---

## 1. 全景：应用流转的技术栈分层

把官方口径与本地反编译证据对齐后，整套流转体系可以拆成 **五层**：

| 层 | 职责 | 实现载体 | 证据来源 |
|---|---|---|---|
| ① 连接与认证层 | 设备发现（靠近自动扫描）、跨端认证（TEE 内账号认证+可信设备认证）、端端加密 | 蓝牙/Wi-Fi/USB-DP/UWB 多物理通道；`nio-link-sdk`（IConnection/IToken/DeviceAuthInfo） | 官方 Tech Talk + SDK 类结构 |
| ② 传输层 | 自研 **SkyBus** 协议：按数据量分"车道"并行传输（大流量=屏幕流，小流量=控制信令），官方称天空视窗时延 **50ms** | databus（`com.databus.proto.CastScreenProto` 等protobuf 信令）+ 屏幕流通道 | 官方口径 + skylink 反编译 |
| ③ 投屏会话层 | 车机↔手机协商：屏幕几何、**windowType**、方向、触摸事件回传 | `com.ucarmd.connectly.remoteapi.*`（ScreenCastController 等）；`CastScreenProto.ScreenInfo.windowType` **由车机下发** | 本仓库 §4.13 反编译 |
| ④ 渲染层 | 手机创建虚拟显示器，应用渲染其上；画面编码→车机；车机触摸→注入回手机 | 虚拟显示器 id=90000005（属主 `com.skyui.skylink.coreservice`，FLAG_SECURE）；`BaseVirtualWindowManager` | 本仓库 §4.1 实测 |
| ⑤ 适配层 | 决定"谁享受什么待遇"：白名单匹配、方向管理器、letterbox、尺寸/密度、音频路由 | `SettingsConfig`（supportPkgList）、`SkyScreenCastOrientationManagerImpl`（skyui-services.jar）、`nio_virtual_devices` 音频 | 本仓库 §4.2/4.4/4.14/4.16 |

**官方对架构的表述**（Tech Talk，王晓铁）：把车端 SOA（面向服务的原子化能力）应用到跨端领域——"手机作为访客融入车端"，即**车机是主人、手机是能力提供方**。这解释了为什么所有关键决策（windowType、方向、白名单待遇）都在车机侧：**车机才是流转的会话控制点**。

> 流转的四种产品形态（官方+实测）：
> | 形态 | 通道 | 范围 | 现状 |
> |---|---|---|---|
> | **天空视窗** | 虚拟显示器镜像（windowType=2） | **所有 App**（9:16 竖屏窗口） | ✅ 可用 |
> | **NIO Link 跨端应用** | 白名单 + 原生级（windowType=6，16:9） | 45 应用+10 游戏 | ✅ 可用，名单封闭 |
> | **跨端通知 / 免费窗口** | cross_dev_notify / free_window | 名单为空 | 未启用 |
> | **沉浸声 / 随车播 / 超级会议** | 音频路由 + 座舱硬件（摄像头/麦克风/方控键）融合 | 手机端杜比/无损→座舱 7.1.4 | ✅ 可用（Apple Music 无损已实测） |

---

## 2. 流转建立的全过程（从上车到车机上出现界面）

综合实测与反编译，一次"跨端应用"流转的完整链路是：

```
[上车] UWB/BLE 靠近发现 → TEE 跨端认证（同账号） → SkyBus 连接建立（Wi-Fi P2P/AP 多车道）
   ↓
[车机] 我在车机 App List → "NIO Link 应用" → 点选某应用
   ↓
[车机→手机] databus 信令：CastScreenProto.ScreenInfo{windowType, screenType, 尺寸...}
   ↓
[手机] SkyLink(coreservice) 校验白名单(getCastSupportAppByName) → 创建虚拟显示器 90000005
        → BaseVirtualWindowManager 按 windowType 定几何（6→16:9 / 2→9:16）
        → 方向管理器 SkyScreenCastOrientationManagerImpl 判定/改写应用方向（letterbox）
        → 把目标应用的 Activity 启动/迁移到虚拟显示器上
   ↓
[持续] 应用在手机渲染 → 虚拟屏画面编码 → SkyBus 屏幕流 → 车机显示
        车机触摸 → 回传 → 注入虚拟显示器（输入变换按当前几何映射）
        音频 → 手机本地解码 → nio_virtual_devices（座舱音响，PCM 无压缩）
```

关键细节（均有实测/反编译依据）：

- **白名单匹配在手机侧**：`SettingsConfig.getCastSupportAppByName(pkg)` 按**包名**匹配；`getCastSupportAppByNameAndUid` 在 `uid==999` 时走"应用分身"分支；条目带 `minVer`（versionCode 门槛）。`checkAnyDoppelganger()` 不是反伪装，反而把分身应用**加入**支持列表（"add the cloned doppelganger app into config support list!"）。
- **但最终待遇（windowType=6）由车机决定**：手机侧三个发送点全是把车机下发的值**原样回显**。已实测：adb 直接把白名单应用启动到车机显示器**也只能拿到 2**——说明原生级待遇还要走**车机侧的正常启动流程**（从车机 App List 点开），不只是包名。⏳ 这是当前最大的未验证前提，零成本即可验证（见 §6 路线图第 1 步）。
- **方向不是应用能自主决定的**：方向管理器把应用分三类——声明横屏的判 `user`（跟随显示器用户旋转）；特殊名单（如 Apple Music 的 `behind`）被**强制竖屏**；飞书/腾讯会议的三个 Activity 写死在 `mForcePortraitForOmniActivities`。NIO 还留了私有后门 `dumpsys window allPackagesFullscreen 1`（置 `mAllowAllPackagesFullScreen=1`，跳过全部白名单检查）——但调用点有 `enforceCallerIsRoot()`，是否 root 专用待车内实测。
- **屏幕参数手机侧改不了**：`wm size` 强改会被 SkyLink 写回且输入变换错位 2.03×（触摸必坏）；正确的横屏杠杆是显示器级 `wm user-rotation -d 90000005 lock 1` + `wm set-ignore-orientation-request -d 90000005 1`。
- **音频是独立车道**：应用声音不经屏幕流，而是手机本地解码 → `nio_virtual_devices` 虚拟声卡（IP 音频、PCM 无压缩、支持 5.1/7.1.4）→ 座舱音响。这就是"手机无损音乐上车"的实现，与画面通道解耦。
- **云端可更新但已冻结**：白名单配置（ver=20260114）支持 `com.skyui.cloud.config` 云端下发（加应用不需 OTA），但所有更新入口带系统签名级权限守卫，第三方无法注入；生效配置缓存在 SkyLink 私有目录（shell 也写不了）。

---

## 3. 官方跨端 SDK 深挖（本次新成果：`nio-link-sdk.jar`）

系统分区 `/system/framework/nio-link-sdk.jar` 此前未被分析过。本次反汇编其 `classes.dex`，得到 NIO 跨端能力的**官方编程接口面**：

### 3.1 SDK 结构（com.skyui.nms.* / com.skyui.dlink.*）

| 包 | 内容 | 对应能力 |
|---|---|---|
| `nms.link.connection` | `IConnection`(AIDL)、`Payload{File,Stream}`、`PayloadTransfer(Update)`、`IPayloadCallback`、`IProjectionCallback`、`IPositionCallback`、`ConnectEngine`、`IDiagnoseCallback` | **通用跨端连接**：字节/文件/流传输、**投影会话回调**、位置回调、诊断。API 形态几乎复刻 Google **Nearby Connections** |
| `nms.link.device` | `IDeviceManager`、`DeviceInfo`、`Capbilities/CdcCapbilities`、`AudioSinkInfo`（音频输出端信息）、`DeviceAuthInfo` | 设备管理、**能力协商**（对端支持什么）、**音频汇点**（沉浸声的基础） |
| `nms.link.api` | `IToken`、`TokenInfo`、`VersionInfo` | 跨端认证令牌（TEE 认证的客户端面） |
| `nms.task` | Task/Promise 风格异步框架 | API 易用性封装 |
| `dlink.*` | `IDLinkClient`/`IDLinkService`(AIDL 双向)、`DLinkClientManager`、`DLinkConnectEngine` | 客户端-服务绑定框架（手机内系统组件 ↔ SkyLink 服务） |

### 3.2 对"我们自研应用"意味着什么

- **普通第三方应用用不了**：SkyLink 清单中服务入口
  `<service android:exported="true" android:name="com.nio.nio_link_device.NioLinkService" android:permission="com.skylink.coreservice.permission">`
  ——`exported=true` 但权限守卫是 NIO 平台签名级（`signature`），我们的应用拿不到该权限，`bindService` 必被拒。SDK 的定位是**给 NIO 自家系统组件**（智能车控卡、系统相册、通话等）提供跨端能力，不是开放给生态的。
- **理论上唯一残余价值**：如果未来拿到 root/刷入自编系统，这层 SDK 就是现成的"合法流转接口"（Payload 传输、投影回调、AudioSinkInfo 等都在），无需逆向协议。**仅作记录，当前不投入。**
- 侧面印证架构判断：SDK 里**没有**任何"创建虚拟显示器/请求 windowType"的应用侧 API——应用在流转里是**被动搬运的货物**，会话控制完全在 SkyLink（手机系统服务）与车机之间。

---

## 4. 生态现状（网络调研）：为什么"只能靠自己"

| 事实 | 来源与时间 | 影响 |
|---|---|---|
| NIO 手机团队 2025 年收缩：独立业务线裁撤，软件团队并入**数字座舱**部门；两代产品后终止迭代，累计投入超百亿的项目按新 ROI 规则不再获批 | 2025 年报/多篇 2026 年报道 | **白名单、天空视窗、SkyLink 的手机侧迭代基本冻结** |
| 2026-05 有"新款 NIO Phone 宣传图"流出，但被解读为存量设计的延续而非重启；核心车手互联团队"没散，换汇报对象" | 新浪 2026-05 | 车端（数字座舱）可能仍会维护 SkyLink 兼容性，但**手机侧应用生态不会再扩张** |
| 官方接入闭环 = 上架 **NIO 应用商店**（白名单条目自带商店图标 URL `appIcon`）+ NIO 云端推送白名单 | 官方指南 + settings_config.json | 官方路径两头都握在 NIO 手里；团队收缩后**实质关闭** |
| 官方反馈渠道仍在：「设置→帮助和反馈→车手互联」可提应用建议 | 官方指南 | 成本≈0 可提交，但预期响应极低 |
| **对标（ICCOA CarLink）**：小米/OPPO/vivo 主导的开放联盟协议，投屏→融合桌面(1.5)→应用小窗(1.6)→镜像(2.0)→3.0(多窗口/语音融合)，装车 1500 万辆 | ICCOA 官网/百科 | 行业通用做法也是"**虚拟屏 + 应用适配 + 联盟认证**"，与 NIO 私有体系同构；但 蔚来车机**没有** ICCOA 客户端，此路不适用于本机，仅作机制参照 |

> 一个值得注意的细节：ICCOA 的表述"结合手机系统能力**创建虚拟屏幕**，将适配过车机端的 APP 显示在车机端"与本仓库对 SkyLink 的反编译结论**完全同构**——这佐证我们的架构理解就是业界通用模型，只是 NIO 做成了全私有栈（连投屏协议都不用现成的 Miracast/投屏标准，自研 SkyBus 以压时延）。

---

## 5. 自研应用上车的全部候选路径（现状与风险全景）

前提约束（全部实测）：无 root、平台签名拿不到、白名单配置写不了、车机显示器 FLAG_SECURE 截不了图、`pm disable-user` 不能改第三方组件、手机只保留干净的 NioPlay（不再装 NioPlay 系新应用——**注意：路 B 的精简壳不属 NioPlay 系，但需我点头**）。

### 路 A：系统杠杆（不改应用，让任意 App 16:9）⏳ 唯一待办
| 杠杆 | 机制 | 状态 |
|---|---|---|
| `wm set-ignore-orientation-request -d 90000005 1` | AOSP 标准：显示器忽略应用请求的方向 | 本机命令可用，**车内待验证（最有希望）** |
| `wm user-rotation -d 90000005 lock 1` | 锁定车机显示器用户旋转为横屏 | 待验证（与一条旧死路记录冲突，需成对测） |
| `am compat enable 265464455 <pkg>` | OVERRIDE_ANY_ORIENTATION 兼容性覆盖 | 待重测（上轮未真启动应用，结论无效） |
| `dumpsys window allPackagesFullscreen 1` | NIO 私有：跳过白名单 letterbox 检查 | 代码确认有效路径存在；疑被 `enforceCallerIsRoot()` 拦，待车内验证 |
| `skyui_custom_rotation` / `skylink_inject_rotation(_value)` | 框架/SkyLink 的旋转注入 hack（shell 可写） | 语义未全解，作为备选试探 |

- ✅ 对**任何应用**（含自研 App、Apple Music）一视同仁，不碰包名、风险可一键还原。
- ❌ 只解决"方向/全屏"，**改不了 windowType**（仍是 2，形态=放大窗口而非原生级入口）；若 `allPackagesFullscreen` 被 root 门槛拦掉，则依赖 B 组开关生效。
- 脚本：`tools/car-orientation-test.sh（已作废，勿运行）`（6 组对照，已就绪，判据：车机屏几何 3200×1440=成功）。

### 路 B：白名单"精简壳"（自研 UI + 借名单包名当门票）
- 设计条件（§4.16 已完全摸清）：包名 ∈ 名单未安装空位（41 个可选）+ `versionCode ≥ minVer` + **只留一个渲染 UI 的 launcher Activity**（严禁带 CarPlay/MFI/USB 全套——上次完整拷贝导致 NIO Link 闪退）+ 回滚 = `adb uninstall`。
- 能得到什么：车机 App List 出现我们的入口、按跨端应用流程启动。**但 windowType=6 仍由车机下发**——需先完成 §6 第 1 步的基线观测（白名单应用走正常流程到底拿 6 还是 2）才值得投入。
- 风险最高（曾致 NIO Link 闪退）；且壳上跑的是自研 UI（我已否过一次自研界面，需确认这次的产品形态不同——壳里跑"任何我们想上车的东西"）。

### 路 C：接收端形态（NioPlay 通道复用）
- 已验证的成熟通道：NioPlay（CarPlay 接收端）把 iPhone 界面投上 ET5T 中控，横屏、触摸、车机按钮、座舱音频全部可用。
- 变体：把"接收端"从 iPhone 换成**同一台手机上的自研应用内容**（应用把画面/控制暴露出来，经既有通道呈现到车机屏）。
- ✅ 唯一**完全不依赖 NIO 配合**、且画面比例完全可控的路。
- ❌ 本质仍是"镜像类"，非 NIO Link 原生级；需解决手机→车机的画面通路（NioPlay 通道是 iPhone↔手机的，手机本机内容要走 MediaProjection 类方案）。

### 已封死的路（别再投入）
| 路 | 死因 |
|---|---|
| 官方 SDK 接入 | `NioLinkService` 挂系统签名权限守卫（本次查证） |
| 改白名单配置 / 等云端推名单 | 无 root + 平台签名 + 私有目录 + 权限守卫；且手机团队已收缩，无新增预期 |
| 重打包目标 App（改包名进白名单） | 破坏签名 → DRM/登录/完整性检查崩（Apple Music 实测 85 处 FairPlay 痕迹） |
| Android Auto 路线 | CDM `signature|privileged` 权限死结（§4.9/4.12 双证据链） |
| `wm size` 强改车机显示器 | SkyLink 写回 + 输入变换 2.03× 错位 |

---

## 6. 建议的执行路线图（一次进车可完成 1–2 步）

1. **基线观测（零风险，决定路 B 生死）**：车内打开天空视窗 → 从**车机** App List 点开已装的 4 个白名单应用之一（YouTube/Chrome/腾讯视频/文件管理）→ 看是否铺满 16:9 + 抓 `BaseVirtualWindowManager ... mWindowType=?`。
   - 拿到 **6** → 包名是门票，路 B 可行；
   - 仍是 **2** → 路 B 白做，聚焦路 A/C。
2. **同趟车跑 `tools/car-orientation-test.sh（已作废，勿运行）`（6 组对照）**：判定系统杠杆能否让任意应用 16:9（判据：车机屏几何 3200×1440）。
3. **按 1/2 结果选择**：
   - 杠杆有效 → 自研 App 直接以普通应用身份上车（配合 `wm density -d 90000005 600` 出平板布局），零伪装零风险；
   - 杠杆无效且基线=6 → 做白名单精简壳（先精简设计 + 回滚预案，选 `installed=no` 的媒体类空位包名）；
   - 都不行 → 路 C 接收端形态兜底。
4. **顺手做（成本 0）**：手机「设置→帮助和反馈→车手互联」提交自研应用接入诉求，保留一条官方窗口。

> 我能独立完成的：壳开发、脚本、logcat 抓取与分析、构建与回滚。
> 需要我：物理上车 + 在车机上点击 + 人眼判断画面效果（车机屏 FLAG_SECURE，无法截图验证）。

---

## 7. 本次调研新增事实清单（此前文档未覆盖）

| # | 新事实 | 方式 |
|---|---|---|
| 1 | `nio-link-sdk.jar` 完整类结构：Nearby-Connections 风格的 IConnection/Payload/IProjectionCallback/IToken/DeviceManager + `dlink` 客户端框架 | dexdump 反汇编 |
| 2 | SkyLink 清单中 `com.nio.nio_link_device.NioLinkService` exported=true 但带 `com.skylink.coreservice.permission` 守卫 → SDK 对第三方应用**关闭** | 读反编译清单 |
| 3 | `NioLinkSettingsActivity` 带 `com.skylink.permission.NIO_LINK_SETUP` 守卫；`NioLinkInCallService` 是系统 InCallService（超级会议的通话路由载体） | 同上 |
| 4 | NIO 手机业务现状：2025 独立业务线裁撤、并入数字座舱、ROI 规则下不再获批迭代；2026-05 有存量宣传图流出但非重启 | 网络调研（2025 年报、多篇 2026 报道） |
| 5 | 官方架构口径：SkyBus 多车道协议（50ms 时延）、车端 SOA 复用到跨端（"手机作为访客"）、TEE 账号+可信设备认证、端端加密 | 官方 Tech Talk（王晓铁）/ 百科 |
| 6 | 超级会议/会议类应用（type=2）的额外待遇来源：车机把视频流转到中控屏、音频流转到座舱音响/麦克风、方控键接挂——是**座舱硬件融合**，不只是屏幕流转 | 官方《玩转 NIO Phone》 |
| 7 | 官方指南确认：NIO Link 应用**必须经 NIO 应用商店下载**（与白名单条目 `appIcon` 商店 URL 互证）——官方生态闭环形态 | 官方指南 |
| 8 | ICCOA CarLink 模式（虚拟屏+融合桌面+应用小窗+联盟认证）与 SkyLink 同构；蔚来车机无 ICCOA 客户端，不可用，仅作参照 | ICCOA 官网/百科 |

---

## 8. 参考资料

**本地（实测/反编译）**
- `docs/项目上下文与成果备忘.md` §4.1–4.16（虚拟显示器、白名单、windowType、方向管理器）、§5（死路）、§7.5（工具坑）
- `docs/NIO-Link调研报告.md`（机制深挖、方向注入通道）、`docs/NIO-Link白名单与触发机制.md`（55 条白名单台账+修订记录）、`docs/NIO-Link原生级体验-可行路径.md`（A/B/C 方案设计）
- `data/nio_link_whitelist.csv`、`data/settings_config.json`（白名单机器可读数据，md5 已核验）
- `tmp/skylink/dec/`（SkyLink 2.10.8 全量反编译）、`tmp/niolink/`（skyui-services/framework.jar、nio-link-sdk.jar）

**网络**
- 蔚来官方 Tech Talk《车与手机的全景互联是如何实现的?》 https://www.nio.cn/smart-technology/20240119011 （王晓铁：SkyBus/SOA/TEE）
- NIO Link 百科（技术原理/迭代时间线） https://baike.baidu.com/item/NIO Link/63503653
- 官方指南《如何在舱内体验更多手机应用》 https://phone.nio.com/niolink-guide/how-to-use-more-mobile-applications-inside-of-vehicle
- 官方《玩转 NIO Phone｜打造私人会议室》 https://www.nio.cn/app-articles/531433
- NIO 手机业务收缩报道（新浪 2026-05、头条 2026 等，见正文 §4 表格）
- ICCOA 智慧车联开放联盟 https://www.iccoa.cn/ 及 Carlink 百科（对标参照）
