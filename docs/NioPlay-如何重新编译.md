> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](PUBLICATION-NOTES.md)。

# NioPlay 自编译版（DiPlay 0.2.13 + 7 个补丁）说明

## 这个包和官方包的区别

包名、版本号都和官方一致（`com.shihab.diplay` / 0.2.13 / versionCode 32），区别只有七处代码改动：

| # | 补丁 | 文件 | 作用 |
|---|---|---|---|
| 1 | **BYD 空转守卫** | `shared/src/main/java/com/shilapi/xcertplay/hud/BydNavigationOutputs.kt` | 非比亚迪设备上不再启动 `BydHudBridge`（原来会每 **300ms** 向不存在的 `com.ts.car.someip` 服务 `bindService` 一次，永不停止） |
| 2 | **LocalOnlyHotspot 放回 UI** | `common/.../DiPlayActivity.kt`、`common/.../CarPlayHostActivity.kt`、`common/.../AirPlayPersistence.kt` | 连接方式里重新出现 `LocalOnlyHotspot` 选项；同时删掉了把 `LOCAL_ONLY_HOTSPOT` 强制改写成 `MANUAL` 的两处代码 |
| 3 | **固定横屏** | `common/src/main/AndroidManifest.xml` | 6 个 Activity 全部设为 `landscape`（**固定一个横屏方向**，不再用 `sensorLandscape`，这样设置页与 CarPlay 画面方向永远一致） |
| 4 | **NIO 品牌** | `AirPlayPersistence.kt` 的 `DEFAULT_OEM_LABEL` 改成 `"NIO"`；`common/src/main/res/raw/ic_car_home.png` 换成 NIO logo | CarPlay 应用列表里"返回车辆原生界面"那个按钮的名称与图标 |
| 5 | **挖孔满屏** | `CarPlayHostActivity.applyFullscreenMode()`、`DiPlayActivity.onCreate()` | 设 `layoutInDisplayCutoutMode = ALWAYS`。不设的话横屏时窗口会被挖孔避让挤掉 116px（实测窗口从 `[116,0][3200,1440]` 变成 `[0,0][3200,1440]`） |
| 6 | **应用名 NioPlay** | `common/src/main/res/values*/strings.xml` 的 `app_name` | 安卓桌面 / 最近任务 / 应用信息里显示 `NioPlay`（所有语言） |
| 7 | **出厂默认值固化** | `common/.../AirPlayPersistence.kt` | HEVC **开**、音乐缓冲 **开**、车载热点 SSID **carplay** / 密码写进默认值 → 卸载重装或换机后开箱即用，不用再配 |
| 8 | **全面改名 NioPlay** | 全部 `res/values*/strings.xml`（327 处）+ `hotspot_join.xml` + LOH 的 SSID | 我可见文案里 `DiPlay` → `NioPlay`。**未改**：包名 `com.shihab.diplay`（改了会丢设置+要重新配对）、内部日志 tag |
| 9 | **极致流畅化**（画布 60% + GPU 锐化） | `CarPlayPicture.kt`（AGSL 着色器）、`CarPlayHostActivity.createAirPlayConfig()`（画布缩减）、`DiPlayActivity`（开关） | 打开后：① 声明给 iPhone 的画布缩到 60%（**接收端唯一能减轻 iPhone 编码负担的杠杆**）② 本机 GPU 用 luma-only unsharp 把放大后的画面锐化回来。强度 0.30，correction 软限幅 ±0.125 |
| 10 | **LOH 支持 Android 14** | `shared/.../network/LocalOnlyHotspotManager.kt` | SDK 门从 `==33 \|\| >=36` 放开到 `>=33`；无 STA 时显式用 2.4GHz（5GHz 让给车机链路）。⚠️ LOH 的 SSID 每次随机，破坏 iOS"已知网络"前提，**不作为推荐路径** |
| 11 | **CarPlay 尺寸加 275mm 档** | `CarPlaySize.kt`、`LocalizedOptions.kt`、`AirPlayDisplaySettings.kt` | 新增 `MEDIUM_LARGE("中大",275)`；屏宽步进 `WIDTH_PHYSICAL_MM_STEP` 50 → **25**（否则 275 会被吸附回 300） |

> **分辨率保持 100%（`CarPlayDisplayScale.DEFAULT_TENTHS = MAX_TENTHS`）**：画布 = 屏幕分辨率才不会被插值放大，低于 100% 一定会糊。想减小带宽请改 **CarPlay 尺寸**（`CarPlaySize`：`LARGE`=报告屏宽 250mm → iOS 控件更大，画布不变），而不是降分辨率。
> 当前在用的组合：**分辨率 100% + CarPlay 尺寸「大」** → 实测 2.4GHz 上 30.1fps、点按延迟 30ms。

