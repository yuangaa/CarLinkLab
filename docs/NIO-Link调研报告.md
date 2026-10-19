> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](PUBLICATION-NOTES.md)。

# NIO Link / 天空视窗 / 跨端应用 —— 调研报告

> 目的：搞清楚「蔚来车机是怎么把手机应用按车机屏幕比例展示成"原生感"的」，以及**让 NIO Phone 上的 Apple Music 在车机上获得大界面 + 可操作 + 无损音频**这条路的可行性与备选方案。
> 状态：**纯调研**（只读：拉 APK / 读配置 / 反编译 / 查系统设置；**未做任何设备改动**）。
> 日期：2026-10-07　设备：NIO Phone N2301（SkyUI / Android 14）、蔚来 ET5T（Banyan 平台）
> 关联文档：`docs/项目上下文与成果备忘.md`（§4.3 / §4.4 / §4.13 / §5 / §6 为本报告的实测基础）

---

## 0. 结论速览（TL;DR）

1. **你的判断基本正确**：SkyLink 对白名单里的应用，会给它一个**按车机屏几何的横屏大尺寸显示环境**，应用于是走自己的"大屏/横屏"布局 —— 官方文案原话是 **「应用界面完美适配车机中控屏」**。可理解为"给应用造了一块横屏大屏"，效果接近应用的**平板模式**，而不是把手机竖屏放大。应用算力仍在手机（官方文案：「应用运行依赖手机算力和网络」）。
2. **Apple Music 现在难看，是三层原因叠加**：① **不在白名单** → 退化为"手机镜像"分支（9:16）；② 它的 Activity 大量声明 `behind`，被 SkyLink 方向管理器判为竖屏；③ 天空视窗本身是"第二界面"窗口，**不是铺满中控屏的全屏**。
3. **好消息（本次最有价值的正面结论）**：Apple Music 安卓版 **6.5.2 自身具备横屏/大屏适配能力** —— 带 `land / large / xlarge / sw600dp / sw720dp / sw900dp-land / w640dp-land / h360dp-land / h480dp-land` 全套资源，且 `resizeableActivity=true`。**它缺的不是能力，而是"被放进一个横屏大屏环境"**。
4. **白名单本身改不了**（系统只读分区 + 云端配置 + 私有目录 + 权限保护），但发现 SkyLink 内部有一条**虚拟显示器方向注入通道**（`VirtualDisplayOrientationUtil`，**带触摸补偿**，由**车机侧**发起）—— 这是目前最值得试的"自助"杠杆。
5. **白名单里一个音乐 App 都没有**（45 项，零音乐）→ 说明"NIO Link 应用"这条产品线定位在**会议/办公/视频/证券**；音乐是交给**车机原生音乐应用 + 沉浸声**的。这是 Apple Music 上车的最大**非技术**障碍。
6. **官方有正式需求渠道**：手机「设置 → 帮助和反馈 → 车手互联」；且名单是**云端下发**的（配置 `ver=20260114`，框架见 §2.3）→ NIO 加一条**不需要 OTA**。
7. **另外一条更彻底的路已经探明且被判死**：Apple Music 自带 `com.google.android.gms.car.application` → **原生支持 Android Auto**，所以"AA 车机端"理论上能给它官方车机 UI；但**这台 NIO Phone 上 AA 单机自投影无解**（见 §6，理由：AA 非系统应用，缺 `signature|privileged` 的 CDM 权限）。

---

## 1. 先把 NIO Link 里的几个东西分清楚

| 名称 | 是什么（官方口径） | 与"用 Apple Music"的关系 |
|---|---|---|
| **天空视窗** | 中控屏里出现一块手机"第二界面"；手机与车机可**并行独立操作**（非纯投屏）；**"可以使用手机上的所有 App"**；支持横屏显示（适合游戏/视频）；音视频应用可直接用**座舱高功率音响** | ✅ 任何应用（含 Apple Music）都能开；但窗口/比例不理想 → 界面小、9:16 |
| **NIO Link 应用**（= 跨端应用，`cross_dev_app`） | 白名单应用在车机上的"原生级"呈现：**「应用界面完美适配车机中控屏」**，可调车内摄像头/麦克风/音响、支持方控键 | ❌ 白名单**无音乐类应用**，Apple Music 不在其中 |
| **NIO Link 游戏**（`cross_dev_game`） | 手机游戏流转到中控屏，配手柄 | ⚪ 无关，但它是"按屏给尺寸"的样本：`gameSize[]` 逐屏列了尺寸与填充方式 |
| **跨端通知**（`cross_dev_notify`） / **免费窗口**（`free_window`） | 手机通知在车机提醒 / 悬浮小窗 | ⚪ 两个名单**都是空的** |
| **沉浸声** | 手机端杜比全景声/无损音频 → 车端 7.1.4 音响 | ✅ 这正是"用手机 Apple Music"的**音质卖点**（`nio_virtual_devices`，PCM 无压缩） |

