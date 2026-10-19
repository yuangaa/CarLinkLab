> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](PUBLICATION-NOTES.md)。

# 让 Apple Music（及其他 App）拿到 NIO Link 原生级体验 —— 可行路径与套壳设计

> 背景：NIO Phone 团队已解散 → **白名单不会再有官方更新**，与车机的互动只能靠我们自己。
> 前置阅读：`NIO-Link白名单与触发机制.md`（白名单台账）、`NIO-Link调研报告.md`（机制）、`项目上下文与成果备忘.md` §4.13–4.16 / §5 / §6.7。

---

## 0. 结论先行

**1. "套壳能不能成"取决于一个尚未验证的前提，必须先测。**

`mWindowType`（`6` = 车机原生级 16:9，`2` = 9:16 手机镜像）**由车机通过 databus protobuf 下发**，手机只是原样回显（主文档 §4.13，反编译结论）。
而已知的事实是：**白名单应用用 `adb` 直接启动到车机显示器，也只拿到 `2`**（本报告 §5 实测）。
→ 说明 **"包名在名单里"并不自动等于 `6`**。

那么关键就变成：

> **走车机正常流程（从车机应用列表点开）时，白名单应用到底拿到 6 还是 2？**

- **若拿到 6** → 包名就是门票，**套壳可行**（方案 A）。
- **若仍是 2** → 包名不是门票，套壳白做（还赔一次 NIO Link 闪退的风险），**改走方案 C**。

**2. 这个前提可以零成本验证**：手机现在装着 4 个白名单应用（YouTube / Chrome / 腾讯视频 / 文件管理），
在车里从车机列表打开 YouTube 即可，**不装任何东西、不改任何设置**。详见 `NIO-Link白名单与触发机制.md` §6.0。

**3. 三条已封死的路**（别再试）：重打包 Apple Music / 改 SkyLink 白名单 / 等云端更新。

---

## 1. 方案 A：套壳 —— 白名单包名 + 自绘 UI（推荐，风险最低）

### 1.1 核心思路

**不伪装"内容"，只借用"门票"。**

- 借一个**未安装的白名单包名**当壳的包名 → 让车机认为它是名单内应用 → 争取 `mWindowType=6`
- 壳**自己画 16:9 车机 UI**，内容通过 `media3` 从 Apple Music 拿
- **完全不碰 Apple Music 本体**：不重打包、不动签名、不碰 DRM

这个方案之所以成立，是因为 Apple Music 的外部可控性**已实测确认**：

| 事实 | 证据 |
|---|---|
| 暴露媒体服务且**无权限守卫** | `com.apple.android.music.player.MediaPlaybackService`，`exported=true`，同时声明 `androidx.media3.session.MediaSessionService` + `android.media.browse.MediaBrowserService`（读 APK 清单） |
| 服务此刻**确实在运行** | `adb shell cmd media_session list-sessions` → `tag=androidx.media3.session.id.com.apple.android.music` |
| 可读 | 正在播放（标题/歌手/专辑）、**封面 URL**、进度、**队列（含每首 mediaId）** |
| 可控 | 播放/暂停/上一首/下一首/跳转、进度拖动（31 条命令） |
| ⚠️ 资料库浏览**被拒** | `getLibraryRoot` 返回 `code=-4` —— 只对 Android Auto 等系统客户端开放 |

> 以上四条来自主文档 §4.6，本次复核了"服务声明"与"会话在跑"两条，仍然成立。

### 1.2 包名选择（**未安装**的 `cross_dev_app`，共 41 个可选）

优先挑**媒体/内容类**（语义最贴近，出问题也不显眼），`versionCode` 必须 **≥ `minVer`**：

| 应用 | 包名 | minVer（versionCode 下限） | type |
|---|---|---|---|
| VidHub | `com.oumi.utility.media.hub` | 84 | 0 |
| 网易爆米花 | `com.netease.filmlytv` | 311 | 0 |
| 优酷视频 | `com.youku.phone` | 786 | 0 |
| 西瓜视频 | `com.ss.android.article.video` | 916 | 0 |
| 腾讯体育 | `com.tencent.qqsports` | 1363 | 0 |
| 咪咕视频 | `com.cmcc.cmvideo` | 260330009 | 0 |

> ⚠️ `com.oumi.utility.media.hub`（VidHub）**已经当过一次壳并导致 NIO Link 闪退**（本报告 §5），
> 建议换用别的包名，或明确知道"闪退与包名无关、与组件过多有关"后再复用。
> ⚠️ 匹配规则（主文档 §4.16）：**按包名匹配** + `versionCode ≥ minVer` + 只保留渲染目标 UI 的 launcher Activity。

### 1.3 UI 与交互设计