> ⚠️ 补丁 7 会把热点密码以明文形式编译进 APK（`classes3.dex` 里能直接搜到）。个人自用没问题，**别把带密码的包分发出去**。换热点名/密码后记得在 DiPlay 里同步改一次。

另外新增了中英文文案 `hotspot_mode_local_desc`。

> 注意：`android:layoutInDisplayCutoutMode` **不是清单属性**，写进 AndroidManifest.xml 会编译失败（`AAPT: error: attribute ... not found`）。必须在代码里设 `WindowManager.LayoutParams.layoutInDisplayCutoutMode`，并且 `LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS` 要 API 30+ 判断，低版本退回 `SHORT_EDGES`。

未改动：身份资产（`assets/offline-mfi/`，与官方包逐字节一致）、native 源码、其余全部业务逻辑。

## 编译环境（已装好）

| 组件 | 位置 |
|---|---|
| JDK 25 | `/opt/homebrew/opt/openjdk@25` |
| Android SDK | `/opt/homebrew/share/android-commandlinetools`（platform 37.0 / build-tools 37.0.0 / NDK 28.2.13676358 / cmake 3.22.1） |
| 源码 | `~/DiPlay-src/DiPlay-0.2.13` |
| 身份资产输入 | `~/DiPlay-src/auth-assets/offline-mfi/{identity.pk8,certificate.p7b}` |
| 签名密钥 | `~/DiPlay-src/diplay-local.keystore`（alias `diplay`，口令 `<KEYSTORE_PASSWORD>`，SHA256 `9c10829f…b0ccb8c`） |

### 网络坑（重要）

这台机器访问 `repo.maven.apache.org` 和 `plugins.gradle.org` 都返回 **403**，直接编译会挂在拉依赖上（实测耗了近 3 小时才失败）。已在 `settings.gradle.kts` 里改成阿里云镜像：

```kotlin
maven("https://maven.aliyun.com/repository/google")
maven("https://maven.aliyun.com/repository/public")
maven("https://maven.aliyun.com/repository/gradle-plugin")
```

并且去掉了 `foojay-resolver-convention` 插件（在线解析 JDK 用不上，JDK 25 已本地安装）。改完后编译只要 **1~3 分钟**。

## 重新编译

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@25
export PATH="$JAVA_HOME/bin:/opt/homebrew/bin:$PATH"
export DIPLAY_AUTH_ASSETS_DIR=~/DiPlay-src/auth-assets
export ANDROID_KEYSTORE_PATH=~/DiPlay-src/diplay-local.keystore
export ANDROID_KEYSTORE_PASSWORD="填写你自己的签名密码"
export ANDROID_KEY_ALIAS=diplay
export ANDROID_KEY_PASSWORD="$ANDROID_KEYSTORE_PASSWORD"
cd ~/DiPlay-src/DiPlay-0.2.13
./gradlew :mobile:assembleRelease
```

产物：`mobile/build/outputs/apk/release/mobile-release.apk`

**注意**：不要用 `assembleDebug` —— debug 变体带 `applicationIdSuffix = ".hudtest"`，包名会变成
`com.shihab.diplay.hudtest`，装上去是并存的第二个 App。要出调试包用
`./gradlew :mobile:assembleStandaloneDebug`（它会先校验身份资产）。

## 安装 / 升级规则

- 本包用自建密钥签名，**和官方包签名不同** → 第一次安装必须先卸载官方版
  （`adb uninstall com.shihab.diplay`），会清掉 DiPlay 自己的设置和配对记录，
  iPhone 的系统蓝牙配对不受影响。
- 之后再改再编译，只要**一直用同一把 `diplay-local.keystore`**，就能 `adb install -r` 直接覆盖，
  设置和配对都能保留。
- 一旦用回官方 APK，下次再装自编译版就又要卸载一次。

## 已知未做的改动

- **BYD 车辆数据**（车速/档位/电量上报给 iPhone）仍是比亚迪专属实现，蔚来车机上无后端可用。
- 未做 release 混淆以外的体积优化；release 构建里 `optimization.enable = false`，与官方包一致。

---

# 第二阶段：车内链路实测与结论（2026-10-07）

## 完整链路（实测数字，不是推测）

```
iPhone
 ├─①无线 CarPlay ──▶ DiPlay 解码 [1512×848 @30fps]
 │                     │
 │                     ├─ 运行在「天空视窗」创建的虚拟显示器 3024×1696（16:9）
 │                     └─ GPU 边缘感知锐化（AGSL / RenderEffect on TextureView）
 │
 ├─②天空视窗编码 ──▶ 800×1600（横向 1600×800）@ 6 Mbps ──▶ 车机屏
 │                    ↑ 这是硬天花板：把 5.1Mpx 砍到 1.28Mpx
 │
 └─音频：AAC-LC 48kHz ──▶ DiPlay 解码 PCM ──▶ nio_virtual_devices (IP, High-quality)
                                             ──▶ 车机音响（PCM 无压缩传输）
