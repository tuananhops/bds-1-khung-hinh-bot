#!/usr/bin/env python3
"""Render bản giao 1 KHUNG EDITED full 1080x1920 (không ô RAW, không nền mờ, không khung bo góc) + vtk qc.
  python3 render_final.py --video edit_v.mp4 --audio mix.wav --ass fx7.ass --ass intro.ass -o "Tên dễ đọc - bản 1.mp4" \
      [--max-mb 92] [--qc] [--vtk vtk] [--fontsdir DIR]
Bitrate: vb = min(7000, max-mb*8*1000/dur - 300) kbps (KHÔNG dùng crf: crf 21 từng ra file quá 95MB).
Sau khi xuất: ảnh cover ở giây 4 và (nếu --qc) `vtk qc <out> --platform all --json <out>_qc.json`; FAIL → exit 2, không giao.
"""
import argparse,json,os,subprocess,sys
ap=argparse.ArgumentParser(description='Render 1 khung + QC'); A=ap.add_argument
A('--video',required=True); A('--audio',required=True); A('--ass',action='append',default=[]); A('-o','--out',required=True)
A('--max-mb',type=float,default=92); A('--qc',action='store_true'); A('--vtk',default='vtk'); A('--fontsdir',default=''); A('--preset',default='medium')
g=ap.parse_args()
dur=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',g.video],capture_output=True,text=True).stdout)
vb=int(min(7000,g.max_mb*8*1000/dur-300))
esc=lambda p: p.replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
vf=','.join(f"ass='{esc(a)}'"+(f":fontsdir='{esc(g.fontsdir)}'" if g.fontsdir else '') for a in g.ass)
vf=(vf+',' if vf else '')+'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p'
subprocess.run(['ffmpeg','-y','-v','error','-i',g.video,'-i',g.audio,'-map','0:v','-map','1:a','-shortest','-vf',vf,
  '-c:v','libx264','-preset',g.preset,'-b:v',f'{vb}k','-maxrate',f'{int(vb*1.2)}k','-bufsize',f'{vb*2}k',
  '-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-c:a','aac','-b:a','256k','-ar','48000','-movflags','+faststart',g.out],check=True)
base=os.path.splitext(g.out)[0]; mb=os.path.getsize(g.out)/1e6
subprocess.run(['ffmpeg','-v','error','-y','-ss',str(min(4,dur/2)),'-i',g.out,'-frames:v','1','-q:v','2',base+'_cover.jpg'])
print('xuất %s: %.1fs, %d kbps, %.1f MB'%(g.out,dur,vb,mb))
if mb>=95: print('LỖI: file ≥95MB'); sys.exit(2)
if g.qc:
    q=base+'_qc.json'; subprocess.run([g.vtk,'qc',g.out,'--platform','all','--json',q],stdout=subprocess.DEVNULL)
    r=json.load(open(q)); print('QC',r.get('verdict'),'fail:',r.get('fail'),'loudness:',r.get('loudness'))
    if str(r.get('verdict','')).upper().startswith('FAIL'): sys.exit(2)
