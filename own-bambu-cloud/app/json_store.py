"""
Own your bambu Cloud - JSON Storage Engine
Thread-safe, atomic, pure-JSON persistence layer.
Zero SQL database required.
Copyright (c) 2026 Ryan Ben Hassine (ryanbenhassine).
"""

import os
import json
import time
import threading
from typing import Any, Dict, List, Optional

class JSONStore:
    def __init__(self, data_dir: str):
        self.data_dir = os.path.abspath(data_dir)
        os.makedirs(self.data_dir, exist_ok=True)
        self._lock = threading.RLock()
        
        # Core JSON storage paths
        self.printers_file = os.path.join(self.data_dir, "printers.json")
        self.settings_file = os.path.join(self.data_dir, "settings.json")
        self.filaments_file = os.path.join(self.data_dir, "filaments.json")
        self.inspections_file = os.path.join(self.data_dir, "ai_inspections.json")
        self.timelapses_file = os.path.join(self.data_dir, "timelapses.json")
        self.history_file = os.path.join(self.data_dir, "history.json")
        self.bed_state_file = os.path.join(self.data_dir, "bed_state.json")
        
        self._init_defaults()

    def _init_defaults(self):
        with self._lock:
            # 1. Default Settings
            if not os.path.exists(self.settings_file):
                default_settings = {
                    "app_name": "Own your bambu Cloud",
                    "author": "ryanbenhassine",
                    "copyright": "Copyright (c) 2026 Ryan Ben Hassine",
                    "version": "1.0.0-oss",
                    "theme": "dark",
                    "auto_light_off": {
                        "enabled": True,
                        "idle_timeout_seconds": 180
                    },
                    "ai_eye": {
                        "provider": "openai",  # "openai", "opensource", or "builtin_paid"
                        "enabled": False,
                        "auto_interval_seconds": 120,
                        "openai": {
                            "api_key": "",
                            "model": "gpt-4o-mini"
                        },
                        "opensource": {
                            "base_url": "http://localhost:11434/v1",
                            "model": "llava",
                            "api_key": ""
                        },
                        "builtin_paid": {
                            "unlocked": False,
                            "license_key": ""
                        }
                    },
                    "video_processor": {
                        "logo_path": "",
                        "logo_filename": "",
                        "watermark_position": "bottom_right",
                        "watermark_opacity": 0.85,
                        "watermark_scale_pct": 15,
                        "add_telemetry_hud": True
                    },
                    "schedule_pro": {
                        "unlocked": False,
                        "license_key": ""
                    }
                }
                self._write_json_atomic(self.settings_file, default_settings)

            # 2. Empty Printers list (Zero pre-seeded printers - clean manual testing)
            if not os.path.exists(self.printers_file):
                self._write_json_atomic(self.printers_file, [])

            # 3. Filaments, Inspections, Timelapses, History files
            for f in [self.filaments_file, self.inspections_file, self.timelapses_file, self.history_file]:
                if not os.path.exists(f):
                    self._write_json_atomic(f, [])

            if not os.path.exists(self.bed_state_file):
                self._write_json_atomic(self.bed_state_file, {})

    def _read_json(self, file_path: str, fallback: Any = None) -> Any:
        with self._lock:
            if not os.path.exists(file_path):
                return fallback
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[JSONStore] Error reading {file_path}: {e}")
                return fallback

    def _write_json_atomic(self, file_path: str, data: Any):
        with self._lock:
            temp_path = f"{file_path}.tmp.{int(time.time() * 1000)}"
            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(temp_path, file_path)
            except Exception as e:
                print(f"[JSONStore] Error writing {file_path}: {e}")
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                raise e

    # --- Printers ---
    def get_printers(self) -> List[Dict[str, Any]]:
        return self._read_json(self.printers_file, [])

    def get_printer(self, printer_id: str) -> Optional[Dict[str, Any]]:
        printers = self.get_printers()
        for p in printers:
            if p.get("id") == printer_id:
                return p
        return None

    def add_printer(self, printer_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            printers = self.get_printers()
            # Generate unique ID
            new_id = printer_data.get("id") or f"printer-{int(time.time()*1000)}"
            printer_data["id"] = new_id
            printer_data["created_at"] = time.time()
            if not printers:
                printer_data["is_default"] = True
            elif printer_data.get("is_default"):
                for p in printers:
                    p["is_default"] = False
            printers.append(printer_data)
            self._write_json_atomic(self.printers_file, printers)
            return printer_data

    def update_printer(self, printer_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            printers = self.get_printers()
            target = None
            for p in printers:
                if p.get("id") == printer_id:
                    if updates.get("is_default"):
                        for other in printers:
                            other["is_default"] = False
                    p.update(updates)
                    p["updated_at"] = time.time()
                    target = p
                    break
            if target:
                self._write_json_atomic(self.printers_file, printers)
            return target

    def delete_printer(self, printer_id: str) -> bool:
        with self._lock:
            printers = self.get_printers()
            initial_len = len(printers)
            printers = [p for p in printers if p.get("id") != printer_id]
            if len(printers) < initial_len:
                if printers and not any(p.get("is_default") for p in printers):
                    printers[0]["is_default"] = True
                self._write_json_atomic(self.printers_file, printers)
                return True
            return False

    # --- Settings ---
    def get_settings(self) -> Dict[str, Any]:
        return self._read_json(self.settings_file, {})

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            current = self.get_settings()
            
            # Deep update for nested dicts
            def deep_update(d, u):
                for k, v in u.items():
                    if isinstance(v, dict) and isinstance(d.get(k), dict):
                        deep_update(d[k], v)
                    else:
                        d[k] = v

            deep_update(current, updates)
            current["updated_at"] = time.time()
            self._write_json_atomic(self.settings_file, current)
            return current

    # --- AI Inspections ---
    def get_inspections(self, limit: int = 50) -> List[Dict[str, Any]]:
        inspections = self._read_json(self.inspections_file, [])
        return inspections[-limit:]

    def add_inspection(self, record: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            inspections = self._read_json(self.inspections_file, [])
            record["id"] = f"insp-{int(time.time()*1000)}"
            record["timestamp"] = time.time()
            inspections.append(record)
            # Retain last 200 inspections to keep JSON lightweight
            if len(inspections) > 200:
                inspections = inspections[-200:]
            self._write_json_atomic(self.inspections_file, inspections)
            return record

    # --- Timelapses / Videos ---
    def get_timelapses(self) -> List[Dict[str, Any]]:
        return self._read_json(self.timelapses_file, [])

    def add_timelapse(self, record: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            timelapses = self._read_json(self.timelapses_file, [])
            record["id"] = f"tl-{int(time.time()*1000)}"
            record["created_at"] = time.time()
            timelapses.insert(0, record)
            self._write_json_atomic(self.timelapses_file, timelapses)
            return record

    def delete_timelapse(self, tl_id: str) -> bool:
        with self._lock:
            timelapses = self._read_json(self.timelapses_file, [])
            new_list = [t for t in timelapses if t.get("id") != tl_id]
            if len(new_list) < len(timelapses):
                self._write_json_atomic(self.timelapses_file, new_list)
                return True
            return False

    # --- Bed Position State ---
    def get_bed_state(self, printer_id: str) -> Dict[str, Any]:
        all_states = self._read_json(self.bed_state_file, {})
        return all_states.get(printer_id, {"bed_position_pct": 0, "bed_position_z": 0.0})

    def set_bed_state(self, printer_id: str, pct: int, z_mm: float, note: str = ""):
        with self._lock:
            all_states = self._read_json(self.bed_state_file, {})
            all_states[printer_id] = {
                "bed_position_pct": max(0, min(100, int(round(pct)))),
                "bed_position_z": max(0.0, min(256.0, round(float(z_mm), 2))),
                "updated_at": time.time(),
                "note": note
            }
            self._write_json_atomic(self.bed_state_file, all_states)

    # --- Filament Inventory Management ---
    def get_filaments(self) -> List[Dict[str, Any]]:
        return self._read_json(self.filaments_file, [])

    def add_filament(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            filaments = self.get_filaments()
            new_id = data.get("id") or f"spool-{int(time.time()*1000)}"
            data["id"] = new_id
            data["created_at"] = time.time()
            data["remaining_grams"] = float(data.get("remaining_grams", 1000.0))
            data["initial_grams"] = float(data.get("initial_grams", 1000.0))
            filaments.insert(0, data)
            self._write_json_atomic(self.filaments_file, filaments)
            return data

    def update_filament(self, filament_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            filaments = self.get_filaments()
            target = None
            for f in filaments:
                if f.get("id") == filament_id:
                    f.update(updates)
                    f["updated_at"] = time.time()
                    target = f
                    break
            if target:
                self._write_json_atomic(self.filaments_file, filaments)
            return target

    def delete_filament(self, filament_id: str) -> bool:
        with self._lock:
            filaments = self.get_filaments()
            initial_len = len(filaments)
            filaments = [f for f in filaments if f.get("id") != filament_id]
            if len(filaments) < initial_len:
                self._write_json_atomic(self.filaments_file, filaments)
                return True
            return False
