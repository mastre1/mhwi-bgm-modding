# 诊断 FLAC 文件损坏位置：统计帧同步字、零字节区间、文件尾部特征
# 用法: python A0_FLAC体检.py 源.flac
#   若判定有坏帧/截断 → 依次跑 A3(帧扫描) A4(帧CRC定位) A5(时间轴) → A6(分段修复解码)
import sys

p = sys.argv[1]
d = open(p, 'rb').read()
print('size', len(d))
print('magic', d[:4])
# fLaC 元数据块
pos = 4
while pos < len(d):
    hdr = d[pos]
    last = hdr & 0x80
    btype = hdr & 0x7F
    ln = int.from_bytes(d[pos + 1:pos + 4], 'big')
    print('meta block type=%d last=%d len=%d at %d' % (btype, bool(last), ln, pos))
    pos += 4 + ln
    if last:
        break
print('audio data starts at', pos)
audio = d[pos:]
# 统计同步字 0xFF 0xF8/0xF9
import re
locs = [m.start() for m in re.finditer(rb'\xff[\xf8\xf9]', audio)]
print('sync candidates', len(locs))
# 每 1MB 区间的同步字数量
buckets = {}
for o in locs:
    buckets[o // (1 << 20)] = buckets.get(o // (1 << 20), 0) + 1
print('sync per MB:', {k: buckets[k] for k in sorted(buckets)})
# 零字节大块
run = 0
maxrun = 0
maxpos = 0
cur = 0
for i in range(len(audio) - 1):
    if audio[i] == 0:
        cur += 1
        if cur > maxrun:
            maxrun, maxpos = cur, i - cur + 1
    else:
        cur = 0
print('longest zero run', maxrun, 'at audio offset', maxpos, '=> file offset', maxpos + len(d) - len(audio))
# 尾部 64 字节
print('tail hex', d[-64:].hex())
