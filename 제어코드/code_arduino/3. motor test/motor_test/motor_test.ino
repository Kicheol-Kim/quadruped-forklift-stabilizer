#include <Dynamixel2Arduino.h>

#define DXL_SERIAL   Serial1
#define DIR_PIN      2 // 나노 RP2040에 연결한 방향 제어 핀

const uint8_t DXL_ID_1 = 1; // 첫 번째 모터 ID
const uint8_t DXL_ID_2 = 2; // 두 번째 모터 ID
const float DXL_PROTOCOL_VERSION = 2.0; // XL430-W250-T의 기본 프로토콜

Dynamixel2Arduino dxl(DXL_SERIAL, DIR_PIN);

void setup() {
  Serial.begin(115200);
  while(!Serial);

  // 통신 속도 57600 bps 설정
  dxl.begin(57600);
  dxl.setPortProtocolVersion(DXL_PROTOCOL_VERSION);

  Serial.println("🚀 듀얼 모터 동시 구동 테스트 시작!");

  // --- 모터 1 초기 세팅 ---
  dxl.torqueOff(DXL_ID_1); // 모드 변경을 위해 토크 해제
  dxl.setOperatingMode(DXL_ID_1, OP_POSITION); // 위치 제어 모드
  dxl.torqueOn(DXL_ID_1); // 토크 켜기

  // --- 모터 2 초기 세팅 ---
  dxl.torqueOff(DXL_ID_2); // 모드 변경을 위해 토크 해제
  dxl.setOperatingMode(DXL_ID_2, OP_POSITION); // 위치 제어 모드
  dxl.torqueOn(DXL_ID_2); // 토크 켜기
}

void loop() {
  Serial.println("위치 A로 이동 (150도)");
  // 두 모터에 동시에 150도 위치 명령 전송
  dxl.setGoalPosition(DXL_ID_1, 150, UNIT_DEGREE);
  dxl.setGoalPosition(DXL_ID_2, 150, UNIT_DEGREE);
  delay(1000); // 1초 대기

  Serial.println("위치 B로 이동 (210도)");
  // 두 모터에 동시에 210도 위치 명령 전송
  dxl.setGoalPosition(DXL_ID_1, 210, UNIT_DEGREE);
  dxl.setGoalPosition(DXL_ID_2, 210, UNIT_DEGREE);
  delay(1000); // 1초 대기
}