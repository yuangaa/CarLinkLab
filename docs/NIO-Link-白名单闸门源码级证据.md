> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](PUBLICATION-NOTES.md)。

# NIO Link 白名单闸门：源码级证据（2026-10-07）

> 本文只记录**反编译**得到的结论，用来回答一个具体问题：
> 「所谓『NIO Link 应用』到底有没有为蔚来写过代码？跨端入口的闸门究竟拦在哪一层？」
> 所有引用都给出资产路径 + 行号，可复查。

## 0. 一句话结论

**没有。** 白名单条目 = **包名 + 展示元数据**，不含组件名、不含 SDK、不含任何 per-app 回调。
被放行的 App（腾讯视频 / Chrome / YouTube / 微信 / 抖音 ……）是**手机上原封不动的 App**，
由 SkyLink 把它们**启动到一块叫 `90000001` 的虚拟显示器**上，画面串流到车机、触摸反向回传、音频走车机路由。

闸门只有一道：**system_server 里按包名查的一张表**。

## 1. 证据 A：白名单条目的 schema 里没有"代码契约"

`tmp/skylink/dec/assets/settings_config.json`（SkyLink 内置默认白名单）里，
`supportPkgList` 分四类 `bizType`：`cross_dev_notify` / `cross_dev_app` / `cross_dev_game` / `free_window`。

以飞书条目为例，字段全集是：

```json
{ "pkgName": "com.ss.android.lark", "appName": {...多语言...}, "appNameCharacters": {...},
  "minVer": 6060650, "screenType": 7, "type": 2,
  "immersive": false, "support_min_window": true, "appIcon": "https://pp.myapp.com/..." }
```

字段含义全部是**展示/策略**，没有一个字段指向 App 内部的组件、接口或权限：

| 字段 | 作用 |
|---|---|
| `pkgName` | 唯一标识（闸门就认这个） |
| `minVer` | 版本下限；低于它不享受跨端 |
| `screenType` / `type` | 车机侧用哪种窗口形态呈现（7=手机横屏画布；0=应用 1=游戏 2=会议） |
| `immersive` | 是否沉浸（隐藏车机系统栏） |
| `support_min_window` | 是否允许小窗 |
| `appName` / `appIcon` | 车机应用列表里的名字和图标 |

**推论：** App 侧零改造即可被跨端。凡是被加进这张表的包名，行为就和 Chrome / 腾讯视频一致。

补充两条反证：
- `free_window` 类的 `pkgs` 是 **空的**（`settings_config.json:636`），说明连"通类"都没有代码依赖。
- system_server 里确实存在**按组件名硬编码的例外**（见 §5），但都在**系统侧**，不在 App 侧。

## 2. 证据 B：闸门链（system_server）

`tmp/skyui-framework/ScreenCastControllerSkyImpl.asm.txt`（来自 `skyui-services.jar`）：

```
入口  shouldAbortActivityStart(TaskDisplayArea, ActivityRecord, ActivityStarter, Task, ActivityOptions):Z
      @ line 21012 / 字节码 22ee00        ← 每次跨端 Activity 启动都会被它过一遍
      ↓ 按包名查表
      mLinkDisplayPackage : ConcurrentHashMap<String, …>     @ field 306（<init> 里 new，line 1669-1671，初始为空）
      ↑ 由回调刷新
      onWhitePackageListChange():V                            @ line 12253 / 236ee8
        → ScreenCastConfigManager.dealWhiteListChange(Consumer)   (236f06)
      ↑ 由 updateLinkWhitePackage() 触发
      ScreenCastConfigManager.updateLinkWhitePackage():V       @ classes.asm.txt 931960 / 2299c0
        → mCallback.onWhitePackageListChange()  (2299d8)
      ↑ 由配置下发触发
      ScreenCastConfigManager.dealScreenCastConfig(Bundle):V   @ classes.asm.txt 931983 / 2297b4
        读 Bundle 键： "package_list_kill" → mLinkKillList
                     "package_list_white" → 白名单            ← 就是它
                     "omni_black_app_list" → mOmniBlackList
      ↑ 由外部进程经 Binder 推进来（同一个 Bundle 派发器还处理
        dealMovePackageToDisplay / dealCurrentCastStatus / dealBackToPhone / goHome / backPressInject…）
```

即：**白名单是一张包名表，以 `package_list_white` 这个 Bundle 键的形式被推进 system_server**，
落在 `mLinkDisplayPackage`。非白名单包在此被拒（现象 = 车机不弹窗，只走 `mWindowType=2` 竖屏镜像）。

