"""
Own your bambu Cloud - Custom Video Cloud Processor with Logo Watermark
Cloud processes final timelapses & videos, letting users burn in their custom logo/watermark.
Uses standard ffmpeg for high-performance video compositing.
Copyright (c) 2026 Ryan Ben Hassine (ryanbenhassine).
"""

import os
import time
import shutil
import subprocess
from typing import Dict, Any, Optional

class VideoProcessor:
    def __init__(self, json_store, uploads_dir: str):
        self.store = json_store
        self.uploads_dir = uploads_dir
        self.logos_dir = os.path.join(self.uploads_dir, "logos")
        self.videos_dir = os.path.join(self.uploads_dir, "videos")
        os.makedirs(self.logos_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)

    def save_logo(self, filename: str, file_bytes: bytes) -> str:
        """Saves a user's custom logo file."""
        clean_name = f"logo_{int(time.time())}_{os.path.basename(filename)}"
        target_path = os.path.join(self.logos_dir, clean_name)
        with open(target_path, "wb") as f:
            f.write(file_bytes)
        
        # Update settings
        self.store.update_settings({
            "video_processor": {
                "logo_path": target_path,
                "logo_filename": clean_name
            }
        })
        return clean_name

    def process_timelapse_with_logo(
        self,
        input_video_path: str,
        output_name: str,
        printer_name: str = "Bambu Printer",
        custom_logo_path: Optional[str] = None,
        position: str = "bottom_right",
        opacity: float = 0.85,
        scale_pct: int = 15
    ) -> Dict[str, Any]:
        """Burns custom user logo into input video using ffmpeg filter_complex."""
        settings = self.store.get_settings().get("video_processor", {})
        logo_path = custom_logo_path or settings.get("logo_path", "")
        
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        final_filename = f"processed_{timestamp_str}_{os.path.basename(output_name)}"
        if not final_filename.endswith(".mp4"):
            final_filename += ".mp4"
        output_path = os.path.join(self.videos_dir, final_filename)

        if not os.path.exists(input_video_path):
            return {"success": False, "error": f"Input video not found: {input_video_path}"}

        # Calculate ffmpeg overlay position coordinates
        pos_map = {
            "top_left": "x=20:y=20",
            "top_right": "x=main_w-overlay_w-20:y=20",
            "bottom_left": "x=20:y=main_h-overlay_h-20",
            "bottom_right": "x=main_w-overlay_w-20:y=main_h-overlay_h-20",
            "center": "x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2"
        }
        overlay_coords = pos_map.get(position, pos_map["bottom_right"])

        if logo_path and os.path.exists(logo_path):
            # Scale logo relative to video width, adjust alpha opacity
            scale_ratio = max(0.05, min(0.40, scale_pct / 100.0))
            filter_str = (
                f"[1:v]format=rgba,colorchannelmixer=aa={opacity},"
                f"scale=iw*{scale_ratio}:-1[logo];"
                f"[0:v][logo]overlay={overlay_coords}"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", input_video_path,
                "-i", logo_path,
                "-filter_complex", filter_str,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "fast",
                "-crf", "23",
                output_path
            ]
        else:
            # Fallback if no logo selected: copy video cleanly
            cmd = [
                "ffmpeg", "-y",
                "-i", input_video_path,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                output_path
            ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if res.returncode == 0 and os.path.exists(output_path):
                file_size_mb = round(os.path.getsize(output_path) / (1024 * 1024), 2)
                record = {
                    "filename": final_filename,
                    "printer_name": printer_name,
                    "size_mb": file_size_mb,
                    "has_logo": bool(logo_path and os.path.exists(logo_path)),
                    "position": position,
                    "download_url": f"/api/videos/download/{final_filename}"
                }
                self.store.add_timelapse(record)
                return {"success": True, "record": record}
            else:
                err_text = res.stderr.decode("utf-8", errors="ignore")[:300]
                return {"success": False, "error": f"ffmpeg processing error: {err_text}"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Video processing timed out (>120s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_demo_timelapse(self, printer_name: str = "Bambu P1S") -> Dict[str, Any]:
        """Creates a sample demo timelapse for testing watermark feature out of the box."""
        demo_input = os.path.join(self.videos_dir, "demo_source.mp4")
        if not os.path.exists(demo_input):
            # Generate a 4-second 720p sample countdown video with ffmpeg
            gen_cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", "testsrc=size=1280x720:rate=30",
                "-t", "4",
                "-pix_fmt", "yuv420p",
                demo_input
            ]
            subprocess.run(gen_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return self.process_timelapse_with_logo(
            input_video_path=demo_input,
            output_name="bambu_timelapse_demo.mp4",
            printer_name=printer_name
        )
