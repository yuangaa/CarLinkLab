> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](../PUBLICATION-NOTES.md)。

# GitHub 调研：Tesla 及各车机上的 Apple Music 项目（参考材料）

> 调研时间：2026-10-07 ｜ 目的：为「NIO Phone → 蔚来车机的 Apple Music 大画布」三条路线（① dumpsys 上屏官方 App ② 自绘 UI + 后台原生播放 ③ 网页套壳）寻找可参考/可复用的开源项目。
> 元数据均来自 GitHub API 实查（star 数为 2026-10-07 当日值）。

---

## 0. 结论速览

| 发现 | 对我们的价值 | 音质 |
|---|---|---|
| **apple-music-android-landscape-patcher**（中文项目） | ⭐⭐⭐ 路线①的最佳拍档：把 Apple Music APK 重打包成**车机横屏版** | 无损保留（官方 App 本体解码） |
| **BimmerGestalt/AAIdrive**（BMW IDrive 逆向） | ⭐⭐⭐ 路线②的完整参考实现：车机 UI + MediaBrowser 遥控 Apple Music，Kotlin/MIT | 无损（原生 App 播放） |
| **Flux 轻应用**（NIO 官方，即车上的 flux music） | 证实网页套壳是 NIO 官方路线，但**已被 NIO 自己做掉**且天花板明确 | ❌ AAC 256k 封顶 |
| **MusicKit JS 官方确认不支持无损**（Apple Developer Forums） | ⚠️ 一锤定音：**一切网页/MusicKit 路线（Musish/Cider/Automus）都没有无损** | ❌ |
| **Automus**（AAOS 第三方 Apple Music 客户端） | 证明「MusicKit 车机客户端」产品形态成立，但闭源且无无损 | ❌ |
| **Tesla Android**（树莓派 CarPlay 进 Tesla） | 架构参考：浏览器/显示通道 + 手机侧渲染，与我们 CarPlay 线（已完成）同构 | — |
| Tesla 官方 Apple Music | 行业标杆也是 AAC，**无损在整个车机行业都只能靠"原生 App 播放"** | ❌ AAC |

**核心推论**：想要无损，必须让 **Apple Music Android 官方 App 本体**参与播放（路线①或②）；任何网页/网页套壳/MusicKit 方案都封顶 AAC 256k。这从行业侧再次印证了我们此前的结论。

---

## 1. ⭐ apple-music-android-landscape-patcher（最贴合本项目）

- 仓库：`coolzoojoker/apple-music-android-landscape-patcher`（Java，Apache-2.0，5★，2026-09/10 活跃）
- 做什么：**在我电脑本地把 Apple Music 6.5.0 (1580) APKM 重打包成横屏优化版**，面向 Android TV / 横屏平板 / **可装第三方 APK 的 Android 车机**。
- 补丁内容：
  - 横屏 HOME：封面/视频画面、歌曲信息、进度与控制区重排；
  - 歌词、待播清单横屏左右分栏（复用原播放器数据与按钮状态）；
  - 视频歌曲尽量复用原视频输出；
  - 触摸/鼠标操作 + 整页下滑收起；**车机配置（`car-armv7`/`car-arm64`）额外做沉浸式系统栏隐藏**；
  - 修复"有线网络被误判为离线"（车机常见坑！我们的场景可能同样踩到）；
  - 本地自签（v1+v2+v3 + 对齐校验）。
- 合规设计值得学习：仓库**只发布补丁源码和构建脚本**，不含 Apple APK/资源/DEX/通用签名密钥，我自备正版安装包。
- 技术栈：Windows PowerShell 工具链（Temurin JDK + Android SDK + APKEditor + Apktool），补丁采用**锚点校验、失败即停**；作者明确"升级 Apple Music 版本必须重新审计"。
- **对我们的用法**：
  1. 我们手机装的是 **6.5.2**，补丁器锚点按 6.5.0 校验 → 要么装 6.5.0 再补丁，要么按其文档《解包、改写、重打包原理》把补丁移植到 6.5.2；
  2. 若路线①（`movePackageToDisplay` 把官方 App 搬上车机屏）走通，**横屏补丁版 Apple Music 在车机画布上的显示效果会远好于原版**（原版只给 9:16 手机布局）；
  3. 重打包后签名变化 = 新包名签名不影响白名单判定（白名单按包名），但**无法再覆盖官方版**，且 Android Auto/媒体服务行为需实测。