> 官方指南引文（天空视窗）：*"通过车内中控屏可以快捷预览手机桌面，**可以使用手机上的所有 App**"*；*"在'中控屏'打开的手机音视频应用，可以直接使用座舱高功率音响系统播放音乐"*；*"天空视窗**支持横屏显示**，适合：游戏、视频等应用"*。
> 官方指南引文（NIO Link 应用）：*"部分功能体验不友好，**取决于三方应用适配度**"*；*"如希望支持更多应用，你可以通过手机『设置』-『帮助和反馈』-『车手互联』提交你的建议"*；且**应用需通过 NIO 应用商店下载**。

**关键区分**：天空视窗 = 「所有 App」的通用通道（所以 Apple Music 能开，但形态不受控）；**跨端应用 = 精选白名单 + 逐应用适配参数**（所以"像原生"）。我想要的正是后者的效果。

---

## 2. 跨端应用是怎么"适配"的（机制，含代码级证据）

### 2.1 两条渲染分支（实测）

| 分支 | 日志特征 | 结果 |
|---|---|---|
| 手机镜像 | `BaseVirtualWindowManager: getVirtualDisplay mScreenType=1, **mWindowType=2**` | 按手机比例（9:16）投到车机屏 → 界面小、两侧黑边 |
| 车机原生级 | **`mWindowType=6`** | 16:9 铺满、应用走大屏布局 → "如原生" |

- 天空视窗显示器：`id=90000005`、`uniqueId` 含 `com.nio.link.connly.five`、属主 `com.skyui.skylink.coreservice`、带 `FLAG_SECURE`（所以**车机屏无法截图**）/`FLAG_ROTATES_WITH_CONTENT`/`FLAG_PRESENTATION`。
- SkyLink 里还有 `nio.link.connly.one / two / … / seven` 多个通道名 → 同一机制可按通道建多个显示环境（对应中控屏/后排屏等）。
- **`mWindowType` 由车机下发**：反编译（项目文档 §4.13）显示它来自车机 databus protobuf `CastScreenProto.ScreenInfo.windowType`，手机只是回显 → **手机侧无法自己决定要 6**。

### 2.2 白名单配置（车机上生效的实物）

- 位置：SkyLink APK 内 `assets/settings_config.json`；**手机上当前生效的 SkyLink 是 2.10.8**（`/data/app`，可更新版），系统分区另有出厂 2.0.7。
- 结构与规模：
  - `ver = 20260114`（2026-01 的名单版本）；`controlSwitch.crossApp = 1`（跨端应用**已开启**）
  - `supportPkgList[]`：`cross_dev_app` **45 项**、`cross_dev_game` 10 项、`cross_dev_notify` **0**、`free_window` **0**
  - 每项字段：`pkgName` / `appName`(多语言) / `minVer` / `screenType` / `type` / `immersive` / `immersiveDisplayMode` / `supportSize` / `support_min_window`
- **音乐类检索结果：零**。全文无 `apple / spotify / netease / kugou / kuwo` 任何包名。名单里最"娱乐"的是腾讯视频、爱奇艺、优酷、B站、抖音、快手、芒果TV、YouTube、VidHub、网易爆米花。
- 字段语义（**推断**，依据取值分布 + 屏幕清单 + 游戏尺寸表）：
  - `screenType`：**疑似按位表示"允许出现在哪些屏"**。应用多为 `7`（=1\|2\|4）；文件管理 `5`（=1\|4）；游戏 `3`（=1\|2）。游戏的 `gameSize[]` 显式列了 `screenType: 1/2/4/8` 各自的尺寸与填充 → 强烈支持"位掩码 = 屏幕集合"。
  - `immersive` + `immersiveDisplayMode(fitX/fitY/fitXY)`：是否沉浸全屏 + 填充策略。
  - `supportSize`：目标渲染尺寸（游戏给的是 `[1728,1296]`）。
  - `support_min_window`：是否允许小窗（微信/飞书/钉钉为 `true`）。
  - `minVer`：应用最低版本门槛（伪装包曾靠"提高 versionCode"绕过）。
