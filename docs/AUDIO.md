# Apple Music 杜比全景声实测

**项目作者已明确确认：Apple Music 杜比全景声通过实车验证。** 此项验收针对本项目 NIO Phone × NIO ET5T 环境，不将同一结论自动延伸到 Spotify、其他车辆或所有音乐曲目。

## 两类证据

1. **实车验收**：作者在车内实际使用并确认杜比全景声体验；于公开版整理时明确补充该结论。
2. **手机侧诊断**：已有播放状态采集显示 Apple Music 音轨处于 started / Active，路由到 `Nio Virtual Multi_7_1_4_Out High-quality`。采样率 48 kHz，声道掩码 `0x2d63f`；AudioFlinger 列出 12 个位置，包括前后各两个高度声道。

这比“播放页出现 Dolby Atmos 标识”多了一层正在运行的多声道输出证据。手机音轨配置为 16-bit PCM，输出配置为 24-bit PCM；输出位深不等于源音轨精度，**Atmos 与无损也不应混为一谈**。

## 验证范围

保留作者的实车验收结论，同时区分手机端诊断与车机端仪器测量：现有诊断没有逐个测量车机扬声器的信号，不据此声称每个声道都完成了独立校准或信号分析。

Apple Music / Spotify 的画面、触摸与播放均已实车确认；Atmos 实车结论针对 Apple Music。桥接的长期保活、黑屏重连与黑边仍有待解决，音频验收不等于全部软件稳定性已经完成。

## 证据出处

原始诊断保留本地，未公开账号、设备标识或完整日志。供项目维护者追溯的索引：

- `data/atmos-check-20261011-live/media-session.txt:40`：Apple Music PLAYING。
- 同目录 `audio.txt:356`：同一应用音轨 started，48 kHz / `0x2d63f`。
- `audio-policy.txt:63`：7.1.4 设备；`:1582–1594`：Active 客户端及音轨格式。
- `audio-flinger.txt:977`：12 声道；`:1103`：同一播放音轨 active。

较早的 `data/atmos-check-20261011/` 是暂停快照，应优先采用上述后续播放中采集，不能把两次采集状态混用。
