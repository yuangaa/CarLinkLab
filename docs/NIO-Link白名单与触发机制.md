> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](PUBLICATION-NOTES.md)。

# NIO Link / 天空视窗 —— 白名单应用与触发机制

> **面向后续接手者的完整资料**。全部内容来自实机实测（NIO Phone N2301 + 蔚来 ET5T）。
> 解析后的机器可读数据见 `data/nio_link_whitelist.csv`，原始配置见 `data/settings_config.json`。
>
> ✅ **2026-10-07 已由第二轮独立复核 二次核验**：数据文件与**生效** APK 内配置 **md5 完全一致**（数据可信）；
> 共修正 5 处结论，详见 **§8 修订记录**。核验方式：`pm path` / `aapt2 dump badging` / 两版 APK 配置对比 / 设备权限状态。

---

## 0. 相关文档（先看这个）

| 文档 | 定位 |
|---|---|
| **本文档** | **完整白名单数据**（55 条 = 45 应用 + 10 游戏，含字段说明、已装标记、机器可读 CSV）+ **§6.0 零风险基线观测** |
| `NIO-Link调研报告.md` | 另一条独立线索 的**机制层深挖**：SkyLink 反编译证据、两条渲染分支、**虚拟显示器方向注入通道**（`skylink_inject_rotation`）、可行路径对比、Android Auto 实测否决 |
| `项目上下文与成果备忘.md` | 项目总上下文：硬约束、死路清单、命令手册 |
| `../data/nio_link_whitelist.csv` | 白名单机器可读版（可直接被脚本消费）|
| `../data/settings_config.json` | 从 SkyLink APK 提取的原始配置 |

> **分工提示**：机制与路径设计见《调研报告》；**具体有哪些应用在名单里、字段是什么意思**见本文档。

---

## 1. 数据来源

| 项 | 值 |
|---|---|
| 承载应用 | `com.skyui.skylink.coreservice`（系统应用，`android.uid.system`）|
| **生效安装位置** | **`/data/app/~~…/com.skyui.skylink.coreservice-…/base.apk`（versionName `2.10.8` / versionCode `2010008`）** |
| 出厂位置 | `/system_ext/app/skylink/skylink.apk`（`2.7.19` / `2007019`，**31.9 MB，只读**）|
| 配置文件 | APK 内 `assets/settings_config.json` |
| 配置版本 | `ver = 20260114`，含 `updateApp` 版本字段（**云端可更新**）|