- 屏幕清单（来自 SkyLink 文案）：**中控屏、左后排屏、右后排屏、后排娱乐屏**（副驾/行政屏按车型）。

### 2.3 名单是**云端可更新**的

SkyLink 内有完整云端配置框架：`/nio/base/config/ConfigManager`、`ConfigUpdateReceiver`、`bean/{Config, GlobalConfig, SettingsConfig, SupportApp, SupportPkgListDTO, GameSize}`，内容提供者 `com.skyui.cloud.config`（表 `base_config` 等）。

- 实测：以 shell 查询被拒 → `requires com.skyui.cloud.permission.CLOUD_SYNC`（**无 root 读不到**）。
- 缓存位置（项目文档 §4.13）：`Context.getFilesDir()/settings_config.json` → 私有目录，**shell 写不了**；更新入口 `ConfigUpdateReceiver` 虽 `exported=true`，但带 `android:permission="com.skyui.netconfig.permissions.CONFIG_UPDATE"` → 第三方发不进去。
- 意义：**NIO 加一个新应用只需云端推配置，不需要整车 OTA、不需要升级 SkyLink**。对"提需求"这条路是重大利好。

### 2.4 【本次新发现】SkyLink 内置的"虚拟显示器方向注入"通道

反编译 `tmp/skylink/dec/` 查到 `com/nio/util/virtual_display/b` = **`VirtualDisplayOrientationUtil`**（单例）：

- 两个 Global 设置键：`skylink_inject_rotation`（状态；写入 **4 = 注入生效**）、`skylink_inject_rotation_value`（字符串三元组）
- 内置 8 个注入值（4 个方向 × 2 组）：
  `"0,-10,0"`、`"10,0,0"`、`"0,10,0"`、`"-10,0,0"`、`"1,-10,0"`、`"10,1,0"`、`"1,10,0"`、`"-10,1,0"`
- `start(orientation)`：只接受 **0~3**，否则打日志 `start fail, invalid orientation`；随后把 `skylink_inject_rotation` 置 4，并在自己的 `Orientation_Thread` 上**每 1 秒循环重发**注入值（`handleMessage` 里 `sendMessageDelayed(..., 1000)`）→ 与系统的方向锁定"对抗"
- **调用方是"车机侧 API 层"**：`com/ucarmd/connectly/remoteapi/b.adjustOrientation(boolean)` → `false → 方向 3`、`true → 方向 2`
- 设备实测这些键确实存在且可写：`skylink_inject_rotation=4`、`skylink_inject_rotation_value=0,10,0`、`skylink_feature_switch=15`、`skylink_cast_start=null`、另有 `skyui_custom_rotation=-1`

**意义**：说明 NIO 自己有"旋转虚拟显示器"这条路径，**并且配套做了触摸坐标补偿**（这正是 `wm size` 强改后会 2.03× 错位的反面 —— 走它的通道才不错位）。因为两个键是 shell 可写的 Global 设置，**存在"人工模拟车机请求"的可能**（需在车机连着时实测；语义尚未完全解析，尤其是方向 2/3 到底对应横/竖）。这是本次调研给出的**最有希望的自助杠杆**。

---

## 3. 为什么 Apple Music 现在是"竖屏小界面"

1. **不在白名单** → 不走"原生级"分支 → 退化为手机镜像（9:16）。**主因**。
2. **方向声明为 `behind`** → SkyLink 方向管理器 `SkyScreenCastOrientationManagerImpl` 判其为竖屏并锁住（实测日志 `modify orientation from 0 to 1`）。
3. **天空视窗不是全屏设计**：官方定位是"中控屏右侧的第二界面"（可拖动/最小化/自动收起），官方也说"放视频时可放大至半屏，**不能全屏观看**"。

