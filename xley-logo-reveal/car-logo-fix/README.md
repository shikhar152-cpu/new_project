# Car door logo fix

Replaces the wrong ".XLEY" text on the car door in the last shot of the brand
clip (frames 254-344, 10.6s to the end) with the real Xley logo.

1. Extract the shot's frames with exact rounding into `$WORK/oldf/f254.png ... f344.png`:
   `ffmpeg -i clip.mp4 -vf "select='gte(n\,254)',scale=flags=accurate_rnd+full_chroma_int,format=rgb24" -vsync 0 -start_number 254 $WORK/oldf/f%03d.png`
2. `WORK=... python3 track.py` (run inside a scratch folder) tracks the old decal
   through the shot (ECC homography against the first frame) and saves the
   per-frame homographies and decal masks.
3. `WORK=... python3 fix.py` erases the old decal and the small trademark mark
   (inpainting), then renders the real logo on the door plane with the shot's
   perspective, lighting and softness into `$WORK/fixf/`. It also reads
   `refspeck.png`, a mask of the trademark mark beside the Y.
4. Put the fixed frames back over the original frames and upscale as before
   (hqdn3d, Lanczos to 1080x1920, light unsharp), converting with
   `accurate_rnd+full_chroma_int` so the colours stay identical.

Needs `opencv-python-headless` and `numpy`.
