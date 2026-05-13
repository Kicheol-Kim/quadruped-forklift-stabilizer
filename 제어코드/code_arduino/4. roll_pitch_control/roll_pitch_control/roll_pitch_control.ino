#include <Dynamixel2Arduino.h>

#define DXL_SERIAL   Serial1
#define DIR_PIN      2 

const uint8_t DXL_ID_ROLL = 1;  // Roll 축
const uint8_t DXL_ID_PITCH = 2; // Pitch 축
const float DXL_PROTOCOL_VERSION = 2.0;

Dynamixel2Arduino dxl(DXL_SERIAL, DIR_PIN);

// 기구학 변환 함수 (Roll 1:3.5, Pitch 1:1)
float getRollMotorAngle(float targetRoll) {
  return 180.0 + (targetRoll * 3.5); 
}

float getPitchMotorAngle(float targetPitch) {
  return 180.0 + (targetPitch * 1.0);
}

void setup() {
  Serial.begin(115200);
  while(!Serial);

  dxl.begin(57600);
  dxl.setPortProtocolVersion(DXL_PROTOCOL_VERSION);

  // 모터 초기 세팅
  dxl.torqueOff(DXL_ID_ROLL);
  dxl.setOperatingMode(DXL_ID_ROLL, OP_POSITION);
  dxl.torqueOn(DXL_ID_ROLL);

  dxl.torqueOff(DXL_ID_PITCH);
  dxl.setOperatingMode(DXL_ID_PITCH, OP_POSITION);
  dxl.torqueOn(DXL_ID_PITCH);

  Serial.println("===== WASD 방향 테스트 시작 =====");
  Serial.println("W: Pitch +20 / S: Pitch -20");
  Serial.println("A: Roll -20 / D: Roll +20");
  Serial.println("스페이스바: 수평(0도) 복귀");
  
  // 0도(수평)로 초기화
  dxl.setGoalPosition(DXL_ID_ROLL, getRollMotorAngle(0.0), UNIT_DEGREE);
  dxl.setGoalPosition(DXL_ID_PITCH, getPitchMotorAngle(0.0), UNIT_DEGREE);
}

void loop() {
  // 시리얼 모니터에서 입력된 값이 있는지 확인
  if (Serial.available() > 0) {
    char key = Serial.read(); // 한 글자씩 읽기
    
    if (key == 'w' || key == 'W') {
      Serial.println("입력: W -> Pitch: +20도");
      dxl.setGoalPosition(DXL_ID_PITCH, getPitchMotorAngle(20.0), UNIT_DEGREE);
    }
    else if (key == 's' || key == 'S') {
      Serial.println("입력: S -> Pitch: -20도");
      dxl.setGoalPosition(DXL_ID_PITCH, getPitchMotorAngle(-20.0), UNIT_DEGREE);
    }
    else if (key == 'a' || key == 'A') {
      Serial.println("입력: A -> Roll: -20도");
      dxl.setGoalPosition(DXL_ID_ROLL, getRollMotorAngle(-20.0), UNIT_DEGREE);
    }
    else if (key == 'd' || key == 'D') {
      Serial.println("입력: D -> Roll: +20도");
      dxl.setGoalPosition(DXL_ID_ROLL, getRollMotorAngle(20.0), UNIT_DEGREE);
    }
    else if (key == ' ') {
      Serial.println("입력: Space -> 수평 복귀(0도)");
      dxl.setGoalPosition(DXL_ID_ROLL, getRollMotorAngle(0.0), UNIT_DEGREE);
      dxl.setGoalPosition(DXL_ID_PITCH, getPitchMotorAngle(0.0), UNIT_DEGREE);
    }
  }
}