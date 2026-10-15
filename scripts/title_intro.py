#!/usr/bin/env python3
"""Title intro generator (fb_reel style): giant price word zooms from huge -> small tilted starburst badge,
then a title stack types on word by word at the top (line1 red/white bold w/ dark outline, line2 white).
Outputs an ASS overlay (1080x1920) + an SFX cue file (t kind gain) for mixing.

Usage:
  python3 title_intro.py -o intro.ass --sfx intro_sfx.txt \
     --line1 "NHÀ ĐẸP VĂN CAO" --line2 "73m² x 4 PN" --badge "3,98 TỶ" \
     [--top 300] [--dur 3.2] [--red "NHÀ ĐẸP"]   # words in --red are red, others white
  Burn:  ffmpeg -i edit.mp4 -vf "ass=subs.ass,ass=intro.ass" ...
  Mix SFX: kinds = slam (whoosh+hit at badge land), pop (per word). Gains are linear.
Keep --top so the stack ends above the speaker's head (check faces.json: top y of face - 60).
Fonts: Paytone One (Bungee lacks Vietnamese À/Ằ...), Paytone One (line2/badge). No black/fade frames at t=0 (qc).
"""
import argparse, math
a=argparse.ArgumentParser(description='Màn tiêu đề 3s kiểu FB reel: huy hiệu giá nổ + tiêu đề gõ từng chữ + stem SFX mở đầu to'); A=a.add_argument
A('-o',default='intro.ass'); A('--sfx',default='intro_sfx.txt'); A('--line1',required=True); A('--line2',required=True)
A('--badge',required=True); A('--top',type=int,default=300); A('--dur',type=float,default=3.2); A('--red',default='')
A('--bx',type=int,default=250); A('--by',type=int,default=0)
A('--stem',default='',help='đường dẫn wav stem SFX mở đầu (mặc định = <sfx>.wav)'); A('--no-stem',action='store_true')
g=a.parse_args()
ts=lambda t:f'{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}'
ms=lambda t:int(t*1000)
ev=[];sfx=[]; D=g.dur; T=g.top; OUT=0.18
fade=f'\\fad(0,{ms(OUT)})'
def dl(layer,a,b,txt): ev.append(f'Dialogue: {layer},{ts(a)},{ts(b)},T,,0,0,0,,{txt}')
# --- badge: fly-in from huge (scale 900%) to badge in 0.25s, small overshoot
by=g.by or T+330; bx=g.bx; LAND=0.25
star=[]; n=14
for i in range(2*n):
    r=200 if i%2==0 else 150; an=math.pi*i/n
    star.append((int(r*math.cos(an)),int(r*0.62*math.sin(an))))
path='m '+' l '.join(f'{x} {y}' for x,y in star)
zoom=f'\\fscx900\\fscy900\\t(0,{ms(LAND)},\\fscx92\\fscy92)\\t({ms(LAND)},{ms(LAND+0.08)},\\fscx108\\fscy108)\\t({ms(LAND+0.08)},{ms(LAND+0.16)},\\fscx100\\fscy100)'
dl(10,0,D,f'{{\\an7\\pos({bx},{by})\\frz8\\1c&H0000E6&\\bord6\\3c&H00D7FF&\\shad0{zoom}{fade}\\p1}}{path}')
dl(11,0,D,f'{{\\an5\\pos({bx},{by})\\frz8\\fnPaytone One\\fs96\\1c&H00E6FF&\\bord5\\3c&H101010&\\shad3\\4c&H000000&{zoom}{fade}}}{g.badge}')
sfx.append((max(0,LAND-0.22),'whoosh',0.45)); sfx.append((LAND,'hit',0.55))
# --- line1 / line2 word by word
red=set(g.red.upper().split())
def typeon(words,y,t0,step,style):
    acc=[]; t=t0
    for i,w in enumerate(words):
        acc.append(w)
        nxt=t0+step*(i+1)
        b=nxt if i<len(words)-1 else D
        s=' '.join(style(x) for x in acc)
        dl(20,t,b,f'{{\\an8\\pos(540,{y})\\bord6\\3c&H101010&\\shad4\\4c&H000000&\\4a&H60&\\fscx100\\fscy100'+(fade if b>=D else '')+f'}}{s}')
        sfx.append((t,'pop',0.30)); t=nxt
    return t
c1=lambda w: '{\\fnPaytone One\\fs118\\1c'+('&H2020E8&' if w.upper() in red else '&HFFFFFF&')+'}'+w
c2=lambda w: '{\\fnPaytone One\\fs120\\1c&HFFFFFF&}'+w
w1=g.line1.split(); w2=g.line2.split()
t=typeon(w1,T,0.30,0.16,c1)
typeon(w2,T+125,t,0.14,c2)
H='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T,Bungee,74,&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,0,0,0,0,100,100,0,0,1,6,3,8,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
open(g.o,'w').write(H+'\n'.join(ev)+'\n')
open(g.sfx,'w').write('\n'.join(f'{t:.3f} {k} {v}' for t,k,v in sfx)+'\n')
print(len(ev),'events',len(sfx),'sfx ->',g.o,g.sfx)

# ---------- loud opener SFX stem (default ON; needs numpy+soundfile) ----------
# Matches fb_reel ref: 0-0.5s loud bright transient (46% energy >3kHz) + ~110Hz body, RMS ~-11dBFS.
# Writes <sfx>.wav = 48k stereo stem: whoosh-in -> TING chime + BOOM impact at badge land, pops per word.
# Gains are dBFS peaks: opener -1 dBFS peak, pops -3 dBFS peak (mix voice at ~-3 dBFS peak so opener >= voice).
try:
    if g.no_stem: raise ImportError
    import numpy as np, soundfile as sf
    SR=48000; L=int((D+1.0)*SR); st=np.zeros(L); rng=np.random.default_rng(7)
    def env(n,dec): return np.exp(-np.arange(n)/SR/dec)
    def add(x,t,peak_db):
        x=x/np.abs(x).max()*10**(peak_db/20); i=int(t*SR); st[i:i+len(x)]+=x[:L-i]
    n=int(0.28*SR); w=rng.standard_normal(n); w=np.convolve(w,np.ones(6)/6,'same')*np.linspace(0,1,n)**2
    add(w,max(0,LAND-0.28),-6)                                   # whoosh in
    n=int(1.1*SR); t=np.arange(n)/SR
    ting=sum(a*np.sin(2*np.pi*f*t)*env(n,d) for f,a,d in((1568,1,.45),(3136,.6,.3),(4704,.35,.2),(6272,.2,.12)))
    add(ting,LAND,-2)
    n=int(0.8*SR); t=np.arange(n)/SR; ph=2*np.pi*np.cumsum(45+90*np.exp(-t/0.08))/SR
    boom=np.sin(ph)*env(n,0.25)+0.5*rng.standard_normal(n)*env(n,0.012)
    add(np.tanh(boom*2.5),LAND,-1)
    n=int(0.09*SR); t=np.arange(n)/SR; pop=np.sin(2*np.pi*(900+1400*np.exp(-t/0.01))*t)*env(n,0.025)
    for tt,k,gn in sfx:
        if k=='pop': add(pop,tt,-3)
    st=np.clip(st,-0.99,0.99); STEM=g.stem or g.sfx.rsplit('.',1)[0]+'.wav'; sf.write(STEM,np.stack([st,st],1).astype(np.float32),SR)
    print('opener stem ->',STEM)
except ImportError: print('no stem (numpy/soundfile missing or --no-stem): use cue file')