`ScreenCastConfigManager` 同时持有大量同类表，进一步说明这是**唯一的配置权威**（方法名一览）：
`isLinkWhitePackage` / `isLinkBlackPackage` / `isLinkKillPackage` / `isInAbortComponentList` /
`isInAllowStartOtherAppsList` / `isInRestartProcessPackageList` / `isLinkLoginSwitchPackageName` /
`isLinkPreserveWindowPackage` / `isLinkSkipStartComponentOnScreencast` /
`isLinkAbortStartComponentOnScreencast` / `isOmniBlackPackage` / `isForbidAppOnOmniWhenParkingOff` …

**显示器 ID 常量**（`<clinit>`，line 1642 / 232038）：

| 十进制 | hex | 用途 |
|---|---|---|
| 90000001 | `0x055d4a81` | 跨端应用画布（connly.one） |
| 90000005 | `0x055d4a85` | 天空视窗镜像桌面（connly.five，FLAG_SECURE） |
| 90000100 | `0x055d4ae4` | `sNextSkyLinkDisplayId` 起始值（按需新开的 SkyLink 屏） |

`shouldAbortActivityStart` 里可见 `if-eq v6, 0x055d4a81`（displayId==90000001）与 `if-nez v6`（displayId==0）的分支，
以及唯一一条硬编码组件例外：
`com.ss.android.lark/.main.app.MainActivityInvokePlaceholderActivity`（line 21075 / 22eeea）→ 直接 abort。

## 3. 证据 C：方向是**逐 Activity** 被判定的，会被改写成「竖屏」或「user」（**本节已修正**）

> ⚠️ 本节初版写的是「系统不改写方向」——**那是错的**，现已纠正，勿再引用旧版结论。
> `getOverrideOrientation(WindowContainer, I)` 确实是纯透传（`return originOrientation`，line 700487），
> 但它**不是**决定方向的那条路径。真正的路径是同一个类里的另一个方法。

`tmp/skyui-framework/classes.asm.txt:700771`：

```
SkyScreenCastOrientationManagerImpl.resolveAppOrientationIfNeed(ActivityRecord, Configuration, int, Configuration):V
   @ 字节码 245400
   v0 = getDisplayIdFromActivityRecord(ar)
   if (!Display.isSkyLinkDisplay(v0)) return;              // 只对 SkyLink 显示器生效
   v1 = config.orientation                                  // 原始方向
   if (ActivityInfo.isFixedOrientationPortrait(orient)) {
       config.orientation = 1;                              // 固定竖屏 → 强制竖屏
   } else if (ActivityInfo.isFixedOrientationLandscape(orient)) {
       if (config.orientation != 2) config.orientation = 2;  // 固定横屏 → 强制 2（user）
   }
   if (config.orientation != v1)
       Slog.d("SkyScreenCastOrientationManagerImpl", "[" + ar.shortComponentName + "]: modify orientation from " + v1 + " to " + config.orientation);
```

即：**SkyUI 按"这个 Activity 声明的方向"分三类处理** —— 固定竖屏 → 压成 1；
固定横屏 → 压成 2（user，本 ROM 上落到横屏）；其余（`behind`/`unspecified` 等）→ 不动。
判定粒度是 **Activity**，不是包。

**日志实证**（`data/car-sessions/` + `data/logcat-天空视窗-2026-10-07.log`）：

| 组件 | 被改成 | 车机上结果 |
|---|---|---|
| `com.apple.android.music/.common.MainContentActivity` | `0 → 1`（竖屏） | 竖屏窄条（1488×2992） |
| `com.shihab.diplay/…CarPlayHostActivity` | `0 → 2`（user） | **横屏铺满 3024×1696** |
| `com.tencent.qqlive/.kmm.VideoDetailKmmActivityBk`（播放页） | `0 → 2` | 横屏 |
| `com.tencent.qqlive/.ona.activity.SplashHomeActivity`（首页） | `0 → 1` | 竖屏 |
| `com.skyui.launcher/…QuickstepLauncher` | `0 → 1` | 竖屏镜像桌面 |

**结论（这才是"Apple Music 为什么是窄条"的根因）：**
能不能横屏铺满，取决于应用那个 Activity 声明的方向。CarPlay 宿主声明横屏 → 车机屏转成横屏铺满；
Apple Music 主界面声明 `behind` → 被判成竖屏 → 车机屏保持竖屏 → 在横屏车机上就是一条窄边。

