#!/usr/bin/env python3
"""Dò mặt (YuNet) 5 lần/giây → faces.json {t:[[x,y,w,h]]} theo toạ độ của video (1080x1920).
  python3 facemap.py edit_v.mp4 faces.json [--model vendor/video-toolkit/models/face_detection_yunet_2023mar.onnx] [--fps 5]
"""
import argparse,json,os,cv2
H=os.path.dirname(os.path.abspath(__file__))
ap=argparse.ArgumentParser(description='Bản đồ mặt cho chữ né mặt'); ap.add_argument('src'); ap.add_argument('out')
ap.add_argument('--model',default=os.path.join(H,'..','vendor','video-toolkit','models','face_detection_yunet_2023mar.onnx')); ap.add_argument('--fps',type=float,default=5)
g=ap.parse_args()
cap=cv2.VideoCapture(g.src); fps=cap.get(cv2.CAP_PROP_FPS) or 30; W=int(cap.get(3)); Hh=int(cap.get(4)); sw,shh=W//2,Hh//2
det=cv2.FaceDetectorYN.create(g.model,'',(sw,shh),0.6); step=max(1,int(round(fps/g.fps))); R={}; i=0
while cap.grab():
    if i%step==0:
        ok,f=cap.retrieve(); _,fs=det.detect(cv2.resize(f,(sw,shh)))
        R[round(i/fps,2)]=[[float(v*2) for v in x[:4]] for x in fs] if fs is not None else []
    i+=1
json.dump(R,open(g.out,'w')); print(len(R),'mẫu,',sum(1 for v in R.values() if v),'có mặt ->',g.out)
