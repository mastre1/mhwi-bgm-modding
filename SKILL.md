---
name: mhwi-bgm-modding
description: 为 Windows PC 版《怪物猎人：世界 冰原》制作、验证或排查战斗 BGM 替换 MOD。用于指定怪物或任务的 NPCK、Wwise WEM、nativePC 安装包、槽位声道、响度、循环，以及替换后无声或乱码。
compatibility: Windows x64、Python 3.10+。制作需要本地 FFmpeg、Audiokinetic Wwise Authoring、wwiseutil 和 ww2ogg，均可用显式路径指定。用户需提供有权使用的音源和与游戏版本匹配的原版 NPCK。
---

# 冰原战斗 BGM MOD

使用此 Skill 时，以本文件所在目录为 Skill 根目录。原版 NPCK、用户音源和游戏安装目录只读。配置和交付写入用户指定的工程目录，命令中的输出目录应是新目录。工具来源和安装说明见 [README.md](README.md)。

## 0. 先检查工具

开始制作前先运行 `python --version`。如果 Python 缺失、无法执行或低于 3.10，立即反馈给请求者，并提供 [Python 官方下载入口](https://www.python.org/downloads/windows/) 或请其提供可用的解释器路径。

将 `$skill` 指向本文件所在的绝对路径，再做一次只读检查。在读取音源、分析原版或创建交付目录前完成这一步。

```powershell
python (Join-Path $skill 'scripts/env_check.py')
```

- 以退出码和 JSON 中的 `_preflight.ready` 判断能否继续。`_preflight.missing` 列出全部阻塞项，每项包含名称、原因、路径参数和获取方式。发现缺项时立即汇报，暂停受影响的流程。已有工具时按提示传入路径后重新检查。
- `_preflight.optional_missing` 只作提示。没有 `revorb` 可继续制作。
- 只做原版定位或提取时，改用 `--stage chunk`，并按 README 传入游戏目录和提取工具路径。没有这组依赖时，可以请请求者提供对应原版 NPCK。
- 只分析 NPCK 或给已有成品打 ZIP 时，Python 即可运行。修复 FLAC 或生成试听的入口会先检查 FFmpeg。

## 1. 确认制作范围

开始前核对三项：

1. 目标是哪个怪物、任务或战斗阶段，实际加载的 NPCK 文件名是什么。
2. 哪份原版 NPCK 与使用者的游戏版本对应。改过的旧 MOD 可以参照响度，原版用于校验媒体 ID 和槽位规格。
3. 使用者想整包替换为同一首歌，还是只改指定槽位。槽位未确认时先列出候选和已有证据，停在分析阶段。文件名、时长和声道数都不能单独证明游戏内的触发条件。

有原版 NPCK 时直接开始。没有时先请使用者提供对应原版，或按 [原版索引和提取](README.md#可选从本机游戏定位原版) 的步骤在本机定位候选。同名候选可能来自不同更新包，要保留来源并确认生效版本。以下两个历史对应关系只能用于已核对的任务和游戏版本：

| 历史目标 | 原文件 | 槽位规格 |
| --- | --- | --- |
| 激昂金狮子（活动斗技场） | `bgm_slugger_ingame_11_00.npck` | 9 槽，第 2、8 槽双声道，其余四声道 |
| 煌黑龙 | `bgm_slugger_ingame_14_00.npck` | 11 槽，全四声道 |

按请求决定响度和裁剪。无明确要求时保留首尾内容，采用 0 dB 增益和峰值限幅。默认短淡入淡出可通过参数关闭。旧 MOD 的 LUFS 只作该次请求的参考。比较时保持声道口径一致，试听和游戏混音仍需单独确认。

## 2. 从任意工作目录运行

把下面 PowerShell 变量赋值为实际路径。配置放在已存在的工程目录，原版和音源可以在别处。参数支持带空格和中文的路径。工程目录应在游戏安装目录之外。

```powershell
$skill = '该 Skill 的绝对路径'
$work = '本次工程的绝对路径'
$reference = '原版 NPCK 的绝对路径'
$source = '替换音源的绝对路径'
$target = '游戏实际加载的文件名.npck'
$envFile = Join-Path $work 'env.json'

python (Join-Path $skill 'scripts/env_check.py') --out $envFile
if ($LASTEXITCODE -ne 0) { throw '工具检查未通过。先处理上面的缺项。' }
python (Join-Path $skill 'scripts/A1_分析原版.py') $reference
```

保存配置时带上自检通过的路径参数。配置记录本机路径，换电脑时重新自检并使用新的 `--out` 路径。

槽位从 1 开始。下面只替换第 2、8 槽，前提是它们已确认；整包应用同一首歌时，用 `--all-slots` 替代两个 `--slot`。不同 NPCK 分别运行，有合并需求时再用 A8。

```powershell
python (Join-Path $skill 'scripts/make_mod.py') --env $envFile --reference $reference --source $source --target $target --output (Join-Path $work '交付') --slot 2 --slot 8
```

主流程使用 FFmpeg 准备 48 kHz、16 位的 2ch 或 4ch 音频，经 Wwise 官方 Vorbis 编码及 wwiseutil 重建。按原版逐槽验证 ID、采样率和声道，检查选中槽位与编码 WEM 的字节，并比对未选中槽位是否保持原媒体。每种实际使用的 WEM 都回读并完整解码，核对采样率、声道和时长。

- `--trim-start` 和 `--trim-end` 是原音源时间轴上的秒数。需要卡点时用可复核的时间戳，裁后试听。
- `--gain-db` 手动指定增益，`--peak-db` 指定限幅阈值，默认 −1.5 dBFS。
- `--fade-in` 和 `--fade-out` 以秒为单位，传 `0` 可以关闭。
- 支持本格式中 48 kHz 的 2ch 和 4ch 槽位。遇到其它包装格式或声道布局，先确认文件和规格再决定后续操作。
- 音源解码失败时先换无损坏的源。确需抢救 FLAC 时走下方的诊断分支。

定点诊断可以用 `A2_导出wem.py 原版.npck 新目录 --slot 序号` 导出少量候选供本机核对。单独验收现有包时用 `verify_npck.py 成品.npck 原版.npck`，其检查范围是容器结构和原版规格。游戏内事件与循环要结合实际任务验证。

## 3. 交付与游戏验收

在交付目录核对原名 NPCK、`*_mod.zip`、`preview_stereo.mp3`、`verification.json`。试听是同一处理后混音的立体声预览。安装 ZIP 内的路径应为 `nativePC/sound/wwise/Windows/<文件名>.npck`。可按 [安装说明模板](模板_安装说明.md) 填写目标任务、槽位、冲突文件和测试状态。

报告的 `game_test: pending` 表示仅完成离线验收。用户如需实机确认，应在目标任务检查每个改动阶段的触发、响度、循环、场景切换和其它槽位的原音。手动安装、移除或启用 MOD 应另行获得用户授权。覆盖同名单包的 MOD 要先处理冲突。

## 可选诊断

- **装了但没生效。** 先查 MOD 管理器是否已启用、归档路径是否正确、当前任务是否加载该 NPCK，以及相同路径是否被其它 MOD 覆盖。
- **静音或乱码。** 核对实际部署的 NPCK、逐槽规格、对应的 Wwise 编码和完整回读。不要手改 WEM 标识、长度或码本字段。
- **响度异常。** 用 `ffmpeg -i 文件 -af loudnorm=print_format=summary -f null -` 读取 `Input Integrated` 和 `Input True Peak`。双声道和四声道分别量，记录参考是原版、旧 MOD 还是使用者指定的目标。
- **损坏的 FLAC。** `A3_FLAC帧扫描.py 源.flac` 比较声明与扫描样本数，`A4_FLAC帧CRC.py 源.flac` 给出疑似坏帧（从 0 开始），`A5_时间轴定位.py 源.flac [秒数]` 用源采样率定位。确认帧号后运行 `A6_修复解码.py 源.flac 新目录 --bad 帧号[,帧号...] --env env.json`。只有确认尾部截断时才传 `--trim-tail N`。输出 `repaired.wav` 可作为制作音源。修复会丢弃指定帧，试听接缝并核对时长。
- **多目标合包。** 用 `A8_打包.py 工程目录 --npck 包1.npck 包2.npck --output 新交付目录` 合并已分别验收的包。需要试听时显式传 `--preview-wav`，它应和这些包对应。

[煌黑龙旧案](实战/01_雨爱_煌黑龙.md)和[金狮子、煌黑龙旧案](实战/02_月声尽_金狮子+煌黑龙.md)记录了历史参数与游戏反馈，可供排查。现行入口和参数以本页为准。