**连带两条修正：**
- 旧结论「manifest 声明横屏会被改写回 `user`」——**这个观察本身是对的**（确实会改成 2），
  但由它推出的「所以声明横屏没用」是错的：**正因为它被改成 user，车机才把屏转成横屏铺满**。
- 本文件不再声称"系统不改写方向"。改写确实发生，只是发生在这个方法里。

车机侧的旋转仍由 SkyLink 的 `forceRotation` 完成（另一条链）：
`com/ucarmd/connectly/remoteapi/mode/a.smali:~335` 判定横竖
→ 反射调用 `com/nio/util/c0.smali::c(IZI)V` → `IWindowManager.setFixedToUserRotation()` + `freezeDisplayRotation()`
（且**每秒重新冻结**，所以公开 `wm user-rotation` 会被它覆盖 —— 见 `data/car-sessions/` 实测）。

## 4. 证据 D：`free_window` = 天空视窗 = "在车机上使用手机所有应用"

`tmp/skylink/dec/res/values-zh-rCN/strings.xml`:

```xml
descriptor_free_window  = 可在车辆中控屏，使用手机所有应用，应用运行依赖手机算力和网络。…
set_title_free_window   = 天空视窗
title_enable_free_window= 天空视窗
```

开关：`res/xml/free_window_preferences.xml` → `SkySwitchPreference key="enable_free_win" defaultValue="true"`。

**含义：** 「在车机上跑任意手机 App」这条路**本来就存在**且默认开着，走的是 `90000005` 镜像桌面。
它的问题是**形态**（竖屏小窗镜像），不是**能不能跑**。这正好解释了实车现象：
Apple Music 能显示、能出声、能操作，只是拿不到 `90000001` 的大画布。

## 5. NIO 侧确实硬编码了少量"按 App"的例外（但都在系统侧）

`ScreenCastControllerSkyImpl.<init>`（line 1658-1692 / 23206c 起）里直接 `newHashSet` 写死：

| 字段 | 写死的组件 |
|---|---|
| `mIgnoreOrientationActivities` | `com.ss.android.lark/com.ss.android.vc.meeting.module.multi.ByteRTCMeetingActivityInstance` |
| `mIgnoreOrientationNotifyActivities` | `com.alibaba.android.rimet/…TeleVideoConfActivity`、`com.tencent.wemeet.app/…InMeetingActivity` |
| `mIgnoreOrientationActivitiesAR` | `com.tencent.wemeet.app/…InMeetingActivity` |

外加 §2 里那条 abort 例外（飞书的 placeholder Activity）。

**注意区分：** 这些是**蔚来在系统里针对某些 App 的会议/通话页做的特判**，
不是"App 为蔚来写的代码"。对"应用侧零代码"的结论没有影响，反而印证了：
**特殊行为都由系统侧表驱动**。

## 6. 对「官方界面 + 无损」的含义

要把**原生 Apple Music**放上 `90000001`，只有一条链路需要打通：
**让 `com.apple.android.music` 出现在 `package_list_white` 里**。

- 免 root：该表由 `com.skyui.netconfig`（signature|knownSigner 权限）下发，改不动。
- **有 root**：可直接改这张表的**任一段**——
  1. `com.skyui.netconfig` 的数据源（最上游，改一次全链路生效）；
  2. SkyLink 私有目录里的缓存副本 + 强杀重启 SkyLink；
  3. 最下游：hook / patch `ScreenCastConfigManager.dealScreenCastConfig(Bundle)` 或直接预置 `mLinkDisplayPackage`。
  条目照抄现成的即可，例如 `{"pkgName":"com.apple.android.music","minVer":<AM versionCode 或更小>,"screenType":7,"type":0,"immersive":false,"support_min_window":true}`。
- 零改动自检（有 root 就能做）：`am start --display 90000001 -n com.apple.android.music/<主 Activity>`，
  然后在 logcat 里找 `ScreenCastController: abortActivityStart … on 90000001` —— 这一行就是闸门。

### 与「横屏补丁器」的关系：互补，不是替代

`tmp/ref/apple-music-android-landscape-patcher/`（本地已 clone）：

- 它把 Apple Music **6.5.0 (1580)** 重建为横屏友好版；**保持包名不变**、用使用者自己的密钥重签。
- README 明写：「由于签名不同，通常不能覆盖 Apple 官方版本；安装前请确认账号和离线下载可恢复，再卸载原版。」
  → **必须卸载官方版**才能装，这是代价。
