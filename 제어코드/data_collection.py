import socket
import threading
import time
import csv
import datetime
import os

# --- 통신 설정 ---
UDP_IP_BIND = "0.0.0.0"
DATA_PORT = 9998      
INTERNAL_PORT = 9995  

sock_data = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_data.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock_data.bind((UDP_IP_BIND, DATA_PORT))

sock_ctrl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_ctrl.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock_ctrl.bind(("127.0.0.1", INTERNAL_PORT))

# 💡 시스템 상태 저장소 (dist와 radius 포함)
sys_state = {
    'is_recording': False,
    'target_vx': 0.0, 'target_yaw': 0.0, 'target_r': 0.0, 'target_p': 0.0,
    'target_dist': 0.0, 'target_radius': 0.0
}

sensor_data = {
    'go1_vx': 0.0, 'go1_yaw_rate': 0.0, 'go1_r': 0.0, 'go1_p': 0.0, 'go1_y': 0.0,
    'go1_ax': 0.0, 'go1_ay': 0.0, 'go1_az': 0.0,
    'stab_r': 0.0, 'stab_p': 0.0, 'obj_r': 0.0, 'obj_p': 0.0
}

def receive_ctrl():
    print("🟢 [Ctrl_Rx] 컨트롤러 통신 대기 중... (Port: 9995)")
    while True:
        try:
            data, _ = sock_ctrl.recvfrom(1024)
            msg = data.decode('utf-8').strip()
            if msg.startswith("CTRL,"):
                parts = msg.split(',')
                # 💡 길이 상관없이 안전하게 파싱하도록 보강
                sys_state['is_recording'] = bool(int(parts[1]))
                sys_state['target_vx'] = float(parts[2])
                sys_state['target_yaw'] = float(parts[3])
                sys_state['target_r'] = float(parts[4])
                sys_state['target_p'] = float(parts[5])
                
                # 데이터가 8개(Index 7)까지 꽉 차있으면 dist와 radius 저장
                if len(parts) >= 8:
                    sys_state['target_dist'] = float(parts[6])
                    sys_state['target_radius'] = float(parts[7])
        except Exception as e: 
            pass

def receive_sensors():
    print("🟢 [Sensor_Rx] 아두이노/Go1 통신 대기 중... (Port: 9998)")
    while True:
        try:
            data, _ = sock_data.recvfrom(1024)
            msg = data.decode('utf-8').strip()
            parts = msg.split(',')
            
            if msg.startswith("GO1,") and len(parts) >= 9:
                sensor_data['go1_vx'] = float(parts[1])
                sensor_data['go1_yaw_rate'] = float(parts[2])
                sensor_data['go1_r'] = float(parts[3]); sensor_data['go1_p'] = float(parts[4])
            elif msg.startswith("STAB,") and len(parts) >= 3:
                sensor_data['stab_r'] = float(parts[1]); sensor_data['stab_p'] = float(parts[2])
            elif msg.startswith("OBJ,") and len(parts) >= 3:
                sensor_data['obj_r'] = float(parts[1]); sensor_data['obj_p'] = float(parts[2])
        except Exception as e: 
            pass

def logging_loop():
    print("📡 [Collector] 백그라운드 데이터 로깅 스레드 시작됨!")
    os.makedirs("collected_data", exist_ok=True) 

    csv_file = None
    csv_writer = None
    start_time = 0.0
    was_recording = False

    while True:
        is_rec = sys_state['is_recording']
        
        # 녹화 시작
        if is_rec and not was_recording:
            filename = f"collected_data/run_Vx{sys_state['target_vx']:.2f}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            try:
                csv_file = open(filename, mode='w', newline='')
                csv_writer = csv.writer(csv_file)
                # 💡 헤더에 Dist와 Radius 추가 완료
                headers = [
                    'Time(s)', 'Target_Vx', 'Target_Dist', 'Target_Radius', 'Go1_Vx', 'Target_YawRate', 'Go1_YawRate',
                    'Target_Roll', 'Go1_Roll', 'Stab_Roll', 'Obj_Roll',
                    'Target_Pitch', 'Go1_Pitch', 'Stab_Pitch', 'Obj_Pitch'
                ]
                csv_writer.writerow(headers)
                start_time = time.time()
                print(f"⏺ [Collector] 녹화 시작됨: {filename}")
                was_recording = True
            except Exception as e:
                print(f"❌ [Collector Error] 파일 생성 실패: {e}")

        # 데이터 기록 중
        elif is_rec and was_recording and csv_writer:
            elapsed = time.time() - start_time
            # 💡 Row 배열에 Dist와 Radius 매핑 완료
            row = [
                f"{elapsed:.3f}",
                f"{sys_state['target_vx']:.3f}", f"{sys_state['target_dist']:.3f}", f"{sys_state['target_radius']:.3f}", f"{sensor_data['go1_vx']:.3f}",
                f"{sys_state['target_yaw']:.3f}", f"{sensor_data['go1_yaw_rate']:.3f}",
                f"{sys_state['target_r']:.3f}", f"{sensor_data['go1_r']:.3f}", f"{sensor_data['stab_r']:.3f}", f"{sensor_data['obj_r']:.3f}",
                f"{sys_state['target_p']:.3f}", f"{sensor_data['go1_p']:.3f}", f"{sensor_data['stab_p']:.3f}", f"{sensor_data['obj_p']:.3f}"
            ]
            csv_writer.writerow(row)

        # 녹화 종료
        elif not is_rec and was_recording:
            if csv_file: 
                csv_file.close()
            print("⏹ [Collector] 녹화 종료 및 파일 저장 완료.")
            was_recording = False

        time.sleep(0.01)

if __name__ == "__main__":
    threading.Thread(target=receive_ctrl, daemon=True).start()
    threading.Thread(target=receive_sensors, daemon=True).start()
    logging_loop()