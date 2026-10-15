#!/usr/bin/env python3
"""Sinh phụ đề/chữ nghệ thuật VÀNG KIM (style v7 đã duyệt) dạng ASS 1080x1920, đồng bộ lời nói, né mặt.

  python3 gold_text.py --words words.json --faces faces.json --config text_cfg.json -o fx7.ass [--pops pops.txt]

words.json : [[word,start,end],...]  hoặc {"words":[{"word","start","end"}]} (whisper trên audio ĐÃ CẮT)
faces.json : {"t": [[x,y,w,h],...]} toạ độ 1080x1920 (facemap.py)
config     : xem examples/van-cao-7948-ban-4/text_cfg.json. Khoá:
  dur, cta_time, cta_text, start_after (bỏ chữ trong màn intro), fix {sai:đúng, "":xoá},
  merge [{"match":["4",",2","tỷ"],"extra":1,"text":"4,28 tỷ"}]  (ghép số/giá; extra = số token sau đó nuốt thêm),
  keywords [...] (1–4 từ, IN HOA vàng kim Bungee), emo [...] (Pacifico, viết hoa đầu + "!"),
  strike ["4,28"] (giá cũ có gạch ngang), kw_font (Bungee; dùng "Paytone One" nếu từ có À/Ằ... bị thiếu glyph)
In ra: số cụm, số từ khoá, danh sách cụm bị drop vì không có chỗ né mặt.
"""
import argparse, json
ap=argparse.ArgumentParser(description=__doc__.split('\n')[1]); A=ap.add_argument
A('--words',required=True); A('--faces',required=True); A('--config',required=True); A('-o','--out',default='fx7.ass'); A('--pops',default='')
g=ap.parse_args(); C=json.load(open(g.config))
W=json.load(open(g.words))
if isinstance(W,dict): W=[[x['word'].strip(),x['start'],x['end']] for x in W['words']]
F={float(k):v for k,v in json.load(open(g.faces)).items()}
DUR=float(C['dur']); CTA=float(C.get('cta_time',DUR-3)); CTA_TXT=C.get('cta_text','Inbox ngay để xem nhà ->'); ST=float(C.get('start_after',0))
fix=C.get('fix',{}); MERGE=C.get('merge',[]); KW=C.get('keywords',[]); EMO={x.lower() for x in C.get('emo',[])}
STRIKE=C.get('strike',[]); KWF=C.get('kw_font','Bungee')
T=[];i=0
while i<len(W):
    w,s,e=W[i][:3]; done=False
    for m in MERGE:
        L=len(m['match']); ex=m.get('extra',0)
        if i+L+ex<=len(W) and [x[0] for x in W[i:i+L]]==m['match']:
            T.append([m['text'],s,W[i+L+ex-1][2]]); i+=L+ex; done=True; break
    if done: continue
    if w=='%' and T: T[-1][0]+='%'; T[-1][2]=e; i+=1; continue
    x=fix.get(w,w)
    if x: T.append([x,s,e])
    i+=1
T=[t for t in T if t[1]>=ST]
low=[t[0].lower() for t in T]; mark=[None]*len(T)
for k in KW:
    for j in range(len(T)):
        for m in (1,2,3,4):
            if ' '.join(low[j:j+m])==k.lower() and all(x is None for x in mark[j:j+m]):
                for q in range(j,j+m): mark[q]=j
P=[];i=0
while i<len(T):
    if mark[i] is not None:
        j=i
        while j<len(T) and mark[j]==mark[i]: j+=1
        P.append(dict(k=1,w=T[i:j])); i=j; continue
    gg=[T[i]]; i+=1
    while i<len(T) and len(gg)<4 and mark[i] is None and T[i][1]-gg[-1][2]<0.35: gg.append(T[i]); i+=1
    P.append(dict(k=0,w=gg))
for n,p in enumerate(P):
    p['s']=p['w'][0][1]; nx=P[n+1]['w'][0][1] if n+1<len(P) else DUR
    p['e']=nx if nx-p['w'][-1][2]<0.7 else p['w'][-1][2]+0.4
    p['t']=' '.join(x[0] for x in p['w'])
def faces(a,b):
    r=[f for t,v in F.items() if a-0.2<=t<=b+0.2 for f in v if f[2]>=120]
    if not r: return None
    return min(f[1] for f in r), max(f[1]+f[3] for f in r)