- 它**不破坏**登录/播放（项目在维护中，还给车机加了沉浸式系统栏处理），
  说明「重打包 Apple Music 会破坏 DRM」这条旧结论**很可能站不住**（顶多是视频类 DRM 的顾虑，与音频无损无关）。
- 原创代码只有两个文件：`src/car/com/apple/android/music/car/CarWindowProvider.java`、
  `src/tv/com/apple/android/music/player/fragment/TVLyricsLayout.java`，其余是 smali 改写脚本。

**所以：** 白名单（或 root）负责把 AM **送到**大画布上；补丁器负责让 AM 的 UI **长成**大画布的样子。
两者叠加才是"官方界面 + 无损 + 大画布"。单独任何一个都不够——
补丁器改不了包名，所以它**过不了 NIO 的闸门**。

## 7. 仍未解 / 需要实机确认

1. **N2301 能不能解锁 BL** —— 这是 root 路线的唯一前置。现状：`ro.build.type=user`、
   `oem_unlock_allowed=0`、无 `su`、`adb root` 被拒。需要在开发者选项打开「OEM 解锁」后试
   `fastboot flashing unlock`（**会清空手机**）。若厂商禁止，root 路线作废，退回套壳。
2. `package_list_white` Bundle 的**推送方是谁**（SystemUI 还是 SkyLink），决定 root 后改哪一段最省事。
   未定位到派发器的外层方法名，需要再翻一段。
3. `minVer` 是"≥"还是"=="语义；以及 `screenType` 选 7 是否会强行走横屏画布 —— 需实机验证。

---

## 8. 追加：所有"免 root 捷径"的排查结果（2026-10-07 晚）

结论：**没有免 root 的旁路。** 逐条排查如下。

### 8.1 `allPackagesFullscreen` —— 存在，但入口是死的 + 要 root
`ScreenCastControllerSkyImpl.onCommand(PrintWriter, String[])`（`classes.asm.txt:672718 / 231420`）
是一个 dump 派发器，子命令：`transactinfo` / `letterBoxAspectRatio` / `dumpChoreographer` / `dump` /
**`allPackagesFullscreen`** / `castStatus` / `appType` / `parkingState` / `timeline` / `happycast` / `dumpUids`。

`allPackagesFullscreen` 分支（`23154e`）→ `dealAllowAllPackagesFullscreen`（`657011`）
→ `SkyScreenCastOrientationManagerStub.allowAllPackagesFullscreen(Z)`（`657025`）
→ `SkyScreenCastOrientationManagerImpl.mAllowAllPackagesFullScreen`（`700436`），
该字段被 `isNeedLetterbox` 消费（`700670`）——**语义正是"让所有包都拿全屏画布"**，即我们的目标。

**但两道锁：**
1. 每个分支前都先调 `enforceCallerIsRoot()`（`231548` 等 7 处）。其字节码（`658731`）=
   `if (Binder.getCallingUid() == 0) return; else throw new SecurityException("Caller is not Root!");`
   → `adb shell`（uid 2000）被拒，**必须真 root**。
2. `ScreenCastControllerSkyImpl.onCommand` 在 skyui-services.jar 里**找不到任何调用方**
   （grep `invoke.*ScreenCastControllerSkyImpl;.onCommand` 无命中；同类 `SkyBroadcastManager` /
   `SkyAppUsageStatistics` 的 `onCommand` 都有 impl→base 的调用）。
   签名带 `PrintWriter`，不可能是 Binder 接口 → 大概率是**死代码**（与旧结论一致）。
   ⇒ 即使 root，"这个开关能不能从 dumpsys 摸到"仍**需要实机验证**。

### 8.2 `mSkyLinkFeatureSwitch` —— 在 Settings 里，shell 可写，但管不到白名单
`updateDefaultSkylinkFeatureSwitch()`（`classes.asm.txt:14792 / 238e70`）读：
- `Settings.Secure.getInt(cr, "skylink_feature_switch_version", 0)`
- `Settings.Global.getInt(cr, "skylink_feature_switch", 0)`

若 version < 4 则逐版本 `doUpdateFeatureSwitch()` 应用默认，然后 `putInt` 写回。

位含义（由 `isFeatureEnabled(switch, mask)` 的调用点推出）：

