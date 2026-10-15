#!/usr/bin/env python3
"""Kiểm tra SFX khớp hình bằng cross-correlation (mục tiêu ≤20 ms).
  python3 verify_sync.py <stem.wav|final.mp4> --events sfx_events.json --sfx-dir sfx/
"""
import argparse,json,subprocess,numpy as np,soundfile as sf
from scipy.signal import butter,sosfilt
ap=argparse.ArgumentParser(description='Đo độ lệch SFX'); ap.add_argument('src'); ap.add_argument('--events',default='sfx_events.json'); ap.add_argument('--sfx-dir',default='sfx')
g=ap.parse_args(); SR=48000
if g.src.lower().endswith(('.mp4','.mov','.mkv')):
    x=np.frombuffer(subprocess.run(['ffmpeg','-v','error','-i',g.src,'-ac','1','-ar','48000','-f','f32le','-'],capture_output=True).stdout,np.float32).astype(float)
else: x=sf.read(g.src)[0]; x=x.mean(1) if x.ndim>1 else x
hp=lambda y: sosfilt(butter(4,1500,'hp',fs=SR,output='sos'),y)
x=hp(x); T={k:hp(sf.read(f'{g.sfx_dir}/{k}.wav')[0]) for k in('ting','cash','whoosh')}; OFF={'ting':0,'cash':0,'whoosh':0.25}
err={}
for ts,k,_ in json.load(open(g.events)):
    tp=T[k]; a=max(0,int((ts-OFF[k]-0.1)*SR)); seg=x[a:a+len(tp)+int(.2*SR)]
    if len(seg)<len(tp): continue
    c=np.correlate(seg,tp,'valid'); err.setdefault(k,[]).append(((a+c.argmax())/SR+OFF[k]-ts)*1000)
ok=True
for k,v in err.items():
    v=np.array(v); n=(np.abs(v)<=20).sum(); ok&=n==len(v)
    print(k,len(v),'mean %.1fms max|%.1f|ms trong20ms=%d/%d'%(v.mean(),np.abs(v).max(),n,len(v)))
print('SYNC','PASS' if ok else 'FAIL')