- **布局**：单 Activity，`res/` 只放 `layout-land/` 大屏横屏版；密度按车机平板档（参考 `wm density -d 90000005 600`）
- **内容**：
  - 左 2/3：大封面（来自 media3 `MediaMetadata.artworkUri`）+ 标题/歌手/专辑
  - 右 1/3 或底部：进度条 + 播放控制（上/下一首、播放暂停、跳转）
  - 队列页：用 media3 队列（mediaId 可读）渲染，点选即跳
- **选内容怎么办（资料库浏览被拒）**：用 **deep link**
  - Apple Music 清单里声明了 `host = music.apple.com` 的 VIEW intent-filter（APK 清单 line 622 已确认）
  - 壳可以 `startActivity(ACTION_VIEW, "https://music.apple.com/cn/album/…")` → Apple Music 定位并播放 → 壳回到"遥控器"角色
  - 壳内放几个"快捷入口"（常听的专辑/播放列表）；或让我先在手机上把队列排好
  - ⚠️ 壳的清单需要 `<queries>` 才能解析到 Apple Music（主文档 §4.6 的前置条件；shell 侧 `am start -p` 常被可见性限制挡掉，这属于同一类问题）
- **音频**：Apple Music 在后台本地解码 → 直接 PCM 输出到**座舱音响** → **无损**（主文档 §4.7）

### 1.4 可直接复用的历史资产

项目里**已经写过一版**（后来因"太丑"被删除，源码留着）：

| 文件 | 说明 |
|---|---|
| `archive/自研音乐界面(已弃用)/CarPlayMusicActivity.kt` | 464 行，已验证 media3 连接 Apple Music 的读/控 |
| `archive/自研音乐界面(已弃用)/ic_music_*.xml` | 播放控制图标 5 个 |
| `archive/自动播放功能(已移除)/CarAutoPlayService.kt` | 162 行，检测座舱音响后发 `MEDIA_PLAY`（**抢 DRM 许可证**用，见主文档 §4.5） |

> 所以这一版的重点不是"能不能控"，而是**"把界面做对 + 把包名套对"**。

### 1.5 风险与回滚

| 风险 | 处置 |
|---|---|
| **NIO Link 闪退**（上次真实发生过） | 只留渲染 UI 的 launcher Activity；**不要**带 CarPlay/MFI/USB-accessory 整套组件 |
| 装错包名覆盖真应用 | 只在 CSV `installed=no` 的包里挑；装前先 `pm list packages \| grep <包名>` 确认 |
| `versionCode < minVer` 不生效 | 构建时显式指定，对照上表 |
| 回滚 | `adb uninstall <包名>` —— 上次就是这么恢复的 |

---

## 2. 方案 B：套壳变体 —— "自绘镜像壳"（兜底，但要还债）

如果最终 `windowType` 拿不到 6，或者想**一次解决所有 App**（微信、高德、网易云）：

- 壳申请 **MediaProjection**（我授权一次）→ 把手机上目标 App 的画面裁切成 16:9 渲染进自己的 Surface
- 用 **AccessibilityService** 把车机屏上的触摸坐标映射回目标 App 的窗口 → 恢复交互

**优点**：不管 `windowType` 是 2 还是 6，**画面是我们自己画的**，比例、裁切、布局全可控；对所有 App 通用。
**代价**：延迟；需要无障碍授权（我要有心理准备）；触摸映射的精度/手势（滑动、长按）要自己调；`FLAG_SECURE` 的界面拍不到。
**注意**：壳**仍然需要出现在车机显示器上** → 包名还是得落在白名单里。所以它是方案 A 的兜底，不是替代。

---

## 3. 方案 C：不套壳 —— 用系统杠杆改"尺寸/方向"

目标：**不改包名**，让 Apple Music 自己（或任意应用）在车机显示器上变成 16:9。
全部是 shell 可写命令，脚本已就绪：`tools/car-orientation-test.sh（已作废，勿运行） [包名]`。

| 杠杆 | 机制 | 风险 |
|---|---|---|
| `dumpsys window allPackagesFullscreen 1` | NIO 私有命令 → 置 `mAllowAllPackagesFullScreen=1` → `isNeedLetterbox()` **跳过白名单判定**（主文档 §4.14-B） | ⚠️ 调用点前有 `enforceCallerIsRoot()`，**可能 root 专用**；须车内实测 |
| `wm set-ignore-orientation-request -d 90000005 1` | AOSP 标准，让显示器**忽略应用请求的方向**（主文档 §4.14-A，**最有希望**） | 低 |
| `wm user-rotation -d 90000005 lock 1` | 把车机显示器锁横屏（主文档 §3.4 一行设置） | 低（但与主文档 §5 死路清单存在冲突，见下） |
| `am compat enable 265464455 com.apple.android.music` | `OVERRIDE_ANY_ORIENTATION`，**Apple Music 早已被单独 override** | 低，上次因没真启动 App 而结论无效，**待重测** |
| `settings put global skyui_custom_rotation 0/1` | 框架层"让应用以为屏幕转到某角度"（主文档 §4.15-A） | 低 |
| `settings put global skylink_inject_rotation(_value)` | SkyLink 自带的虚拟显示器旋转注入（每秒循环）（主文档 §4.15-B） | 低，语义未完全确认 |

