# 实验工具与依赖

这里保存实验期间的脚本，不是完整应用或一键部署工具。运行前阅读脚本、检查设备和依赖。仅在停车时调试；修改显示、旋转、网络或应用状态前记录原值及恢复步骤。

| 工具类别 | 文件示例 | 所需条件 |
|---|---|---|
| UI XML 坐标解析 | `uifind.py` | Python 3、设备导出的 UI XML；它输出坐标，点击需要另外执行 |
| TCP 中继 | `relay.py` | Python 3、可达的目标地址 |
| Chrome 调试 | `cdp_*.js` | Node.js（内置 WebSocket）、ADB 转发、已启用调试的手机 Chrome |
| 备份与恢复 | `backup-apps.sh` / `restore-apps.sh` | ADB、足够空间、目标设备序列号；备份含私人数据与第三方 APK，禁止提交 |
| 系统与无线诊断 | `root-feasibility.sh` / `car-wireless.sh` / `car-session.py` | ADB、相应 ROM 命令；部分动作修改无线调试或设备设置，先看帮助和源码 |
| 图像与帧分析 | `review-*.py` / `analyze-nio-test-data.py` | 脚本指定的本地采集数据及 Python 库；数据未公开 |
| 桌面模拟、桥接和采集 | `desktop-am-lab.py` / `arm-am-embedded.py` / `prepare-phone-test-entry.py` 等 | 部分需要 scrcpy 5.0、Android SDK、JDK、`apps/am-landscape` 助手及桥接文件；这些文件没有随本仓库发布，克隆后不能直接完成实验 |
| 旧方向对照 | `car-orientation-test.sh` | **已作废，入口已阻止执行，仅留作历史** |

部分工具使用 `NIO_DEV` 环境变量；部分直接调用 `adb`。不要假设所有工具共享统一的设备选项。多设备连接时先确认每个脚本的选择逻辑。

示例：

```bash
adb devices
NIO_DEV='你的设备序列号' bash tools/root-feasibility.sh
```

本公开版仅执行静态语法和数据一致性检查；未重新运行设备修改、车机实验或采集程序。以 [当前结论与适用边界](../docs/PUBLICATION-NOTES.md) 为准。
