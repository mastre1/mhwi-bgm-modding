# 成品 wav（第 1 版响度路线）：对 A6 的 _joined.npy 施加增益 + 首尾余弦淡化，输出 16bit stereo wav。
# 用法: python A7_成品wav.py 工程目录 [--gain-db -10.5] [--fade-in 0.35] [--fade-out 1.2] [--out 文件名]
#   增益值来自 loudnorm 测量（SKILL.md §3）：对齐原版 BGM 约 -10.5dB；对齐"用户旧 mod"的更响路线用 A9。
import argparse
import os
import wave

import numpy as np

SR = 48000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('workdir', help='本次工程目录（含 01_aud/_joined.npy）')
    ap.add_argument('--gain-db', type=float, default=-10.5)
    ap.add_argument('--fade-in', type=float, default=0.35)
    ap.add_argument('--fade-out', type=float, default=1.2)
    ap.add_argument('--out', default='song_final_stereo.wav')
    args = ap.parse_args()

    x = np.load(os.path.join(args.workdir, '01_aud', '_joined.npy')).astype(np.float32) / 32768.0
    g = 10 ** (args.gain_db / 20.0)
    x = x * g

    n = len(x)
    fi = int(args.fade_in * SR)
    fo = int(args.fade_out * SR)
    x[:fi] *= (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fi))).reshape(-1, 1)
    x[-fo:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo))).reshape(-1, 1)

    peak = float(np.abs(x).max())
    print('gain %.2f dB -> peak %.4f (%.2f dBFS), rms %.2f dBFS, 时长 %.3fs'
          % (args.gain_db, peak, 20 * np.log10(peak), 20 * np.log10(np.sqrt((x ** 2).mean())), n / SR))
    assert peak < 1.0, '削波了：减小增益或加限幅'

    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype('<i2')
    out = os.path.join(args.workdir, '01_aud', args.out)
    with wave.open(out, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print('wrote', out, os.path.getsize(out))


if __name__ == '__main__':
    main()
