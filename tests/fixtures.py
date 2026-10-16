"""Synthetic camera packets, containing no captured personal imagery."""
import numpy as np
from xreal_windows import REORDER

def synthetic_capture(pairs=45):
    frames=[]
    block=np.full((128,2400),55,np.uint8)
    block[0,:128]=0
    for counter in range(pairs):
        # Reverse the arrival order on alternating pairs.
        for camera in ([1,0] if counter%2 else [0,1]):
            frame=np.zeros((482,640),np.uint8)
            raw=frame[:480].reshape(128,2400)
            phase=(counter*3+camera)%128
            raw[REORDER[(phase+np.arange(128))%128]]=block
            meta=frame[480]
            meta[18:22]=np.frombuffer(counter.to_bytes(4,'little'),np.uint8)
            meta[51:57]=[128,2,224,1,128,2]
            meta[59]=camera
            frame[481]=92
            frames.append(frame)
    return np.array(frames)
