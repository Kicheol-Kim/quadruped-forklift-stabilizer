#include <Dynamixel2Arduino.h>

#define DXL_SERIAL   Serial1
#define DIR_PIN      2

Dynamixel2Arduino dxl(DXL_SERIAL, DIR_PIN);

void setup() {
  Serial.begin(115200);
  while(!Serial);

  Serial.println("🔍 다이나믹셀 스캔 시작...");

  // 프로토콜 1.0, 2.0 모두 확인
  for(int protocol = 1; protocol <= 2; protocol++) {
    dxl.setPortProtocolVersion((float)protocol);
    
    // 자주 쓰는 통신속도 4가지 스캔
    const int baudrates[] = {57600, 1000000, 9600, 115200};
    
    for(int b = 0; b < 4; b++) {
      dxl.begin(baudrates[b]);
      Serial.print("탐색 중... Protocol: ");
      Serial.print(protocol);
      Serial.print(" | Baudrate: ");
      Serial.println(baudrates[b]);

      // ID 0부터 252까지 핑(Ping) 날려보기
      for(int id = 0; id <= 252; id++) {
        if(dxl.ping(id)) {
          Serial.print("✅ 모터 찾음! -> ID: ");
          Serial.print(id);
          Serial.print(", Protocol: ");
          Serial.print(protocol);
          Serial.print(", Baudrate: ");
          Serial.println(baudrates[b]);
        }
      }
    }
  }
  Serial.println("🏁 스캔 종료.");
}

void loop() {}