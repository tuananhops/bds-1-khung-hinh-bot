#!/usr/bin/env python3
"""Tự tổng hợp nhạc deep house sáng (mặc định 122 BPM) không bản quyền, có click kick cho loa điện thoại.
  python3 make_music.py -o music.wav --dur 130 [--bpm 122 --seed 3]
"""
import argparse,numpy as np,soundfile as sf
ap=argparse.ArgumentParser(description='Nhạc deep house tổng hợp'); ap.add_argument('-o','--out',default='music.wav'); ap.add_argument('--dur',type=float,default=98); ap.add_argument('--bpm',type=float,default=122); ap.add_argument('--seed',type=int,default=3)
g=ap.parse_args(); sr=48000; b=60/g.bpm; D=g.dur; n=int(D*sr); out=np.zeros((n,2)); rng=np.random.default_rng(g.seed)
f=lambda m:440*2**((m-69)/12)
def add(s,t,gn=1,pan=0):
    i=int(t*sr); j=min(n,i+len(s))
    if i<n: out[i:j,0]+=s[:j-i]*gn*(1-pan); out[i:j,1]+=s[:j-i]*gn*(1+pan)
kt=np.arange(int(.25*sr))/sr; kick=np.sin(2*np.pi*(55*kt+90*(1-np.exp(-kt*35))/35))*np.exp(-kt*12)+0.3*rng.normal(0,1,len(kt))*np.exp(-kt*200)
ht=np.arange(int(.05*sr))/sr; hat=np.diff(np.r_[0,rng.normal(0,1,len(ht))])*np.exp(-ht*60)
ch=[[69,72,76,79],[65,69,72,76],[60,67,71,76],[67,71,74,77]]
pt=np.arange(int(.35*sr))/sr; bt=np.arange(int(b*.8*sr))/sr
for k in range(int(D/b)+1):
    t=k*b; add(kick,t,.8); add(hat,t+b/2,.35,.3); add(hat,t+b/4,.12,-.3); add(hat,t+3*b/4,.12,-.3); c=ch[(k//4)%4]
    for s in ((0,0.75,1.5) if k%2==0 else (0.5,)):
        add(sum(np.sin(2*np.pi*f(m)*pt)+.4*np.sin(2*np.pi*2*f(m)*pt) for m in c)*np.exp(-pt*7)/5,t+s*b,.55,.15 if s else -.15)
    add((np.sin(2*np.pi*f(c[0]-24)*bt)+.5*np.sin(2*np.pi*f(c[0]-12)*bt))*np.exp(-bt*4),t+b/2,.35)
t=np.arange(n)/sr; out*=(0.6+0.4*np.minimum(1,((t%b)/b)/0.35))[:,None]
out*=np.minimum(1,np.minimum(t/0.5,(D-t)/2))[:,None]; out/=np.abs(out).max()*1.1
sf.write(g.out,out.astype(np.float32),sr); print('nhạc %.1fs %g BPM -> %s'%(D,g.bpm,g.out))
