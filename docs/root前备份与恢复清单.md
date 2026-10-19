> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](PUBLICATION-NOTES.md)。

# root 前：应用备份与恢复清单

> 机型 NIO Phone N2301 · Android 14 / SkyUI · 构建 `34.1742765436`
> 场景：解锁 BL + root。本机解 BL **必然清空 /data**。
> 配套脚本：`tools/backup-apps.sh`（存）、`tools/restore-apps.sh`（装回）。

一句话：**关键 App 的安装包仓库里基本都有了，Apple Music 那份还是 Apple 原签名的可用包；但手机上真实的版本没核对过，而且 App 内部数据（Apple Music 的登录态与离线歌曲）一律救不回来，只能重登重下。**

## 1 仓库里已经安全的

这些不用再找，恢复时直接装：

| 文件 | 大小 | sha256（前 16） | 是什么 | 装完要做什么 |
|---|---|---|---|---|
| `tmp/applemusic/base.apk` | 205 MB | `a05a36a5678015fd` | Apple Music **6.5.2 / versionCode 1586**。含 arm64-v8a、armeabi-v7a、x86、x86_64 **四套 ABI**，清单里**没有** `isSplitRequired` / `requiredSplitTypes` → 可以单装 | 重登 Apple ID；离线歌曲重下 |
| `apk/NioPlay-latest.apk` | 38.5 MB | `8688698855c4d5e6` | 车机上实测通过的 NioPlay（CarPlay 那条路，✅ 已完成） | 直接装 |
| `apps/nio-link-shell/niolink-shell.apk` | 33 KB | `306740d0878ddbcb` | 套壳，占白名单里的 VidHub 包位 | **必须授通知监听**（见 §4） |
| `apps/nio-link-shell/niolink-shell-3.3-landscape.apk` | 29 KB | `cc0e18fedeee8633` | 同上，`sensorLandscape` 版 | 同上 |
| `apk/stage2/OpenHeadunit-3.5.0-beta3.apk` | 13.7 MB | `db95450f4f2cdad2` | AA 车机端模拟器（研究用） | 可选 |
| `apk/stage2/AuroraStore-4.8.4.apk` | 9.4 MB | `fd9c75d90d0f4a7c` | 免 Google 账号装 Play 应用的客户端 | 可选，恢复期挺有用 |
| `tmp/skylink/skylink.apk` | 32 MB | `fafa281bff8d5e6e` | SkyLink 本体 | 仅留档，`/system` 不受解 BL 影响 |
| `tmp/netconfig/NetConfig.apk` | 654 KB | `f048f756ab1d2c02` | SkyUI 配置服务（白名单 provider 所在） | 仅留档 |

两点说明。上面 sha256 是 2026-10-07 实测值，套壳那份此刻还有另一条线 在改，`niolink-shell.apk` 可能已变；另外 `tmp/hu/hu.apk` 与 `apk/stage2/OpenHeadunit-*.apk` 是同一个文件（hash 相同），不用重复存。

Apple Music 那份我验过签名：`apksigner verify` 通过，仅 v2 方案，签名者 `CN=Apple Inc, O=Apple Inc`，1024 位 RSA。也就是说它是 Apple 自己签的包，不是镜像站重签的，装回后 Play 仍能按正常升级路径更新它。

## 2 缺口 —— 需要动手的

**设备上的 Apple Music 版本没核对过。** 仓库这份是"一份包带全部 ABI"的形态（universal 包的特征），而 Play 分发到手机上通常是 base + 若干 split（只含 arm64）的形态。两者版本号可能不同。核对：

```bash
adb shell dumpsys package com.apple.android.music | grep -m2 -E 'versionCode|versionName'
```

**第三方应用全表从来没记录过。** 不知道手机上一共装了什么，也就不知道漏了哪个。

**App 数据一律救不了。** 无 root 读不到 `/data/data`；`adb backup` 对 `allowBackup=false` 的应用本来就无效，Apple Music 就是这一类，Android 12+ 上也基本不可用。所以离线歌曲、登录态、播放列表缓存都要重新来一遍。

## 3 备份：在仓库根目录跑一条命令

```bash
./tools/backup-apps.sh
```

手机 USB 连上、USB 调试已开即可（脚本走 `adb -s <DEVICE_SERIAL>`，序列号不对就 `NIO_DEV=<序列号> ./tools/backup-apps.sh`）。它按 `pm path <包名>` 拉 **base 加全部 split**，而不是只拉 base —— 少一份 split，恢复时就会 `INSTALL_FAILED_MISSING_SPLIT`。

抓下来的东西：

