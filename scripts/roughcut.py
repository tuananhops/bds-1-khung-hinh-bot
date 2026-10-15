#!/usr/bin/env python3
"""Cắt thô talking-head theo skill master-rough-cut-talking-head (từ transcript có timestamp từng từ).
  python3 roughcut.py raw.MOV --words words.json -o rc.mov [--drop "23.8-25.5,27.6-32.9"] [--edl edl.json] [--size 1080x1920]
- Bỏ filler (ờ/ừm/à...) <0.6s, từ lặp <0.4s, các khoảng --drop (câu hỏng/false start do người duyệt chọn).
- In −0.10s / out +0.16s, snap về frame có RMS thấp, gộp gap ≤0.35s, afade 15ms; 30fps CFR.
words.json: {"words":[{"word","start","end"}]} hoặc [[w,s,e],...] trên audio GỐC.
"""
import argparse,json,subprocess,os,numpy as np
ap=argparse.ArgumentParser(description='Cắt thô theo transcript'); A=ap.add_argument
A('src'); A('--words',required=True); A('-o','--out',default='rc.mov'); A('--drop',default=''); A('--edl',default='edl.json'); A('--size',default='1080x1920')
A('--fill',default='ờ,ừm,à,uh,um,ơ,ừ'); g=ap.parse_args()
w=json.load(open(g.words)); w=w['words'] if isinstance(w,dict) else [dict(word=a,start=b,end=c) for a,b,c,*_ in w]
DROP=[tuple(map(float,x.split('-'))) for x in g.drop.split(',') if x.strip()]
FILL=set(g.fill.split(','))
x=np.frombuffer(subprocess.run(['ffmpeg','-v','error','-i',g.src,'-vn','-ac','1','-ar','16000','-f','f32le','-'],capture_output=True).stdout,np.float32); sr=16000
keep=[];rm=[];prev=None
for t in w:
    wd=t['word'].strip().lower().strip('.,?!')
    if any(a<=t['start']<b for a,b in DROP): continue
    if wd in FILL and t['end']-t['start']<0.6: rm.append((t['start'],wd)); continue
    if prev and wd==prev[0] and t['start']-prev[1]<0.4: rm.append((t['start'],'lặp '+wd)); continue
    keep.append(t); prev=(wd,t['end'])
segs=[];cur=[keep[0]['start'],keep[0]['end']]
for t in keep[1:]:
    if t['start']-cur[1]>0.35: segs.append(cur); cur=[t['start'],t['end']]
    else: cur[1]=t['end']
segs.append(cur)
rms=lambda c: np.sqrt(np.mean(x[max(0,int(c*sr)-160):int(c*sr)+160]**2)) if int(c*sr)<len(x) else 0
snap=lambda t,lo,hi: float(min(np.round(np.arange(t+lo,t+hi,1/30)*30)/30,key=rms))
E=[[max(0,snap(a-0.10,-0.04,0.04)),snap(b+0.16,-0.04,0.06)] for a,b in segs]
for i in range(1,len(E)):
    if E[i][0]<E[i-1][1]: E[i][0]=E[i-1][1]
M=[E[0]]
for a,b in E[1:]:
    if a-M[-1][1]<=0.35: M[-1][1]=b
    else: M.append([a,b])
M=[s for s in M if s[1]-s[0]>0.25]
json.dump({'source':os.path.basename(g.src),'segments':M,'drop':DROP,'removed_words':rm},open(g.edl,'w'),ensure_ascii=False,indent=1)
W,H=g.size.split('x'); fc=''
for i,(a,b) in enumerate(M):
    d=b-a; fc+=(f"[0:v]trim={a:.4f}:{b:.4f},setpts=PTS-STARTPTS,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30[v{i}];"
               f"[0:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.015,afade=t=out:st={max(0,d-0.015):.4f}:d=0.015[a{i}];")
fc+=''.join(f'[v{i}][a{i}]' for i in range(len(M)))+f'concat=n={len(M)}:v=1:a=1[v][a]'
fp=g.out+'.filter.txt'; open(fp,'w').write(fc)
subprocess.run(['ffmpeg','-y','-v','error','-i',g.src,'-filter_complex_script',fp,'-map','[v]','-map','[a]','-c:v','libx264','-crf','18','-preset','veryfast','-pix_fmt','yuv420p','-c:a','pcm_s16le',g.out],check=True)
print('gốc %.1fs → cắt %.1fs, %d đoạn, bỏ %d từ -> %s'%(len(x)/sr,sum(b-a for a,b in M),len(M),len(rm),g.out))
