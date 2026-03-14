import logging
import os
import subprocess
import aiohttp
import asyncio
from typing import List, Optional

import cairosvg
from schemas import StoryBeat, MoviePlan, ShotPlan

class VideoEngine:
    def __init__(self, storage_service: 'StorageService', temp_dir: str = "/tmp/kidsketch_video"):
        self.storage_service = storage_service
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)

    async def create_animated_movie(
        self,
        session_id: str,
        movie_plan: MoviePlan,
        output_path: str,
        title: Optional[str] = None,
        local_audio_paths: Optional[List[str]] = None,
        local_image_paths: Optional[List[str]] = None,
    ) -> str:
        """
        Creates an animated movie from a MoviePlan using motion effects.
        If title is provided, a title frame is prepended at the beginning.
        local_audio_paths: optional list of local TTS mp3 paths (one per shot index).
        local_image_paths: optional list of local beat image paths (one per shot index) so we don't re-download.
        """
        segment_files = []
        use_audio = True  # if title with audio fails, set False and create all segments video-only

        # --- Title card at beginning (optional) ---
        if title and title.strip():
            title_card_png = os.path.join(self.temp_dir, f"{session_id}_titlecard.png")
            title_card_path = os.path.join(self.temp_dir, f"{session_id}_titlecard.mp4")
            await asyncio.to_thread(self._create_title_card_image, title.strip(), title_card_png)
            proc_title = await asyncio.to_thread(subprocess.run, [
                'ffmpeg', '-y', '-loop', '1', '-i', title_card_png, '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                '-vf', 'fade=t=in:st=0:d=1,fps=25', '-c:v', 'libx264', '-t', '3', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-shortest', '-map', '0:v:0', '-map', '1:a:0',
                title_card_path
            ], capture_output=True, text=True)
            if proc_title.returncode == 0 and os.path.isfile(title_card_path):
                segment_files.append(title_card_path)
            else:
                print(f"Title card with audio failed, trying video-only: {proc_title.stderr[-300:] if proc_title.stderr else ''}")
                proc_v = await asyncio.to_thread(subprocess.run, [
                    'ffmpeg', '-y', '-loop', '1', '-i', title_card_png,
                    '-vf', 'fade=t=in:st=0:d=1,fps=25', '-c:v', 'libx264', '-t', '3', '-pix_fmt', 'yuv420p',
                    title_card_path
                ], capture_output=True, text=True)
                if proc_v.returncode == 0 and os.path.isfile(title_card_path):
                    segment_files.append(title_card_path)
                    use_audio = False
                else:
                    print(f"Title card video-only failed: {proc_v.stderr[-300:] if proc_v.stderr else ''}")

        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
            for i, shot in enumerate(movie_plan.shots):
                if not shot.bgImageUrl:
                    print(f"Skipping shot {i}: no bgImageUrl")
                    continue
                try:
                    # 1. Background image: use local path from export when available, else download
                    local_bg = os.path.join(self.temp_dir, f"{session_id}_shot_{i}_bg.png")
                    if local_image_paths and i < len(local_image_paths) and local_image_paths[i]:
                        lp = local_image_paths[i]
                        if os.path.isfile(lp) and os.path.getsize(lp) > 0:
                            local_bg = lp
                    if not os.path.isfile(local_bg) or os.path.getsize(local_bg) == 0:
                        if shot.bgImageUrl and "storage.googleapis.com" in str(shot.bgImageUrl):
                            await self.storage_service.download_file(shot.bgImageUrl, local_bg)
                        elif shot.bgImageUrl and shot.bgImageUrl.startswith("http"):
                            self._validate_url(shot.bgImageUrl)
                            async with session.get(shot.bgImageUrl) as resp:
                                resp.raise_for_status()
                                content = await resp.read()
                                await asyncio.to_thread(self._write_file, local_bg, content)
                        elif shot.bgImageUrl:
                            local_bg = shot.bgImageUrl
                    if not os.path.isfile(local_bg):
                        print(f"Skipping shot {i}: image file missing")
                        continue

                    # FFmpeg has no SVG decoder; convert SVG beat images to PNG
                    local_bg = await asyncio.to_thread(
                        self._ensure_png_for_ffmpeg, local_bg, session_id, i
                    )

                    # 2. Narration audio: use local path from TTS when provided, else download
                    local_audio = os.path.join(self.temp_dir, f"{session_id}_shot_{i}_audio.mp3")
                    has_audio = False
                    if local_audio_paths and i < len(local_audio_paths) and local_audio_paths[i]:
                        lp = local_audio_paths[i]
                        if os.path.isfile(lp) and os.path.getsize(lp) > 0:
                            local_audio = lp
                            has_audio = True
                    if not has_audio and shot.audioUrl:
                        try:
                            if "storage.googleapis.com" in str(shot.audioUrl):
                                await self.storage_service.download_file(shot.audioUrl, local_audio)
                            elif shot.audioUrl.startswith("http"):
                                self._validate_url(shot.audioUrl)
                                async with session.get(shot.audioUrl) as resp:
                                    resp.raise_for_status()
                                    content = await resp.read()
                                    await asyncio.to_thread(self._write_file, local_audio, content)
                            else:
                                await self.storage_service.download_file(shot.audioUrl, local_audio)
                            has_audio = os.path.isfile(local_audio) and os.path.getsize(local_audio) > 0
                        except Exception as e:
                            print(f"Failed to download audio for shot {i}: {e}")

                    # 3. Duration from real audio or default; ensure we have an audio source for every segment
                    shot_duration = 5.0
                    if has_audio:
                        try:
                            probe = await asyncio.to_thread(
                                subprocess.run,
                                ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                                 '-of', 'default=noprint_wrappers=1:nokey=1', local_audio],
                                capture_output=True, text=True
                            )
                            if probe.stdout and probe.returncode == 0:
                                audio_dur = float(probe.stdout.strip())
                                shot_duration = audio_dur + 0.5
                                print(f"Shot {i} audio duration: {audio_dur:.2f}s → video duration: {shot_duration:.2f}s")
                        except Exception as e:
                            print(f"Could not probe audio duration for shot {i}: {e}")

                    # 4. Create segment with both video and audio (concat requires same stream layout)
                    segment_path = os.path.join(self.temp_dir, f"{session_id}_shot_{i}.mp4")
                    is_last = (i == len(movie_plan.shots) - 1)
                    fps = 25
                    num_frames = int(shot_duration * fps)
                    fade_duration = 1.0
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
                    if is_last:
                        fade_start = max(shot_duration - fade_duration, 0)
                        filter_complex = f"{motion_filter},fade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}"
                    else:
                        filter_complex = motion_filter

                    # Every segment: 1 video + 1 audio when use_audio else video-only (to match title/pause/end)
                    use_real_audio = use_audio and has_audio and os.path.isfile(local_audio) and os.path.getsize(local_audio) > 0
                    use_silent_audio = use_audio and not use_real_audio
                    if use_real_audio:
                        # Normalize TTS (often 24k mono) to 44.1k stereo so concat/final export plays correctly
                        cmd = ['ffmpeg', '-y', '-loop', '1', '-i', local_bg, '-i', local_audio,
                               '-vf', filter_complex, '-c:v', 'libx264', '-t', str(shot_duration), '-pix_fmt', 'yuv420p',
                               '-c:a', 'aac', '-ar', '44100', '-ac', '2', '-shortest', '-map', '0:v:0', '-map', '1:a:0', segment_path]
                    elif use_silent_audio:
                        cmd = ['ffmpeg', '-y', '-loop', '1', '-i', local_bg, '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                               '-vf', filter_complex, '-c:v', 'libx264', '-t', str(shot_duration), '-pix_fmt', 'yuv420p',
                               '-c:a', 'aac', '-shortest', '-map', '0:v:0', '-map', '1:a:0', segment_path]
                    else:
                        cmd = ['ffmpeg', '-y', '-loop', '1', '-i', local_bg,
                               '-vf', filter_complex, '-c:v', 'libx264', '-t', str(shot_duration), '-pix_fmt', 'yuv420p',
                               segment_path]
                    proc = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True)
                    if proc.returncode == 0:
                        segment_files.append(segment_path)
                    else:
                        print(f"Shot {i} ffmpeg failed: {proc.stderr[-500:] if proc.stderr else proc}")
                except Exception as e:
                    print(f"Shot {i} error: {e}")

        if not segment_files:
            raise ValueError("No segments generated for movie")

        # --- Black pause (1s) ---
        pause_path = os.path.join(self.temp_dir, f"{session_id}_pause.mp4")
        pause_ok = False
        if use_audio:
            proc_pause = await asyncio.to_thread(subprocess.run, [
                'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1280x720:r=25:d=1',
                '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', '1',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                pause_path
            ], capture_output=True, text=True)
            pause_ok = proc_pause.returncode == 0 and os.path.isfile(pause_path)
        if not pause_ok:
            if use_audio:
                print("Pause with audio failed, using video-only")
            proc_pause_v = await asyncio.to_thread(subprocess.run, [
                'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1280x720:r=25:d=1', '-t', '1',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', pause_path
            ], capture_output=True, text=True)
            pause_ok = proc_pause_v.returncode == 0 and os.path.isfile(pause_path)
        if pause_ok:
            segment_files.append(pause_path)

        # --- End Card (4s) - "Created with KidSketch" ---
        end_card_png = os.path.join(self.temp_dir, f"{session_id}_endcard.png")
        end_card_path = os.path.join(self.temp_dir, f"{session_id}_endcard.mp4")
        await asyncio.to_thread(self._create_end_card_image, end_card_png)
        end_ok = False
        if use_audio:
            proc_end = await asyncio.to_thread(subprocess.run, [
                'ffmpeg', '-y', '-loop', '1', '-i', end_card_png, '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                '-vf', 'fade=t=in:st=0:d=1,fps=25', '-c:v', 'libx264', '-t', '4', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-shortest', '-map', '0:v:0', '-map', '1:a:0',
                end_card_path
            ], capture_output=True, text=True)
            end_ok = proc_end.returncode == 0 and os.path.isfile(end_card_path)
        if not end_ok:
            if use_audio:
                print("End card with audio failed, using video-only")
            proc_end_v = await asyncio.to_thread(subprocess.run, [
                'ffmpeg', '-y', '-loop', '1', '-i', end_card_png,
                '-vf', 'fade=t=in:st=0:d=1,fps=25', '-c:v', 'libx264', '-t', '4', '-pix_fmt', 'yuv420p',
                end_card_path
            ], capture_output=True, text=True)
            end_ok = proc_end_v.returncode == 0 and os.path.isfile(end_card_path)
        if end_ok:
            segment_files.append(end_card_path)

        # Only concat segments that exist (so we don't fail on missing files)
        existing = [p for p in segment_files if os.path.isfile(p) and os.path.getsize(p) > 0]
        if not existing:
            raise ValueError("No valid segment files to concatenate")
        print(f"Export: concatenating {len(existing)} segments into final movie")

        concat_list = os.path.join(self.temp_dir, f"{session_id}_shots.txt")
        await asyncio.to_thread(self._write_concat_file, concat_list, existing)

        # Re-encode on concat: normalize audio to 44.1kHz stereo so gTTS (often 24k mono) plays at correct speed
        final_cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-ar', '44100', '-ac', '2',
            output_path
        ]
        proc_final = await asyncio.to_thread(subprocess.run, final_cmd, capture_output=True, text=True)
        if proc_final.returncode != 0:
            print(f"Concat failed: {proc_final.stderr[-1000:] if proc_final.stderr else ''}")
            raise RuntimeError(f"FFmpeg concat failed: {proc_final.stderr or 'unknown'}")
        return output_path

    async def create_movie(self, session_id: str, history: List[StoryBeat], output_path: str) -> str:
        # Keep old method as fallback or for legacy use
        pass

    def _validate_url(self, url: str):
        """Basic SSRF protection: only allow GCS and trusted placeholder domains."""
        allowed_domains = ["storage.googleapis.com", "placehold.co"]
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.netloc not in allowed_domains:
            raise ValueError(f"Unauthorized asset domain: {parsed.netloc}")

    def _is_svg(self, path: str) -> bool:
        """True if file looks like SVG (ffmpeg has no SVG decoder)."""
        try:
            with open(path, "rb") as f:
                head = f.read(1024)
            return b"<svg" in head or (b"<?xml" in head and b"<svg" in head.lower())
        except Exception:
            return False

    def _svg_to_png_sync(self, svg_path: str, png_path: str) -> bool:
        """Convert SVG to PNG so ffmpeg can use it. Returns True on success."""
        try:
            cairosvg.svg2png(url=svg_path, write_to=png_path)
            return os.path.isfile(png_path) and os.path.getsize(png_path) > 0
        except (ImportError, OSError, ValueError) as e:
            logging.warning("SVG to PNG conversion failed: %s", e)
            return False

    def _ensure_png_for_ffmpeg(self, image_path: str, session_id: str, shot_i: int) -> str:
        """Return a path to a PNG ffmpeg can decode. Converts SVG to PNG if needed."""
        if not os.path.isfile(image_path) or not self._is_svg(image_path):
            return image_path
        png_path = os.path.join(self.temp_dir, f"{session_id}_shot_{shot_i}_from_svg.png")
        if self._svg_to_png_sync(image_path, png_path):
            return png_path
        return image_path

    def _write_file(self, path: str, data: bytes):
        with open(path, 'wb') as f:
            f.write(data)

    def _write_concat_file(self, path: str, segments: List[str]):
        with open(path, "w") as f:
            for seg in segments:
                # Escape single quotes for ffmpeg concat demuxer
                escaped = seg.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

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

    def _create_title_card_image(self, title: str, output_path: str, width: int = 1280, height: int = 720):
        """Generate a 1280x720 title card PNG with the story title."""
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (width, height), color=(80, 50, 120))
        draw = ImageDraw.Draw(img)

        font_paths = [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/SFNSRounded.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]

        def load_font(size):
            for fp in font_paths:
                if os.path.exists(fp):
                    try:
                        return ImageFont.truetype(fp, size)
                    except Exception:
                        pass
            return ImageFont.load_default()

        title_font = load_font(64)
        display_title = title if len(title) <= 40 else title[:37] + "..."
        t_bbox = draw.textbbox((0, 0), display_title, font=title_font)
        t_w = t_bbox[2] - t_bbox[0]
        t_h = t_bbox[3] - t_bbox[1]
        draw.text(((width - t_w) / 2, (height - t_h) / 2), display_title, font=title_font, fill=(255, 255, 255))
        img.save(output_path)
        print(f"✅ Title card image saved: {output_path}")
