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
# 2. Global State & Logging Variables
# ==========================================
current_data = {'go1_r': 0.0, 'go1_p': 0.0}
is_recording = False
csv_file = None
csv_writer = None
start_time_record = 0.0

class Go1Commander(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Go1 Stabilizer Commander")
        self.geometry("400x550")
        self.configure(padx=20, pady=20)

        # Robot State Variables
        self.is_walking = False
        self.target_vx = 0.0
        self.target_yaw = 0.0
        self.target_pitch = 0.0
        self.walk_end_time = 0.0

        self.create_widgets()
        
        # Start background threads for Data Rx and Command Tx
        threading.Thread(target=self.receive_data_loop, daemon=True).start()
        self.send_cmd_loop() # 100Hz Tick Loop

    def create_widgets(self):
        # 1. Forward Speed
        tk.Label(self, text="Forward Speed (m/s) [+:Fwd, -:Bwd]", font=("Arial", 10, "bold")).pack(pady=(5, 0))
        self.entry_speed = tk.Entry(self, justify='center', font=("Arial", 12))
        self.entry_speed.insert(0, "0.3")
        self.entry_speed.pack(pady=5)

        # 2. Travel Distance
        tk.Label(self, text="Travel Distance (m)", font=("Arial", 10, "bold")).pack(pady=(5, 0))
        self.entry_dist = tk.Entry(self, justify='center', font=("Arial", 12))
        self.entry_dist.insert(0, "1.0")
        self.entry_dist.pack(pady=5)

        # 3. Turning Radius
        tk.Label(self, text="Turning Radius (m) [0:Straight, +:L, -:R]", font=("Arial", 10, "bold")).pack(pady=(5, 0))
        self.entry_radius = tk.Entry(self, justify='center', font=("Arial", 12))
        self.entry_radius.insert(0, "0.0")
        self.entry_radius.pack(pady=5)

        # 4. Body Pitch
        tk.Label(self, text="Body Pitch (deg) [+:Up, -:Down]", font=("Arial", 10, "bold")).pack(pady=(5, 0))
        self.entry_pitch = tk.Entry(self, justify='center', font=("Arial", 12))
        self.entry_pitch.insert(0, "0.0")
        self.entry_pitch.pack(pady=5)

        # Status Label
        self.lbl_status = tk.Label(self, text="Status: Standby", fg="blue", font=("Arial", 12, "bold"))
        self.lbl_status.pack(pady=15)

        # Button Frame
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=10)

        self.btn_run = tk.Button(btn_frame, text="▶ RUN", bg="lightgreen", font=("Arial", 12, "bold"), command=self.start_walk)
        self.btn_run.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5, ipady=5)

        self.btn_stop = tk.Button(btn_frame, text="🛑 E-STOP", bg="red", fg="white", font=("Arial", 12, "bold"), command=self.emergency_stop)
        self.btn_stop.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5, ipady=5)

        # Logging Button
        self.btn_record = tk.Button(self, text="⏺ Start Recording", bg="lightgray", font=("Arial", 12, "bold"), command=self.toggle_recording)
        self.btn_record.pack(fill=tk.X, pady=10, ipady=5)

    def start_walk(self):
        try:
            vx = float(self.entry_speed.get())
            dist = float(self.entry_dist.get())
            radius = float(self.entry_radius.get())
            pitch_deg = float(self.entry_pitch.get())

            if vx == 0 or dist <= 0:
                messagebox.showwarning("Input Error", "Speed cannot be 0, and distance must be positive.")
                return

            # Kinematics Calculation
            duration = dist / abs(vx)
            if radius == 0:
                yaw_rate = 0.0
            else:
                yaw_rate = vx / radius # v = r * w

            # Update State
            self.target_vx = vx
            self.target_yaw = yaw_rate
            self.target_pitch = math.radians(pitch_deg) # deg -> rad
            self.walk_end_time = time.time() + duration
            self.is_walking = True

            self.lbl_status.config(text=f"Status: Walking ({duration:.1f}s)", fg="green")
            self.btn_run.config(state=tk.DISABLED)

        except ValueError:
            messagebox.showerror("Input Error", "Please enter numeric values only.")

    def emergency_stop(self):
        self.is_walking = False
        self.target_vx = 0.0
        self.target_yaw = 0.0
        # Pitch is maintained here. To reset, add: self.target_pitch = 0.0
        self.lbl_status.config(text="Status: E-STOP Triggered", fg="red")
        self.btn_run.config(state=tk.NORMAL)

    def toggle_recording(self):
        global is_recording, csv_file, csv_writer, start_time_record
        if not is_recording:
            filename = f"stabilizer_profile_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            csv_file = open(filename, mode='w', newline='')
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(['Time(s)', 'Target_Vx', 'Target_Yaw', 'Target_Pitch', 'Go1_Roll', 'Go1_Pitch'])
            
            start_time_record = time.time()
            is_recording = True
            self.btn_record.config(text="⏹ Stop Recording", bg="red", fg="white")
            print(f"[Logging] Started: {filename}")
        else:
            is_recording = False
            if csv_file: csv_file.close()
            self.btn_record.config(text="⏺ Start Recording", bg="lightgray", fg="black")
            print("[Logging] Stopped.")

    def receive_data_loop(self):
        """Receive Robot IMU data from C++ Engine at 100Hz"""
        while True:
            try:
                data, _ = sock_data.recvfrom(1024)
                msg = data.decode('utf-8')
                if msg.startswith("GO1,"):
                    _, r, p = msg.split(',')
                    current_data['go1_r'] = float(r)
                    current_data['go1_p'] = float(p)
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

        # Generate Protocol String (1: Stand, 2: Walk)
        mode = 2 if self.is_walking else 1
        cmd_str = f"CMD,{mode},{self.target_vx:.3f},{self.target_yaw:.3f},{self.target_pitch:.3f}"
        sock_cmd.sendto(cmd_str.encode('utf-8'), (UDP_IP, CMD_PORT))

        # Data Logging
        if is_recording and csv_writer:
            elapsed = time.time() - start_time_record
            csv_writer.writerow([
                f"{elapsed:.3f}", 
                f"{self.target_vx:.3f}", 
                f"{self.target_yaw:.3f}", 
                f"{self.target_pitch:.3f}",
                f"{current_data['go1_r']:.2f}", 
                f"{current_data['go1_p']:.2f}"
            ])

        # Self-call for 100Hz loop
        self.after(10, self.send_cmd_loop)

if __name__ == "__main__":
    app = Go1Commander()
    app.mainloop()