---

## 4. Apple Music 自身能力体检（实测清单数据）

版本：`com.apple.android.music` **6.5.2（versionCode 1586）**，targetSdk 35。

| 项 | 结果 | 意义 |
|---|---|---|
| `resizeableActivity` | **true** | 允许被自由调整大小（大屏/多窗友好） |
| Activity 方向声明 | `behind`×12、`portrait`×7、`unspecified`×1 | 主界面走 `behind`；少数次要页（onboarding/播放等）锁竖屏 |
| 大屏/横屏资源 | **有**：`land`、`large`、`xlarge`、`h360dp-land`、`h480dp-land`、`sw600dp`、`sw720dp`、`sw900dp-land`、`w600dp-land`、`w640dp-land`（含 `land` 的配置 200+ 处） | **具备在横屏大屏上出"平板式"布局的能力** ← 最有价值的正面结论 |
| Android Auto | 声明 `com.google.android.gms.car.application` | **原生支持 AA** → 原理上能拿到官方车机 UI（但本机 AA 路已断，见 §6） |
| DRM | 只在"开始播放"那一刻校验输出路径（19623） | 先起播 → 再投屏 即可绕开（项目已有结论） |

---

## 5. 可行路径对比（按推荐度）

| # | 路径 | 做法 | 前置条件 | 预期效果 | 风险/成本 |
|---|---|---|---|---|---|
| **A** | **逼 Apple Music 走横屏大屏**（自助，最优先） | ① 兼容性覆盖 `am compat enable 265464455 com.apple.android.music`（`OVERRIDE_ANY_ORIENTATION`；实测该 change 在本机存在且 **Apple Music 已被单独 override**）；② 试 `skylink_inject_rotation` / `_value` 这组**shell 可写**开关（模拟车机的 `adjustOrientation`）；③ 配合已设好的显示器横屏 | **必须在车里**（需要天空视窗显示器存在）；已有脚本 `tools/car-orientation-test.sh（已作废，勿运行）` | 若成功 → **真正的 16:9 车机界面**，音频仍是手机端无损 | 中。7 个竖屏页会 letterbox；天空视窗"非全屏"是产品限制 |
| **B** | **官方渠道提需求：把 Apple Music 加进 `cross_dev_app`** | 手机「设置→帮助和反馈→车手互联」提交；或走更正式渠道（已有《给 NIO 的需求稿》） | NIO 产品决策 | 一旦加入 = **"完美适配车机中控屏" + 无损音频**，最理想 | 低风险、低确定性；名单**零音乐**说明是产品定位问题 |
| **C** | **身份伪装（精简壳）** | 用白名单里某个包名装一个**只做一件事的精简壳**（上次完整拷贝 → NIO Link 闪退） | 需严格精简 + 准备好回滚（卸载伪装包） | 车机可能给出"原生级"入口（`mWindowType=6`） | 高。合规/稳定性风险最大；且宿主拿到 6 不等于 Apple Music 拿到 6 |
| **D** | 改 Apple Music APK（改方向/塞横屏） | 重打包 | — | 不可行 | 破签名 → 登录/DRM 风险大；且它本就有横屏资源，收益为 0 |
| ~~E~~ | ~~Android Auto 车机端~~ | Self-Mode（Open Headunit） | — | ~~官方车机 UI~~ | ❌ **已被实测否决**（见 §6） |

---

## 6. 关于 Android Auto（补充：这条路已实测否决）

- 期望：Apple Music 有官方 AA 元数据 → AA 车机端一旦跑通，就能给它**官方车机 UI**（大按钮、横屏）。
- 实测否决（项目文档 §4.9 / §4.12，两条独立证据链）：
  - AA **17.7**：`headunit-server`（5277）一 accept，AA 的 `:car` 就要拉 `gmscorecompat.FirstActivityImpl`，而该 Activity 清单写死 `enabled=false` → `ActivityNotFoundException` → 连接立即被丢弃（这也解释了"接受连接但一个字节不回"的观感）。
  - 降级 **17.3**：能走到 `WIRELESS_WIFI_SOCKET_CONNECTED`，但 AA 注册车辆时缺 **`REQUEST_COMPANION_SELF_MANAGED`（`signature|privileged`）** → `Failed to register vehicle with CDM` → 连接被 reset。
  - 本机 **AA 是纯用户应用**（无系统 stub），永远拿不到该权限 → **单机自投影无解**（除非 root/改 system，或换一台"AA 是预装系统应用"的设备）。
