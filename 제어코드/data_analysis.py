import pandas as pd
import matplotlib.pyplot as plt
import glob
import os

def batch_analyze():
    data_dir = "collected_data"
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    if not csv_files:
        print("❌ 분석할 CSV 파일이 'collected_data' 폴더에 없습니다.")
        return

    print(f"📊 총 {len(csv_files)}개의 실험 데이터를 일괄 분석합니다...")

    # 결과를 저장할 리스트
    results = []

    for file in csv_files:
        df = pd.read_csv(file)
        if df.empty: continue
        
        # 1. 파일에서 해당 실험의 세팅값(Target Vx) 추출
        # (녹화 구간 내의 평균값 또는 첫 번째 값을 사용)
        target_vx = df['Target_Vx'].iloc[0]
        
        # 2. 과도 응답(Transient Response) 분석
        # 가속이 시작되는 시점(Target_Vx가 들어간 직후)의 최대 피칭 쏠림 추출
        max_pitch_disturbance = df['Go1_Pitch'].max()
        min_pitch_disturbance = df['Go1_Pitch'].min()
        
        # 최대 쏠림이 발생한 시점 (Delay 계산용)
        max_pitch_time = df.loc[df['Go1_Pitch'].idxmax(), 'Time(s)']
        
        # 스태빌라이저와 물체의 보상 후 최대 잔여 오차
        max_obj_error = df['Obj_Pitch'].abs().max()

        results.append({
            'File': os.path.basename(file),
            'Target_Vx': target_vx,
            'Go1_Max_Pitch_Up': max_pitch_disturbance,
            'Go1_Max_Pitch_Down': min_pitch_disturbance,
            'Peak_Time(s)': max_pitch_time,
            'Max_Object_Error': max_obj_error
        })

    # 데이터프레임으로 변환하여 요약 출력
    summary_df = pd.DataFrame(results)
    summary_df = summary_df.sort_values(by='Target_Vx') # 속도 순으로 정렬
    
    print("\n=== 📈 실험 결과 요약 (Target_Vx에 따른 외란 분석) ===")
    print(summary_df.to_string(index=False))

    # 💡 속도(Vx)에 따른 차체 흔들림(Pitch) 상관관계 그래프 (Feed-forward 모델링용)
    plt.figure(figsize=(10, 6))
    plt.scatter(summary_df['Target_Vx'], summary_df['Go1_Max_Pitch_Down'], color='red', label='Max Forward Pitch (Dive)')
    plt.scatter(summary_df['Target_Vx'], summary_df['Go1_Max_Pitch_Up'], color='blue', label='Max Backward Pitch (Squat)')
    
    plt.title("Correlation: Target Velocity vs Go1 Body Pitching", fontsize=14, fontweight='bold')
    plt.xlabel("Target Forward Velocity (m/s)", fontsize=12)
    plt.ylabel("Go1 Pitch Disturbance (deg)", fontsize=12)
    plt.axhline(0, color='black', linewidth=1)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend()
    plt.show()

if __name__ == "__main__":
    batch_analyze()