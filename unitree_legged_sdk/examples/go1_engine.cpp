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
    int mode = 1; // 1: Stand, 2: Walk
    float target_vx = 0.0, target_yaw = 0.0, target_pitch = 0.0;

    while (true) {
        // [A] 파이썬에서 새로운 명령이 왔는지 확인 (형식: "CMD,모드,속도,요속도,피치")
        char rx_buf[256];
        int n = recv(rx_sock, rx_buf, sizeof(rx_buf) - 1, 0);
        if (n > 0) {
            rx_buf[n] = '\0';
            sscanf(rx_buf, "CMD,%d,%f,%f,%f", &mode, &target_vx, &target_yaw, &target_pitch);
        }

        // [B] 수신된 명령을 로봇 제어 구조체에 적용
        cmd.mode = mode;
        cmd.euler[1] = target_pitch; // 피치(기울기)는 항상 적용

        if (mode == 2) { // 걷기 모드
            cmd.gaitType = 1;
            cmd.velocity[0] = target_vx;
            cmd.yawSpeed = target_yaw;
            cmd.bodyHeight = 0.1; 
        } else { // 정지 모드 (대기 상태)
            cmd.gaitType = 0;     
            cmd.velocity[0] = 0.0;
            cmd.yawSpeed = 0.0;
            cmd.bodyHeight = 0.0; 
        }

        // [C] 로봇에게 명령 송신 및 상태 수신
        udp.SetSend(cmd);
        udp.Send();

        if (udp.Recv() == 0) {
            udp.GetRecv(state);
            
            // 파이썬으로 보낼 확장된 상태 데이터 패킷 생성
            // 포맷: GO1, vx, yaw_rate, roll, pitch, yaw, ax, ay, az
            char tx_buf[256];
            snprintf(tx_buf, sizeof(tx_buf), "GO1,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f",
                     state.velocity[0],                 // 로봇 추정 전진 속도 (m/s)
                     state.yawSpeed,                    // 로봇 추정 회전 속도 (rad/s)
                     state.imu.rpy[0] * 57.2958f,       // Roll (도 단위 변환)
                     state.imu.rpy[1] * 57.2958f,       // Pitch (도 단위 변환)
                     state.imu.rpy[2] * 57.2958f,       // Yaw (도 단위 변환)
                     state.imu.accelerometer[0],        // X축 가속도 (m/s^2)
                     state.imu.accelerometer[1],        // Y축 가속도 (m/s^2)
                     state.imu.accelerometer[2]);       // Z축 가속도 (m/s^2)
                     
            sendto(tx_sock, tx_buf, strlen(tx_buf), 0, (struct sockaddr*)&tx_addr, sizeof(tx_addr));
        }

        // 100Hz 주기
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return 0;
}