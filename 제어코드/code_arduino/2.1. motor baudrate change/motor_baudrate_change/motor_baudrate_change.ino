#include <Dynamixel2Arduino.h>

#define DXL_SERIAL   Serial1
#define DIR_PIN      2

Dynamixel2Arduino dxl(DXL_SERIAL, DIR_PIN);

void setup() {
  Serial.begin(115200);
  while(!Serial);

  // 1. 기존 속도(57600)로 통신 시작
  dxl.begin(57600);
  dxl.setPortProtocolVersion(2.0);

  Serial.println("보드레이트 변경을 시작합니다...");

  // 2. EEPROM 값을 바꾸려면 반드시 토크를 꺼야 함
  dxl.torqueOff(1);
  dxl.torqueOff(2);

  // 3. 모터의 보드레이트를 1Mbps로 변경
  dxl.setBaudrate(1, 1000000);
  dxl.setBaudrate(2, 1000000);

  // 4. 아두이노의 시리얼 통신 속도도 1Mbps로 재설정
  dxl.begin(1000000);

  // 5. 변경된 속도로 통신이 되는지 핑(Ping) 테스트
  if (dxl.ping(1) && dxl.ping(2)) {
    Serial.println("✅ 두 모터 모두 1,000,000 bps(1Mbps)로 변경 완료!");
    Serial.println("이제 메인 코드의 dxl.begin(57600)을 dxl.begin(1000000)으로 바꿔서 사용하세요.");
  } else {
    Serial.println("❌ 변경 실패 (연결을 확인하세요)");
  }
}

void loop() {}