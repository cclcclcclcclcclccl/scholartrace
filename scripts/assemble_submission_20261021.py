"""Assemble disclosed edited real-browser scenes with local Mandarin narration."""
from pathlib import Path
import json,re,subprocess
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'artifacts/submission-20261021';out=ROOT/'output/video-20261021';out.mkdir(parents=True,exist_ok=True)
ff=imageio_ffmpeg.get_ffmpeg_exe();scenes=json.loads((folder/'narration.json').read_text('utf-8'));record=json.loads((folder/'recording.json').read_text('utf-8'))
assert len(record['scenes'])==8 and all(x.get('ok') for x in record['scenes']) and not record['errors']
def stamp(t):
 h=int(t//3600);m=int(t%3600//60);s=t%60
 return f'{h}:{m:02d}:{s:05.2f}'
def srtstamp(t):return stamp(t).replace('.',',')+'0'
all_srt=[];elapsed=0;parts=[];manifest=[]
for scene in scenes:
 id=scene['id'];src=folder/f'scene-{id}.webm';audio=folder/f'voice-{id}.wav';target=max(38,scene['audio_seconds']+3)
 probe=subprocess.run([ff,'-i',str(src)],capture_output=True,text=True,encoding='utf-8',errors='replace').stderr
 m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe);assert m,probe
 raw=int(m[1])*3600+int(m[2])*60+float(m[3]);edit=min(raw,18)
 header='''[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Microsoft YaHei,28,&H00FFFFFF,&H00FFFFFF,&H00202020,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,80,80,15,1\nStyle: Title,Microsoft YaHei,24,&H00FFFFFF,&H00FFFFFF,&H00202020,&H00000000,0,0,0,0,100,100,0,0,1,1,0,8,35,35,12,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
 ass=[header,f'Dialogue: 0,0:00:00.00,{stamp(target)},Title,,0,0,0,,研证 ScholarTrace | {id:02d} {scene["title"]} | 实录 · 合成旁白 · 等待剪辑\n']
 chunks=re.findall(r'[^，。；！？：]+[，。；！？：]?',scene['text']);pos=0;total=sum(len(c) for c in chunks)
 for chunk in chunks:
  start=pos/total*scene['audio_seconds'];pos+=len(chunk);end=pos/total*scene['audio_seconds'];ass.append(f'Dialogue: 0,{stamp(start)},{stamp(end)},Default,,0,0,0,,{chunk}\n');all_srt.append(f'{len(all_srt)+1}\n{srtstamp(elapsed+start)} --> {srtstamp(elapsed+end)}\n{chunk}\n')
 ap=folder/f'scene-{id}.ass';ap.write_text(''.join(ass),'utf-8-sig')
 # Filters use paths relative to cwd; ffmpeg arguments are passed without a shell.
 rel=ap.relative_to(ROOT).as_posix()
 if raw>18:
  base=f'[0:v]split[a][b];[a]trim=0:8,setpts=PTS-STARTPTS[head];[b]trim=start={raw-10:.3f},setpts=PTS-STARTPTS[tail];[head][tail]concat=n=2:v=1:a=0[edit];'
 else:base='[0:v]setpts=PTS-STARTPTS[edit];'
 filters=base+f'[edit]fps=25,setsar=1[clip];[2:v]fps=25,setsar=1,trim=duration={target},setpts=PTS-STARTPTS[snap];[clip][snap]concat=n=2:v=1:a=0[held];[held]scale=1778:1000,setsar=1,pad=1920:1080:71:40:color=0x142b24,subtitles={rel}[v];[1:a]apad[a]'
 dest=folder/f'part-{id}.mp4'
 cmd=[ff,'-y','-hide_banner','-loglevel','error','-i',str(src),'-i',str(audio),'-loop','1','-framerate','25','-i',str(folder/f'scene-{id}.png'),'-filter_complex',filters,'-map','[v]','-map','[a]','-t',str(target),'-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-b:a','160k',str(dest)]
 subprocess.run(cmd,check=True,cwd=ROOT);parts.append(dest);manifest.append({'id':id,'title':scene['title'],'original_seconds':raw,'final_seconds':target,'editing':'First 8s + last 10s when longer than 18s; hold the genuine final screenshot during narration. No fabricated app responses.','start':elapsed});elapsed+=target;print('encoded',id,flush=True)
concat=folder/'concat.txt';concat.write_text('\n'.join("file '"+p.name+"'" for p in parts),'utf-8');final=out/'研证_ScholarTrace_演示_1080p_2026-10-21.mp4'
subprocess.run([ff,'-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-c:v','libx264','-preset','fast','-crf','21','-r','25','-fps_mode','cfr','-c:a','aac','-b:a','160k','-movflags','+faststart',str(final)],check=True)
(out/'研证_演示字幕_2026-10-21.srt').write_text('\n'.join(all_srt),'utf-8-sig');(out/'video-manifest.json').write_text(json.dumps({'duration_seconds':elapsed,'resolution':[1920,1080],'fps':25,'voice':'Microsoft Huihui Desktop / offline synthesized Mandarin','scenes':manifest},ensure_ascii=False,indent=2),'utf-8');print(final,elapsed)