- 结论：**AA 不作为本目标的手段**；手机上的 AA 已恢复为原 17.7。

> 备注：本会话早期曾怀疑"NIO 的 `QuickFreezeManager` 冻结 AA 进程导致握手无响应"——该现象**确实存在**（AA/OHU 都被冻过，可用 `settings put global cached_apps_freezer disabled` + Doze 白名单缓解），但它**不是** AA 走不通的根因；根因以上面两条 CDM/组件禁用为准。

---

## 7. 建议的下一步实验（等确认后再动手）

1. **实验 A-1（成本最低，已有脚本）**：在车里 → 打开天空视窗 → 跑 `tools/car-orientation-test.sh（已作废，勿运行） com.apple.android.music`（自动做"`am compat enable/disable 265464455`"两组对照，读车机显示器几何 + 应用窗口 frame + `mWindowType` 日志，结束自动还原）。
   - 通过标准：显示器 `cur=3024x1696`（横屏）且 Apple Music 出现横向布局。
2. **实验 A-2（本次新发现，最值得试）**：在车内、天空视窗已开的前提下，用 `settings put global skylink_inject_rotation 4` + `skylink_inject_rotation_value <某个三元组>` 逐个试探（8 个内置值 + 方向 2/3 的对应关系），观察车机显示器是否旋转、触摸是否仍然准确。
   - 注意：一次只改一个值；改前记录原值（当前 `4` / `0,10,0`），随时可还原。
3. **路径 B（零风险，可立刻做）**：手机「设置→帮助和反馈→车手互联」正式提交"希望 Apple Music 支持跨端应用"，附《给 NIO 的需求稿》（论点：名单云端可更新、已是现成机制、只差一条配置）。
4. **路径 C（最后手段）**：只有 A/B 都不通才考虑"精简壳"伪装，且必须先设计好回滚。

**需要你在车里确认的（我做不了）**：
- 天空视窗有没有"全屏/横屏"按钮？窗口能拖到多大？
- 车机 App List → "NIO Link 应用"里实际列出的应用，是否与 45 项配置一致？
- 跨端应用打开时是铺满还是带黑边？

---

## 8. 证据与文件清单

| 项 | 位置 / 说明 |
|---|---|
| SkyLink 当前生效 APK | 设备 `/data/app/~~YlMlYgmrEt9Ff8VYZGKxMw==/com.skyui.skylink.coreservice-vUt9XELuf0TnKtT7RmbNnw==/base.apk`（**2.10.8**）；本地副本 `/tmp/skylink/skylink-current.apk` |
| 白名单配置 | APK 内 `assets/settings_config.json`；本地解析副本 `/tmp/skylink/extracted/assets/settings_config.json`（`ver=20260114`） |
| SkyLink 反编译 | `tmp/skylink/dec/`（apktool 全量）；方向注入：`smali_classes2/com/nio/util/virtual_display/b.smali`、`b$a.smali`、调用方 `com/ucarmd/connectly/remoteapi/b.smali` |
| Apple Music APK | 本地副本 `/tmp/skylink/applemusic.apk`（6.5.2 / 1586） |
| SkyLink 内嵌文案 | 「应用界面完美适配车机中控屏」「应用运行依赖手机算力和网络」「允许跨端使用的应用/游戏/通知」「使用手机所有应用」「应用投屏开关」「中控屏/左后排屏/右后排屏/后排娱乐屏」 |
| 云端配置框架 | `/nio/base/config/ConfigManager`、`ConfigUpdateReceiver`、provider `com.skyui.cloud.config`（权限 `com.skyui.cloud.permission.CLOUD_SYNC`） |
| 官方指南 | `phone.nio.com/niolink-guide/how-to-use-nio-phone-in-the-vehicle-centeral-control-screen`；`.../how-to-use-more-mobile-applications-inside-of-vehicle` |
| 实测命令 | `aapt2 dump badging/resources`、`adb pull`、`settings list global \| grep skylink`、`dumpsys platform_compat \| grep 265464455` |