> ⚠️ **待澄清的冲突**：`NIO-Link白名单与触发机制.md` §3.6 说"用户旋转可用 `wm user-rotation -d 90000005 lock 1` 设为横屏（关键）"，
> 而主文档 §5 死路清单记着"用户旋转锁 → **该 ROM 不响应**"。命令本机存在，但对**虚拟显示器 90000005** 是否有效**从未实测**。两组文档建议**同一次进车一起验证**。

---

## 4. 方案 D：已封死（别再投入）

| 路 | 为什么死 |
|---|---|
| **重打包 Apple Music 改包名/改清单** | APK 内含 **Play Integrity / Widevine / FairPlay / `isRooted` / attestation**（本次实测 grep 到 85 处 FairPlay、9 处 Widevine、2 处 `play.core.integrity`）→ 重签名几乎必然破坏 DRM 与登录 |
| **改 SkyLink 白名单** | 生效包在 `/data/app`（2.10.8），**平台签名** + 设备**非 root 生产版**（`ro.secure=1`/`ro.debuggable=0`/无 `su`）；配置在私有目录；更新入口 `ConfigUpdateReceiver` 带 `com.skyui.netconfig.permissions.CONFIG_UPDATE`；全部 provider 带权限守卫 |
| **等云端下名单** | 配置确由 `com.skyui.cloud.config` 下发（加一条不需 OTA），但 **NIO Phone 团队已解散** → 预期无响应。仍可用「设置 → 帮助和反馈 → 车手互联」提一次（成本≈0） |
| **NIO Link 白名单伪装（完整拷贝）** | ❌ 已实测导致 **NIO Link 闪退**（本报告 §5） |

---

## 5. 推荐执行顺序

| 步 | 做什么 | 成本 | 成功判据 |
|---|---|---|---|
| **1** | **车内零成本前提验证**：从车机应用列表打开 YouTube / 腾讯视频，观察是否铺满 16:9；同时抓 `BaseVirtualWindowManager: getVirtualDisplay mScreenType=1, mWindowType=?` | 只跑一趟车 | 拿到"白名单应用走正常流程"的**真实 `mWindowType`** |
| **2** | 同一趟车顺手跑完方案 C 的 6 组对照（`tools/car-orientation-test.sh（已作废，勿运行）`） | 同上一趟 | 有一组能让目标应用铺满 16:9 |
| **3a** | 若第 1 步是 **6** → 做方案 A 的壳（复用 `archive/自研音乐界面`，重做 UI + 套包名） | 开发量中等 | 车机上壳铺满 16:9 且能控 Apple Music |
| **3b** | 若第 1 步是 **2**、且第 2 步无一组生效 → 做方案 B 自绘镜像壳 | 开发量大 | 任意 App 能在车机上 16:9 且可交互 |

> 第 1、2 步**必须在车里做**（车机显示器带 `FLAG_SECURE`，**截不了图**，只能人眼观察 + logcat）。
> 我能做的部分（写壳、写脚本、抓 logcat、分析）都可以提前准备，只等你到车上。

---

## 6. 附：本次新增/复核的事实

| 项 | 结论 | 方式 |
|---|---|---|
| Apple Music 媒体服务可外部连接 | ✅ `MediaPlaybackService` `exported=true`，无 `android:permission` 守卫，带 media3 + MediaBrowserService 双 action | `aapt2 dump xmltree` 读清单 |
| 媒体会话此刻在运行 | ✅ `androidx.media3.session.id.com.apple.android.music` | `adb shell cmd media_session list-sessions` |
| 深链可用 | ✅ 清单声明 `host = music.apple.com` | 读清单 line 622 |
| 重打包不可行 | ❌ 含 Play Integrity / Widevine / FairPlay / attestation 痕迹 | APK 字符串 grep |
| 白名单候选池 | 41 个未安装的 `cross_dev_app`（本表 §1.2 取前 6） | 解析 `data/nio_link_whitelist.csv` |
| 历史资产可复用 | ✅ `CarPlayMusicActivity.kt` 464 行 + 自动播放服务 162 行 | `archive/` |