```

**关键结论**：
1. **手机自己的 3200×1440 屏幕不在链路里** —— DiPlay 跑在天空视窗的虚拟显示器上
2. **链路②（6 Mbps / 1.28 Mpx）是唯一瓶颈** —— 所以 CarPlay 画布压到 **1512×848**（=1.28Mpx，精确匹配）后，**再高的画布纯属浪费**
3. **CarPlay 音频固定 AAC-LC，有线也一样**（实测：已声明未压缩 PCM，iPhone 不选）→ **有线无音质收益**
4. **DiPlay → 座舱音响 → 车机是全 PCM 无损** ✅（唯一的损失来自 iPhone 的 AAC）
5. **想真无损只能绕开 CarPlay**：车机自带流媒体 App、或 iPhone 走 iPod/USB 音频模式

## 5GHz 冲突实测（重要）

| 现象 | 数据 |
|---|---|
| 设置页选择 | `AP 频段: 5 GHz 频段` |
| **热点实际运行** | **`frequency = 2462`（2.4GHz ch11）** |
| 天空视窗 P2P | 5180 / 5200 / 5745（5GHz） |

**结论：设置选 5GHz，系统会静默回落到 2.4GHz —— 因为 5GHz 射频被天空视窗的 P2P 组占着。**
**而这个回落恰好是最优解**：热点 2.4GHz + 天空视窗 5GHz = 两条**独立射频真并行**。
"两个都在 5GHz"在硬件上只会让它们**分时抢同一条射频**，不会更快。

（补充：早先"DiPlay 抢不过 NIO Link"那次是 **P2P vs P2P**（系统规定同一时刻只能有一个 P2P 组，普通应用抢不过系统进程，有 `connectivityLevelFailureCode=CANCEL` 为证），**不是**热点 vs P2P。）

## 本轮新增补丁

| # | 补丁 | 文件 | 作用 |
|---|---|---|---|
| 12 | **CarPlay 身份硬编码改名** | `CarPlayHostActivity.kt`（iAP2 `name`/`serialNumber`/`label`/`deviceName`/`hostName`）、`AirPlayPersistence.kt`（`DEFAULT_MODEL`/`DEFAULT_MANUFACTURER`）、`NavigationWidget.kt`、`DiPlaySessionService.kt` | 这 9 处是**硬编码字符串**（不在 `strings.xml`），会显示在 **iPhone 的 CarPlay 车辆列表**里。全部改为 `NioPlay` / `NIOPLAY-` / `nioplay-`。⚠️ 序列号变了 → iOS 会当"新车"，CarPlay 列表可能出现旧「DiPlay」残留（手动删） |
| 13 | **画面上限档位** | `AirPlayPersistence.kt`（`ultra_smooth_percent`）、`DiPlayActivity.kt` | 「极致流畅化」下面新增 **75% / 60% / 50%** 三档。**实测最优是 50%**（=1512×848，精确等于链路②的 1.28Mpx） |

## 验证/复现命令

```bash
# 热点真实频段（设置页会骗你）
adb shell dumpsys wifi | grep -oE "SoftApInfo\{[^}]*frequency= [0-9]+"

# 天空视窗用的信道
adb shell dumpsys wifi | grep -oE "channelFrequency=[0-9]+"

# CarPlay 协商结果（画布/帧率/物理尺寸）
adb logcat -d | grep "airplay /info displays" | tail -1

# 链路② 的编码参数（6 Mbps = 800×1600）
adb shell dumpsys media.metrics | grep -B2 "bitrate=6000000"

# 音频编解码器（无线/有线都是 AAC_LC）
adb logcat -d | grep "DiPlay-AudioStats: audio stats" | tail -1

# 座舱音响的虚拟音频设备
adb shell dumpsys media.audio_policy | grep -i nio_virtual

# 无线调试通道（USB 口要让给 iPhone 时）
adb tcpip 5555 && adb connect <手机热点IP>:5555
adb usb      # 还原
```

## 已知坑（踩过的）

1. **切有线 CarPlay 前必须关掉 iPhone 的 Wi-Fi** —— 否则 iOS 占着无线会话，USB 侧读取全部超时（实测 382/412 次）
2. **`cmd wifi stop-softap` / `start-softap -f <MHz>` 被安全策略拦**（需要 `MAINLINE_NETWORK_STACK`）；只有 `-b <band>` 能过，但**改不了已运行热点的频段**
3. **iPhone 开个人热点 + 要连别的 Wi-Fi 会冲突** —— 个人热点开着时 iPhone 的 Wi-Fi 工作在 AP 模式，无法作为客户端加入 `carplay`