| 位 | 判定方法 | 语义 |
|---|---|---|
| 0x2 | `isSkylinkSwitchToPhoneEnabled` | 允许切回手机 |
| 0x4 | `isSkylinkIgnoreOrientationEnabled` | 忽略方向干预 |
| 0x8 | `isSkylinkFixedDisplayIdEnabled` | 固定 displayId |

**这两个 Settings 键 `adb shell settings put secure/global …` 就能改（无需 root）**，
但它们**只管这三个行为，与白名单（`mLinkDisplayPackage`）无关** → 不是旁路。
可以作为独立的调参旋钮（例如强制 `ignoreOrientation`），值得实机试。

### 8.3 `mLinkDevelopPackages` —— 来自 framework 资源数组，ROM 固化
`initLinkDevelopPackageList()`（`ScreenCastControllerSkyImpl.asm.txt:6388 / 2342d4`）
从框架资源读 `getStringArray(0x0c020027)` 塞进 `mLinkDevelopPackages`，
`isSkylinkDevelopPackage(pkg)` 查它；`getSkylinkFixedDisplayIdForDevelop(name)` 里
`"com.skyui.link.developer"` 对应 `mDevelopmentDisplayId`（`5365` / `231108`）。

⇒ 这是**编译进 ROM 的资源数组**，运行期不可改 → 免 root 不可用。

## 9. 顺带解出的事实

- 本机 Apple Music 包信息（从 `tmp/applemusic/base.apk` 的二进制 manifest 解出）：
  `package = com.apple.android.music`，`versionName = 6.5.2`，**`versionCode = 1586`**，
  `minSdkVersion = 30`，`targetSdkVersion = 35`，`compileSdkVersion = 35`。
  → 白名单条目的 `minVer` 可取 ≤1586（横屏补丁器针对的是 6.5.0/1580，比本机旧）。
- 横屏补丁器**保持包名不变**（README 自述签名不同、需先卸载官方版）→ 它过不了 NIO 闸门，
  与"加白名单"是**互补**关系。


---

## 10. 追加：两份白名单 + 两条硬约束（2026-10-07 深夜）

### 10.1 存在**两份**名单，且不一致
| 出处 | version | 条目 | 内容 |
|---|---|---|---|
| `data/screencast_config_preload.json`（键名就是 `package_list_white`） | **20230918** | 33 | 老名单：飞书/微信/腾讯会议 + 一堆腾讯系游戏；**无 YouTube / Chrome / 腾讯视频** |
| 云端 CloudConfig（`data/nio_link_whitelist.csv`，来自 `assets/settings_config.json`） | **20260114** | 55 | 现役：YouTube / Chrome / 腾讯视频 / 优酷 / 抖音 / B站 / VidHub(`com.oumi.utility.media.hub`)… |

**实测生效的是云端那份**（YouTube/Chrome 都不在老名单里，却都拿到了跨端待遇）。
→ 老 `screencast_config` 更像出厂兜底种子。**两份名单里都没有任何音乐类 App**，
`com.apple.android.music` 在**两份里都不存在**（已逐项核对）。

### 10.2 用 `adb`/shell 往投屏显示器启动应用会被**拦**
`ScreenCastController.abortActivityStart` 返回 `result code=102`，Activity 不创建；
**白名单应用（YouTube）同样被拦** ⇒ 判断依据包含"启动来源"，不只是目标包名。
所以 `am start --display 90000001 …` 不是可用入口：**App 只能由车机/天空视窗 UI 那条链拉上去**。

### 10.3 Apple Music 6.5.2 的清单体检（本次实测）
- `resizeableActivity = true`；Activity 方向分布 **`behind`×12 / `portrait`×7 / `unspecified`×1**；
  主界面 `MainContentActivity` 的 `configChanges` 含 **orientation|screenSize**（自己处理转屏）。
- **只带 `androidx.car.app.CarAppPermissionActivity` / 通知接收器 / connection provider，
  没有声明任何 `CarAppService`** ⇒ **没有 Android Automotive(AAOS) 车机 UI 入口**，
  想让 AM 走 AAOS 车机模板这条路不通（AA 又已因 CDM 权限被判死）。
- 资源目录名被混淆（`res/wem`、`res/tr3` 之类），**不能用目录名判断有没有 `-land`/`sw600dp`**；
  旧文档"带全套 land/sw600dp 资源"的说法来自 Mac 上的 `aapt2`（读 resources.arsc），
  比只看 zip 目录名可靠，**本次不推翻它**。
