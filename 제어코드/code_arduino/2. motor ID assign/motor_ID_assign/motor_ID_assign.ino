#include <Dynamixel2Arduino.h>

#define DXL_SERIAL   Serial1
#define DIR_PIN      2 // 나노 RP2040에 연결한 방향 제어 핀

const uint8_t OLD_ID = 1; // 현재 ID (출고값)
const uint8_t NEW_ID = 2; // 바꿀 ID

Dynamixel2Arduino dxl(DXL_SERIAL, DIR_PIN);

void setup() {
  Serial.begin(115200);
  while(!Serial); // 시리얼 모니터 대기

  dxl.begin(57600); // 찾았던 기본 속도
  dxl.setPortProtocolVersion(2.0); // 프로토콜 2.0

  Serial.println("===== 다이나믹셀 ID 변경 =====");
  
  if (dxl.ping(OLD_ID)) {
    Serial.print("기존 ID("); Serial.print(OLD_ID); Serial.println(") 모터 발견!");
    
    // EEPROM(설정값)을 변경하려면 반드시 토크를 꺼야 해!
    dxl.torqueOff(OLD_ID); 
    
    // ID 변경 명령
    if(dxl.setID(OLD_ID, NEW_ID)) {
      Serial.print("✅ ID 변경 성공! 새 ID: ");
      Serial.println(NEW_ID);
      Serial.println("이제 이 모터에 '2번'이라고 네임펜이나 테이프로 표시해두세요!");
    } else {
      Serial.println("❌ ID 변경 실패 (통신 오류)");
    }
  } else {
    Serial.println("❌ 모터를 찾을 수 없습니다. 선 연결을 확인하세요.");
  }
}

void loop() {}