# 成品 wav（第 2 版"满响度"路线）：对 ffmpeg 已裁剪/限幅过的输入 wav 加首尾余弦淡化，16bit 输出。
# 用法: python A9_v2成品wav.py 工程目录 [--in 输入wav] [--out 输出wav] [--fade-in 0.15] [--fade-out 1.5]
#   典型分工：响度/裁剪交给 ffmpeg（loudnorm 定增益 + atrim 裁前奏 + alimiter 限幅，见 SKILL.md §3），
#   本脚本只负责安全的淡入淡出，避免循环回跳硬切。
import argparse
import os
import wave

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('workdir')
    ap.add_argument('--in', dest='inp', default=None, help='默认取 01_aud/ 下最新的 _try_*.wav')
    ap.add_argument('--out', default='v2_final_stereo.wav')
    ap.add_argument('--fade-in', type=float, default=0.15)
    ap.add_argument('--fade-out', type=float, default=1.5)
    args = ap.parse_args()

    p = args.inp
    if p is None:
        import glob
        cands = sorted(glob.glob(os.path.join(args.workdir, '01_aud', '_try_*.wav')))
        assert cands, '01_aud/ 下没有 _try_*.wav，请用 --in 指定输入'
        p = cands[-1]

    w = wave.open(p)
    n, ch = w.getnframes(), w.getnchannels()
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, ch).astype(np.float32) / 32768.0
    w.close()

    fi, fo = int(args.fade_in * sr), int(args.fade_out * sr)
    x[:fi] *= (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fi))).reshape(-1, 1)
    x[-fo:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo))).reshape(-1, 1)

    peak = float(np.abs(x).max())
    rms = float(np.sqrt((x ** 2).mean()))
    print('ch=%d sr=%d 时长 %.3fs peak %.2f dBFS rms %.2f dBFS'
          % (ch, sr, n / sr, 20 * np.log10(peak), 20 * np.log10(rms)))
    assert peak < 1.0, '削波了：回上游调限幅'

    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype('<i2')
    out = os.path.join(args.workdir, '01_aud', args.out)
    with wave.open(out, 'wb') as o:
        o.setnchannels(ch)
        o.setsampwidth(2)
        o.setframerate(sr)
        o.writeframes(pcm.tobytes())
    print('wrote', out, os.path.getsize(out))


if __name__ == '__main__':
    main()
