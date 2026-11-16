"""
Own your bambu Cloud - Bambu Lab LAN Mode Multi-Printer Controller
Direct MQTT over TLS + FTPS management for Bambu 3D printers.
Zero external libraries - pure standard library socket & ssl.
Copyright (c) 2026 Ryan Ben Hassine (ryanbenhassine).
"""

import os
import ssl
import time
import json
import socket
import threading
from typing import Dict, Any, Optional, Callable

# MQTT 3.1.1 byte encoders
def _encode_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return len(b).to_bytes(2, "big") + b

def _encode_rem_len(length: int) -> bytes:
    rl = bytearray()
    while True:
        b = length % 128
        length //= 128
        if length > 0:
            b |= 128
        rl.append(b)
        if length <= 0:
            break
    return bytes(rl)

class BambuPrinterController:
    """Manages connection and commands for an individual Bambu printer."""
    def __init__(self, printer_config: Dict[str, Any]):
        self.config = printer_config
        self.ip = printer_config.get("ip", "")
        self.access_code = printer_config.get("access_code", "")
        self.serial = printer_config.get("serial", "")
        self.mqtt_port = int(printer_config.get("mqtt_port", 8883))
        self.camera_port = int(printer_config.get("camera_port", 6000))
        self.printer_id = printer_config.get("id", "printer-1")
        self.name = printer_config.get("name", "Bambu Printer")

        self.last_telemetry: Dict[str, Any] = {}
        self.last_update_time: float = 0
        self.last_action_time: float = time.time()
        self.last_state: str = "IDLE"
        self.is_connected: bool = False
        self._lock = threading.Lock()
        self._listener_thread: Optional[threading.Thread] = None
        self._running: bool = False

    def update_config(self, new_config: Dict[str, Any]):
        with self._lock:
            self.config = new_config
            self.ip = new_config.get("ip", self.ip)
            self.access_code = new_config.get("access_code", self.access_code)
            self.serial = new_config.get("serial", self.serial)
            self.name = new_config.get("name", self.name)

    def _create_ssl_socket(self, timeout: float = 4.0) -> ssl.SSLSocket:
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(timeout)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ssl_sock = ctx.wrap_socket(raw_sock, server_hostname=self.ip)
        ssl_sock.connect((self.ip, self.mqtt_port))
        return ssl_sock

    def send_command(self, payload_dict: Dict[str, Any]) -> bool:
        """Sends an MQTT command to device/<serial>/request topic."""
        if not self.ip or not self.access_code or not self.serial:
            return False

        topic = f"device/{self.serial}/request"
        payload = json.dumps(payload_dict)

        # Build MQTT CONNECT packet
        client_id = f"own_bambu_{int(time.time()*1000)}"
        var_header = b"\x00\x04MQTT\x04\xc2\x00\x3c" # Clean session, Username + Password flags
        payload_bytes = _encode_str(client_id) + _encode_str("bblp") + _encode_str(self.access_code)
        connect_packet = b"\x10" + _encode_rem_len(len(var_header) + len(payload_bytes)) + var_header + payload_bytes

        # Build MQTT PUBLISH packet (QoS 0)
        pub_var_header = _encode_str(topic)
        pub_payload = payload.encode("utf-8")
        publish_packet = b"\x30" + _encode_rem_len(len(pub_var_header) + len(pub_payload)) + pub_var_header + pub_payload

        # Disconnect packet
        disconnect_packet = b"\xe0\x00"

        try:
            s = self._create_ssl_socket(timeout=4.0)
            s.sendall(connect_packet)
            
            # Read CONNACK (4 bytes: 0x20, 0x02, flag, return_code)
            connack = s.recv(4)
            if len(connack) < 4 or connack[3] != 0:
                s.close()
                return False

            s.sendall(publish_packet)
            time.sleep(0.05)
            s.sendall(disconnect_packet)
            s.close()
            return True
        except Exception as e:
            print(f"[{self.name}] MQTT Send Error: {e}")
            return False

    def query_status(self, timeout: float = 4.0) -> Dict[str, Any]:
        """Queries status and waits for device/<serial>/report packet."""
        if not self.ip or not self.access_code or not self.serial:
            return {"error": "Printer configuration incomplete"}

        client_id = f"own_bambu_status_{int(time.time()*1000)}"
        var_header = b"\x00\x04MQTT\x04\xc2\x00\x3c"
        payload_bytes = _encode_str(client_id) + _encode_str("bblp") + _encode_str(self.access_code)
        connect_packet = b"\x10" + _encode_rem_len(len(var_header) + len(payload_bytes)) + var_header + payload_bytes

        # Subscribe to device/<serial>/report
        sub_topic = f"device/{self.serial}/report"
        sub_id = (1).to_bytes(2, "big")
        sub_payload = _encode_str(sub_topic) + b"\x00"
        subscribe_packet = b"\x82" + _encode_rem_len(len(sub_id) + len(sub_payload)) + sub_id + sub_payload

        # Request pushall
        pub_topic = f"device/{self.serial}/request"
        req_json = json.dumps({"pushing": {"sequence_id": "0", "command": "pushall"}}).encode("utf-8")
        pub_vh = _encode_str(pub_topic)
        pushall_packet = b"\x30" + _encode_rem_len(len(pub_vh) + len(req_json)) + pub_vh + req_json

        start_time = time.time()
        buf = bytearray()
        parsed_status: Dict[str, Any] = {}

        try:
            s = self._create_ssl_socket(timeout=timeout)
            s.sendall(connect_packet)
            connack = s.recv(4)
            if len(connack) < 4 or connack[3] != 0:
                s.close()
                return {"error": "Authentication failed"}

            s.sendall(subscribe_packet)
            suback = s.recv(5)

            s.sendall(pushall_packet)

            # Read responses
            while time.time() - start_time < timeout:
                try:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buf.extend(chunk)

                    # Extract JSON packets
                    while True:
                        brace_start = buf.find(b'{"print":')
                        if brace_start == -1:
                            brace_start = buf.find(b'{"device":')
                        if brace_start == -1:
                            break

                        depth = 0
                        end_pos = -1
                        for i in range(brace_start, len(buf)):
                            if buf[i] == ord(b'{'):
                                depth += 1
                            elif buf[i] == ord(b'}'):
                                depth -= 1
                                if depth == 0:
                                    end_pos = i + 1
                                    break

                        if end_pos != -1:
                            raw_json = buf[brace_start:end_pos].decode("utf-8", errors="ignore")
                            buf = buf[end_pos:]
                            try:
                                data = json.loads(raw_json)
                                print_data = data.get("print", {})
                                if print_data:
                                    parsed_status.update(self._format_telemetry(print_data))
                                    if "gcode_state" in print_data:
                                        s.sendall(b"\xe0\x00")
                                        s.close()
                                        with self._lock:
                                            self.last_telemetry = parsed_status
                                            self.last_update_time = time.time()
                                            self.is_connected = True
                                        return parsed_status
                            except Exception:
                                pass
                        else:
                            break
                except socket.timeout:
                    break

            s.close()
        except Exception as e:
            with self._lock:
                self.is_connected = False
            return {"error": str(e), "is_online": False}

        if parsed_status:
            with self._lock:
                self.last_telemetry = parsed_status
                self.last_update_time = time.time()
                self.is_connected = True
            return parsed_status

        return {"error": "No response from printer", "is_online": False}

    def _format_telemetry(self, print_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translates raw Bambu MQTT print node into clean, unified telemetry."""
        gcode_state = print_data.get("gcode_state", "UNKNOWN")
        nozzle_temper = float(print_data.get("nozzle_temper", 0.0))
        nozzle_target_temper = float(print_data.get("nozzle_target_temper", 0.0))
        bed_temper = float(print_data.get("bed_temper", 0.0))
        bed_target_temper = float(print_data.get("bed_target_temper", 0.0))
        chamber_temper = float(print_data.get("chamber_temper", 0.0))
        
        # Fans
        cooling_fan_speed = int(print_data.get("cooling_fan_speed", 0)) # 0-15 scale
        heatbreak_fan_speed = int(print_data.get("heatbreak_fan_speed", 0))
        big_fan1_speed = int(print_data.get("big_fan1_speed", 0)) # Aux fan
        big_fan2_speed = int(print_data.get("big_fan2_speed", 0)) # Chamber fan

        # Progress
        mc_percent = int(print_data.get("mc_percent", 0))
        mc_remaining_time = int(print_data.get("mc_remaining_time", 0)) # minutes
        layer_num = int(print_data.get("layer_num", 0))
        total_layer_num = int(print_data.get("total_layer_num", 0))
        subtask_name = print_data.get("subtask_name") or print_data.get("gcode_file", "")
        
        # Speed mode
        spd_mag = int(print_data.get("spd_mag", 100))
        spd_lvl = int(print_data.get("spd_lvl", 2)) # 1: Silent, 2: Standard, 3: Sport, 4: Ludicrous
        speed_labels = {1: "Silent (50%)", 2: "Standard (100%)", 3: "Sport (124%)", 4: "Ludicrous (166%)"}

        # Chamber light
        lights_report = print_data.get("lights_report", [])
        chamber_light = False
        for l in lights_report:
            if l.get("node") == "chamber_light":
                chamber_light = (l.get("mode") == "on")
                break

        # Auto Light-Off Watchdog: Turn off when print finishes or after 180s idle
        if gcode_state in ["FINISH", "IDLE"] and self.last_state == "RUNNING" and chamber_light:
            print(f"[{self.name}] Print finished. Auto turning chamber light OFF.")
            threading.Thread(target=self.set_chamber_light, args=(False,), daemon=True).start()
        elif gcode_state in ["FINISH", "IDLE"] and chamber_light and (time.time() - self.last_action_time > 180):
            print(f"[{self.name}] Inactive for >180s. Auto turning chamber light OFF.")
            threading.Thread(target=self.set_chamber_light, args=(False,), daemon=True).start()
        self.last_state = gcode_state

        # AMS Spools
        ams_data = print_data.get("ams", {})
        ams_list = []
        if ams_data and "ams" in ams_data:
            for ams_unit in ams_data.get("ams", []):
                unit_id = ams_unit.get("id", "0")
                trays = []
                for tray in ams_unit.get("tray", []):
                    tray_id = tray.get("id", "0")
                    tray_color = tray.get("tray_color", "FFFFFF")
                    tray_type = tray.get("tray_type", "PLA")
                    remain_pct = tray.get("remain", 100)
                    trays.append({
                        "tray_id": tray_id,
                        "color_hex": f"#{tray_color[:6]}",
                        "material": tray_type,
                        "remain_pct": remain_pct
                    })
                ams_list.append({"ams_id": unit_id, "trays": trays})

        return {
            "printer_id": self.printer_id,
            "printer_name": self.name,
            "model": self.config.get("model", "P1S"),
            "ip": self.ip,
            "serial": self.serial,
            "is_online": True,
            "gcode_state": gcode_state,
            "subtask_name": subtask_name,
            "progress_pct": mc_percent,
            "remaining_minutes": mc_remaining_time,
            "layer_num": layer_num,
            "total_layer_num": total_layer_num,
            "nozzle_temp": round(nozzle_temper, 1),
            "nozzle_target": round(nozzle_target_temper, 1),
            "bed_temp": round(bed_temper, 1),
            "bed_target": round(bed_target_temper, 1),
            "chamber_temp": round(chamber_temper, 1),
            "fans": {
                "part_cooling_pct": int(min(100, round((cooling_fan_speed / 15.0) * 100))),
                "aux_pct": int(min(100, round((big_fan1_speed / 15.0) * 100))),
                "chamber_pct": int(min(100, round((big_fan2_speed / 15.0) * 100)))
            },
            "speed_mode": {
                "level": spd_lvl,
                "label": speed_labels.get(spd_lvl, "Standard (100%)"),
                "magnitude": spd_mag
            },
            "chamber_light": chamber_light,
            "wifi_signal": print_data.get("wifi_signal", "-55dBm"),
            "ams": ams_list,
            "updated_at": time.time()
        }

    # --- Actions & Controls ---
    def record_user_action(self):
        self.last_action_time = time.time()

    def set_chamber_light(self, on: bool) -> bool:
        self.record_user_action()
        mode = "on" if on else "off"
        cmd = {
            "system": {
                "sequence_id": "0",
                "command": "ledctrl",
                "led_node": "chamber_light",
                "led_mode": mode,
                "led_on_time": 500,
                "led_off_time": 500,
                "loop_times": 0,
                "interval_time": 0
            }
        }
        return self.send_command(cmd)

    def pause_print(self) -> bool:
        self.record_user_action()
        return self.send_command({"print": {"sequence_id": "0", "command": "pause"}})

    def resume_print(self) -> bool:
        self.record_user_action()
        return self.send_command({"print": {"sequence_id": "0", "command": "resume"}})

    def stop_print(self) -> bool:
        self.record_user_action()
        return self.send_command({"print": {"sequence_id": "0", "command": "stop"}})

    def assign_ams_tray(self, ams_id: int, tray_id: int, color_hex: str, tray_type: str, nozzle_temp_min: int = 190, nozzle_temp_max: int = 240) -> bool:
        """Configures filament color & material directly to AMS tray."""
        self.record_user_action()
        clean_color = color_hex.lstrip("#").upper()
        if len(clean_color) == 6:
            clean_color += "FF"
        cmd = {
            "print": {
                "sequence_id": "0",
                "command": "ams_filament_setting",
                "ams_id": int(ams_id),
                "tray_id": int(tray_id),
                "tray_color": clean_color,
                "tray_type": tray_type,
                "nozzle_temp_min": nozzle_temp_min,
                "nozzle_temp_max": nozzle_temp_max
            }
        }
        return self.send_command(cmd)

    def set_speed_level(self, level: int) -> bool:
        # level: 1 (Silent), 2 (Standard), 3 (Sport), 4 (Ludicrous)
        return self.send_command({
            "print": {
                "sequence_id": "0",
                "command": "print_speed",
                "param": str(max(1, min(4, level)))
            }
        })

    def send_gcode(self, gcode_str: str) -> bool:
        clean = gcode_str.strip()
        if not clean.endswith("\n"):
            clean += "\n"
        return self.send_command({
            "print": {
                "sequence_id": "0",
                "command": "gcode_line",
                "param": clean
            }
        })

    # --- Smart Positioning ---
    def position_service(self) -> bool:
        """Service position: bed down to 70% (~Z180) and head to front-center (X128 Y20)."""
        gcode = "G90\nM204 S5000\nG1 Z180 F3000\nG1 X128 Y20 F9000\n"
        return self.send_gcode(gcode)

    def position_trash(self) -> bool:
        """Purge chute position: head to poop bucket (X65 Y245)."""
        gcode = "G90\nG1 X65 Y245 F12000\n"
        return self.send_gcode(gcode)

    def position_bump(self) -> bool:
        """Stringing cleanup: drops bed to Z250 and returns to Z20."""
        gcode = "G90\nG1 Z250 F4000\nG4 P500\nG1 Z20 F4000\n"
        return self.send_gcode(gcode)

    def position_center(self) -> bool:
        """Moves head to bed center (X128 Y128)."""
        gcode = "G90\nG1 X128 Y128 F9000\n"
        return self.send_gcode(gcode)

    def position_home(self) -> bool:
        """Auto-home printer."""
        return self.send_gcode("G28\n")

    def move_bed_pct(self, pct: int) -> bool:
        """Sets bed position from 0% (Z0 top) to 100% (Z256 bottom)."""
        pct = max(0, min(100, int(round(pct))))
        z_mm = round((pct / 100.0) * 256.0, 1)
        gcode = f"G90\nG1 Z{z_mm} F3000\n"
        return self.send_gcode(gcode)

    def jog(self, axis: str, dist_mm: float) -> bool:
        axis = axis.upper()
        if axis not in ["X", "Y", "Z"]:
            return False
        feed = 9000 if axis in ["X", "Y"] else 3000
        gcode = f"G91\nG1 {axis}{dist_mm} F{feed}\nG90\n"
        return self.send_gcode(gcode)


class BambuMultiPrinterManager:
    """Orchestrates multiple Bambu Lab printers concurrently."""
    def __init__(self, json_store):
        self.store = json_store
        self.controllers: Dict[str, BambuPrinterController] = {}
        self._lock = threading.Lock()
        self.sync_from_store()

    def sync_from_store(self):
        with self._lock:
            printers = self.store.get_printers()
            active_ids = {p["id"] for p in printers}

            # Remove deleted
            for pid in list(self.controllers.keys()):
                if pid not in active_ids:
                    del self.controllers[pid]

            # Add or update
            for p in printers:
                pid = p["id"]
                if pid in self.controllers:
                    self.controllers[pid].update_config(p)
                else:
                    self.controllers[pid] = BambuPrinterController(p)

    def get_controller(self, printer_id: str) -> Optional[BambuPrinterController]:
        self.sync_from_store()
        with self._lock:
            return self.controllers.get(printer_id)

    def get_all_telemetry(self) -> Dict[str, Any]:
        self.sync_from_store()
        telemetry_map = {}
        with self._lock:
            ctrls = list(self.controllers.items())

        for pid, ctrl in ctrls:
            # Query if cached telemetry is older than 4 seconds
            if time.time() - ctrl.last_update_time > 4.0:
                telemetry_map[pid] = ctrl.query_status(timeout=2.5)
            else:
                telemetry_map[pid] = ctrl.last_telemetry
        return telemetry_map
