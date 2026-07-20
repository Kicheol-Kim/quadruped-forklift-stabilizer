#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <fcntl.h>
#include <string.h> // for strlen
#include "unitree_legged_sdk/unitree_legged_sdk.h"

using namespace UNITREE_LEGGED_SDK;

int main() {
    std::cout << "🚀 [C++ Engine] Go1 제어 엔진 시작 (데이터 수집 확장판)..." << std::endl;

    // 1. Go1 통신 설정 (SDK)
    UDP udp(8090, "192.168.123.161", 8082, sizeof(HighCmd), sizeof(HighState));
    HighCmd cmd = {0};
    HighState state = {0};
    udp.InitCmdData(cmd);

    // 2. 파이썬의 제어 명령을 받을 로컬 수신 소켓 (포트 9999, Non-blocking)
    int rx_sock = socket(AF_INET, SOCK_DGRAM, 0);
    fcntl(rx_sock, F_SETFL, O_NONBLOCK); // 멈추지 않고 계속 루프를 돌기 위해 설정
    struct sockaddr_in rx_addr;
    rx_addr.sin_family = AF_INET;
    rx_addr.sin_port = htons(9999);
    rx_addr.sin_addr.s_addr = INADDR_ANY;
    bind(rx_sock, (struct sockaddr*)&rx_addr, sizeof(rx_addr));

    // 3. 파이썬으로 IMU/State 데이터를 보낼 로컬 송신 소켓 (포트 9998)
    int tx_sock = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in tx_addr;
    tx_addr.sin_family = AF_INET;
    tx_addr.sin_port = htons(9998);
    inet_pton(AF_INET, "127.0.0.1", &tx_addr.sin_addr);

    // 기본 제어 변수
    int received_mode = 1;
    float target_vx = 0.0, target_yaw = 0.0, target_pitch = 0.0;

    while (true) {
        // [A] 파이썬에서 새로운 명령이 왔는지 확인 (형식: "CMD,모드,속도,요속도,피치")
        char rx_buf[256];
        int n = recv(rx_sock, rx_buf, sizeof(rx_buf) - 1, 0);
        if (n > 0) {
            rx_buf[n] = '\0';
            sscanf(rx_buf, "CMD,%d,%f,%f,%f", &received_mode, &target_vx, &target_yaw, &target_pitch);
        }

        // [B] 수신된 명령을 로봇 제어 구조체에 적용
        cmd.mode = received_mode;
        cmd.euler[1] = target_pitch; // 피치(기울기)는 항상 적용

        if (cmd.mode == 2) { 
            // 일반 보행 모드 (Trot)
            cmd.gaitType = 1;
            cmd.velocity[0] = target_vx;
            cmd.yawSpeed = target_yaw;
            cmd.bodyHeight = 0.1;
        } 
        else if (cmd.mode == 3 || cmd.mode == 4) {
            // 계단 모드(3) 또는 장애물 모드(4)
            cmd.gaitType = (cmd.mode == 3) ? 3 : 4; 
            cmd.velocity[0] = target_vx; // 계단/장애물 모드에서도 전진 속도 인가 가능
            cmd.yawSpeed = target_yaw;
            cmd.bodyHeight = 0.1;
        } 
        else {
            // 그 외의 모드 (1, 5, 6, 7, 8) 에서는 이동 명령을 0으로 묶어 안전성 확보
            cmd.gaitType = 0;     
            cmd.velocity[0] = 0.0;
            cmd.yawSpeed = 0.0;

            // 모드 1(Force Stand)일 때는 자세(Pitch/Roll) 제어 가능
            if (cmd.mode == 1) {
                cmd.euler[1] = target_pitch; // Pitch 각도 제어
                // (필요 시 Roll 제어도 파이썬에서 받아서 추가 가능)
            }
        }

        // [C] 로봇에게 명령 송신 및 상태 수신 (기존 코드)
        udp.SetSend(cmd);
        udp.Send();

        if (udp.Recv() == 0) {
            udp.GetRecv(state);
            
            // 💡 [수정] 파이썬으로 보낼 거대한 바이너리 데이터 배열 생성
            // 총 92개의 float 데이터 (92 * 4 = 368 bytes, UDP로 전송하기 완벽한 크기)
            float tx_data[92];
            int idx = 0;

            // 1. IMU & Posture (13개)
            for(int i=0; i<3; i++) tx_data[idx++] = state.imu.rpy[i];           // [0~2] Roll, Pitch, Yaw (rad)
            for(int i=0; i<4; i++) tx_data[idx++] = state.imu.quaternion[i];    // [3~6] q0, q1, q2, q3
            for(int i=0; i<3; i++) tx_data[idx++] = state.imu.gyroscope[i];     // [7~9] gx, gy, gz
            for(int i=0; i<3; i++) tx_data[idx++] = state.imu.accelerometer[i]; // [10~12] ax, ay, az

            // 2. Velocity & Kinematics (7개)
            for(int i=0; i<3; i++) tx_data[idx++] = state.velocity[i];          // [13~15] Vx, Vy, Vz
            tx_data[idx++] = state.yawSpeed;                                    // [16] Yaw Rate
            for(int i=0; i<3; i++) tx_data[idx++] = state.position[i];          // [17~19] X, Y, Z

            // 3. Foot Force (8개)
            for(int i=0; i<4; i++) tx_data[idx++] = state.footForce[i];         // [20~23] 원시 발 반발력
            for(int i=0; i<4; i++) tx_data[idx++] = state.footForceEst[i];      // [24~27] 알고리즘 추정 발 반발력

            // 4. Motor States (12개 모터 * 5개 상태 = 60개) -> [28 ~ 87]
            for(int i=0; i<12; i++) {
                tx_data[idx++] = state.motorState[i].q;           // 위치(각도)
                tx_data[idx++] = state.motorState[i].dq;          // 속도
                tx_data[idx++] = state.motorState[i].ddq;         // 가속도
                tx_data[idx++] = state.motorState[i].tauEst;      // 추정 토크
                tx_data[idx++] = state.motorState[i].temperature; // 온도
            }

            // 5. System & Power (4개) -> [88 ~ 91]
            tx_data[idx++] = (float)state.bms.SOC;                // 배터리 잔량 (%)
            
            // 전류: comm.h를 보면 mA 단위이므로 A(암페어)로 변환
            tx_data[idx++] = (float)state.bms.current / 1000.0f;  

            // 전압: 10개 셀의 전압(mV)을 모두 더해서 전체 전압(V)으로 변환
            float total_voltage = 0.0f;
            for(int i = 0; i < 10; i++) {
                total_voltage += state.bms.cell_vol[i];
            }
            tx_data[idx++] = total_voltage / 1000.0f;             

            // 타임스탬프: HighState에 없으므로 0.0으로 빈자리 채우기 (배열 크기 92 유지)
            tx_data[idx++] = 0.0f;                                

            // 💡 바이너리 형태로 파이썬 수집기로 전송
            sendto(tx_sock, (const char*)tx_data, sizeof(tx_data), 0, (struct sockaddr*)&tx_addr, sizeof(tx_addr));
        }

        // 100Hz 주기
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return 0;
}