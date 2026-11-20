# 怪物猎人：世界 冰原 BGM MOD 制作

`mhwi-bgm-modding` 是面向 Windows PC 版《怪物猎人：世界 冰原》的 Agent Skill。用你提供的音源替换指定任务或怪物的战斗音乐。制作时先检查工具，再依据对应游戏版本的原版 NPCK 确认音频槽位。可以只替换选中的槽位，也可以整包换成同一首曲子。

交付包括原名 NPCK、可解压到游戏目录的 `nativePC` ZIP、立体声试听 MP3 和 `verification.json`。脚本会离线核对媒体 ID、声道、采样率和解码结果。任务内何时触发、循环和实际听感需要进游戏确认。

## 安装和使用

1. 下载或克隆本仓库，把整个目录放进 Agent 的 Skills 目录，并保留相对目录结构。Codex 项目级安装可使用 `.agents/skills/mhwi-bgm-modding/`。
2. 准备有权使用的替换音源、与游戏版本匹配的原版 NPCK，以及位于游戏目录之外的工作目录。只有游戏安装文件时，可以走下文的本机提取流程。
3. 让 Agent 读取 [SKILL.md](SKILL.md)。告诉它目标任务或怪物、音源路径，以及整包换曲还是只替换指定槽位。Agent 会先检查本机工具，发现缺项立即报告，再按确认的槽位制作。

也可以直接运行 [工具预检](scripts/env_check.py) 和 [制作脚本](scripts/make_mod.py)。核心脚本只用 Python 标准库，音频处理调用本机工具。工具、游戏文件和歌曲由使用者自行准备。 [第三方工具与素材说明](THIRD_PARTY.md)

## 外部工具

| 依赖 | 要求与来源 |
| --- | --- |
| Python | 3.10 或更新版本，Windows x64。[官方安装包](https://www.python.org/downloads/windows/) |
| FFmpeg、ffprobe | 同一套 Windows 构建，带 `pan`、`afade`、`alimiter`、`loudnorm` 及 `libmp3lame`。放入 PATH 或指定路径。[下载入口](https://ffmpeg.org/download.html) |
| Audiokinetic Wwise Authoring | 已验证 2025.1.12，使用官方 Launcher 安装带 Windows 支持的 Authoring。本流程需要可运行的 `WwiseConsole.exe` 及其安装组件。[Audiokinetic Launcher](https://www.audiokinetic.com/en/download/) |
| wwiseutil | 官方 1.1 CLI `wwiseutil.exe`。[上游发布](https://github.com/hpxro7/wwiseutil/releases/tag/1.1) |
| ww2ogg | 官方 0.22 发布包里的 `ww2ogg.exe` 和 `packed_codebooks_aoTuV_603.bin` 保持同目录。已有可信的 `revorb.exe` 可以作为可选步骤指定。[上游发布](https://github.com/hcs64/ww2ogg/releases/tag/0.22) |

## PowerShell 快速开始

把变量换成实际路径。工具已经在 PATH 或默认位置时，可以省略相应的路径参数。首次运行使用新的环境配置和交付目录。

```powershell
$skill = 'Skill 的绝对路径'
$work = '已存在的工程目录'
$tools = '已存在的工具目录'
$wwise = '自定义 Wwise 安装目录中的 WwiseConsole.exe'
$envFile = Join-Path $work 'env.json'
python (Join-Path $skill 'scripts/env_check.py') --out $envFile --tools-dir $tools --wwise $wwise
if ($LASTEXITCODE -ne 0) { throw '先处理预检列出的必需项。' }

$reference = '原版 NPCK 的绝对路径'
$source = '替换音源的绝对路径'
$target = Split-Path $reference -Leaf
python (Join-Path $skill 'scripts/make_mod.py') --env $envFile --reference $reference --source $source --target $target --output (Join-Path $work '交付') --all-slots
```

示例用原版文件的名称作为目标名，下载或提取后若改过名，请把 `$target` 设置为游戏实际加载的文件名。`--all-slots` 表示整包换曲。只改已确认的槽位时，可换成 `--slot 2 --slot 8` 等参数。

`--tools-dir` 下默认查找 `wwiseutil.exe` 和 `ww2ogg/ww2ogg.exe`，各工具也可用同名参数单独传入。省略 `--out` 即可只读检查。缺少必需项时，脚本以退出码 1 停止，标准错误和 JSON 的 `_preflight.missing` 会列出原因、路径参数和获取方式。`revorb` 是可选项。环境配置记录本机路径，换电脑时重新生成。

## 可选：从本机游戏定位原版

有原版 NPCK 可跳过本节。定位功能面向本机中受支持的 `chunkG*.bin`，需要使用者提供本地 Steam 游戏目录、兼容的 `oodle.dll` 和对应的 `keyseq.key`。这些文件只用于读取自己安装的游戏。缺少这组依赖时可直接由使用者提供原版 NPCK，主流程照常使用。

```powershell
$chunkEnv = Join-Path $work 'chunk-env.json'
$index = Join-Path $work 'bgm-index.json'
python (Join-Path $skill 'scripts/env_check.py') --stage chunk --game $game --oodle $oodle --keyseq $keyseq --out $chunkEnv
if ($LASTEXITCODE -ne 0) { throw '提取工具检查未通过。先处理上面的缺项。' }
python (Join-Path $skill 'scripts/chunk_extract.py') --env $chunkEnv --index $index --list-bgm
```

`$game`、`$oodle` 和 `$keyseq` 分别指向游戏根目录、兼容 DLL 和序列文件的实际路径。知道准确文件名时，用 `--target 游戏文件名.npck` 替代 `--list-bgm`，可重复指定。查看索引中的完整游戏路径、来源 chunk 和跳过的归档，确认候选后按序号提取：

```powershell
python (Join-Path $skill 'scripts/extract_targets.py') --env $chunkEnv --index $index --candidate 1 --output (Join-Path $work '原版候选')
```

每个候选写入独立目录，保留来源名称，即使文件同名也不覆盖。候选序号从 1 开始，每次提取至少明确指定一个 `--candidate`。索引供同一游戏安装使用，归档变化后重扫。文件表只提供候选，怪物、任务和战斗阶段的实际加载关系要另外核对。

## 历史记录

`实战/` 与 `示例/` 记录曾经完成的「雨爱」与「月声尽」项目。两首歌的响度、裁剪点、坏帧号和怪物槽位都只适用于各自的素材与版本。`A7_成品wav.py` 和 `A9_v2成品wav.py` 是旧工程辅助脚本，使用它们时需要 NumPy。新项目用 `make_mod.py`。

## 署名

项目维护：mastre1。Skill 通用化、工具预检和中文文档由 Codex 协助完成。
