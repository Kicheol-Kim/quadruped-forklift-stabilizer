#include <SPI.h>

// 💡 [핵심 해결책] Arduino의 내장 abs 매크로를 무효화하여 Eigen 수학 라이브러리와의 충돌을 완벽히 방지합니다.
#undef abs 

#include "mpu9250.h"       
#include <MadgwickAHRS.h>
#include <WiFiNINA.h>
#include <WiFiUdp.h>

// =======================================================
// 📡 [네트워크 및 통신 설정]
// =======================================================
char ssid[] = "rml-kkch";           
char pass[] = "00000000";           
IPAddress pcIP(192, 168, 50, 1);    
unsigned int pcPort = 9998;         // 파이썬 통합 수신 포트
unsigned int localPort = 8889;      // 오브젝트용 로컬 포트

int status = WL_IDLE_STATUS;
WiFiUDP Udp;

// =======================================================
// 🧭 [최신 Bolder Flight MPU9255 & 필터 설정]
// =======================================================
const int MPU_CS_PIN = 10;
bfs::Mpu9250 mpu(&SPI, MPU_CS_PIN); 
Madgwick filter;              

unsigned long lastSendTime = 0;
const int sendInterval = 10;  // 100Hz 주기 (10ms)

void setup() {
  Serial.begin(115200);
  delay(3000); 
  Serial.println("\n--- [Tracking Object] Booting (v5.6.0 + MPU9255 + Madgwick) ---");

  // 1. 하드웨어 SPI 시작
  SPI.begin();
  delay(100);

  // 2. MPU9255 초기화 
  if (!mpu.Begin()) {
    while (1) {
      Serial.println("❌ MPU 초기화 실패! 배선을 확인해 주세요.");
      delay(1000);
    }
  }
  Serial.println("✅ MPU9255 9축 센서 인식 완료 (0x73 공식 지원)!");

  // 3. Madgwick 필터 100Hz 세팅
  filter.begin(100);

  // 4. 노트북 핫스팟 연결
  Serial.println("Wi-Fi 연결 시도 중...");
  while (status != WL_CONNECTED) {
    status = WiFi.begin(ssid, pass);
    Serial.print(".");
    delay(2000);
  }
  Serial.println("\n✅ Wi-Fi 연결 성공!");
  Udp.begin(localPort);
}

void loop() {
  // 5. 정확히 10ms(100Hz) 마다 실행
  if (millis() - lastSendTime >= sendInterval) {
    lastSendTime = millis();

    // 6. 센서 데이터 최신화
    mpu.Read();

    // 7. 9축 데이터 추출 및 단위 변환
    float ax = mpu.accel_x_mps2();
    float ay = mpu.accel_y_mps2();
    float az = mpu.accel_z_mps2();
    
    // 자이로 (rad/s -> deg/s 변환)
    float gx = mpu.gyro_x_radps() * 180.0f / PI;
    float gy = mpu.gyro_y_radps() * 180.0f / PI;
    float gz = mpu.gyro_z_radps() * 180.0f / PI;
    
    // 지자기 (uT)
    float mx = mpu.mag_x_ut();
    float my = mpu.mag_y_ut();
    float mz = mpu.mag_z_ut();

    // 8. 9축 Madgwick 필터 업데이트
    filter.update(gx, gy, gz, ax, ay, az, mx, my, mz);
    
    // 9. Roll, Pitch 추출 및 UDP 전송
    float obj_roll  = filter.getRoll();
    float obj_pitch = filter.getPitch();

    Udp.beginPacket(pcIP, pcPort);
    Udp.print("OBJ,");
    Udp.print(obj_roll, 3); 
    Udp.print(",");
    Udp.print(obj_pitch, 3);
    Udp.endPacket();
  }
}
