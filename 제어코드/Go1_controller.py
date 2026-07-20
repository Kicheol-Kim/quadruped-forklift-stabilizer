import tkinter as tk
from tkinter import messagebox
import socket
import time
import json
import os

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
        self.target_dist = 0.0
        self.target_radius = 0.0
        self.walk_end_time = 0.0

        self.data_checkbox_vars = {}
        self.selected_data_columns = [] # 최종 수집할 데이터 리스트

        self.create_widgets()
        self.send_cmd_loop() # 100Hz 루프 시작

    def create_widgets(self):
        frame_posture = tk.LabelFrame(self, text="Robot Posture Control", fg="blue", padx=5, pady=5)
        frame_posture.pack(fill=tk.X, pady=(0, 15))

        tk.Button(frame_posture, text="🛌 Down (5)", command=lambda: self.set_quick_mode(5)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(frame_posture, text="🧍 Up (6)", command=lambda: self.set_quick_mode(6)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(frame_posture, text="🔄 Recover (8)", command=lambda: self.set_quick_mode(8)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(frame_posture, text="🛑 Stand (1)", bg="lightgray", command=lambda: self.set_quick_mode(1)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.btn_mode_select = tk.Button(self, text="Select Robot Mode", bg="lightgray", command=self.open_mode_window)
        self.btn_mode_select.pack(pady=10, fill=tk.X)

        self.lbl_status = tk.Label(self, text="Status: Stand (1)", fg="blue")
        self.lbl_status.pack(pady=10)

        btn_frame1 = tk.Frame(self)
        btn_frame1.pack(fill=tk.X, pady=5)

        self.btn_run = tk.Button(btn_frame1, text="RUN (No Record)", bg="lightblue", command=lambda: self.start_walk(record=False))
        self.btn_run.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2, ipady=8)

        self.btn_run_rec = tk.Button(btn_frame1, text="RUN & RECORD", bg="lightgreen", command=lambda: self.start_walk(record=True))
        self.btn_run_rec.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2, ipady=8)

        self.btn_stop = tk.Button(self, text="E-STOP", bg="red", fg="white", command=self.emergency_stop)
        self.btn_stop.pack(fill=tk.X, pady=10, ipady=8)

        self.ui_container = tk.Frame(self)
        self.ui_container.pack(fill=tk.BOTH, expand=True, pady=10)

        self.btn_data_config = tk.Button(self, text="Configure Data Collection", bg="lightblue", command=self.open_data_config_window)
        self.btn_data_config.pack(pady=10, fill=tk.X)

        # 초기 모드에 맞는 UI 그리기
        self.update_ui_for_mode()

    def set_quick_mode(self, mode_val, mode_name=None, window=None):
        if self.is_walking:
            messagebox.showwarning("Warning", "Cannot change posture while walking!")
            return

        self.current_mode = mode_val
        self.is_walking = False

        if mode_name is None:
            mode_names = {1: "Stand (1)", 5: "Stand Down (5)", 6: "Stand Up (6)", 8: "Recovery (8)"}
            mode_name = mode_names.get(mode_val, f"Mode {mode_val}")
            fg_color = "blue"
        else:
            fg_color = "black"

        self.lbl_status.config(text=f"Status: {mode_name}", fg=fg_color)

        if window is not None:
            window.destroy()

        self.update_ui_for_mode()

    # 💡 [추가] 모드가 바뀔 때마다 호출되어 화면을 갈아끼우는 함수
    def update_ui_for_mode(self):
        # 1. 컨테이너 안의 기존 위젯들을 모두 삭제(초기화)
        for widget in self.ui_container.winfo_children():
            widget.destroy()

        # 2. 모드에 따라 분기 (나중에 if self.current_mode == 1: self.build_stand_ui() 등으로 확장)
        # 현재는 어떤 모드든 동일한 walk UI를 호출합니다.
        self.build_walk_ui()

    # 💡 [추가] 기존의 제어 UI 생성 코드를 모듈화
    def build_walk_ui(self):
        # 부모 위젯을 self가 아니라 self.ui_container로 설정합니다.
        frame = tk.LabelFrame(self.ui_container, text=f"Controls (Mode {self.current_mode})")
        frame.pack(fill=tk.BOTH, expand=True)

        # ⚠️ 기존 create_widgets에 있던 Vx, Yaw, Pitch, Roll 슬라이더와 
        # Run 버튼 생성 코드들을 이곳으로 잘라내기해서 붙여넣습니다. 
        # (단, 위젯들을 선언할 때 부모를 self가 아닌 frame으로 지정해주세요)
        # [예시]
        # self.scale_vx = tk.Scale(frame, from_=-0.5, to=0.5, ...)
        # self.scale_vx.pack(...)
        # self.btn_run = tk.Button(frame, text="Run", ...)
        # self.btn_run.pack(...)
        tk.Label(frame, text="Forward Speed (m/s) [+:Fwd, -:Bwd]").pack(pady=(2, 0))
        self.entry_speed = tk.Entry(frame, justify='center')
        self.entry_speed.insert(0, "0.3")
        self.entry_speed.pack(pady=5)

        tk.Label(frame, text="Travel Distance (m)").pack(pady=(2, 0))
        self.entry_dist = tk.Entry(frame, justify='center')
        self.entry_dist.insert(0, "1.0")
        self.entry_dist.pack(pady=5)

        tk.Label(frame, text="Turning Radius (m) [0:Straight, +:L, -:R]").pack(pady=(2, 0))
        self.entry_radius = tk.Entry(frame, justify='center')
        self.entry_radius.insert(0, "0.0")
        self.entry_radius.pack(pady=5)


    def open_mode_window(self):
        mode_win = tk.Toplevel(self)
        mode_win.title("Select High-Level Mode")
        mode_win.geometry("300x450")
        mode_win.grab_set() # 이 창이 열려있는 동안 메인 창 클릭 방지 (모달 창)

        tk.Label(mode_win, text="Unitree Go1 Modes").pack(pady=10)

        # 독스(Docs) 기준 모드 리스트
        modes = [
            (1, "Mode 1: Force Stand (자세 제어)"),
            (2, "Mode 2: Walk (일반 보행)"),
            (3, "Mode 3: Climb Stairs (계단 모드)"),
            (4, "Mode 4: Trot Obstacle (장애물)"),
            (5, "Mode 5: Stand Down (엎드리기)"),
            (6, "Mode 6: Stand Up (일어서기)"),
            (7, "Mode 7: Damping (휴식/무동력)"),
            (8, "Mode 8: Recovery Stand (복구 기립)")
        ]

        for m_val, m_name in modes:
            btn = tk.Button(mode_win, text=m_name, height=2,
                            command=lambda v=m_val, n=m_name: self.set_mode(v, n, mode_win))
            btn.pack(fill=tk.X, padx=10, pady=2)

    def set_mode(self, mode_val, mode_name, window):
        self.current_mode = mode_val
        self.is_walking = False # 수동으로 모드를 바꾸면 자동 걷기 상태 해제
        self.lbl_status.config(text=f"Status: {mode_name}", fg="black")
        window.destroy() # 창 닫기

        self.update_ui_for_mode()

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
            self.is_recording = record
            self.current_mode = 2
            
            # 💡 [추가] 기록 모드로 실행되었다면, 수집기(data_collection.py)에 시작 명령 전송
            if self.is_recording:
                # 127.0.0.1의 9998번 포트(수집기 대기 포트)로 패킷 전송
                sock_out.sendto(b"START_REC", ("127.0.0.1", 9998))
                print("📡 전송: 수집기에게 기록 시작(START_REC) 명령을 내렸습니다.")

            self.lbl_status.config(text=f"Status: Walking {'& Recording' if record else ''}", fg="green")
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

    # 💡 [추가] 수집할 전체 데이터 분류 체계
    def get_data_categories(self):
        return {
            "1. IMU & Posture (자세 및 관성)": [
                "imu.rpy (Roll, Pitch, Yaw)",
                "imu.quaternion (q0, q1, q2, q3)",
                "imu.gyroscope (gx, gy, gz)",
                "imu.accelerometer (ax, ay, az)"
            ],
            "2. Velocity & Kinematics (속도/위치)": [
                "velocity (Vx, Vy, Vz)",
                "yawSpeed",
                "position (X, Y, Z)"
            ],
            "3. Foot Force & Contact (지면 반발력)": [
                "footForce (센서 원시값 4다리)",
                "footForceEst (알고리즘 추정값 4다리)"
            ],
            "4. Motor States (12개 관절 모터)": [
                "motor.q (회전 위치)",
                "motor.dq (회전 속도)",
                "motor.ddq (각가속도)",
                "motor.tauEst (추정 토크)",
                "motor.temperature (온도)"
            ],
            "5. System & Power (시스템/전원)": [
                "bms.SOC (배터리 잔량 %)",
                "bms.current / voltage",
                "wirelessRemote (조종기 입력)",
                "tick (타임스탬프)"
            ]
        }

    def load_saved_data_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if not os.path.exists(config_path):
            return []

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            selected_columns = config_data.get("selected_columns", [])
            if isinstance(selected_columns, list):
                return [str(item) for item in selected_columns]
        except Exception as e:
            print(f"❌ 설정 불러오기 실패: {e}")

        return []

    # 💡 [추가] 데이터 수집 설정 팝업창
    def open_data_config_window(self):
        config_win = tk.Toplevel(self)
        config_win.title("Select Data to Collect")
        config_win.geometry("380x700")
        config_win.grab_set()
        config_win.transient(self)
        config_win.columnconfigure(0, weight=1)
        config_win.rowconfigure(1, weight=1)

        # 상단 컨트롤 버튼 (전체 선택/해제)
        top_frame = tk.Frame(config_win)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        popup_vars = {}

        tk.Button(top_frame, text="Select All", command=lambda: self.toggle_all_checkboxes(True, popup_vars)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(top_frame, text="Deselect All", command=lambda: self.toggle_all_checkboxes(False, popup_vars)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # 스크롤 가능한 캔버스 생성
        canvas = tk.Canvas(config_win, highlightthickness=0)
        scrollbar = tk.Scrollbar(config_win, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)
        canvas_frame_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_frame_id, width=event.width)

        scroll_frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 10))
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 10))

        categories = self.get_data_categories()
        saved_selected = self.load_saved_data_config()
        self.selected_data_columns = saved_selected

        # 카테고리별로 LabelFrame 및 Checkbutton 생성
        for cat_name, items in categories.items():
            lf = tk.LabelFrame(scroll_frame, text=cat_name, fg="blue")
            lf.pack(fill=tk.X, expand=True, pady=5, ipadx=5, ipady=5)

            for item in items:
                # 아직 등록되지 않은 변수라면 새로 생성 (기본값 False)
                if item not in self.data_checkbox_vars:
                    self.data_checkbox_vars[item] = tk.BooleanVar(value=False)

                self.data_checkbox_vars[item].set(item in saved_selected)
                popup_vars[item] = self.data_checkbox_vars[item]
                cb = tk.Checkbutton(lf, text=item, variable=popup_vars[item], anchor='w')
                cb.pack(fill=tk.X)

        # 하단 적용 버튼
        btn_apply = tk.Button(config_win, text="Save Configuration", bg="lightgreen", command=lambda: self.save_data_config(config_win, popup_vars))
        btn_apply.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))

    # 💡 [추가] 전체 선택/해제 토글 함수
    def toggle_all_checkboxes(self, state, vars_dict=None):
        target_vars = vars_dict if vars_dict is not None else self.data_checkbox_vars
        for var in target_vars.values():
            var.set(state)

    # 💡 [추가] 설정 저장 함수
    def save_data_config(self, window, vars_dict=None):
        # 1. 체크된 항목 리스트 추출
        target_vars = vars_dict if vars_dict is not None else self.data_checkbox_vars
        self.selected_data_columns = [item for item, var in target_vars.items() if var.get()]

        if not self.selected_data_columns:
            messagebox.showwarning("Warning", "선택된 데이터가 없습니다!")
            return

        # 2. JSON 형태로 저장할 딕셔너리 구성
        config_data = {
            "version": "1.0",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "num_items": len(self.selected_data_columns),
            "selected_columns": self.selected_data_columns
        }

        # 3. config.json 파일 쓰기
        config_path = os.path.join(os.path.dirname(__file__), "config.json")

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            print(f"✅ 설정 저장 완료: {config_path} (총 {len(self.selected_data_columns)}개 항목)")
        except Exception as e:
            print(f"❌ 설정 저장 실패: {e}")

        window.destroy()

    def send_cmd_loop(self):
        if self.is_walking and time.time() > self.walk_end_time:
            if self.is_recording:
                sock_out.sendto(b"STOP_REC", ("127.0.0.1", 9998))
                print("📡 전송: 수집기에게 기록 종료(STOP_REC) 명령을 내렸습니다.")
                self.is_recording = False # 기록 상태 해제

            self.is_walking = False
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

    def start_recording(self):
        # 목적지: 로컬호스트(127.0.0.1)의 수집기 포트(9998)
        sock_out.sendto(b"START_REC", ("127.0.0.1", 9998))
        print("전송: 수집기에게 기록 시작 명령을 내렸습니다.")

    def stop_recording(self):
        sock_out.sendto(b"STOP_REC", ("127.0.0.1", 9998))
        print("전송: 수집기에게 기록 종료 명령을 내렸습니다.")

if __name__ == "__main__":
    app = Go1Commander()
    app.mainloop()