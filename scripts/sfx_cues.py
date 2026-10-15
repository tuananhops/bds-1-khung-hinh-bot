#!/usr/bin/env python3
"""Bộ SFX chuẩn sau intro: CHỈ ting (chữ hiện) / cash (giá) / whoosh (chuyển cảnh), khớp frame.

  python3 sfx_cues.py --ass fx7.ass --plan plan.json --voice voice.wav -o sfx.wav \
      --events sfx_events.json --sfx-dir sfx/ [--cta 124.0] [--intro-end 3.3] [--fps 30]

- Sinh/ghi ting.wav, cash.wav, whoosh.wav vào --sfx-dir (transient ting/cash ở sample 0, whoosh ĐỈNH ở 0.25s).
- Sự kiện: mỗi dòng Dialogue lớp 2 màu vàng kim (&H0B86B8&) trong ASS → cash nếu chữ có TỶ/TRIỆU, còn lại ting;
  CTA (--cta) → ting; mỗi đoạn b-roll trong plan.json "BR" [[start,end,...]] → whoosh vào + ra.
- Ưu tiên cash > ting > whoosh, cách nhau ≥ --gap (0.4s), bỏ sự kiện < --intro-end.
- Mức: peak = voice p99.95 × (ting -4 dB, cash -3 dB, whoosh -5 dB). In độ lệch onset (mục tiêu ≤20 ms).
"""
import argparse,json,re,os,numpy as np,soundfile as sf
from scipy.signal import butter,sosfilt
ap=argparse.ArgumentParser(description='SFX ting/cash/whoosh khớp frame'); A=ap.add_argument
A('--ass',required=True); A('--plan',default=''); A('--voice',required=True); A('-o','--out',default='sfx.wav')
A('--events',default='sfx_events.json'); A('--sfx-dir',default='sfx'); A('--cta',type=float,default=None)
A('--intro-end',type=float,default=3.3); A('--fps',type=float,default=30); A('--gap',type=float,default=0.4)
A('--db',default='ting=-4,cash=-3,whoosh=-5',help='mức so với voice p99.95')
g=ap.parse_args()
SR=48000; rng=np.random.default_rng(3); K=g.sfx_dir; os.makedirs(K,exist_ok=True)
hp=lambda x,f=300: sosfilt(butter(4,f,'hp',fs=SR,output='sos'),x)
e=lambda n,d: np.exp(-np.arange(n)/SR/d); t=lambda s: np.arange(int(s*SR))/SR
tt=t(0.6); ting=sum(a*np.sin(2*np.pi*f*tt)*e(len(tt),d) for f,a,d in((2093,1,.22),(4186,.5,.12),(6279,.3,.07),(3136,.25,.15)))
ting*=np.minimum(1,np.arange(len(tt))/48); ting=hp(ting,800)
tc=t(0.8); n=len(tc); cash=np.zeros(n)
ka=rng.standard_normal(int(.02*SR))*e(int(.02*SR),.004); cash[:len(ka)]+=ka*1.2
o=int(.06*SR); ch=sum(a*np.sin(2*np.pi*f*tc[:n-o])*e(n-o,d) for f,a,d in((2637,1,.25),(3520,.8,.22),(5274,.4,.12)))
cash[o:]+=ch*np.minimum(1,np.arange(n-o)/48)
for k in range(6): i=int((.09+k*.035)*SR); cash[i:i+600]+=rng.standard_normal(600)*e(600,.003)*.4
cash=hp(cash,500)
tw=t(0.4); n=len(tw); envw=np.where(tw<.25,(tw/.25)**2.5,np.exp(-(tw-.25)/.04))
w=hp(sosfilt(butter(2,[900,6000],'bp',fs=SR,output='sos'),rng.standard_normal(n))*envw,400); WPK=0.25
for nm,x in(('ting',ting),('cash',cash),('whoosh',w)): sf.write(os.path.join(K,nm+'.wav'),(x/np.abs(x).max()*0.9).astype(np.float32),SR)
fr=lambda s: np.ceil(s*g.fps-1e-6)/g.fps
E=[]
for l in open(g.ass,encoding='utf-8'):
    if not l.startswith('Dialogue: 2,') or '&H0B86B8&' not in l: continue
    p=l.split(',',9); h,m,s=p[1].split(':'); t0=int(h)*3600+int(m)*60+float(s); tx=re.sub(r'\{.*?\}','',p[9]).strip()
    E.append((fr(t0),'cash' if re.search(r'TỶ|TRIỆU',tx.upper()) else 'ting',tx))
if g.cta is not None: E.append((fr(g.cta),'ting','CTA'))
if g.plan:
    for a,b,*_ in json.load(open(g.plan)).get('BR',[]): E+=[(fr(a),'whoosh','cut-in'),(fr(b),'whoosh','cut-out')]
pr={'cash':0,'ting':1,'whoosh':2}
E=sorted([x for x in E if x[0]>=g.intro_end],key=lambda x:(pr[x[1]],x[0])); keep=[]
for x in E:
    if all(abs(x[0]-y[0])>=g.gap for y in keep): keep.append(x)
keep.sort()
v,_=sf.read(g.voice); v=v.mean(1) if v.ndim>1 else v; vp=np.percentile(np.abs(v),99.95)
G={k:10**(float(d)/20) for k,d in (x.split('=') for x in g.db.split(','))}
S={'ting':ting,'cash':cash,'whoosh':w}; OFF={'ting':0,'cash':0,'whoosh':WPK}; out=np.zeros(len(v)+SR)
for t0,k,_ in keep:
    x=S[k]/np.abs(S[k]).max()*vp*G[k]; i=int(round((t0-OFF[k])*SR)); i0=max(0,i); out[i0:i+len(x)]+=x[i0-i:len(out)-i]
sf.write(g.out,out[:len(v)].astype(np.float32),SR)
json.dump([[float(a),b,c] for a,b,c in keep],open(g.events,'w'),ensure_ascii=False)
from collections import Counter; print(dict(Counter(k for _,k,_ in keep)),'voice p99.95 %.1f dBFS'%(20*np.log10(vp+1e-12)))
err=[]
for t0,k,_ in keep:
    a=max(0,int((t0-0.3)*SR)); seg=np.abs(out[a:a+int(.6*SR)])
    if not len(seg) or seg.max()==0: continue
    d=a+(np.convolve(seg,np.ones(240)/240,'same').argmax() if k=='whoosh' else np.argmax(seg>0.1*seg.max()))
    err.append((d/SR-t0)*1000)
if err: print('lệch onset ước lượng thô (chuẩn là verify_sync.py) ms: mean %.1f max|%.1f|'%(np.mean(err),np.max(np.abs(err))))