> ⚠️ **版本陷阱（2026-10-07 二次核验修正）**：这份 45 条的名单来自**生效的 2.10.8**（`/data/app`），
> **不是** `/system_ext` 里那个出厂 2.7.19 —— 后者内置配置是 `ver=20240920`，`cross_dev_app` **只有 12 条**
> （飞书/腾讯会议/钉钉/微信/WPS/腾讯体育/QQ邮箱/网易邮箱/百度网盘/Outlook/文件管理/**抖音**）。
> 两台版本的 `cross_dev_app` 数量：**2.7.19 = 12 条，2.10.8 = 45 条**，差异巨大。
> 因此**主文档 §4.16 里"APK 内置资产只有 12 个 app、45 个是车机下发缓存的"这句需要修正**：
> 45 条就直接 baked 在生效 APK 的 assets 里。（运行时是否优先读私有目录的下载副本未能验证 —— 无 root。）

**"改不了"的真实原因**（原报告写"只读系统分区"，不准确）：设备是**非 root 生产版**
（`ro.secure=1` / `ro.debuggable=0` / 无 `su`，`adb root` 被拒），且 SkyLink 是 **NIO 平台签名**的系统应用
→ 换包/改包必然破坏签名校验。**结论不变，但理由应改成"无 root + 平台签名"**，而不是"分区只读"。

**获取方式**（可复现，务必用 `pm path` 取**生效**包）：
```bash
apk=$(adb shell pm path com.skyui.skylink.coreservice | sed 's/package://' | tr -d '\r')
adb pull "$apk" /tmp/sky.apk          # → 2.10.8，assets 内即本文档那份 45 条
unzip -o /tmp/sky.apk assets/settings_config.json -d /tmp/skyx
# 对照出厂版（只有 12 条）：
# adb pull /system_ext/app/skylink/skylink.apk /tmp/sky-sys.apk
```

---

## 2. 白名单结构

```json
{
  "ver": 20260114,
  "controlSwitch": [ {"mainSwitch":1,"notify":0,"crossApp":1,"game":1,"launcher":1} ],
  "supportPkgList": [
    { "bizType": "cross_dev_notify", "pkgs": [] },
    { "bizType": "cross_dev_app",    "pkgs": [ /* 45 条 */ ] },
    { "bizType": "cross_dev_game",   "pkgs": [ /* 10 条 */ ] },
    { "bizType": "free_window",      "pkgs": [] }
  ]
}
```

- `controlSwitch` **有两条**（`version: 1` 与 `version: 2`，内容相同）：`mainSwitch=1 / notify=0 / crossApp=1 / game=1 / launcher=1`
  → **跨端应用已开启、通知跨端是关闭的**（这解释了 `cross_dev_notify` 为空）
- 每条应用条目字段：

| 字段 | 含义 |
|---|---|
| `pkgName` | **匹配键**：应用包名 |
| `appName` | 多语种显示名（zh_CN / en_ES / zh_HK / zh_TW）|
| `screenType` | ⚠️ **语义未确证，见下方说明**。实测取值集合 = `{1,3,4,5,7,9}`（两版 APK 合计）|
| `type` | `0`=普通应用（41 条），`1`=游戏（10 条），`2`=会议/跨端协作类（微信、飞书、钉钉、腾讯会议，共 4 条）|
| `immersive` | 是否沉浸式全屏（**仅 10 个游戏为 true，45 个应用全为 false**）|
| `immersiveDisplayMode` | 游戏用的适配方式：`fitX` / `fitY` / `fitXY` |
| `supportSize` / `gameSize` | 游戏的目标分辨率（`gameSize` 按屏逐条给出 `screenType` + `immersiveDisplayMode`）|
| `support_min_window` | 是否支持小窗（仅飞书等部分应用有该字段）|
| `minVer` | **应用最低版本号**（低于它可能不生效）|
| `appIcon` | 应用商店图标 URL |

> ⚠️ **`screenType` 的语义（2026-10-07 二次核验修正）**：原报告把它写成
> 「7=常规横屏适配；5=文件管理类；3=游戏宽屏；1=游戏常规；9=休闲游戏」——**这是从单样本反推的猜测，不建议当结论用**。
> 反证（同一份数据内部就自相矛盾）：
> - 游戏条目的 `gameSize` 数组里，**同一个字段名 `screenType` 的取值恰恰是 `1/2/4/8`**，且每项配一个分辨率和 `fitX/fitY/fitXY`
>   → 说明 `1/2/4/8` 是**屏幕标识位**，`screenType` 更像**屏幕位掩码**，而非"布局类型枚举"
> - 所有观测值的均可由 `1/2/4/8` 组合而成：`7=1|2|4`、`5=1|4`、`4=4`、`3=1|2`、`9=8|1`、`1=1`
> - 跨版本还会**变**：抖音 `com.ss.android.ugc.aweme` 在 2.7.19 里是 `4`，在 2.10.8 里变成 `7`（放开到更多屏）——
>   这更像"支持屏幕范围扩大"，而不是"布局类型"被重分类
>
> 因此本字段**尚未定论**。要用它必须先反编译 `SettingsConfig` 的解析方（`com/nio/base/config/bean/SettingsConfig`）确认常量定义。
> 对"伪装壳"方案而言，**决定匹配的是 `pkgName`，`screenType` 是 SkyLink 读配置后自己用的，不需要我们提供**，所以暂不影响动手。

---

## 3. 触发机制（实测结论）

1. **按包名匹配** —— 白名单里有的包名 → 车机侧按该条配置处理；没有的 → 走手机镜像。
2. 车机屏上的虚拟显示器（天空视窗）id 实测为 **90000005**，name `com.nio.link.connly.five`，属主 `com.skyui.skylink.coreservice`。
3. 显示器尺寸/方向由 **SkyLink 决定**，关键日志：
   ```
   BaseVirtualWindowManager: getVirtualDisplay mScreenType=1, mWindowType=X
   SkyScreenCastOrientationManagerImpl: [包名/Activity]: modify orientation from A to B
   ```
   - `mWindowType=6` → 车机原生级全屏（16:9）
   - `mWindowType=2` → 手机镜像（9:16）
4. **实测：只有 `com.shihab.diplay/.CarPlayHostActivity` 能拿到 `mWindowType=6`**（白名单应用与自建 Activity 都是 2）。
5. 方向管理器会把应用分成三类：声明横屏的 → `user`（跟随该显示器的用户旋转设置）；Apple Music（清单 `behind`）→ **强制竖屏**。
6. 显示器的「用户旋转」可用 `wm user-rotation -d 90000005 lock 1` 设为横屏（让被判为 `user` 的应用满屏 16:9）。
   ⏳ **未实测** —— 且**与主文档 §5 死路清单冲突**：那里记着"用户旋转锁（`settings put` / `cmd window user-rotation`）→
   该 ROM 不响应"。命令本身在本机存在（`wm user-rotation` 可执行、`wm get-ignore-orientation-request -d 0` 也正常），
   但**对默认显示器锁定无效**。对 `90000005` 这块虚拟显示器是否有效，只能**在车内**验证。
   与主文档 §4.14-A 的 `wm set-ignore-orientation-request -d 90000005 1` 应**成对测试**。
7. 我反馈：**YouTube 等白名单应用在车机上会触发 NIO Link，呈现"类似原生 App 全屏"的体验** —— 与白名单机制吻合。
   ⚠️ 这条与第 4 条（adb 直接启动白名单应用也只得 `mWindowType=2`）**并不矛盾，但共同指向一个关键推论**：
   **拿到 6 的条件不只是"包名在名单里"，还要走车机侧的启动流程**（见 §6.0）。

---

## 4. 完整清单

### 4.1 `cross_dev_app`（45 个）

| 应用 | 包名 | screenType | type | immersive | minVer | 已装 |
|---|---|---|---|---|---|---|
| Chrome | `com.android.chrome` | 7 | 0 | False | 390000000 | ✅ |
| YouTube | `com.google.android.youtube` | 7 | 0 | False | 100 | ✅ |
| 文件管理 | `com.skyui.filemanager` | 5 | 0 | False | 1000 | ✅ |
| 腾讯视频 | `com.tencent.qqlive` | 7 | 0 | False | 29542 | ✅ |
| Outlook | `com.microsoft.office.outlook` | 7 | 0 | False | 2441 |  |
| QQ邮箱 | `com.tencent.androidqqmail` | 7 | 0 | False | 10160517 |  |
| VidHub | `com.oumi.utility.media.hub` | 7 | 0 | False | 84 |  |
| WPS Office | `cn.wps.moffice_eng` | 7 | 0 | False | 2441 |  |
| 东方财富 | `com.eastmoney.android.berlin` | 7 | 0 | False | 10023010 |  |
| 中信证券 | `com.zxscnew` | 7 | 0 | False | 2024083000 |  |
| 乐道汽车 | `com.nio.alps` | 7 | 0 | False | 6 |  |
| 今日头条 | `com.ss.android.article.news` | 7 | 0 | False | 10100 |  |
| 优酷视频 | `com.youku.phone` | 7 | 0 | False | 786 |  |
| 同花顺 | `com.hexin.plat.android` | 7 | 0 | False | 5052 |  |
| 咪咕视频 | `com.cmcc.cmvideo` | 7 | 0 | False | 260330009 |  |
| 哔哩哔哩 | `tv.danmaku.bili` | 7 | 0 | False | 8300300 |  |
| 国信金太阳 | `com.guosen.android` | 7 | 0 | False | 241 |  |
| 央视频 | `com.cctv.yangshipin.app.androidp` | 7 | 0 | False | 300060 |  |
| 夸克 | `com.quark.browser` | 7 | 0 | False | 762 |  |
| 学习强国 | `cn.xuexi.android` | 7 | 0 | False | 25902 |  |
| 富途牛牛 | `cn.futu.trader` | 7 | 0 | False | 10608 |  |
| 小红书 | `com.xingin.xhs` | 7 | 0 | False | 8691596 |  |
| 平安证券 | `com.hundsun.winner.pazq` | 7 | 0 | False | 906010 |  |
| 微信 | `com.tencent.mm` | 7 | 2 | False | 2441 |  |
| 微博 | `com.sina.weibo` | 7 | 0 | False | 6501 |  |
| 快手 | `com.smile.gifmaker` | 7 | 0 | False | 40125 |  |
| 快手极速版 | `com.kuaishou.nebula` | 7 | 0 | False | 9265 |  |
| 抖音 | `com.ss.android.ugc.aweme` | 7 | 0 | False | 300601 |  |
| 抖音极速版 | `com.ss.android.ugc.aweme.lite` | 7 | 0 | False | 320801 |  |
| 抖音精选 | `com.ss.android.yumme.video` | 7 | 0 | False | 320701 |  |
| 招商证券 | `com.cmschina.stock` | 7 | 0 | False | 770 |  |
| 斗鱼 | `air.tv.douyu.android` | 7 | 0 | False | 10789005 |  |
| 爱奇艺 | `com.qiyi.video` | 7 | 0 | False | 800160150 |  |
| 百度网盘 | `com.baidu.netdisk` | 7 | 0 | False | 2327 |  |
| 红果免费短剧 | `com.phoenix.read` | 7 | 0 | False | 65532 |  |
| 网易爆米花 | `com.netease.filmlytv` | 7 | 0 | False | 311 |  |
| 网易邮箱大师 | `com.netease.mail` | 7 | 0 | False | 393 |  |
| 腾讯会议 | `com.tencent.wemeet.app` | 7 | 2 | False | 2023480451 |  |
| 腾讯体育 | `com.tencent.qqsports` | 7 | 0 | False | 1363 |  |
| 芒果TV | `com.hunantv.imgo.activity` | 7 | 0 | False | 8303100 |  |
| 蔚来 | `cn.com.weilaihui3` | 7 | 0 | False | 565 |  |
| 虎牙直播 | `com.duowan.kiwi` | 7 | 0 | False | 99309 |  |
| 西瓜视频 | `com.ss.android.article.video` | 7 | 0 | False | 916 |  |
| 钉钉 | `com.alibaba.android.rimet` | 7 | 2 | False | 1062 |  |
| 飞书 | `com.ss.android.lark` | 7 | 2 | False | 6060650 |  |

### 4.2 `cross_dev_game`（10 个）

| 应用 | 包名 | screenType | type | immersive | minVer | 已装 |
|---|---|---|---|---|---|---|
| 光·遇 | `com.tencent.tmgp.eyou.eygy` | 1 | 1 | True | 240939 |  |
| 实况足球 | `com.tencent.tmgp.yongyong.skzq` | 1 | 1 | True | 308020001 |  |
| 巅峰极速 | `com.tencent.tmgp.dfjs` | 1 | 1 | True | 91 |  |
| 开心消消乐 | `com.happyelements.AndroidAnimal.qq` | 9 | 1 | True | 130 |  |
| 暗黑破坏神:不朽 | `com.tencent.tmgp.g67` | 3 | 1 | True | 14382342 |  |
| 狂野飙车 | `com.tencent.tmgp.aligames.kybc` | 3 | 1 | True | 36033 |  |
| 王牌竞速 | `com.tencent.tmgp.aceracer` | 1 | 1 | True | 40400 |  |
| 皇室战争 | `com.tencent.tmgp.supercell.clashroyale` | 1 | 1 | True | 576 |  |
| 重生细胞 | `com.tencent.tmgp.bilibili.deadcells.mobile` | 3 | 1 | True | 189 |  |
| 金铲铲之战 | `com.tencent.jkchess` | 1 | 1 | True | 998 |  |

### 4.3 空分组

- `cross_dev_notify`：**0 个**
- `free_window`：**0 个**

---

## 5. 已做过的实验与踩坑（重要）

| 实验 | 结果 |
|---|---|
| 用白名单里的空闲包名 `com.oumi.utility.media.hub`（VidHub）安装 **NioPlay 的完整拷贝** | ❌ **导致 NIO Link 闪退**，已卸载。教训：伪装必须做**精简壳**（不带 CarPlay/MFI 等全套组件）|
| 用 adb 直接把白名单应用启动到车机显示器 | 拿到 `mWindowType=2`（镜像），**没有**原生级待遇 → 说明"原生级"依赖**车机侧/启动流程**，不只是包名 |
| 复制 CarPlayHostActivity 的全部清单属性到自建 Activity | ❌ 仍是 `mWindowType=2`（类名/taskAffinity/resizeableActivity/windowSoftInputMode/USB filter 全试过）|
| 事后 `wm size` 强改车机显示器尺寸 | ❌ SkyLink 创建时写回，且**输入变换错位（2.03×）→ 触摸必坏** |
| 重打包 Apple Music 改横屏清单 | 未执行（方向管理器同样会无视清单，且破坏 Apple 签名）|

---

## 6. 给后续接手者 的建议

### 6.0 【最高优先·零风险】先用手上已有的白名单应用做基线观测

本报告 §4 的「已装」列其实是**整条路线里最有价值的一条线索，却被埋住了**：
手机上**现在就装着 4 个白名单应用**（对照 CSV 的 `installed=yes`，已用设备复核）：

| 应用 | 包名 | screenType |
|---|---|---|
| YouTube | `com.google.android.youtube` | 7 |
| Chrome | `com.android.chrome` | 7 |
| 腾讯视频 | `com.tencent.qqlive` | 7 |
| 文件管理 | `com.skyui.filemanager` | 5 |

> 其余 51 个白名单包名**都未安装**（其中 `com.oumi.utility.media.hub` / VidHub 是唯一被当"壳"用过、现已卸载的空位）。

**为什么必须先做这一步**：它能在**不装任何伪装壳、不改任何设置**的前提下，直接回答"白名单到底给不给 16:9 原生级待遇"，
也就是**整个"伪装壳"路线值不值得做**的前提问题。做法：
1. 车内打开天空视窗 → 在**车机的 NIO Link 应用列表**里确认能看到这几个应用（§3.7 的我反馈就靠这个入口）
2. 从**车机上**启动 YouTube / 腾讯视频，观察是否铺满 16:9、是否走应用自己的大屏布局（对比"镜像"模式的 9:16 + 黑边）
3. 同时抓 `logcat` 里 `BaseVirtualWindowManager: getVirtualDisplay mScreenType=1, mWindowType=?` 与
   `SkyScreenCastOrientationManagerImpl: modify orientation from A to B`
   → **拿到"白名单应用走正常路径时的真实 `mWindowType`"**，这才是判断基准

⚠️ 注意：车机显示器带 `FLAG_SECURE`，**截不了图**（主文档 §7.5），所以只能靠**人眼观察 + logcat**。
这一步做完再决定要不要走 §6.2 的伪装壳（那是唯一会把 NIO Link 弄崩的步骤）。

### 6.1 动手前先读

1. **先读** `AGENTS.md` 与 `docs/项目上下文与成果备忘.md`（含硬约束、死路清单、"方案 D"的 6 组对照脚本 `tools/car-orientation-test.sh（已作废，勿运行）`）。

### 6.2 伪装壳验证路径（**风险最高，务必先跑完 §6.0**）

2. 若要研究"让某个应用获得 NIO Link 原生级待遇"，**首选验证路径**：
   - 找一个**未安装**的白名单包名（见 CSV 中 `installed=no`）→ 做**精简壳**安装 → 在**车机上**通过 NIO Link 打开 → 观察 `mWindowType` 是否变 6。
   - ⚠️ 必须精简，且**先在车机上验证**，避免再次造成 NIO Link 闪退。
   - ⚠️ **回滚预案**（上次的实际处置）：`adb uninstall <伪装的包名>` 后 NIO Link 恢复正常；伪装前先确认该包名在手机上确未安装。
   - ⚠️ 匹配条件（主文档 §4.16）：包名落在名单内 + `versionCode ≥ minVer` + 只留渲染目标 UI 的 launcher Activity。
3. 白名单配置**改不了**（**无 root + 平台签名**，原报告写"只读系统分区"，见 §1 修正），
   但带 `updateApp` 版本字段，属于 NIO 云端可更新内容。
4. 权限/工具限制：车机显示器带 `FLAG_SECURE`（**无法截图**）；`pm disable-user` 不能改第三方组件；应用只能禁用**自己**的组件。

---

## 8. 修订记录

| 日期 | 修订 | 依据 |
|---|---|---|
| 2026-10-07 | 新增本节 | — |
| 2026-10-07（二次核验） | §1 修正**安装位置**：生效包是 `/data/app` 的 **2.10.8**（45 条），`/system_ext` 的出厂 **2.7.19 只有 12 条**；"改不了"的理由改为**无 root + 平台签名** | `pm path` / `aapt2 dump badging` / 两版 APK 的 `assets/settings_config.json` 对比；设备 `ro.secure=1`、`ro.debuggable=0`、无 `su` |
| 同上 | §2 **`screenType` 语义表撤回**为"未确证"（原表是从单样本反推的猜测），给出位掩码反证 | 同字段在 `gameSize` 内取值 `1/2/4/8`；抖音跨版本 `4 → 7` |
| 同上 | §2 `controlSwitch` 实为**两条**（version 1/2） | 原始 JSON |
| 同上 | §3.6 `wm user-rotation` 标为**未实测**，并与主文档 §5 死路清单的冲突显式标注 | 主文档 §5 / §6.7 |
| 同上 | 新增 **§6.0 零风险基线观测**（用现有 4 个已装白名单应用先验证前提） | CSV `installed=yes` + 设备 `pm list packages` 复核 |

> 数据文件与生效 APK 的一致性已核验：`data/settings_config.json` 的 md5 与 `/data/app` 生效版 APK 内
> `assets/settings_config.json` **完全相同**（`db5a4460f30cc9be1bea7f4d518b3124`）——**数据可信，只有 §1 的来源说明曾写错。**

---

## 7. 附：数据文件

| 文件 | 说明 |
|---|---|
| `data/settings_config.json` | 从 SkyLink APK 提取的**原始配置** |
| `data/nio_link_whitelist.csv` | 解析后的**完整清单**（含 installed 标记，可直接被脚本消费）|
