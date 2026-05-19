import tkinter as tk
from tkinter import messagebox
import socket
import time

# --- 통신 설정 ---
UDP_IP_SEND = "127.0.0.1" 
CMD_PORT = 9999       # -> C++ 엔진 (Go1 모터 제어)
INTERNAL_PORT = 9995  # -> data_collection.py (상태 및 타겟 전달)

sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

class Go1Commander(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Go1 Controller (Control Only)")
        self.geometry("450x600")
        self.configure(padx=20, pady=20)

        self.is_walking = False
        self.is_recording = False
        self.current_mode = 1
        
        # 💡 제어 변수들
        self.target_vx = 0.0
        self.target_yaw = 0.0
        self.target_pitch = 0.0
        self.target_roll = 0.0
        self.target_dist = 0.0     # 추가됨
        self.target_radius = 0.0   # 추가됨
        self.walk_end_time = 0.0

        self.create_widgets()
        self.send_cmd_loop() # 100Hz 루프 시작

    def create_widgets(self):
        frame_posture = tk.LabelFrame(self, text="🤖 Robot Posture Control", font=("Arial", 10, "bold"), fg="blue", padx=5, pady=5)
        frame_posture.pack(fill=tk.X, pady=(0, 15))

        tk.Button(frame_posture, text="🛌 Down (5)", command=lambda: self.set_mode(5)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(frame_posture, text="🧍 Up (6)", command=lambda: self.set_mode(6)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(frame_posture, text="🔄 Recover (8)", command=lambda: self.set_mode(8)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(frame_posture, text="🛑 Stand (1)", bg="lightgray", command=lambda: self.set_mode(1)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        tk.Label(self, text="Forward Speed (m/s) [+:Fwd, -:Bwd]", font=("Arial", 10, "bold")).pack(pady=(2, 0))
        self.entry_speed = tk.Entry(self, justify='center', font=("Arial", 12))
        self.entry_speed.insert(0, "0.3")
        self.entry_speed.pack(pady=5)

        tk.Label(self, text="Travel Distance (m)", font=("Arial", 10, "bold")).pack(pady=(2, 0))
        self.entry_dist = tk.Entry(self, justify='center', font=("Arial", 12))
        self.entry_dist.insert(0, "1.0")
        self.entry_dist.pack(pady=5)

        tk.Label(self, text="Turning Radius (m) [0:Straight, +:L, -:R]", font=("Arial", 10, "bold")).pack(pady=(2, 0))
        self.entry_radius = tk.Entry(self, justify='center', font=("Arial", 12))
        self.entry_radius.insert(0, "0.0")
        self.entry_radius.pack(pady=5)

        self.lbl_status = tk.Label(self, text="Status: Stand (1)", fg="blue", font=("Arial", 12, "bold"))
        self.lbl_status.pack(pady=10)

        btn_frame1 = tk.Frame(self)
        btn_frame1.pack(fill=tk.X, pady=5)

        self.btn_run = tk.Button(btn_frame1, text="▶ RUN (No Record)", bg="lightblue", font=("Arial", 11, "bold"), command=lambda: self.start_walk(record=False))
        self.btn_run.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2, ipady=8)

        self.btn_run_rec = tk.Button(btn_frame1, text="⏺ RUN & RECORD", bg="lightgreen", font=("Arial", 11, "bold"), command=lambda: self.start_walk(record=True))
        self.btn_run_rec.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2, ipady=8)

        self.btn_stop = tk.Button(self, text="🛑 E-STOP", bg="red", fg="white", font=("Arial", 12, "bold"), command=self.emergency_stop)
        self.btn_stop.pack(fill=tk.X, pady=10, ipady=8)

    def set_mode(self, mode_val):
        if self.is_walking:
            messagebox.showwarning("Warning", "Cannot change posture while walking!")
            return
        self.current_mode = mode_val
        mode_names = {1: "Stand (1)", 5: "Stand Down (5)", 6: "Stand Up (6)", 8: "Recovery (8)"}
        self.lbl_status.config(text=f"Status: {mode_names.get(mode_val, 'Unknown')}", fg="blue")

    def start_walk(self, record=False):
        try:
            vx = float(self.entry_speed.get())
            dist = float(self.entry_dist.get())
            radius = float(self.entry_radius.get())

            if vx == 0 or dist <= 0: return

            self.current_mode = 1 
            self.is_recording = record 

            duration = dist / abs(vx)
            self.target_vx = vx
            self.target_yaw = (vx / radius) if radius != 0 else 0.0
            
            # 💡 입력받은 거리와 반경 저장
            self.target_dist = dist
            self.target_radius = radius
            
            self.walk_end_time = time.time() + duration
            self.is_walking = True

            status_text = "Walking & Recording" if record else "Walking (No Rec)"
            self.lbl_status.config(text=f"Status: {status_text} ({duration:.1f}s)", fg="green")
            self.btn_run.config(state=tk.DISABLED)
            self.btn_run_rec.config(state=tk.DISABLED)

        except ValueError:
            pass

    def emergency_stop(self):
        self.is_walking = False
        self.is_recording = False
        self.current_mode = 1
        self.target_vx = 0.0
        self.target_yaw = 0.0
        self.target_dist = 0.0
        self.target_radius = 0.0
        self.lbl_status.config(text="Status: E-STOP (Stand)", fg="red")
        self.btn_run.config(state=tk.NORMAL)
        self.btn_run_rec.config(state=tk.NORMAL)

    def send_cmd_loop(self):
        if self.is_walking and time.time() > self.walk_end_time:
            self.is_walking = False
            self.is_recording = False
            self.current_mode = 1
            self.target_vx = 0.0
            self.target_yaw = 0.0
            self.target_dist = 0.0
            self.target_radius = 0.0
            self.lbl_status.config(text="Status: Walk Completed", fg="blue")
            self.btn_run.config(state=tk.NORMAL)
            self.btn_run_rec.config(state=tk.NORMAL)

        # 1. C++ 엔진 송신
        active_mode = 2 if self.is_walking else self.current_mode
        cmd_str = f"CMD,{active_mode},{self.target_vx:.3f},{self.target_yaw:.3f},{self.target_pitch:.3f}"
        sock_out.sendto(cmd_str.encode('utf-8'), (UDP_IP_SEND, CMD_PORT))

        # 2. 💡 수집기(data_collection.py)로 내부 상태 송신 (dist와 radius 포함 총 8개 항목)
        rec_flag = 1 if self.is_recording else 0
        sync_str = f"CTRL,{rec_flag},{self.target_vx:.3f},{self.target_yaw:.3f},{self.target_roll:.3f},{self.target_pitch:.3f},{self.target_dist:.3f},{self.target_radius:.3f}"
        sock_out.sendto(sync_str.encode('utf-8'), (UDP_IP_SEND, INTERNAL_PORT))

        self.after(10, self.send_cmd_loop)

if __name__ == "__main__":
    app = Go1Commander()
    app.mainloop()