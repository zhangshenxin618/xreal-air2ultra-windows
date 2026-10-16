"""Interactive physical-camera identification and eye-output test."""
import argparse
import json
from pathlib import Path
import time
import cv2
import numpy as np
from viewer_display import monitors, load_preferences, save_preferences

ROOT=Path(__file__).resolve().parent

def identify(open_values, left_covered, right_covered):
    baseline=np.asarray(open_values,dtype=float)
    left=np.asarray(left_covered,dtype=float)
    right=np.asarray(right_covered,dtype=float)
    if any(v.shape!=(2,) for v in [baseline,left,right]) or not np.all(np.isfinite([baseline,left,right])):
        raise ValueError('亮度数据不完整，请重试。')
    if np.any(baseline<8):
        raise ValueError('无遮挡画面太暗，请到明亮环境重试。')
    ratios=np.vstack((left/baseline,right/baseline))
    candidates=np.argmin(ratios,axis=1)
    if candidates[0]==candidates[1]:
        raise ValueError('两次遮挡指向同一组，无法确认左右。原设置保持不变。')
    for row,group in zip(ratios,candidates):
        if row[group]>.55 or row[1-group]<.55 or row[group]>.5*row[1-group]:
            raise ValueError('遮挡变化不够明确，请遮住单个摄像头而不是显示镜片。原设置保持不变。')
    return int(candidates[0]),ratios.tolist()

def measure():
    from xreal_windows import NativeCamera
    camera=NativeCamera()
    values=[[],[]]
    started=time.monotonic()
    try:
        count=0
        while min(map(len,values))<40:
            if time.monotonic()-started>12:
                raise RuntimeError('未采到足够两路数据，请关闭其它预览并确认眼镜仍连接。')
            ok,frame=camera.read()
            if not ok:raise RuntimeError('眼镜被其它程序占用或读取失败，请关闭旧预览。')
            count+=1
            if count<30:continue
            if frame.shape!=(482,640):continue
            meta=frame[480]
            if tuple(meta[51:57])!=(128,2,224,1,128,2) or int(meta[59]) not in (0,1):continue
            values[int(meta[59])].append(float(frame[:480].mean()))
    finally:
        camera.release()
    return [float(np.median(group)) for group in values]

def calibrate():
    print('关闭所有摄像头预览。左右均按你戴上眼镜时的方向判断。')
    print('把眼镜朝向明亮、稳定的场景，操作时保持朝向不变；请勿遮住两个镜头。')
    input('第一步：两个摄像头都不遮挡，准备好后按回车。')
    baseline=measure()
    print('无遮挡亮度：',baseline)
    input('第二步：只遮住你佩戴时左侧的外向摄像头，保持遮挡，按回车。')
    left=measure()
    print('左侧遮挡亮度：',left)
    input('第三步：放开左侧，只遮住佩戴时右侧的外向摄像头，保持遮挡，按回车。')
    right=measure()
    group,ratios=identify(baseline,left,right)
    prefs=load_preferences(ROOT/'view-settings.json')
    save_preferences(ROOT/'view-settings.json',prefs['rotations'],prefs['mirrors'],group==1)
    evidence=dict(left_group=group,right_group=1-group,baseline=baseline,
                  left_covered=left,right_covered=right,ratios=ratios,
                  method='user-labelled two-sided occlusion',time=time.time())
    (ROOT/'camera-mapping.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(f'确认：物理左镜头=分组 {group}，右镜头=分组 {1-group}。已保存左右顺序。')
    print('放开镜头，重新运行 start-stereo.cmd 查看结果。这一步不做几何标定。')

def test_pattern(width,height):
    image=np.zeros((height,width,3),np.uint8)
    half=width//2
    for i,label in enumerate(['LEFT / L','RIGHT / R']):
        x0=i*half
        cv2.rectangle(image,(x0+20,20),(x0+half-20,height-20),(120,120,120),3)
        cv2.putText(image,label,(x0+half//4,height//2),cv2.FONT_HERSHEY_SIMPLEX,2,(255,255,255),4)
        cv2.drawMarker(image,(x0+half//2,height//2+120),(0,255,0),cv2.MARKER_CROSS,100,3)
        cv2.putText(image,'TOP',(x0+half//2-60,100),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    return image

def eye_test():
    displays=monitors()
    for i,m in enumerate(displays):print(f"{i}: {m['name']} {m['width']}x{m['height']}")
    entry=input('输入眼镜屏幕编号，q 取消：').strip()
    if entry.lower()=='q':return
    index=int(entry)
    if not 0<=index<len(displays):raise ValueError('屏幕编号无效。')
    monitor=displays[index]
    if monitor['width']/monitor['height']<3:
        raise ValueError('眼镜仍为普通 2D 输出。两眼分别显示的测试需先启用完整 SBS 模式；没有修改显示设置。')
    image=test_pattern(monitor['width'],monitor['height'])
    print('戴上眼镜，分别闭一只眼：左眼应只看到 LEFT，右眼应只看到 RIGHT。')
    print('两眼都能看到两种文字则未正确进入 SBS；此工具不会自动判定成功。按 q 或 Esc 结束。')
    name='Eye output test - q:quit'
    try:
        cv2.namedWindow(name,cv2.WINDOW_NORMAL)
        cv2.moveWindow(name,monitor['x']+10,monitor['y']+10)
        cv2.imshow(name,image)
        cv2.waitKey(1)
        cv2.setWindowProperty(name,cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)
        from xreal_windows import read_key
        while cv2.getWindowProperty(name,cv2.WND_PROP_VISIBLE)>=1:
            if read_key() in [ord('q'),27]:break
    finally:cv2.destroyAllWindows()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eyes',action='store_true')
    args=parser.parse_args()
    try:
        eye_test() if args.eyes else calibrate()
    except (ValueError,RuntimeError,OSError,cv2.error) as error:
        print(f'未完成：{error}')
        raise SystemExit(1)