def ts(t): return f'{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}'
ev=[]; WH='&HFFFFFF&'; GOLD='GOLD'
SC={'Bungee':2.4,'Pacifico':1.6,'Paytone One':1.6}
def txt(a,b,x,y,sz,col,s,an=5,fn='Paytone One'):
    sz0=sz; extra=f'\\fn{fn}'; sz=int(sz*SC.get(fn,1.6)); sh=max(6,int(sz*0.07))
    pop=r'\fscx70\fscy70\t(0,90,\fscx110\fscy110)\t(90,170,\fscx96\fscy96)\t(170,230,\fscx100\fscy100)'
    ev.append(f'Dialogue: 1,{ts(a)},{ts(b)},T,,0,0,0,,{{\\an{an}\\pos({x},{y+sh})\\fs{sz}\\1c&H000000&\\1a&H50&\\blur{int(sz*0.12)}{pop}{extra}}}{s}')
    if col==GOLD:   # 3 lớp: đáy #B8860B, giữa #D4A017, đỉnh #FFE08A, viền #8B6508 (ASS màu BGR)
        H=sz0*0.7
        ev.append(f'Dialogue: 2,{ts(a)},{ts(b)},T,,0,0,0,,{{\\an{an}\\pos({x},{y})\\fs{sz}\\1c&H0B86B8&\\bord3\\3c&H08658B&{pop}{extra}}}{s}')
        ev.append(f'Dialogue: 3,{ts(a)},{ts(b)},T,,0,0,0,,{{\\an{an}\\pos({x},{y})\\fs{sz}\\1c&H17A0D4&\\clip(0,0,1080,{int(y+0.15*H)}){pop}{extra}}}{s}')
        ev.append(f'Dialogue: 4,{ts(a)},{ts(b)},T,,0,0,0,,{{\\an{an}\\pos({x},{y})\\fs{sz}\\1c&H8AE0FF&\\clip(0,0,1080,{int(y-0.2*H)}){pop}{extra}}}{s}')
    else:
        ev.append(f'Dialogue: 2,{ts(a)},{ts(b)},T,,0,0,0,,{{\\an{an}\\pos({x},{y})\\fs{sz}\\1c{col}{pop}{extra}}}{s}')
L=[]
for p in P:
    if p['s']>=CTA: break
    e=min(p['e'],CTA); emo=p['k'] and p['t'].lower() in EMO
    s=(p['t'][0].upper()+p['t'][1:]+'!' if emo else p['t'].upper()) if p['k'] else p['t']
    n=len(s); fb=faces(p['s'],e)
    if p['k']:
        wf=0.5 if emo else 0.8; sz=int(min(210 if emo else 180,880/(n*wf))); h=sz
        if not fb or fb[0]>960+h/2+20 or fb[1]<960-h/2-20: y=960
        else:
            top,bot=fb; up=top-40; dn=1880-bot
            if dn>=h+40: y=bot+30+h/2
            elif up-120>=h: y=top-30-h/2
            else:
                sz=int(sz*max(dn,up-120)/(h+40)); y=bot+20+sz/2 if dn>up-120 else top-20-sz/2
                if sz<80: L.append(('drop',p['t'],round(p['s'],2))); continue
        txt(p['s'],e,540,int(y),sz,GOLD,s,fn='Pacifico' if emo else KWF)
        if any(s.startswith(x) for x in STRIKE):
            w=int(n*sz*0.72); d=f'm 0 0 l {w} 0 l {w} {int(sz*0.1)} l 0 {int(sz*0.1)}'
            ev.append(f'Dialogue: 5,{ts(p["s"]+0.45)},{ts(e)},T,,0,0,0,,{{\\an4\\pos({540-w//2},{int(y)})\\1c&H17A0D4&\\bord2\\3c&H08658B&\\shad0\\fscx0\\t(0,250,\\fscx100)\\p1}}{d}')
    else:
        sz=70; y=1560
        if fb:
            top,bot=fb; y=bot+40+sz/2 if bot+40+sz<1880 else top-30-sz/2
            if top-30-sz<120 and bot+40+sz>=1880: L.append(('drop',p['t'],round(p['s'],2))); continue
        txt(p['s'],e,540,int(y),sz,WH,s)
bw,bh,r=820,150,40; d=f'm {r} 0 l {bw-r} 0 b {bw} 0 {bw} 0 {bw} {r} l {bw} {bh-r} b {bw} {bh} {bw} {bh} {bw-r} {bh} l {r} {bh} b 0 {bh} 0 {bh} 0 {bh-r} l 0 {r} b 0 0 0 0 {r} 0'
fb=faces(CTA,DUR); yb=1700
if fb and fb[1]>yb-bh/2-20: L.append(('cta-face-overlap',fb))
mv=lambda y0,y1,l: f'\\move(540,{y0},540,{y1},0,{l})'
ev.append(f'Dialogue: 6,{ts(CTA)},{ts(DUR)},T,,0,0,0,,{{\\an5{mv(2050,yb+10,350)}\\1c&H000000&\\1a&H60&\\blur14\\p1}}{d}')
ev.append(f'Dialogue: 7,{ts(CTA)},{ts(DUR)},T,,0,0,0,,{{\\an5{mv(2040,yb,350)}\\1c&HFFFFFF&\\p1}}{d}')
ev.append(f'Dialogue: 8,{ts(CTA)},{ts(DUR)},T,,0,0,0,,{{\\an5{mv(2040,yb,350)}\\fs96\\fnPaytone One\\1c&H17A0D4&\\bord3\\3c&H08658B&}}{CTA_TXT}')
H='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T,Be Vietnam Pro Black,70,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
open(g.out,'w').write(H+'\n'.join(ev)+'\n')
if g.pops: open(g.pops,'w').write('\n'.join(str(round(p['s'],2)) for p in P if p['s']<CTA and p['k'])+'\n'+str(CTA)+'\n')
print(len(P),'cụm',sum(p['k'] for p in P),'từ khoá ->',g.out,'| drop:',L)
