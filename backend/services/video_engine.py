import os
import subprocess
import requests
from typing import List
from schemas import StoryBeat, MoviePlan, ShotPlan

class VideoEngine:
    def __init__(self, storage_service: 'StorageService', temp_dir: str = "/tmp/kidsketch_video"):
        self.storage_service = storage_service
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)

    async def create_animated_movie(self, session_id: str, movie_plan: MoviePlan, output_path: str) -> str:
        """
        Creates an animated movie from a MoviePlan using motion effects.
        """
        segment_files = []
        last_valid_index = -1  # Track which shot is truly the last
        
        for i, shot in enumerate(movie_plan.shots):
            if not shot.bgImageUrl:
                continue
            
            # 1. Download Background Image (may be GCS URL or local path)
            local_bg = os.path.join(self.temp_dir, f"{session_id}_shot_{i}_bg.png")
            if shot.bgImageUrl.startswith("http"):
                resp = requests.get(shot.bgImageUrl, timeout=30)
                with open(local_bg, 'wb') as f:
                    f.write(resp.content)
            else:
                local_bg = shot.bgImageUrl
            
            # 2. Download Audio
            local_audio = os.path.join(self.temp_dir, f"{session_id}_shot_{i}_audio.mp3")
            has_audio = False
            if shot.audioUrl:
                try:
                    if shot.audioUrl.startswith("http"):
                        resp = requests.get(shot.audioUrl, timeout=30)
                        with open(local_audio, 'wb') as f:
                            f.write(resp.content)
                    else:
                        await self.storage_service.download_file(shot.audioUrl, local_audio)
                    has_audio = True
                except Exception as e:
                    print(f"Failed to download audio for shot {i}: {e}")

            # 3. Measure actual audio duration to avoid truncation
            shot_duration = 5.0  # default
            if has_audio:
                try:
                    probe = subprocess.run(
                        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                         '-of', 'default=noprint_wrappers=1:nokey=1', local_audio],
                        capture_output=True, text=True
                    )
                    audio_dur = float(probe.stdout.strip())
                    shot_duration = audio_dur + 0.5  # add small buffer so narration isn't clipped
                    print(f"Shot {i} audio duration: {audio_dur:.2f}s → video duration: {shot_duration:.2f}s")
                except Exception as e:
                    print(f"Could not probe audio duration for shot {i}: {e}")

            # 4. Create Animated Segment for this shot
            segment_path = os.path.join(self.temp_dir, f"{session_id}_shot_{i}.mp4")
            is_last = (i == len(movie_plan.shots) - 1)
            
            # Apply motion — calculate frames based on actual duration (25fps)
            fps = 25
            num_frames = int(shot_duration * fps)
            fade_duration = 1.0  # seconds for fadeout on last shot
            
            if shot.motionDirection == 'zoom-in':
                motion_filter = f"zoompan=z='min(zoom+0.0015,1.5)':d={num_frames}:s=1280x720:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',fps={fps}"
            elif shot.motionDirection == 'zoom-out':
                motion_filter = f"zoompan=z='max(1.5-0.0015*on,1)':d={num_frames}:s=1280x720:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',fps={fps}"
            elif shot.motionDirection == 'pan-left':
                motion_filter = f"zoompan=z=1.5:x='if(lte(on,0),0,on*2)':y='ih/2-(ih/zoom/2)':d={num_frames}:s=1280x720,fps={fps}"
            elif shot.motionDirection == 'pan-right':
                motion_filter = f"zoompan=z=1.5:x='iw-iw/zoom-on*2':y='ih/2-(ih/zoom/2)':d={num_frames}:s=1280x720,fps={fps}"
            else:
                motion_filter = f"zoompan=z=1.1:d={num_frames}:s=1280x720,fps={fps}"

            # Add fadeout on the last story card
            if is_last:
                fade_start = max(shot_duration - fade_duration, 0)
                filter_complex = f"{motion_filter},fade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}"
            else:
                filter_complex = motion_filter

            cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', local_bg
            ]
            
            if has_audio:
                cmd.extend(['-i', local_audio])
                
            cmd.extend([
                '-vf', filter_complex,
                '-c:v', 'libx264', '-t', str(shot_duration), '-pix_fmt', 'yuv420p'
            ])
            
            if has_audio:
                cmd.extend(['-c:a', 'aac', '-shortest', '-map', '0:v:0', '-map', '1:a:0'])
                
            cmd.append(segment_path)
            
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                segment_files.append(segment_path)
                last_valid_index = i
            else:
                print(f"Shot {i} failed: {proc.stderr[-500:]}")

        if not segment_files:
            raise ValueError("No segments generated for movie")

        # --- Black pause (1s) ---
        pause_path = os.path.join(self.temp_dir, f"{session_id}_pause.mp4")
        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1280x720:r=25:d=1',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', pause_path
        ], capture_output=True)

        # --- End Card (4s) — generated with Pillow for reliable text rendering ---
        end_card_png = os.path.join(self.temp_dir, f"{session_id}_endcard.png")
        end_card_path = os.path.join(self.temp_dir, f"{session_id}_endcard.mp4")
        self._create_end_card_image(end_card_png)
        subprocess.run([
            'ffmpeg', '-y',
            '-loop', '1', '-i', end_card_png,
            '-vf', 'fade=t=in:st=0:d=1,fps=25',
            '-c:v', 'libx264', '-t', '4', '-pix_fmt', 'yuv420p',
            end_card_path
        ], capture_output=True)

        segment_files.extend([pause_path, end_card_path])

        # Concatenate all segments
        concat_list = os.path.join(self.temp_dir, f"{session_id}_shots.txt")
        with open(concat_list, "w") as f:
            for seg in segment_files:
                f.write(f"file '{seg}'\n")

        final_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0',
            '-i', concat_list,
            '-c', 'copy',
            output_path
        ]
        
        subprocess.run(final_cmd, check=True)
        return output_path

    async def create_movie(self, session_id: str, history: List[StoryBeat], output_path: str) -> str:
        # Keep old method as fallback or for legacy use
        pass

    def _create_end_card_image(self, output_path: str, width: int = 1280, height: int = 720):
        """Generate a 1280x720 end card PNG using Pillow."""
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (width, height), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Try system fonts in order of preference
        font_paths = [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/SFNSRounded.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux fallback
        ]

        def load_font(size):
            for fp in font_paths:
                if os.path.exists(fp):
                    try:
                        return ImageFont.truetype(fp, size)
                    except Exception:
                        pass
            return ImageFont.load_default()

        title_font = load_font(72)
        subtitle_font = load_font(30)

        title = "Created with KidSketch"
        subtitle = "From drawing to living story"

        # Center the title
        t_bbox = draw.textbbox((0, 0), title, font=title_font)
        t_w = t_bbox[2] - t_bbox[0]
        t_h = t_bbox[3] - t_bbox[1]
        draw.text(((width - t_w) / 2, height / 2 - t_h - 20), title, font=title_font, fill=(255, 255, 255))

        # Center the subtitle
        s_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        s_w = s_bbox[2] - s_bbox[0]
        draw.text(((width - s_w) / 2, height / 2 + 20), subtitle, font=subtitle_font, fill=(180, 180, 180))

        img.save(output_path)
        print(f"✅ End card image saved: {output_path}")
