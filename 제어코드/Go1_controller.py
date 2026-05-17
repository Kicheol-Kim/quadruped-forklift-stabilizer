import tkinter as tk
from tkinter import messagebox
import socket
import threading
import time
import math
import csv
import datetime

# ==========================================
# 1. Communication Setup (Local UDP with C++ Engine)
# ==========================================
UDP_IP = "127.0.0.1"
CMD_PORT = 9999  # Port to send commands TO C++ engine
DATA_PORT = 9998 # Port to receive data FROM C++ engine

sock_cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_data = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_data.bind((UDP_IP, DATA_PORT))

# ==========================================
# 2. Global State & Logging Variables (3-Node Architecture)
# ==========================================
# 향후 3곳에서 들어올 데이터를 위한 임시/전역 변수 딕셔너리
current_data = {
    # 1. Go1 Robot IMU & State (From C++ Engine)
    'go1_vx': 0.0, 'go1_yaw_rate': 0.0,
    'go1_r': 0.0, 'go1_p': 0.0, 'go1_y': 0.0,
    'go1_ax': 0.0, 'go1_ay': 0.0, 'go1_az': 0.0,
    
    # 2. Stabilizer Base IMU (From Arduino RP2040 - Temp)
    'stab_r': 0.0, 'stab_p': 0.0,
    
    # 3. Payload / Object IMU (From End-effector - Temp)
    'obj_r': 0.0, 'obj_p': 0.0
}

is_recording = False
csv_file = None
csv_writer = None
start_time_record = 0.0