## 2. ⭐ BimmerGestalt/AAIdrive（路线②参考实现）

- 仓库：`BimmerGestalt/AAIdrive`（Kotlin，MIT，690★，持续活跃；原作者 hufman，有多个活跃 fork）
- 做什么：在 BMW/Mini 的 IDrive 车机上，**用与 Android Auto 相同的 API（MediaBrowserService/MediaSession）自绘车机原生风格 UI，遥控手机上的音乐 App**——与我们"自绘车机 UI + 遥控 Apple Music"的保底路线**完全同构**。
- 已实现能力（可直接借鉴的功能清单）：
  - 浏览/搜索音乐 App 曲库、显示并操作播放队列、上/下曲、进度；
  - UI 自动贴合车机主题；封面、正在播放联动显示；
  - 方向盘按键、音频焦点、来电暂停、重连自动恢复播放；
  - **明确支持 Apple Music**（在"实测可用 App"清单中）。
- 关键经验（与我们实测完全吻合，属跨项目交叉验证）：
  > "Some Android Auto music apps enforce a whitelist of clients, preventing this app from **launching them or browsing their libraries**. **However, once they are running, they can be controlled.**"
  —— 即 Apple Music 这类 App 会按 client 包名白名单限制**拉起与曲库浏览**，但**正在播放后的控制不受影响**。这正是我们在 `:player.MediaPlaybackService` 上看到的"可控播放、拒浏览"。
- **对我们的用法**：路线②（壳自绘 UI）开发时，可直接读它的 music browsing/queue/UI 代码；它处理的 client 白名单限制、会话跟随、音频焦点问题我们都会遇到。

## 3. Flux 轻应用 = 车上那个 flux music 的正身（NIO 官方 PWA）

- 非 GitHub 项目，但调研确认身份：**蔚来 Banyan 3 的「Flux 轻应用平台」**，2024-07 NIO IN 发布，官方用 **Apple Music 网页版**做演示，账号/歌单/曲库与手机 App 同步，支持 NOMI 播放控制。
- 即我车机上的 flux music = NIO 官方 PWA 套壳网页版。**NIO 自己已经做过网页路线，天花板就是网页版**（AAC 256k、无无损、无杜比全景声）——与我"不能用无损所以不想用"的反馈一致。
- 启示：我们**不要复刻 flux**；若做自绘 UI（路线②），交互可以长得像它，但播放必须走原生 App。

## 4. MusicKit JS 无无损 —— Apple 官方实锤

- Apple Developer Forums 帖 683021（Frameworks Engineer 官方回复）：
  > "for web apps using MusicKit JS, playback of music with **Lossless or Hi-Res Lossless quality is not currently supported**."
- 多方实测：网页版最高 AAC 256kbps，无无损、无杜比全景声、无离线下载。
- **推论**：所有基于 MusicKit/网页的项目（下述 Musish、Cider、zachomedia、naveedgol，以及 AAOS 上的 Automus）**音质天花板相同**。它们对我们的价值只剩 **UI/交互参考**，不能作为播放链路。

## 5. Automus（AAOS 商业化第三方客户端）

- `com.lindehammarkonsult.automus`（闭源，Play 商店付费/订阅制，2026 年仍在更新）
- 形态：Android Automotive OS（沃尔沃/极星等）上的第三方 Apple Music 客户端——QR 码扫码登录（Apple 官方认证）、浏览全部曲库、方向盘控制、Google Assistant 语音、Last.fm。
- 证明「车机原生体验的 Apple Music 客户端」有真实市场需求、且 MusicKit API（网页同源）足以支撑浏览/搜索/控制。**但它同样走 MusicKit → 无无损**（商品页只字未提无损）。
- 对我们的价值：UI/功能清单参考（QR 登录、驾驶优化界面、会话持久化"resume where you left off"）。

## 6. Tesla 阵营

