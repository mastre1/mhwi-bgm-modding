# A1 解剖 与 verify 校验实录（2026-10-28 月声尽实做，原样保留）

> 用途：给后来者当"输出长什么样、怎么判读"的对照。工具：`scripts/A1_分析原版.py`、`scripts/verify_npck.py`。

## 1. A1 解剖原版 npck（开工前）

```
python scripts/A1_分析原版.py vanilla_bgm_slugger_ingame_11_00.npck vanilla_bgm_slugger_ingame_14_00.npck
```

实测输出（节选）：

```
== vanilla_bgm_slugger_ingame_11_00.npck  size=122198303 entries=9
  e01 id=0x0166d03c unk=1 size= 20189990 off=0x01000368 tag=b'RIFF' fmt=65535 ch=4 sr=48000
  e02 id=0x0166d03d unk=1 size=  9509327 off=... tag=b'RIFF' fmt=65535 ch=2 sr=48000
  e03 ... ch=4
  ...
  e08 ... ch=2
  e09 ... ch=4
== vanilla_bgm_slugger_ingame_14_00.npck  size=174478926 entries=11
  e01..e11 全部 ch=4 sr=48000
```

判读要点：
- `entries` = 槽位数（11_00 是 9，14_00 是 11）。**替换 mod 的条目数必须与原版一致**。
- **ch 列逐槽记录**——这就是 §2 第 7 步投放 wem 的依据。11_00 的 e02/e08 是 2ch，其余 4ch；14_00 全 4ch。
- `fmt=65535 (0xFFFF)` = Wwise Vorbis；tag 必须 RIFF。
- 需要知道每槽原曲内容/时长时：`A2_导出wem.py` 导出 → `ww2ogg+revorb` 解成 ogg → ffprobe。

已知槽位映射（实测沉淀，直接可查）：

| npck | 怪物/场景 | 槽位 | 声道分布 |
|---|---|---|---|
| `bgm_slugger_ingame_11_00.npck` | 激昂金狮子（活动任务斗技场） | 9 | e02/e08 = 2ch，其余 4ch |
| `bgm_slugger_ingame_14_00.npck` | 煌黑龙 | 11 | 全部 4ch |

其他目标 npck：用 `chunk_extract.py` 按文件名从游戏 chunk 提取后，A1 现场量，别凭经验猜。

## 2. verify_npck 校验成品 npck（交付前，门禁）

```
python scripts/verify_npck.py out/bgm_slugger_ingame_14_00.npck vanilla_bgm_slugger_ingame_14_00.npck
```

实测输出（v2 成品，通过）：

```
entries: 11
  e01 id=0x... unk=1 size= 9097396 off=0x... ch=4 sr=48000 RIFF-OK idOK
  e02 ... RIFF-OK idOK
  ...（11 条全 RIFF-OK idOK，无 GAP!）
  e11 ... RIFF-OK idOK
media end == file size: True
RESULT: ALL OK
```

**验收判据（缺一即失败，回 §2 排查）**：
1. `entries` 与原版一致；
2. 每条 `idOK`（媒体 ID 与原版逐一相同）；
3. 每条 `RIFF-OK`；
4. 无 `GAP!`（媒体区连续）；
5. `media end == file size: True`；
6. 末行 `RESULT: ALL OK`。

对成品 npck 再跑一遍 `A1_分析原版.py`，**ch 列必须与原版逐槽一致**（这是"游戏内静音"最常见根因的最后一道闸）。

## 3. ww2ogg 回读（音频内容门禁）

```
tools/ww2ogg/ww2ogg.exe <某槽.wem> --pcb tools/ww2ogg/packed_codebooks_aoTuV_603.bin -o t.ogg
tools/ww2ogg/revorb.exe t.ogg t_rev.ogg
ffmpeg -i t_rev.ogg -f null -          # 全解码无报错
ffprobe t_rev.ogg                      # 声道/采样率/时长对得上
```

实测回读：48kHz / 2ch 与 4ch / 239.356s——容器里塞的确实是能解码的完整音频。
注意：ww2ogg 能解 ≠ 游戏里能响（第三方编码器产物反解正常但游戏内乱码，见 SKILL.md §5 坑 3/9），
它只证明"容器里的数据是完整可解码音频"，编码器合法性由"只用 WwiseConsole"这条规则保证。
