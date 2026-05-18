import tkinter as tk
from tkinter import messagebox
import socket
import threading
import time
import csv
import datetime

# ==========================================
# 1. Communication Setup (UDP Only)
# ==========================================
UDP_IP_BIND = "0.0.0.0"   
UDP_IP_SEND = "127.0.0.1" 
CMD_PORT = 9999           
DATA_PORT = 9998          

sock_cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_data = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_data.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
sock_data.bind((UDP_IP_BIND, DATA_PORT))

# ==========================================
# 2. Global State & Logging Variables
# ==========================================
current_data = {
    'go1_vx': 0.0, 'go1_yaw_rate': 0.0,
    'go1_r': 0.0, 'go1_p': 0.0, 'go1_y': 0.0,
    'go1_ax': 0.0, 'go1_ay': 0.0, 'go1_az': 0.0,
    'stab_r': 0.0, 'stab_p': 0.0,
    'obj_r': 0.0, 'obj_p': 0.0
}

is_recording = False
csv_file = None
csv_writer = None
start_time_record = 0.0

class Go1Commander(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Go1 Stabilizer Commander - Pro")
        self.geometry("450x650") # UI가 늘어나서 창 크기 증가
        self.configure(padx=20, pady=20)

        self.is_walking = False
        self.current_mode = 1 # 💡 기본 모드: 1 (Stand / Lock)
        self.target_vx = 0.0
        self.target_yaw = 0.0
        self.target_pitch = 0.0
        self.target_roll = 0.0
        self.walk_end_time = 0.0

        self.create_widgets()
        threading.Thread(target=self.receive_data_loop, daemon=True).start()
        self.send_cmd_loop() 

    def create_widgets(self):
        # 💡 1. 로봇 자세 제어 패널 (신규 추가)
        frame_posture = tk.LabelFrame(self, text="🤖 Robot Posture Control", font=("Arial", 10, "bold"), fg="blue", padx=5, pady=5)
        frame_posture.pack(fill=tk.X, pady=(0, 15))

        btn_down = tk.Button(frame_posture, text="🛌 Down (5)", command=lambda: self.set_mode(5))
        btn_down.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        btn_up = tk.Button(frame_posture, text="🧍 Up (6)", command=lambda: self.set_mode(6))
        btn_up.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        btn_recover = tk.Button(frame_posture, text="🔄 Recover (8)", command=lambda: self.set_mode(8))
        btn_recover.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        btn_stand = tk.Button(frame_posture, text="🛑 Stand (1)", bg="lightgray", command=lambda: self.set_mode(1))
        btn_stand.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # 2. 이동 명령 패널
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

        self.lbl_status = tk.Label(self, text="Status: Standby (1)", fg="blue", font=("Arial", 12, "bold"))
        self.lbl_status.pack(pady=10)

        # 3. 주행 버튼 패널
        btn_frame1 = tk.Frame(self)
        btn_frame1.pack(fill=tk.X, pady=5)

        self.btn_run = tk.Button(btn_frame1, text="▶ RUN (No Record)", bg="lightblue", font=("Arial", 11, "bold"), 
                                 command=lambda: self.start_walk(record=False))
        self.btn_run.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2, ipady=8)

        self.btn_run_rec = tk.Button(btn_frame1, text="⏺ RUN & RECORD", bg="lightgreen", font=("Arial", 11, "bold"), 
                                     command=lambda: self.start_walk(record=True))
        self.btn_run_rec.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2, ipady=8)

        self.btn_stop = tk.Button(self, text="🛑 E-STOP", bg="red", fg="white", font=("Arial", 12, "bold"), command=self.emergency_stop)
        self.btn_stop.pack(fill=tk.X, pady=10, ipady=8)

        # 4. 데이터 모니터링 라벨
        self.lbl_debug = tk.Label(self, text="Stab: 0.0 | Obj: 0.0", font=("Arial", 9))
        self.lbl_debug.pack(side=tk.BOTTOM, pady=10)

    # 💡 모드 변경 함수
    def set_mode(self, mode_val):
        if self.is_walking:
            messagebox.showwarning("Warning", "Cannot change posture while walking!")
            return
        self.current_mode = mode_val
        
        mode_names = {1: "Stand (1)", 5: "Stand Down (5)", 6: "Stand Up (6)", 8: "Recovery (8)"}
        self.lbl_status.config(text=f"Status: {mode_names.get(mode_val, 'Unknown')}", fg="blue")

    def start_recording(self):
        global is_recording, csv_file, csv_writer, start_time_record
        filename = f"stabilizer_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_file = open(filename, mode='w', newline='')
        csv_writer = csv.writer(csv_file)
        
        headers = [
            'Time(s)', 'Target_Vx', 'Go1_Vx', 'Target_YawRate', 'Go1_YawRate',
            'Target_Roll', 'Go1_Roll', 'Stab_Roll', 'Obj_Roll',
            'Target_Pitch', 'Go1_Pitch', 'Stab_Pitch', 'Obj_Pitch',
            'Go1_Accel_X', 'Go1_Accel_Y', 'Go1_Accel_Z'
        ]
        csv_writer.writerow(headers)
        start_time_record = time.time()
        is_recording = True
        print(f"[Logging] Started: {filename}")

    def stop_recording(self):
        global is_recording, csv_file
        is_recording = False
        if csv_file: csv_file.close()
        print("[Logging] Stopped and Saved.")

    def start_walk(self, record=False):
        try:
            vx = float(self.entry_speed.get())
            dist = float(self.entry_dist.get())
            radius = float(self.entry_radius.get())

            if vx == 0 or dist <= 0: return
            
            # 주행을 시작하기 전에는 항상 1(Stand) 모드로 리셋 후 2(Walk)로 넘어가는 것이 안전합니다.
            self.current_mode = 1 
            if record: self.start_recording()

            duration = dist / abs(vx)
            yaw_rate = (vx / radius) if radius != 0 else 0.0

            self.target_vx = vx; self.target_yaw = yaw_rate
            self.target_pitch = 0.0; self.target_roll = 0.0
            self.walk_end_time = time.time() + duration
            self.is_walking = True

            status_text = "Walking & Recording" if record else "Walking (No Rec)"
            self.lbl_status.config(text=f"Status: {status_text} ({duration:.1f}s)", fg="green")
            self.btn_run.config(state=tk.DISABLED); self.btn_run_rec.config(state=tk.DISABLED)

        except ValueError:
            pass

    def emergency_stop(self):
        self.is_walking = False
        self.current_mode = 1 # E-STOP 시 모터 락(1) 모드로 전환
        self.target_vx = 0.0; self.target_yaw = 0.0
        self.lbl_status.config(text="Status: E-STOP (Stand)", fg="red")
        self.btn_run.config(state=tk.NORMAL); self.btn_run_rec.config(state=tk.NORMAL)
        global is_recording
        if is_recording: self.stop_recording()

    def receive_data_loop(self):
        while True:
            try:
                data, _ = sock_data.recvfrom(1024)
                msg = data.decode('utf-8').strip()
                parts = msg.split(',')
                
                if msg.startswith("GO1,") and len(parts) >= 9:
                    current_data['go1_vx'] = float(parts[1])
                    current_data['go1_yaw_rate'] = float(parts[2])
                    current_data['go1_r'] = float(parts[3])
                    current_data['go1_p'] = float(parts[4])
                    current_data['go1_y'] = float(parts[5])
                    current_data['go1_ax'] = float(parts[6])
                    current_data['go1_ay'] = float(parts[7])
                    current_data['go1_az'] = float(parts[8])
                
                elif msg.startswith("STAB,") and len(parts) >= 3:
                    current_data['stab_r'] = float(parts[1])
                    current_data['stab_p'] = float(parts[2])
                
                elif msg.startswith("OBJ,") and len(parts) >= 3:
                    current_data['obj_r'] = float(parts[1])
                    current_data['obj_p'] = float(parts[2])
                    
            except Exception:
                pass

    def send_cmd_loop(self):
        global is_recording, csv_writer, start_time_record

        self.lbl_debug.config(text=f"Stab_P: {current_data['stab_p']:.1f}° | Obj_P: {current_data['obj_p']:.1f}°")

        if self.is_walking and time.time() > self.walk_end_time:
            self.is_walking = False
            self.current_mode = 1 # 걷기 종료 시 Stand 모드로 복귀
            self.target_vx = 0.0; self.target_yaw = 0.0
            self.lbl_status.config(text="Status: Walk Completed", fg="blue")
            self.btn_run.config(state=tk.NORMAL); self.btn_run_rec.config(state=tk.NORMAL)
            if is_recording: self.stop_recording()

        # 💡 현재 상태에 따라 보낼 모드 결정 (걷기 중이면 무조건 2, 아니면 UI에서 선택한 모드)
        active_mode = 2 if self.is_walking else self.current_mode
        cmd_str = f"CMD,{active_mode},{self.target_vx:.3f},{self.target_yaw:.3f},{self.target_pitch:.3f}"
        sock_cmd.sendto(cmd_str.encode('utf-8'), (UDP_IP_SEND, CMD_PORT))

        if is_recording and csv_writer:
            elapsed = time.time() - start_time_record
            row = [
                f"{elapsed:.3f}",
                f"{self.target_vx:.3f}", f"{current_data['go1_vx']:.3f}",
                f"{self.target_yaw:.3f}", f"{current_data['go1_yaw_rate']:.3f}",
                f"{self.target_roll:.3f}", f"{current_data['go1_r']:.3f}", f"{current_data['stab_r']:.3f}", f"{current_data['obj_r']:.3f}",
                f"{self.target_pitch:.3f}", f"{current_data['go1_p']:.3f}", f"{current_data['stab_p']:.3f}", f"{current_data['obj_p']:.3f}",
                f"{current_data['go1_ax']:.3f}", f"{current_data['go1_ay']:.3f}", f"{current_data['go1_az']:.3f}"
            ]
            csv_writer.writerow(row)

        self.after(10, self.send_cmd_loop)

if __name__ == "__main__":
    app = Go1Commander()
    app.mainloop()