### 6.1 Tesla 官方 Apple Music（2022.40 假日更新起内置）
- 扫码登录、曲库同步，但**只流 AAC（无无损、无 Dolby Atmos）**——行业事实：车机厂内置 Apple Music 也拿不到无损。
- Tesla 从不支持 CarPlay/Android Auto；Musk 的原话是"用蓝牙听"。

### 6.2 Tesla Android 项目（github.com/tesla-android，GPL-3.0）
- Michał Gapiński 的开源方案：树莓派（早期两块、现单 Pi 4/5）跑定制 Android + CarPlay 通道，**Tesla 车机浏览器显示 CarPlay 界面**，Apple Music/地图/电话全功能，方向盘按键可控，行驶中可用。
- 组织仓库：`tesla-android-os`（98★，raspbian 发行版）、`android-raspberry-pi`（165★）、`flutter-app`（47★）、`android-external-tesla-android-virtual-display`（虚拟显示通道，7★）等。
- 与我们的关系：**同构于我们已完成的 CarPlay 线**（手机侧渲染 → 车机侧显示/触摸回传）。其虚拟显示/浏览器显示通道的代码对理解"手机内容如何高效上屏"有参考价值；但 NIO 场景下我们已有 NIO Link 自己的通道，无需引入硬件。

## 7. Web 播放器家族（仅 UI 参考，全部无无损）

| 仓库 | ★ | 协议 | 状态 | 备注 |
|---|---|---|---|---|
| `Musish/Musish` | 3.2k | AGPL-3.0 | 活跃 | musi.sh，MusicKit JS，界面最接近官方 |
| `ciderapp/Cider` | 7.1k | AGPL-3.0 | **已归档** | Electron+Vue 桌面客户端，动态歌词/均衡器/遥控/WebSocket API，UI 组件库丰富 |
| `naveedgol/music-web-player`（原 apple-music-web-player） | 923 | GPL-3.0 | 已归档 | 最早的第三方网页播放器 |
| `zachomedia/apple-music-webplayer` | 604 | MIT | 停更 2026-06 | Vue，协议宽松，适合抄 UI |

- 若路线②自绘 UI 想"长得像 Apple Music"，Cider 的组件结构（app-navigation / chrome-bottom 播放栏 / mediaitem-* / lyrics-view / cider-queue）是最好的拆解对象；Musish 次之。

## 8. 另一条遥控通道参考：MediaSession 监听（非 media3）

- `Aditya-Prakash-YT/media-listener--module-`（Expo 原生模块）：用 **MediaSessionManager + NotificationListener** 监听并控制**任意**媒体 App（明确含 Apple Music）——元数据、封面、播放/暂停/上下曲/精确 seek。
- 与 media3 `MediaController`（连 `:player.MediaPlaybackService`）相比，这条通道只需"通知读取权限"，不依赖 Apple Music 是否接受会话连接。**路线②开发时可作为 media3 失败时的备选**，或双通道互备。

## 9. 顺带确认：GitHub 上没有 NIO Link/SkyUI 逆向项目

- 检索 "NIO Phone / SkyLink / NIO Link / 天空视窗" 无任何开源逆向成果——**我们的调研（白名单、ScreenCastController、dumpsys 命令通道）是公开渠道独一份**，相关文档（`docs/NIO-Link-*.md`、`tmp/skyui-framework/`）要保存好。

---

## 10. 对三条路线的最终启示

1. **路线①（dumpsys `movePackageToDisplay` 把官方 App 搬上车机屏）**：若走通，叠加 **landscape-patcher** 的横屏补丁 = 最接近"官方界面 + 无损"的终局形态。风险：补丁锚点需适配 6.5.2；重签名后媒体服务行为要实测。
2. **路线②（壳自绘 UI + 后台原生播放，保底）**：**AAIdrive 是功能级参考实现**（尤其"client 白名单限制下如何控制 Apple Music"），Cider/Musish 提供 UI 蓝本，media-listener 提供备用控制通道。音质无损（原生 App 后台解码），是目前**唯一确定能同时拿到无损 + 车机大屏交互**的方案。
3. **路线③（网页套壳）**：**已判死刑**——NIO 官方 Flux 已做过、MusicKit JS 官方确认无无损、Tesla 官方也只有 AAC。不再投入。
