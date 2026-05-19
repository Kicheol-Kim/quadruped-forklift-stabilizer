# Quadruped Forklift Stabilizer System Development

> **Unitree Go1 사족보행 로봇 기반의 능동형 포크리프트 스태빌라이저 시스템 개발 및 동적 외란 보상(Dynamic Compensation) 연구**

<img width="1116" height="626" alt="Image" src="https://github.com/user-attachments/assets/9ecc4498-ed16-493d-83ee-1507dd57b185" />

본 프로젝트는 사족보행 로봇(Quadruped Robot)의 고유한 민첩성(Agility) 및 보행 시 발생하는 흔들림 속에서도 적재된 화물의 수평을 능동적으로 유지하기 위한 **2축(Roll/Pitch) 능동형 스태빌라이저 시스템** 개발을 목표로 합니다. 

현재 중력 가속도 방향 정렬을 통한 **정상 상태 안정화(Steady-state Stabilizing)**를 완료하였으며, 가감속 시 발생하는 동적 외란을 상쇄하기 위한 **동적 피드포워드(Dynamic Feed-forward) 제어기 설계 및 대량의 주행 데이터 수집 파이프라인(100Hz)** 구조가 반영되어 있습니다.


---

## 🛠️ 1. System Architecture

<img width="1412" height="814" alt="image" src="https://github.com/user-attachments/assets/e167ec05-a8c8-4dda-a421-5412d03f95ba" />

### 1) Hardware Configuration
* **Main Robot Platform:** Unitree Go1 (2021 Model, SDK v3.4.2)
* **Actuator:** Dynamixel XL430-W250-T x 2 (Roll / Pitch 독립 제어)
  * **Mechanical Gear Ratio:** Roll Axis = `3.5 : 1` / Pitch Axis = `1.5 : 1` (동적 보상 토크 확보용 외부 기어단 결합)
* **Microcontroller:** Arduino Nano RP2040 Connect x 2
  * **Module 1 (Stabilizer):** 듀얼코어(mbed RTOS) 기반 IMU 연산 및 다이나믹셀 위치 제어전담
  * **Module 2 (Payload/Object):** 최종 화물 상단에 부착되어 실제 수평 유지도(Ground Truth) 측정

### 2) Network Topology
Go1 메인 로봇의 내장 핫스팟(5GHz)과 아두이노 무선 칩셋(2.4GHz 전용) 간의 하드웨어적 대역폭 불일치를 극복하기 위해 **노트북(Host PC) 중심의 하이브리드 라우팅** 구조를 설계했습니다.
* **Wired (Ethernet):** Host PC (Ubuntu 22.04) $\leftrightarrow$ Unitree Go1
* **Wireless (2.4GHz Hotspot):** Host PC (AP 모드) $\leftrightarrow$ Arduino Boards

---

## 📂 2. Software Structure & Module Separation

프로세스 간 독립성을 확보하고 데이터 로깅의 안정성을 높이기 위해 ROS(Robot Operating System) 노드 구조와 유사한 **IPC(UDP 프로세스 간 통신) 기반 모듈화**를 달성했습니다.

```text
📁 quadruped-forklift-stabilizer/
├── 📁 제어코드/
│   ├── main.py                 # 전체 시스템 통합 실행기 (Subprocess 매니저)
│   ├── Go1_controller.py       # Tkinter 기반 로봇 주행 제어 UI (Control Only)
│   ├── data_collection.py      # 백그라운드 멀티센서 수집기 (100Hz 로깅 및 CSV 저장)
│   ├── data_analysis.py        # 수집된 실험 데이터 일괄 배치 분석 및 시각화 스크립트
│   ├── 📁 collected_data/      # 주행중 수집한 각 MCU들의 IMU 데이터 CSV 파일 저장소
│   └── 📁 code_arduino/        # 모터 세팅부터 stabilizer 제어코드 등 arduino 관련 .ino파일들
│
└── 📁 unitree_legged_sdk/
    └── 📁 examples/
        └── go1_engine.cpp      # Unitree 제공 High-level SDK 기반 로봇 모터 토크 제어 C++ 엔진
```

## 📑 2.1 상세 기능 및 프로세스 간 상호작용 메커니즘

본 시스템은 자율주행 노드 구조와 유사하게 역학적 연산(C++), 사용자 제어(Python UI), 백그라운드 데이터 수집(Python Daemon), 센서 계측(Embedded C++)이 독립된 프로세스로 구동되며, 내부 및 외부 UDP 네트워크망을 통해 상호작용합니다.

### 1) 각 모듈별 상세 기능 (Component Functions)

