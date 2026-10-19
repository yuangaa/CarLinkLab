> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](PUBLICATION-NOTES.md)。

# 让 Apple Music 上车（大画布 / 无损）—— 最终结论与可行路径

> 实测环境：NIO Phone N2301（Android 14，`UKQ1.240227.001` release-keys）+ 蔚来 ET5T
> 结论时间：2026-10-07 17:15（车内实测，天空视窗已开启）
> 前置问题：「从车机应用列表点开 Apple Music，有没有『是否打开天空视窗体验』弹窗？」→ **实测回答：没有弹窗。**

---

## 0. 一句话结论

**NIO Link 的「原生级大画布」是一道包名白名单闸门，Apple Music 不在名单里，所以不给弹窗、只走竖屏镜像。
而这份白名单在免 root 条件下**改不动**——它由系统应用 `com.skyui.netconfig` 经签名级 ContentProvider 下发，缓存进 SkyLink 的私有目录。
因此：想让**原生 Apple Music**触发 NIO Link，只剩 **root 手机** 或 **厂商签名** 两条路。**
（"套壳"仍然可行，但套出来的画布里是**我们自己的 UI**，不是官方界面。）

---

## 1. 为什么没有弹窗（实测证据）

车机上点开 Apple Music → 无弹窗 → 仍 `mWindowType=2`（397dp 竖屏镜像）。

对照：手机端**真正能触发 NIO Link 的应用 = 白名单 ∩ 已安装 = 恰好 4 个**，与我观察完全一致：

| 我看到的 4 个 | 包名 | 白名单字段 |
|---|---|---|
| 腾讯视频 | `com.tencent.qqlive` | screenType=7, type=0 |
| 文件管理 | `com.skyui.filemanager` | screenType=**5**, type=0 |
| Chrome | `com.android.chrome` | screenType=7, type=0 |
| YouTube | `com.google.android.youtube` | screenType=7, type=0 |

白名单共 55 条（`cross_dev_app` 45 + `cross_dev_game` 10，`cross_dev_notify` / `free_window` 为空），
**没有任何音乐类应用**；Apple Music `com.apple.android.music`（6.5.2）不在其中。

→ **弹窗 = 白名单命中。** 没命中就不弹，直接回落到普通镜像。

---

## 2. 白名单为什么改不动（免 root 死路，证据链）

```
com.skyui.netconfig（系统应用，NetConfig 1.9.6，/system_ext/app/NetConfig）
   └ ConfigContentProvider  authority: com.skyui.netconfig.db   表 conf(cid, ckey, cvalue, ctype, _id)
        ▲ 权限：com.skyui.netconfig.permissions.CONFIG_UPDATE = signature|knownSigner  ← 卡死点 1
        │
        │  广播 skyui.intent.action.NET_CONFIG_UPDATE
        ▼
com.nio.base.config.ConfigUpdateReceiver   （exported=true，但同样挂签名级权限）  ← 卡死点 2
        └ com.skyui.config.d.b()  query provider → ckey="f_settings_config" → 用 cvalue(URI) 当 InputStream
              └ com.nio.base.config.loader.h (SettingsConfigLoader) 解析并缓存
                    └ 缓存位置 = Context.getFilesDir()  →  /data/data/com.skyui.skylink.coreservice/files/   ← 卡死点 3（无 root 读写不了）
```

补充卡点：

- SkyLink 全部对外入口权限均为 `signature|knownSigner`：`com.skylink.coreservice.permission`、`com.skylink.permission.NIO_LINK_SETUP`、`com.nio.link.permission.CALL_NIO_LINK` → 第三方 App 无法 bind/call。
- 设备状态：`ro.build.type=user`、`ro.secure=1`、`ro.debuggable=0`、`release-keys` → `adb root` 被拒（"adbd cannot run as root in production builds"）；无 `su`；`/data/data/com.skyui.skylink.coreservice` Permission denied。
- 外部可写目录 `…/Android/data/com.skyui.skylink.coreservice/files/` **不是**配置读取路径（只放了 `car_transfer.txt`）。

→ 改 APK assets 也没用：运行时以 provider 下发/本地缓存为准，assets 只是首启兜底。

