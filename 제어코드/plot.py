import pandas as pd
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog
import os

def main():
    # 1. 파일 선택 UI 띄우기 (터미널에서 매번 파일명을 입력할 필요 없도록 구성)
    root = tk.Tk()
    root.withdraw() # 메인 창 숨기기
    file_path = filedialog.askopenfilename(
        title="분석할 CSV 파일을 선택하세요",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    if not file_path:
        print("❌ 파일 선택이 취소되었습니다.")
        return

    print(f"📊 데이터 분석 시작: {os.path.basename(file_path)}")

    # 2. CSV 데이터 로드
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"❌ 파일을 읽는 중 오류가 발생했습니다: {e}")
        return

    # 시간 축 데이터
    time = df['Time(s)']

    # 3. 그래프 세팅 (4행 1열의 서브플롯 생성)
    # 한 화면에서 시간대별로 4가지 지표의 변화를 수직으로 비교하기 좋게 세팅합니다.
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(f"Quadruped Forklift Stabilizer Data Analysis\n[{os.path.basename(file_path)}]", fontsize=16, fontweight='bold')

    # --- [1] 선속도 (Linear Velocity Vx) ---
    axes[0].plot(time, df['Target_Vx'], label='Target Velocity', linestyle='--', color='black', linewidth=2)
    axes[0].plot(time, df['Go1_Vx'], label='Go1 Actual Velocity', color='blue', alpha=0.7)
    axes[0].set_ylabel('Velocity (m/s)')
    axes[0].set_title('Linear Velocity (Forward/Backward)')
    axes[0].legend(loc='upper right')
    axes[0].grid(True, linestyle=':', alpha=0.6)

    # --- [2] 회전 각속도 (Yaw Rate) ---
    axes[1].plot(time, df['Target_YawRate'], label='Target Yaw Rate', linestyle='--', color='black', linewidth=2)
    axes[1].plot(time, df['Go1_YawRate'], label='Go1 Actual Yaw Rate', color='green', alpha=0.7)
    axes[1].set_ylabel('Yaw Rate (rad/s)')
    axes[1].set_title('Yaw Rate (Turning)')
    axes[1].legend(loc='upper right')
    axes[1].grid(True, linestyle=':', alpha=0.6)

    # --- [3] Roll (좌우 기울기) ---
    axes[2].plot(time, df['Target_Roll'], label='Target Roll (0°)', linestyle='--', color='black')
    axes[2].plot(time, df['Go1_Roll'], label='Go1 Roll (Disturbance)', color='red', alpha=0.4) # 로봇 본체의 흔들림
    axes[2].plot(time, df['Stab_Roll'], label='Stabilizer Roll (Action)', color='orange', alpha=0.8) # 짐벌의 보상 움직임
    axes[2].plot(time, df['Obj_Roll'], label='Object Roll (Result)', color='purple', linewidth=2) # 최종 물체의 상태
    axes[2].set_ylabel('Angle (deg)')
    axes[2].set_title('Roll Angle Compensation (Left/Right)')
    axes[2].legend(loc='upper right')
    axes[2].grid(True, linestyle=':', alpha=0.6)

    # --- [4] Pitch (앞뒤 기울기) ---
    axes[3].plot(time, df['Target_Pitch'], label='Target Pitch (0°)', linestyle='--', color='black')
    axes[3].plot(time, df['Go1_Pitch'], label='Go1 Pitch (Disturbance)', color='red', alpha=0.4) # 가감속 시 본체의 쏠림
    axes[3].plot(time, df['Stab_Pitch'], label='Stabilizer Pitch (Action)', color='orange', alpha=0.8) # 짐벌의 보상 움직임
    axes[3].plot(time, df['Obj_Pitch'], label='Object Pitch (Result)', color='purple', linewidth=2) # 최종 물체의 상태
    axes[3].set_ylabel('Angle (deg)')
    axes[3].set_xlabel('Time (seconds)', fontsize=12)
    axes[3].set_title('Pitch Angle Compensation (Forward/Backward Acceleration)')
    axes[3].legend(loc='upper right')
    axes[3].grid(True, linestyle=':', alpha=0.6)

    # 레이아웃 정리 및 출력
    plt.tight_layout(rect=[0, 0.03, 1, 0.95]) # suptitle 공간 확보
    plt.show()

if __name__ == "__main__":
    main()