import socket
import struct
import json
import csv
import time
import os
import sys

# ==========================================
# 1. 데이터 파싱 맵 (C++ 배열 인덱스 매칭)
# UI의 config.json에 저장되는 문자열과 동일해야 합니다.
# ==========================================
DATA_MAP = {
    "imu.rpy (Roll, Pitch, Yaw)": [("Roll_rad", 0), ("Pitch_rad", 1), ("Yaw_rad", 2)],
    "imu.quaternion (q0, q1, q2, q3)": [("q0", 3), ("q1", 4), ("q2", 5), ("q3", 6)],
    "imu.gyroscope (gx, gy, gz)": [("Gyro_X", 7), ("Gyro_Y", 8), ("Gyro_Z", 9)],
    "imu.accelerometer (ax, ay, az)": [("Acc_X", 10), ("Acc_Y", 11), ("Acc_Z", 12)],
    
    "velocity (Vx, Vy, Vz)": [("Vx", 13), ("Vy", 14), ("Vz", 15)],
    "yawSpeed": [("YawRate", 16)],
    "position (X, Y, Z)": [("Pos_X", 17), ("Pos_Y", 18), ("Pos_Z", 19)],
    
    "footForce (센서 원시값 4다리)": [("FF_FR", 20), ("FF_FL", 21), ("FF_RR", 22), ("FF_RL", 23)],
    "footForceEst (알고리즘 추정값 4다리)": [("FFE_FR", 24), ("FFE_FL", 25), ("FFE_RR", 26), ("FFE_RL", 27)],
    
    "motor.q (회전 위치)": [(f"Mot{i}_q", 28 + i*5 + 0) for i in range(12)],
    "motor.dq (회전 속도)": [(f"Mot{i}_dq", 28 + i*5 + 1) for i in range(12)],
    "motor.ddq (각가속도)": [(f"Mot{i}_ddq", 28 + i*5 + 2) for i in range(12)],
    "motor.tauEst (추정 토크)": [(f"Mot{i}_tauEst", 28 + i*5 + 3) for i in range(12)],
    "motor.temperature (온도)": [(f"Mot{i}_temp", 28 + i*5 + 4) for i in range(12)],
    
    "bms.SOC (배터리 잔량 %)": [("Batt_SOC", 88)],
    "bms.current / voltage": [("Batt_Current_A", 89), ("Batt_Voltage_V", 90)],
    "tick (타임스탬프)": [("Tick", 91)]
}

# ==========================================
# 2. 통신 및 파일 설정
# ==========================================
UDP_IP = "0.0.0.0"   # 모든 IP에서 수신 대기
UDP_PORT = 9998      # 💡 C++ 엔진에서 데이터를 쏘는 목적지 포트와 동일해야 함!

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"📡 [수집기] 백그라운드 대기 중... (UI의 수집 시작 명령을 기다립니다)")

    is_recording = False
    csv_file = None
    writer = None
    target_indices = []
    start_time = None
    packet_count = 0

    try:
        while True:
            packet, addr = sock.recvfrom(1024)
            
            # ----------------------------------------------------
            # 1. 파이썬 UI로부터 제어 명령(START/STOP)을 받았을 때
            # (명령어 패킷은 길이가 짧은 문자열임)
            # ----------------------------------------------------
            if len(packet) < 100:
                try:
                    msg = packet.decode('utf-8')
                    if msg == "START_REC":
                        # 명령을 받으면 비로소 config.json을 읽습니다.
                        if os.path.exists("config.json"):
                            with open("config.json", "r", encoding="utf-8") as f:
                                cfg = json.load(f)
                                selected_categories = cfg.get("selected_columns", [])

                            # 헤더 및 인덱스 추출
                            csv_headers = ["Time(s)"]
                            target_indices = []
                            for cat in selected_categories:
                                if cat in DATA_MAP:
                                    for col_name, idx in DATA_MAP[cat]:
                                        csv_headers.append(col_name)
                                        target_indices.append(idx)

                            # CSV 파일 생성 및 열기
                            timestamp = time.strftime("%Y%m%d_%H%M%S")
                            filename = f"Go1_Log_{timestamp}.csv"
                            csv_file = open(filename, mode="w", newline="")
                            writer = csv.writer(csv_file)
                            
                            metadata = f"# [METADATA] Config: {cfg.get('timestamp', 'N/A')}, Items: {len(selected_categories)}"
                            csv_file.write(metadata + "\n")
                            writer.writerow(csv_headers)

                            is_recording = True
                            start_time = time.time()
                            packet_count = 0
                            print(f"🔴 [수집기] 데이터 기록 시작! -> {filename}")
                        else:
                            print("⚠️ [수집기] config.json 파일이 없습니다. 메인 UI에서 설정을 먼저 저장해주세요.")

                    elif msg == "STOP_REC":
                        if is_recording:
                            is_recording = False
                            if csv_file:
                                csv_file.close()
                                csv_file = None
                            print(f"⏹️ [수집기] 데이터 기록 종료! (총 {packet_count} 행 저장됨)")
                except UnicodeDecodeError:
                    pass # 문자열이 아닌 알 수 없는 패킷은 무시

            # ----------------------------------------------------
            # 2. C++ 엔진으로부터 센서 데이터를 받았을 때 (기록 중일 때만)
            # (우리가 맞춘 규격: 92개의 float = 정확히 368바이트)
            # ----------------------------------------------------
            elif len(packet) == 368 and is_recording:
                data = struct.unpack('<92f', packet)
                t = time.time() - start_time
                
                # 선택된 데이터만 쏙쏙 뽑아서 기록
                row = [t] + [data[i] for i in target_indices]
                writer.writerow(row)
                
                packet_count += 1
                if packet_count % 1000 == 0:
                    print(f"   ... {packet_count} 패킷 기록됨 (Time: {t:.1f}s)")

    except KeyboardInterrupt:
        pass # main.py에서 terminate()로 종료시킬 것이므로 조용히 넘어감
    finally:
        if csv_file:
            csv_file.close()
        sock.close()

if __name__ == "__main__":
    main()