---

## 3. "copy flux music" 的真相

车机上的 **flux music** = 套 Apple Music **网页版**（music.apple.com）的第三方 App。

- 网页播放器上限 **AAC 256kbps**，**没有无损**。
- 所以它"比手机端少无损"，根因在**播放器形态（Web）**，不在 UI。

**结论：复刻 flux music 的 UI = 复刻它的上限，一样没有无损。**
想同时要"漂亮车机 UI"+"无损"，就必须让**原生 Apple Music**参与播放。

---

## 4. 可行路径对比

| 路径 | 做法 | 能拿到什么 | 代价 / 风险 | 免 root |
|---|---|---|---|---|
| **A. 套壳顶位** | 用白名单里**未安装**的包名（如 `com.oumi.utility.media.hub`，minVer 84，screenType=7/type=0）自建 APK，versionCode 拉高顶过 minVer | 861dp 原生大画布（横屏） | 画布里是**自绘 UI**；要无损须"前台遥控 UI + 后台原生 Apple Music 播放"，**且音频能否随会话路由到车机未验证** | ✅ |
| **B. root 手机** | 直接改 `/data/data/com.skyui.skylink.coreservice/files/f_settings_config`，给 `com.apple.android.music` 加一条（抄 YouTube：screenType=7, type=0），重启 SkyLink | **官方 Apple Music 界面 + 无损**，最彻底 | 需解锁 BL / root（N2301 属 user 版，难度大、有变砖/失去保修/影响车机联动的风险） | ❌ |
| **C. 车机侧 App** | 车机允许侧载（flux music 就是装上去的），自建车机 App | 车机原生进程、性能最好 | 仍受"Web 播放器无无损"限制；需要车机侧开发环境与安装通道 | — |
| **D. 现成彩蛋（零成本）** | 用**已在白名单**的 Chrome，在车机上打开 music.apple.com | 立刻得到 861dp 大画布 + 完整网页 Apple Music | 无无损；只是缓解"小窗不好操作" | ✅ |

> **A 与 B 的关键差别**：A 拿到的是"大画布"，B 拿到的是"大画布 + 官方 App 本体"。
> 只有 B（或厂商把 Apple Music 加进白名单）能同时满足"官方界面"和"无损"。

---

## 5. 建议的下一批实验（车内 10 分钟可做完）

1. **音频路由判定（决定 A 是否成立）**
   在**镜像模式**下（当前 Apple Music 竖屏镜像）播放 → 听声音是否从车机出。
   - 能出 → NIO Link 会转发媒体音频，A 方案"后台原生播放 + 前台遥控"有戏；
   - 不能出 → A 方案必须让音频由**被跨端的那个 App 自己**播放，A 基本只能做到"无无损"。
2. **套壳最小验证（占一个白名单空位）**
   自建一个空壳 APK（包名 `com.oumi.utility.media.hub`，versionCode 调高），装上后看：
   - 手机端"支持应用"列表里是否多出它；
   - 从车机点开它，是否弹出「是否打开天空视窗体验」→ 是否变成大画布。
   → 这一步一旦通过，套壳通道就**打通了**，后面只是"里面放什么 UI"的工程问题。
3. **Chrome 彩蛋验证（顺手）**
   用 Chrome 开 music.apple.com，确认大画布下的网页 Apple Music 是否"能用"（作为过渡方案）。

---

## 6. 待你决策

- **Q1｜CarPlay**：项目最初记录"在手机上实现 CarPlay（已实现）"。如果 CarPlay 现在**可用**，Apple Music 在 CarPlay 里本身就是原生横屏 + 无损，整条 NIO Link 套壳路线就不再必要 —— 请确认它到底能不能用、为什么不用。
- **Q2｜是否愿意 root**：这是唯一能"官方界面 + 无损"一起拿到的路。愿意的话我先去查 N2301 的解锁/root 可行性；不愿意就只做免 root 的 A / D。
- **Q3｜套壳可接受度**：如果能拿到大画布，你能接受"**自绘车机 UI + 后台原生 Apple Music 放无损**"吗？还是必须看到官方 Apple Music 界面？
