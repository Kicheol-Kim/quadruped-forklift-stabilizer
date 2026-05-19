import subprocess
import time
import sys

def main():
    print("🚀 [Main] Starting Quadruped Stabilizer System...")

    try:
        # 1. 데이터 수집기 실행
        print("📡 [Main] Launching Data Collector (Background)...")
        collector_process = subprocess.Popen([sys.executable, "data_collection.py"])
        time.sleep(1) # 포트 열리는 시간 대기

        # 2. 컨트롤러 UI 실행
        print("🎮 [Main] Launching Go1 Controller (UI)...")
        controller_process = subprocess.Popen([sys.executable, "Go1_controller.py"])

        # UI 창이 닫힐 때까지 대기
        controller_process.wait()

    except KeyboardInterrupt:
        print("\n🛑 [Main] Interrupted by user.")
    finally:
        # 프로그램이 종료되면 백그라운드 수집기도 안전하게 종료
        print("🛑 [Main] UI Closed. Terminating Data Collector...")
        try:
            collector_process.terminate()
            collector_process.wait()
        except:
            pass
        print("✅ [Main] System shutdown safely.")

if __name__ == "__main__":
    main()