| 产出 | 内容 |
|---|---|
| `apps.tsv` | 每个第三方包的 包名 / versionCode / versionName / APK 份数 / codePath |
| `apk/<包名>/*.apk` | base 与所有 split |
| `pkgs-third.txt` `pkgs-third-u.txt` `pkgs-disabled.txt` `pkgs-system.txt` | 现装 / 含"卸载留数据" / 被禁用 / 系统包 |
| `settings/` | getprop、`dumpsys package` 全文、settings 三张表、`wm size/density/user-rotation`（三个显示器）、display/window dump、通知监听与无障碍、蓝牙与 WiFi 配对、APK 的 sha256 |
| `settings/build-fingerprint.txt` | 构建指纹，找匹配 boot.img 时要用 |

只想存清单不拉 APK（几十秒）：`./tools/backup-apps.sh --no-apk`。

## 4 恢复：一条命令 + 五件手工事

```bash
./tools/restore-apps.sh backup/<时间戳>
```

单份 APK 走 `install -r`，base + split 走 `install-multiple -r`；安装顺序是 Apple Music → 套壳 → NioPlay → 其余（套壳要能查到 AM）。默认跳过 Android Auto 家族，`--all` 可强制。先看会装什么用 `--list`，只想看命令用 `--dry-run`，只装一个用 `--only <包名>`。

脚本跑完会打印下面五件手工事，它不自动做：

1. **给套壳授通知监听** —— 这是套壳拿 `MediaSessionManager.getActiveSessions()` 权限的真实来源。
   ```bash
   adb shell cmd notification allow_listener \
     com.oumi.utility.media.hub/com.oumi.utility.media.hub.MediaListenerService
   ```
   顺带纠正一处：套壳清单里那句 `<uses-permission android:name="android.permission.BIND_NOTIFICATION_LISTENER_SERVICE" />` 是**无效的** —— 它是 `signature` 级权限，声明不会授予，只能靠上面这条命令。清单里那段注释把它说成"声明即授予"是错的。
2. **确认套壳包位** —— 包名必须保持 `com.oumi.utility.media.hub`，versionCode 不低于云白名单里的 `minVer`。
3. **NIO 账号与车机** —— 登录 NIO 账号，重新配对 NIO Link。
4. **Apple Music** —— 重登 Apple ID，离线歌曲重下。
5. **现场设置**（多数系统会自己重建，不必当必做项）—— 见下一节。

## 5 会丢什么

| 项目 | 解 BL 后 | 怎么办 |
|---|---|---|
| 第三方 App 本体 | 丢 | `restore-apps.sh` 装回 |
| App 数据（AM 离线歌曲、登录态、书签） | 丢 | 重登、重下 |
| 通知监听 / 无障碍授权 | 丢 | 手工命令恢复 |
| 投屏白名单（云端那份） | **不丢** | 云端重新下发，不用恢复 |
| 系统应用（SkyUI、NIO Link、NetConfig…） | **不丢** | `/system` 不受影响 |
| NIO Link 与车机配对 | 丢 | 重登账号重新配 |
| 蓝牙 / WiFi 配对 | 丢 | 重配，列表已存 `settings/pairings.txt` |
| `wm` 尺寸与方向覆盖 | 丢，但无所谓 | SkyLink 每秒重设，恢复也没用 |
| Play Integrity / 银行与支付类 App | **会破** | 需要 Magisk DenyList + 隐藏，另案 |

## 6 明确不要装回去的

**`apk/NioLink-CrossApp-vidhub.apk`**（sha256 `1496a23f26589622`）—— 整份 NioPlay 伪装包，曾经把 NIO Link 搞崩，只在白名单 CSV 里 `installed=no` 的空位包名下才安全，别直接 `adb install`。

**`com.google.android.apps.auto*`** —— Android Auto 在这台机器上有两道内部墙（`gmscorecompat.FirstActivityImpl` 被禁用、`REQUEST_COMPANION_SELF_MANAGED` 缺 `signature|privileged`），装了只是占地方。除非后面真要接着做"root 版 AA"，否则不用装回来。

## 7 和 root 的衔接

备份必须在**解 BL 之前**跑完，解 BL 当场就抹 `/data`，没有第二次机会。

顺手把构建指纹留档：备份脚本存了 `settings/build-fingerprint.txt`（`ro.build.display.id` / `ro.build.fingerprint`）。买或找匹配的 `boot.img` / 固件包时以 `34.1742765436` 为准，型号与版本对不上的一律不能用。

root 之后的事（白名单怎么注入、Apple Music 怎么进大画布）在另一份 playbook 里，不在本文范围。
