#!/usr/bin/env python3
"""Mix âm thanh cuối: giọng (đã giảm ồn) + nhạc duck sidechain + SFX ting/cash/whoosh + stem intro to.
  python3 mix_audio.py --voice voice.wav --music music.wav [--sfx sfx.wav] [--intro intro_sfx.wav] -o mix.wav \
      [--music-lufs -26] [--target -12.6]
Giảm ồn giọng trước đó (bắt buộc):  vtk clean rc48.wav -o vc1.wav --denoise rnn
   && ffmpeg -i vc1.wav -af "afftdn=nr=12:nf=-40,highpass=f=80" voice.wav    (hoặc: --denoise để script tự chạy afftdn+HPF)
Chuỗi: music loudnorm I=-26 → sidechaincompress (thr0.06 ratio2 att40 rel400); amix normalize=0 → loudnorm I=-12.6 TP-2 → alimiter.
Kết quả sau render ≈ -14 LUFS, TP ≤ -1 (kiểm bằng vtk qc).
"""
import argparse,subprocess
ap=argparse.ArgumentParser(description='Mix giọng+nhạc+SFX'); A=ap.add_argument
A('--voice',required=True); A('--music',required=True); A('--sfx',default=''); A('--intro',default=''); A('-o','--out',default='mix.wav')
A('--music-lufs',type=float,default=-26); A('--target',type=float,default=-12.6); A('--denoise',action='store_true'); A('--final-lufs',type=float,default=-14,help='pass 2: đo rồi bù gain về mức này (0 = tắt)')
g=ap.parse_args()
inp=['-i',g.voice,'-stream_loop','-1','-i',g.music]; idx=2; ex=[]
vf='[0:a]'+('afftdn=nr=12:nf=-40,highpass=f=80,' if g.denoise else '')+'aformat=channel_layouts=mono,pan=stereo|c0=c0|c1=c0,asplit=2[v][sc];'
fc=vf+f'[1:a]aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I={g.music_lufs}:TP=-6:LRA=7[m];[m][sc]sidechaincompress=threshold=0.06:ratio=2:attack=40:release=400[md];'
for p in (g.sfx,g.intro):
    if p: inp+=['-i',p]; fc+=f'[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo[s{idx}];'; ex.append(f'[s{idx}]'); idx+=1
n=2+len(ex)
fc+='[v][md]'+''.join(ex)+f'amix=inputs={n}:normalize=0:duration=first,loudnorm=I={g.target}:TP=-2:LRA=11,aresample=192000,alimiter=limit=0.75:level=false,aresample=48000[a]'
subprocess.run(['ffmpeg','-y','-v','error',*inp,'-filter_complex',fc,'-map','[a]','-ar','48000',g.out],check=True)
import json,os,re
def meas(p):
    r=subprocess.run(['ffmpeg','-v','info','-i',p,'-af','loudnorm=print_format=json','-f','null','-'],capture_output=True,text=True).stderr
    return json.loads(re.findall(r'\{[^{}]*\}',r)[-1])
if g.final_lufs:
    m=meas(g.out); gain=g.final_lufs-float(m['input_i']); tmp=g.out+'.tmp.wav'
    subprocess.run(['ffmpeg','-y','-v','error','-i',g.out,'-af',f'volume={gain:.2f}dB,aresample=192000,alimiter=limit=0.66:level=false,aresample=48000',tmp],check=True)
    os.replace(tmp,g.out); m2=meas(g.out); print('pass2: %.1f → %s LUFS, TP %s'%(float(m['input_i']),m2['input_i'],m2['input_tp']))
print('mix ->',g.out)
