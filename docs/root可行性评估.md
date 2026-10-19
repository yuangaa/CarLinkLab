> 公开版校订（2026-10-19）：本文保留实验过程，历史“下一步”和本地路径不代表当前可用步骤。请先读 [当前结论与适用边界](PUBLICATION-NOTES.md)。

# root 可行性评估：N2301 能不能顺利 root

> 机型 NIO Phone N2301 · Android 14 / SkyUI · 构建 `34.1742765436` · 2026-10-07
> 配套脚本：`tools/root-feasibility.sh`（只读探针，不刷机、不清数据）

## 结论先说

**不能从这边替你 root，也还不能断定「root 会顺利」。** 决定权在两个我碰不到的闸门上，都要人在物理世界里过一遍；其中一个（闸门 C）目前已经看得出大概要卡住。

得说清楚为什么不是我偷懒：解 BL 要人手按按键进 fastboot、要过 NIO 自己的授权，而刷机命令得在 Mac 上跑 adb/fastboot —— 我这个沙箱里没有 adb、也不连着手机。这两件事属于**物理操作**，只能你来做。我这边能做的是把「过闸要问什么、怎么读结果、卡在哪一步就停」定死，写成一个跑一遍就把话说清的探针。

## 三道闸门

### 闸门 A：开发者选项里的「OEM 解锁」能不能打开

零风险，十秒钟，看眼睛。

设置 → 关于手机 → 连点版本号 7 次 → 系统与更新 → 开发者选项 → 找「OEM 解锁 / OEM unlocking」。

- 开关能拨动、能打开 → 闸门 A 过
- **开关是灰的、按不动 → 到此为止**，别再往下折腾了。灰掉是 ROM 层不支持解锁（`ro.oem_unlock_supported=false` 之类的编译期决定），不是权限不够，adb 和第三方工具都绕不过去。

有两点证据让我对这道闸门不乐观，但也还没到定论：

1. 项目里记的现状是 `settings global oem_unlock_allowed = 0`、`ro.build.type=user`、`ro.debuggable=0`、无 `su`、`adb root` 被拒 —— 典型的零售锁死形态。
2. 更要紧的是这台 ROM **主动把 OEM 解锁相关属性用 SELinux 挡在 shell 外面**。日志里能直接读到：

   ```
   avc: denied { read } for name="u:object_r:oem_unlock_prop:s0" ...
   Access denied finding property "ro.oem_unlock_supported"
   ```

   AOSP 默认是不挡的（`adb shell getprop ro.oem_unlock_supported` 通常能读）。厂商专门加了一条策略把 `shell` 域对 `oem_unlock_prop` 的读权限拿掉，说明他们对「解锁」这件事是有意收紧的。厂商刻意藏起来的东西，通常不会在 UI 上大方给你。

   连带一个后果：**你在 adb 里也读不到这些属性**，所以闸门 A 只能靠 UI 上的开关判断，脚本里那几行显示「（空 / 被挡）」是正常的，不是脚本坏了。

   另外别想着 `settings put global oem_unlock_allowed 1` 蒙过去 —— 这个开关真正的状态写在 persistent data block 里，必须在 UI 上人工确认，adb 写不进去。

### 闸门 B：bootloader 允不允许解锁

只读查询，会重启手机，**不清数据**。脚本加 `--fastboot` 会自动跑完：

```bash
./tools/root-feasibility.sh --fastboot
```

它做三件事：`adb reboot bootloader` → `fastboot getvar unlocked/secure/flash.locked` → `fastboot flashing get_unlock_ability`，然后 `fastboot reboot` 回系统。

怎么读 `get_unlock_ability`：

| 返回 | 含义 |
|---|---|
| `1` | bootloader 允许解锁 → 闸门 B 过 |
| `0` | 不允许。多半是闸门 A 的开关没开，回去开；开了还是 0 就是厂商禁死了 |
| `unknown command` | 该 bootloader 不支持这个查询，改用 `fastboot oem device-info` 看 |

❗ 这一步**只读**。真正清数据的是 `fastboot flashing unlock`，一执行就把 `/data` 抹掉且不可逆。脚本不会替你跑它。也别顺手试。

### 闸门 C：拿得到与当前构建匹配的 boot.img

这才是最可能卡住的地方。解锁 BL 只是拿到「可以刷」的资格，Magisk 还需要拿一份**与当前系统版本完全一致**的 `boot.img` 打补丁再刷回去。版本对不上，轻则不启动、重则变砖。

当前的来源情况：

- **官方固件包**：查不到 N2301 的完整固件。NeedROM 上只有「NIO Phone 2」（第二代，骁龙 8 Gen 3），与我们这台 N2301（骁龙 8 Gen 2）不是一回事，**绝对不能混用**。
- **系统 OTA 包**：退路是抓完整 OTA 的下载地址，从 `payload.bin` 里用 `payload-dumper-go` 一类工具抽出 `boot.img`，版本要对上 `34.1742765436`。这条路技术上可行，但前提是能抓到完整包（不是增量包）。

两条路都断了的话：**即使闸门 A、B 都过，也补不出 `boot.img`，Magisk 无从下手**，root 依然做不成。

## 顺序（别搞反）

1. `./tools/backup-apps.sh` —— **必须先跑**。见 `docs/root前备份与恢复清单.md`。
2. `./tools/root-feasibility.sh` —— 看闸门 A/B。
3. 闸门 A、B 都过了，再去找匹配 `34.1742765436` 的 `boot.img`（闸门 C）。
4. 三道都过，才动 `fastboot flashing unlock`。
5. 解锁后按标准 Magisk 流程 root，再进白名单注入那一步。

**解 BL 当场抹 `/data`，没有第二次机会**，所以第 1 步永远在最前面。

## 如果 root 走不通，退回去的两条零 root 路

- **改密度让 AM 本体进平板布局** —— AM 6.5.2 的包里确实带了 w600dp / w640dp / w720dp / w834dp 的 `layout` 变体（已验证），所以「平板模式」不是没有，是窗口宽度不够没触发。详见 `tools/` 里的密度实验与任务 #13。
- **继续用套壳** —— 车测已通过（铺满 90000001 + 真能控制 Apple Music），当前可用方案。

## 一句话给未来

问「能不能 root」时，别从「有没有 magisk 工具」下手，直接从闸门 A 下手：**去开发者选项看那个开关是不是灰的**。灰的，整条路就结束了；能开，再往下走。这也是这个评估唯一的、真正的分水岭。
