#!/usr/bin/env python3
"""Cứu vùng chói (KHÔNG phải grade màu): nén luma > knee bằng soft-knee về trần, trả bão hoà nhẹ vùng đó.
  python3 highlight_fix.py in.mp4 out.mp4 [--knee 0.72 --ceil 0.88 --sat 0.25 --crf 14]
In % pixel >235 trước/sau.
"""
import argparse,subprocess,cv2,numpy as np
ap=argparse.ArgumentParser(description='Cứu chói'); A=ap.add_argument; A('src'); A('dst')
A('--knee',type=float,default=0.72); A('--ceil',type=float,default=0.88); A('--sat',type=float,default=0.25); A('--crf',default='14')
g=ap.parse_args()
cap=cv2.VideoCapture(g.src); fps=cap.get(cv2.CAP_PROP_FPS) or 30; W=int(cap.get(3)); H=int(cap.get(4))
x=np.arange(256)/255.; k=g.knee
lut=(np.where(x<k,x,k+(g.ceil-k)*(1-np.exp(-(x-k)/(1-k)*2.0))/(1-np.exp(-2.0)))*255).clip(0,255).astype(np.uint8)
ff=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-i',g.src,'-map','0:v','-map','1:a?','-c:a','copy','-c:v','libx264','-preset','veryfast','-crf',g.crf,'-pix_fmt','yuv420p',g.dst],stdin=subprocess.PIPE)
c0=[];c1=[];i=0
while True:
    ok,f=cap.read()
    if not ok: break
    ycc=cv2.cvtColor(f,cv2.COLOR_BGR2YCrCb); Y=ycc[...,0]
    if i%30==0: c0.append((Y>235).mean())
    m=np.clip((Y.astype(np.float32)-170)/60,0,1)
    if m.max()>0:
        c=ycc[...,1:].astype(np.float32)-128; c*=1+g.sat*m[...,None]; ycc[...,0]=lut[Y]; ycc[...,1:]=np.clip(c+128,0,255).astype(np.uint8)
        f=cv2.cvtColor(ycc,cv2.COLOR_YCrCb2BGR)
    if i%30==0: c1.append((cv2.cvtColor(f,cv2.COLOR_BGR2GRAY)>235).mean())
    ff.stdin.write(f.tobytes()); i+=1
ff.stdin.close(); ff.wait()
print(f"pixel>235: trước {100*np.mean(c0):.2f}% (max {100*max(c0):.1f}%) | sau {100*np.mean(c1):.2f}% (max {100*max(c1):.1f}%)")
