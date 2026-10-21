"""Decode the complete video and sample every chapter; retain media facts."""
import json,subprocess,re
from pathlib import Path
from PIL import Image,ImageDraw
import imageio_ffmpeg
root=Path(__file__).resolve().parents[1];f=next((root/'output/moheng-final-20261021/materials').glob('*.mp4'));ff=imageio_ffmpeg.get_ffmpeg_exe();m=json.loads((root/'output/moheng-final-20261021/materials/video-manifest.json').read_text('utf-8'));out=root/'artifacts/moheng-final-20261021/video-frames';out.mkdir(exist_ok=True)
probe=subprocess.run([ff,'-i',str(f)],capture_output=True,text=True,encoding='utf-8',errors='replace').stderr
assert '1920x1080' in probe and 'h264' in probe and 'aac' in probe
r=subprocess.run([ff,'-hide_banner','-v','error','-i',str(f),'-f','null','-'],capture_output=True,text=True);assert r.returncode==0 and not r.stderr,r.stderr
thumbs=[]
for x in m['scenes']:
 png=out/f"scene-{x['id']}.png";subprocess.run([ff,'-y','-v','error','-ss',str(x['start']+25),'-i',str(f),'-frames:v','1',str(png)],check=True)
 assert png.exists();im=Image.open(png);im.thumbnail((640,360));thumbs.append(im)
for start in [0,4]:
 sheet=Image.new('RGB',(1280,760),'#d5ddd6');d=ImageDraw.Draw(sheet)
 for j,im in enumerate(thumbs[start:start+4]):x=(j%2)*640;y=(j//2)*380;sheet.paste(im,(x,y));d.text((x+10,y+362),f'Scene {start+j+1}',fill='black')
 sheet.save(out/f'contact-{start//4+1}.png')
# A frame near the end verifies that video lasts as long as narration, not only the container.
subprocess.run([ff,'-y','-v','error','-ss',str(m['duration_seconds']-1),'-i',str(f),'-frames:v','1',str(out/'last-second.png')],check=True);assert (out/'last-second.png').exists()
(root/'artifacts/moheng-final-20261021/video-validation.json').write_text(json.dumps({'ffmpeg_full_decode_exit':r.returncode,'decode_errors':r.stderr,'probe':probe,'duration_seconds':m['duration_seconds'],'resolution':'1920x1080','codec':'H264/AAC','sampled_frames':9,'notice':'Synthetic Mandarin audio; timed captions approximate. Full media decode and sampled visual checks, not independent audience review.'},ensure_ascii=False,indent=2),'utf-8');print('Full decode and all nine frames passed',m['duration_seconds'])
