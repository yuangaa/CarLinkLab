> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](../PUBLICATION-NOTES.md)。

# 需求：天空视窗支持 Apple Music 以 16:9 全屏显示

## 现象
在 ET5T 上用「天空视窗」打开 **Apple Music（com.apple.android.music）** 时，
它以 **9:16 竖屏**（1488×2992）投屏，车机横屏上两侧大片黑边，界面只能用手机版布局，不好操作。

## 对比
同一台手机上，**NioPlay（com.shihab.diplay）** 能被正确投成 **16:9（3024×1696）** 全屏。
差别在日志里很明确：

```
# NioPlay（正常，16:9）
BaseVirtualWindowManager: getVirtualDisplay mScreenType=1, mWindowType=6
RegionSamplingHelper: real 3024 x 1696, rotation 1

# Apple Music（9:16）
BaseVirtualWindowManager: getVirtualDisplay mScreenType=1, mWindowType=2
SkyScreenCastOrientationManagerImpl: [com.apple.android.music/.common.MainContentActivity]:
    modify orientation from 0 to 1        ← 被强制成竖屏
```

## 定位到的机制
SkyLink 内置按应用的显示配置（APK 内 `assets/settings_config.json`）：

- `supportPkgList[].bizType = cross_dev_app`（45 个应用）
- 每个条目带 `screenType` / `immersive` / `immersiveDisplayMode(fitX|fitY|fitXY)` / `supportSize`
- 该文件带 `updateApp` 版本号字段，属于**可云端更新**的配置

**`com.apple.android.music` 不在这份名单里** → 因此走到「手机镜像」分支（mWindowType=2 → 9:16）。

## 请求
把 **`com.apple.android.music`（Apple Music）** 加入 `cross_dev_app` 白名单，
参照名单里其它媒体类应用的配置（如 `com.tencent.qqlive`、`com.google.android.youtube`、`com.hunantv.imgo`
均为 `screenType: 7, immersive: false`），让 Apple Music 在天空视窗下按 **16:9 全屏适配**。

## 为什么值得做
1. Apple Music 的音频输出走 **座舱音响**（`nio_virtual_devices`，IP / PCM 无压缩，支持 5.1 / 7.1.4），
   音质是同价位方案里最好的；唯一短板就是它在车机屏上是竖屏、不好操作。
2. 我实际使用链路已经打通：NIO Link 连接 → 座舱音响 → 车机音响（无损），
   只差显示适配这一步。
3. 名单机制是现成的（已有 45 个应用），加一条即可。

## 附：我这边的临时折衷（供参考，不必回复）
- 目前用手机会员侧通过降低虚拟显示密度让 Apple Music 进入「平板布局」（661dp），
  触摸正常但仍是 9:16；
- 另外做了一个「车机音乐」入口，一键把 Apple Music 投到车机屏（仍是 9:16）。
