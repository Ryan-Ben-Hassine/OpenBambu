"""
Own your bambu Cloud - Main Web & API Server
FastAPI-based, zero-SQL, pure JSON backend for multi-printer Bambu Lab management.
Author: Ryan Ben Hassine (https://ryanbenhassine.com)
License: https://ryanbenhassine.com
Copyright (c) 2026 Ryan Ben Hassine. All rights reserved.
"""

import os
import sys
import time
from typing import Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .json_store import JSONStore
from .bambu_client import BambuMultiPrinterManager
from .camera_streamer import MultiCameraManager
from .ai_eye_engine import AIEyeEngine
from .video_processor import VideoProcessor

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Core services
store = JSONStore(data_dir=DATA_DIR)
printer_manager = BambuMultiPrinterManager(json_store=store)
camera_manager = MultiCameraManager(json_store=store)
ai_eye = AIEyeEngine(json_store=store)
video_proc = VideoProcessor(json_store=store, uploads_dir=os.path.join(DATA_DIR, "uploads"))

app = FastAPI(
    title="Own your bambu Cloud",
    description="Open source, zero-database Bambu Lab cloud & multi-printer management platform by Ryan Ben Hassine (https://ryanbenhassine.com).",
    version="1.0.0-oss",
    contact={
        "name": "Ryan Ben Hassine",
        "url": "https://ryanbenhassine.com"
    },
    license_info={
        "name": "Licensed via ryanbenhassine.com",
        "url": "https://ryanbenhassine.com"
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Request Models ---
class PrinterCreateModel(BaseModel):
    name: str
    model: str = "P1S"
    ip: str
    access_code: str
    serial: str
    mqtt_port: int = 8883
    camera_port: int = 6000
    is_default: bool = False

class ActionModel(BaseModel):
    action: str  # pause, resume, stop, light, speed, gcode, service, trash, bump, center, home, bed_pct, jog
    value: Optional[Any] = None
    axis: Optional[str] = None
    dist: Optional[float] = None

class AIEyeSettingsModel(BaseModel):
    provider: str  # "openai", "opensource", "builtin_paid"
    enabled: bool = False
    auto_interval_seconds: int = 120
    openai_key: Optional[str] = None
    openai_model: Optional[str] = "gpt-4o-mini"
    opensource_base_url: Optional[str] = "http://localhost:11434/v1"
    opensource_model: Optional[str] = "llava"
    opensource_key: Optional[str] = ""

class ProLicenseModel(BaseModel):
    license_key: str

class FilamentCreateModel(BaseModel):
    brand: str = "Generic"
    material: str = "PLA"
    color_name: str = "Black"
    color_hex: str = "#000000"
    remaining_grams: float = 1000.0
    initial_grams: float = 1000.0
    diameter: float = 1.75
    notes: Optional[str] = ""

class AmsAssignModel(BaseModel):
    ams_id: int = 0
    tray_id: int = 0
    filament_id: str
    nozzle_temp_min: int = 190
    nozzle_temp_max: int = 240

class VideoProcessModel(BaseModel):
    input_video_path: Optional[str] = None
    position: str = "bottom_right"
    opacity: float = 0.85
    scale_pct: int = 15

# ==================== REST APIS ====================

@app.get("/api/info")
def get_info():
    return {
        "app_name": "Own your bambu Cloud",
        "author": "ryanbenhassine",
        "copyright": "Copyright (c) 2026 Ryan Ben Hassine (ryanbenhassine)",
        "license": "MIT",
        "version": "1.0.0-oss",
        "storage": "JSON (Zero Database)",
        "printers_count": len(store.get_printers())
    }

# --- Printers Management ---
@app.get("/api/printers")
def list_printers():
    return {"printers": store.get_printers()}

@app.post("/api/printers")
def create_printer(payload: PrinterCreateModel):
    data = payload.dict()
    new_printer = store.add_printer(data)
    printer_manager.sync_from_store()
    return {"ok": True, "printer": new_printer}

@app.put("/api/printers/{printer_id}")
def update_printer(printer_id: str, updates: Dict[str, Any]):
    updated = store.update_printer(printer_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Printer not found")
    printer_manager.sync_from_store()
    return {"ok": True, "printer": updated}

@app.delete("/api/printers/{printer_id}")
def delete_printer(printer_id: str):
    success = store.delete_printer(printer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Printer not found")
    printer_manager.sync_from_store()
    return {"ok": True}

@app.post("/api/printers/{printer_id}/set_default")
def set_default_printer(printer_id: str):
    updated = store.update_printer(printer_id, {"is_default": True})
    return {"ok": True, "printer": updated}

# --- Telemetry & Live Status ---
@app.get("/api/status")
def get_all_status():
    telemetry = printer_manager.get_all_telemetry()
    return {"telemetry": telemetry, "timestamp": time.time()}

@app.get("/api/printers/{printer_id}/status")
def get_printer_status(printer_id: str):
    ctrl = printer_manager.get_controller(printer_id)
    if not ctrl:
        raise HTTPException(status_code=404, detail="Printer not found")
    telemetry = ctrl.query_status(timeout=3.0)
    bed_state = store.get_bed_state(printer_id)
    return {
        "printer_id": printer_id,
        "telemetry": telemetry,
        "bed_state": bed_state,
        "timestamp": time.time()
    }

# --- Controls & Actions ---
@app.post("/api/printers/{printer_id}/action")
def execute_action(printer_id: str, payload: ActionModel):
    ctrl = printer_manager.get_controller(printer_id)
    if not ctrl:
        raise HTTPException(status_code=404, detail="Printer not found")

    act = payload.action.lower()
    res = False

    if act == "pause":
        res = ctrl.pause_print()
    elif act == "resume":
        res = ctrl.resume_print()
    elif act == "stop":
        res = ctrl.stop_print()
    elif act == "light":
        on = bool(payload.value)
        res = ctrl.set_chamber_light(on)
    elif act == "speed":
        level = int(payload.value or 2)
        res = ctrl.set_speed_level(level)
    elif act == "gcode":
        gcode = str(payload.value or "")
        res = ctrl.send_gcode(gcode)
    elif act == "service":
        res = ctrl.position_service()
        store.set_bed_state(printer_id, 70, 180.0, note="Service position")
    elif act == "trash":
        res = ctrl.position_trash()
    elif act == "bump":
        res = ctrl.position_bump()
        store.set_bed_state(printer_id, 8, 20.0, note="Bump recovery")
    elif act == "center":
        res = ctrl.position_center()
    elif act == "home":
        res = ctrl.position_home()
        store.set_bed_state(printer_id, 0, 0.0, note="Homed")
    elif act == "bed_pct":
        pct = int(payload.value or 0)
        res = ctrl.move_bed_pct(pct)
        z_mm = round((pct / 100.0) * 256.0, 1)
        store.set_bed_state(printer_id, pct, z_mm, note=f"Bed set to {pct}%")
    elif act == "jog":
        axis = payload.axis or "Z"
        dist = float(payload.dist or 10.0)
        res = ctrl.jog(axis, dist)
        if axis.upper() == "Z":
            cur = store.get_bed_state(printer_id)
            new_z = max(0.0, min(256.0, cur.get("bed_position_z", 0.0) + dist))
            new_pct = int(round((new_z / 256.0) * 100))
            store.set_bed_state(printer_id, new_pct, new_z, note="Jogged Z")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {act}")

    return {"ok": res, "action": act}

# --- Camera Streaming & Snapshots ---
@app.get("/api/printers/{printer_id}/camera/snapshot")
def get_camera_snapshot(printer_id: str):
    streamer = camera_manager.get_streamer(printer_id)
    frame = streamer.get_snapshot() if streamer else None
    if not frame:
        # Return fallback placeholder frame
        from PIL import Image, ImageDraw
        import io
        img = Image.new("RGB", (640, 360), color=(15, 17, 23))
        draw = ImageDraw.Draw(img)
        draw.text((200, 170), "Bambu Camera Offline", fill=(249, 115, 22))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        frame = buf.getvalue()

    return Response(content=frame, media_type="image/jpeg")

@app.get("/api/printers/{printer_id}/camera/stream")
def get_camera_stream(printer_id: str):
    streamer = camera_manager.get_streamer(printer_id)
    if not streamer:
        raise HTTPException(status_code=404, detail="Camera streamer not available")

    def mjpeg_generator():
        while True:
            frame = streamer.get_snapshot()
            if frame:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            time.sleep(0.1)

    return StreamingResponse(
        mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# --- Filament Inventory Management ---
@app.get("/api/filaments")
def list_filaments():
    return {"filaments": store.get_filaments()}

@app.post("/api/filaments")
def create_filament(payload: FilamentCreateModel):
    new_spool = store.add_filament(payload.dict())
    return {"ok": True, "filament": new_spool}

@app.put("/api/filaments/{filament_id}")
def update_filament(filament_id: str, updates: Dict[str, Any]):
    updated = store.update_filament(filament_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Filament not found")
    return {"ok": True, "filament": updated}

@app.delete("/api/filaments/{filament_id}")
def delete_filament(filament_id: str):
    success = store.delete_filament(filament_id)
    if not success:
        raise HTTPException(status_code=404, detail="Filament not found")
    return {"ok": True}

@app.post("/api/printers/{printer_id}/ams/assign")
def assign_filament_to_ams(printer_id: str, payload: AmsAssignModel):
    ctrl = printer_manager.get_controller(printer_id)
    if not ctrl:
        raise HTTPException(status_code=404, detail="Printer not found")
    
    filaments = store.get_filaments()
    spool = next((f for f in filaments if f.get("id") == payload.filament_id), None)
    if not spool:
        raise HTTPException(status_code=404, detail="Spool not found in filament inventory")

    color_hex = spool.get("color_hex", "#FFFFFF")
    material = spool.get("material", "PLA")
    res = ctrl.assign_ams_tray(
        ams_id=payload.ams_id,
        tray_id=payload.tray_id,
        color_hex=color_hex,
        tray_type=material,
        nozzle_temp_min=payload.nozzle_temp_min,
        nozzle_temp_max=payload.nozzle_temp_max
    )
    return {"ok": res, "spool": spool, "ams_id": payload.ams_id, "tray_id": payload.tray_id}

# --- AI Eye Guardian ---
@app.post("/api/ai_eye/inspect")
def inspect_printer_print(printer_id: Optional[str] = None):
    # Select active printer
    if not printer_id:
        printers = store.get_printers()
        default_p = next((p for p in printers if p.get("is_default")), printers[0] if printers else None)
        if not default_p:
            raise HTTPException(status_code=400, detail="No printer available")
        printer_id = default_p["id"]

    printer = store.get_printer(printer_id)
    ctrl = printer_manager.get_controller(printer_id)
    streamer = camera_manager.get_streamer(printer_id)
    
    frame = streamer.get_snapshot() if streamer else None
    if not frame:
        raise HTTPException(status_code=503, detail="Camera frame unavailable for inspection")

    telemetry = ctrl.last_telemetry if ctrl else {}
    result = ai_eye.inspect_frame(
        frame_bytes=frame,
        printer_name=printer.get("name", "Bambu Printer") if printer else "Bambu Printer",
        telemetry=telemetry
    )
    return {"ok": True, "result": result}

@app.get("/api/ai_eye/history")
def get_inspection_history():
    return {"inspections": store.get_inspections(limit=50)}

@app.post("/api/ai_eye/settings")
def update_ai_eye_settings(payload: AIEyeSettingsModel):
    updates = {
        "ai_eye": {
            "provider": payload.provider,
            "enabled": payload.enabled,
            "auto_interval_seconds": payload.auto_interval_seconds,
            "openai": {
                "api_key": payload.openai_key or "",
                "model": payload.openai_model or "gpt-4o-mini"
            },
            "opensource": {
                "base_url": payload.opensource_base_url or "http://localhost:11434/v1",
                "model": payload.opensource_model or "llava",
                "api_key": payload.opensource_key or ""
            }
        }
    }
    updated = store.update_settings(updates)
    return {"ok": True, "settings": updated["ai_eye"]}

@app.post("/api/ai_eye/upgrade")
def upgrade_builtin_ai_eye(payload: ProLicenseModel):
    key = payload.license_key.strip()
    # Simple open-source licensing validation demonstration
    if len(key) >= 8:
        store.update_settings({
            "ai_eye": {
                "builtin_paid": {
                    "unlocked": True,
                    "license_key": key
                }
            }
        })
        return {"ok": True, "message": "Autonomous Built-in AI Eye unlocked successfully!"}
    raise HTTPException(status_code=400, detail="Invalid license key format")

# --- Custom Video Cloud Processing with Logo ---
@app.post("/api/videos/upload_logo")
async def upload_brand_logo(logo: UploadFile = File(...)):
    content = await logo.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo file size exceeds 10MB")
    
    clean_name = video_proc.save_logo(logo.filename, content)
    return {"ok": True, "filename": clean_name, "message": "Custom logo uploaded and configured!"}

@app.post("/api/videos/process")
def process_video_watermark(payload: VideoProcessModel):
    settings = store.get_settings().get("video_processor", {})
    logo_path = settings.get("logo_path")
    if not logo_path or not os.path.exists(logo_path):
        return {"ok": False, "error": "No logo uploaded yet. Please upload a logo first."}

    input_path = payload.input_video_path
    if not input_path or not os.path.exists(input_path):
        # Generate demo timelapse if no input path provided
        res = video_proc.create_demo_timelapse()
        return {"ok": res.get("success", False), "result": res}

    res = video_proc.process_timelapse_with_logo(
        input_video_path=input_path,
        output_name="custom_bambu_video.mp4",
        position=payload.position,
        opacity=payload.opacity,
        scale_pct=payload.scale_pct
    )
    return {"ok": res.get("success", False), "result": res}

@app.post("/api/videos/demo")
def generate_demo_video():
    res = video_proc.create_demo_timelapse()
    return {"ok": res.get("success", False), "result": res}

@app.get("/api/videos/list")
def list_timelapses():
    return {"timelapses": store.get_timelapses()}

@app.get("/api/videos/download/{filename}")
def download_video(filename: str):
    file_path = os.path.join(video_proc.videos_dir, os.path.basename(filename))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(file_path, media_type="video/mp4", filename=filename)

# --- Schedule Pro (Paid Feature) ---
@app.get("/api/schedule/status")
def get_schedule_status():
    settings = store.get_settings().get("schedule_pro", {})
    return {
        "is_unlocked": settings.get("unlocked", False),
        "feature_name": "Schedule Print & Autonomous Queue",
        "description": "Unlock autonomous 24/7 print scheduling, automated batch sequencing, and off-peak energy optimization."
    }

@app.post("/api/schedule/unlock")
def unlock_schedule_pro(payload: ProLicenseModel):
    key = payload.license_key.strip()
    if len(key) >= 8:
        store.update_settings({"schedule_pro": {"unlocked": True, "license_key": key}})
        return {"ok": True, "message": "Schedule Pro unlocked successfully!"}
    raise HTTPException(status_code=400, detail="Invalid license key format")

# --- Settings ---
@app.get("/api/settings")
def get_all_settings():
    return store.get_settings()

@app.post("/api/settings")
def update_system_settings(updates: Dict[str, Any]):
    updated = store.update_settings(updates)
    return {"ok": True, "settings": updated}

# Mount static frontend
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Own your bambu Cloud</h1><p>Frontend loading...</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=9930, reload=False)