#### Arduino Firmware
* **`stabilizer_module.ino` (스태빌라이저 제어 노드):**
  * mbed RTOS 기반의 듀얼코어로 구동되며, 다이나믹셀 서보모터 제어(Core 1)와 IMU 데이터 처리(Core 0)를 하드웨어 레벨에서 분리 처리합니다.
  * 가속도계 기반 정상상태 수평 정렬 알고리즘을 실시간(500Hz) 구동합니다.
  * 시리얼 인터페이스를 통해 두 모터의 실시간 PID 게인 및 LPF 필터 계수 튜닝 기능을 보존합니다.
  * 호스트 PC의 데이터 포트(`9998`)를 향해 현재 짐벌의 기울기 패킷(`STAB,roll,pitch`)을 무선 UDP(100Hz)로 송신합니다.
* **`tracking_object.ino` (최종 적재물 오차 계측 노드): (현재 하드웨어 구현 예정)**
  * 포크리프트 포크 위에 적재된 최종 화물의 최상단 IMU 각도(Ground Truth)를 독립 계측합니다.
  * 네트워크망 내 포트 충돌을 방지하기 위해 로컬 포트 `8889`를 별도 개방하여 호스트 PC(`9998`)로 화물의 잔여 오차 패킷 (`OBJ,roll,pitch`)을 무선 UDP로 송신합니다.

#### 💻 호스트 PC 제어 및 분석 영역 (Host PC Python Scripts)
* **`main.py` (전체 시스템 통합 오케스트레이터):**
  * 전체 시스템 노드를 일괄 기동하는 마스터 스크립트입니다.
  * 파이썬 `subprocess` 모듈을 활용해 백그라운드 수집기(`data_collection.py`)를 먼저 백그라운드로 실행한 후, 메인 제어 UI(`Go1_controller.py`)를 포그라운드로 실행합니다.
  * (구현 예정) Go1과 stabilizer의 독립적인 제어명령을 바탕으로 물체에 접근하고, 들어올리고 내리는 등의 전체 시스템의 제어명령을 취급합니다.
* **`Go1_controller.py` (사용자 인터페이스 및 명령 송신 노드):**
  * Tkinter 기반의 GUI 환경으로 오직 'Go1 제어 및 명령 생성'에만 집중하는 논블로킹(Non-blocking) 노드입니다.
  * `Unitree_legged_sdk 3.4.2`의 high-level control을 기반으로 사용자가 입력한 고위 주행 명령(속도, 주행거리, 선회반경)을 실시간으로 계산하여 주행 시간 주기를 도출합니다.
  * 로봇 자세 제어 모드(Down, Up, Recover, Stand)를 수동 변환할 수 있는 패널을 제공합니다.
* **`data_collection.py` (멀티 소스 데이터 통합 수집기):**
  * UI가 없는 백그라운드 데몬(Daemon) 프로세스로, 대량의 데이터 로깅 환경에서 데이터 누락을 방지합니다.
  * `Go1_controller.py`가 보낸 제어명령과 현재 Go1, Stabilizer, 조작당하는 물체의 IMU데이터를 수집합니다.
  * 외부 네트워크(`0.0.0.0`)와 로컬 루프백망(`127.0.0.1`)을 동시에 리스닝하며 비동기 멀티스레딩 데이터 파싱을 수행합니다.
* **`data_analysis.py` (수집 데이터 분석) :**
  * (구현 예정) 수집한 데이터들을 바탕으로 가감속 구간 가속도와 정속주행중 stabilizer 모듈에 발생하는 노이즈 등을 분석

#### 🤖 로봇 인터페이스 영역 (Robot Engine)
* **`go1_engine.cpp` (SDK 기반 LCM-UDP 게이트웨이):**
  * Unitree High-level SDK 기반의 C++ 프로그램으로, 로봇 내부 통신망(LCM)과 노트북 무선망(UDP) 사이의 변환 가교 역할을 수행합니다.
  * 파이썬 컨트롤러가 내리는 주행 패킷(`CMD`)을 100Hz 주기로 수신하여 로봇 하이레벨 제어 코어에 다이렉트로 매핑합니다.
  * 로봇 내부 IMU 데이터와 내부 추정 선속도 데이터를 파싱하여 파이썬 수집기(`9998`)로 `GO1` 패킷을 전송합니다.

---

### 2) 프로세스 간 상호작용 및 통신 흐름 (Data Interaction Flow)

모듈화된 파이썬 스크립트들과 하드웨어 간의 유기적인 데이터 교환 메커니즘은 다음과 같습니다.

```text
[ Go1_controller.py (UI) ]
       │
       ├─① (외부 UDP 통신: Port 9999) ──> [ go1_engine.cpp ] ──> 로봇(Go1) 기동 제어
       │
       └─② (내부 IPC 통신: Port 9995) ──> [ data_collection.py ]
                                                    ▲
                                                    │ ③ 멀티 소스 비동기 데이터 수신 (Port 9998)
                                                    ├── 유선 LAN : 로봇 상태 패킷 (GO1, ...)
                                                    ├── 무선 2.4G: 스태빌라이저 IMU 패킷 (STAB, ...)
                                                    └── 무선 2.4G: 최종적재물 IMU 패킷 (OBJ, ...)
```