class Go1Commander(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Go1 Stabilizer Commander - Advanced")
        self.geometry("450x550")
        self.configure(padx=20, pady=20)

        # Robot Command State
        self.is_walking = False
        self.target_vx = 0.0
        self.target_yaw = 0.0
        self.target_pitch = 0.0
        self.target_roll = 0.0 # 스태빌라이저 기본 수평 목표값
        self.walk_end_time = 0.0

        self.create_widgets()
        
        # Start background threads for Data Rx and Command Tx
        threading.Thread(target=self.receive_data_loop, daemon=True).start()
        self.send_cmd_loop() # 100Hz Tick Loop

    def create_widgets(self):
        # 1. Forward Speed
        tk.Label(self, text="Forward Speed (m/s) [+:Fwd, -:Bwd]", font=("Arial", 10, "bold")).pack(pady=(2, 0))
        self.entry_speed = tk.Entry(self, justify='center', font=("Arial", 12))
        self.entry_speed.insert(0, "0.3")
        self.entry_speed.pack(pady=5)

        # 2. Travel Distance
        tk.Label(self, text="Travel Distance (m)", font=("Arial", 10, "bold")).pack(pady=(2, 0))
        self.entry_dist = tk.Entry(self, justify='center', font=("Arial", 12))
        self.entry_dist.insert(0, "1.0")
        self.entry_dist.pack(pady=5)

        # 3. Turning Radius
        tk.Label(self, text="Turning Radius (m) [0:Straight, +:L, -:R]", font=("Arial", 10, "bold")).pack(pady=(2, 0))
        self.entry_radius = tk.Entry(self, justify='center', font=("Arial", 12))
        self.entry_radius.insert(0, "0.0")
        self.entry_radius.pack(pady=5)

        # Status Label
        self.lbl_status = tk.Label(self, text="Status: Standby", fg="blue", font=("Arial", 12, "bold"))
        self.lbl_status.pack(pady=10)

        # Button Frame (RUN vs RUN & RECORD)
        btn_frame1 = tk.Frame(self)
        btn_frame1.pack(fill=tk.X, pady=5)

        self.btn_run = tk.Button(btn_frame1, text="▶ RUN (No Record)", bg="lightblue", font=("Arial", 11, "bold"), 
                                 command=lambda: self.start_walk(record=False))
        self.btn_run.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2, ipady=8)

        self.btn_run_rec = tk.Button(btn_frame1, text="⏺ RUN & RECORD", bg="lightgreen", font=("Arial", 11, "bold"), 
                                     command=lambda: self.start_walk(record=True))
        self.btn_run_rec.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2, ipady=8)

        # E-STOP Button
        self.btn_stop = tk.Button(self, text="🛑 E-STOP", bg="red", fg="white", font=("Arial", 12, "bold"), command=self.emergency_stop)
        self.btn_stop.pack(fill=tk.X, pady=10, ipady=8)

    def start_recording(self):
        global is_recording, csv_file, csv_writer, start_time_record
        filename = f"stabilizer_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_file = open(filename, mode='w', newline='')
        csv_writer = csv.writer(csv_file)
        
        # CSV 헤더: Target과 Actual 값을 번갈아가며(Interleaved) 배치
        headers = [
            'Time(s)', 
            'Target_Vx', 'Go1_Vx',
            'Target_YawRate', 'Go1_YawRate',
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
        if csv_file: 
            csv_file.close()
        print("[Logging] Stopped and Saved.")

    def start_walk(self, record=False):
        try:
            vx = float(self.entry_speed.get())
            dist = float(self.entry_dist.get())
            radius = float(self.entry_radius.get())

            if vx == 0 or dist <= 0:
                messagebox.showwarning("Input Error", "Speed cannot be 0, and distance must be positive.")
                return

            # Logging 설정
            if record:
                self.start_recording()

            # Kinematics Calculation
            duration = dist / abs(vx)
            yaw_rate = (vx / radius) if radius != 0 else 0.0

            # Update State
            self.target_vx = vx
            self.target_yaw = yaw_rate
            self.target_pitch = 0.0
            self.target_roll = 0.0
            self.walk_end_time = time.time() + duration
            self.is_walking = True

            status_text = "Walking & Recording" if record else "Walking (No Rec)"
            self.lbl_status.config(text=f"Status: {status_text} ({duration:.1f}s)", fg="green")
            self.btn_run.config(state=tk.DISABLED)
            self.btn_run_rec.config(state=tk.DISABLED)

        except ValueError:
            messagebox.showerror("Input Error", "Please enter numeric values only.")

    def emergency_stop(self):
        self.is_walking = False
        self.target_vx = 0.0
        self.target_yaw = 0.0
        self.lbl_status.config(text="Status: E-STOP Triggered", fg="red")
        self.btn_run.config(state=tk.NORMAL)
        self.btn_run_rec.config(state=tk.NORMAL)
        
        global is_recording
        if is_recording:
            self.stop_recording()

    def receive_data_loop(self):
        """Receive Robot IMU & State data."""
        while True:
            try:
                data, _ = sock_data.recvfrom(1024)
                msg = data.decode('utf-8')
                
                if msg.startswith("GO1,"):
                    parts = msg.split(',')
                    # 데이터가 'GO1' 포함 총 9조각이면 파싱
                    if len(parts) >= 9:
                        current_data['go1_vx'] = float(parts[1])
                        current_data['go1_yaw_rate'] = float(parts[2])
                        current_data['go1_r'] = float(parts[3])
                        current_data['go1_p'] = float(parts[4])
                        current_data['go1_y'] = float(parts[5])
                        current_data['go1_ax'] = float(parts[6])
                        current_data['go1_ay'] = float(parts[7])
                        current_data['go1_az'] = float(parts[8])
            except Exception:
                pass

    def send_cmd_loop(self):
        """Send Control Command to C++ Engine at 100Hz (10ms interval)"""
        global is_recording, csv_writer, start_time_record

        # Check for Walk Completion
        if self.is_walking and time.time() > self.walk_end_time:
            self.is_walking = False
            self.target_vx = 0.0
            self.target_yaw = 0.0
            self.lbl_status.config(text="Status: Walk Completed", fg="blue")
            self.btn_run.config(state=tk.NORMAL)
            self.btn_run_rec.config(state=tk.NORMAL)
            
            if is_recording:
                self.stop_recording()

        # Generate Protocol String (1: Stand, 2: Walk)
        mode = 2 if self.is_walking else 1
        cmd_str = f"CMD,{mode},{self.target_vx:.3f},{self.target_yaw:.3f},{self.target_pitch:.3f}"
        sock_cmd.sendto(cmd_str.encode('utf-8'), (UDP_IP, CMD_PORT))

        # Data Logging (Interleaved Target vs Actual)
        if is_recording and csv_writer:
            elapsed = time.time() - start_time_record
            
            # 소수점 3자리로 통일하여 깔끔하게 저장
            row = [
                f"{elapsed:.3f}",
                f"{self.target_vx:.3f}", f"{current_data['go1_vx']:.3f}",
                f"{self.target_yaw:.3f}", f"{current_data['go1_yaw_rate']:.3f}",
                f"{self.target_roll:.3f}", f"{current_data['go1_r']:.3f}", f"{current_data['stab_r']:.3f}", f"{current_data['obj_r']:.3f}",
                f"{self.target_pitch:.3f}", f"{current_data['go1_p']:.3f}", f"{current_data['stab_p']:.3f}", f"{current_data['obj_p']:.3f}",
                f"{current_data['go1_ax']:.3f}", f"{current_data['go1_ay']:.3f}", f"{current_data['go1_az']:.3f}"
            ]
            csv_writer.writerow(row)

        # Self-call for 100Hz loop
        self.after(10, self.send_cmd_loop)

if __name__ == "__main__":
    app = Go1Commander()
    app.mainloop()