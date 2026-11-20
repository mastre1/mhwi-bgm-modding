# 第三方工具与素材

标准制作流程通过本机安装或使用者指定的路径调用工具。技能说明、Python 脚本和文本参考可以单独交付。现有本地二进制与音频样例保留供原作者使用，版本控制忽略这些文件。直接复制或压缩整个目录前也要排除它们。

| 文件 | 已核对的来源 | 再分发事项 |
| --- | --- | --- |
| `wwiseutil.exe` | 本地文件 SHA-256 与 hpxro7 的 1.1 发布件一致，GPL-3.0。 | 优先引导使用者从上游下载。自行分发时按许可证提供对应源码等材料。[发布](https://github.com/hpxro7/wwiseutil/releases/tag/1.1) · [许可](https://github.com/hpxro7/wwiseutil/blob/1.1/LICENSE) |
| `ww2ogg.exe`、`packed_codebooks_aoTuV_603.bin` | 本地文件与 hcs64 的 0.22 发布包一致，ww2ogg 许可为 BSD-3-Clause。 | 下载发布包并保留许可及版权声明。[发布](https://github.com/hcs64/ww2ogg/releases/tag/0.22) · [许可](https://github.com/hcs64/ww2ogg/blob/0.22/COPYING) |
| `revorb.exe` | 本机旧工具。未包含在 ww2ogg 0.22 上游发布中。 | 可选工具，来源和许可需单独核实。 |
| `oodle.dll`、`keyseq.key` | 自备的本机游戏归档解析组件。 | 当前无可核实的随 Skill 再分发授权。日常制作只需使用者提供原版 NPCK。 |
| `示例/wem样例/*.wem` | 本机旧参考。编码源为第三方歌曲。 | 分享或自动化验收用原创、合成或已授权音源。旧包、原版媒体和试听同样适用。 |
| Wwise Authoring、FFmpeg | 使用者按各工具的安装和许可条款获取。 | Skill 提供外部调用，不携带安装包。 |
