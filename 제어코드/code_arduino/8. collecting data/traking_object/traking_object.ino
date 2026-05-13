#include <SPI.h>
#include <WiFiNINA.h>
#include <WiFiUdp.h>
#include <Arduino_LSM6DSOX.h>

// =======================================================
// [통신 및 네트워크 설정]
// =======================================================
char ssid[] = "rml-kkch";
char pass[] = "00000000";
int status = WL_IDLE_STATUS;

WiFiUDP Udp;
unsigned int localPort = 8889;
IPAddress pcIP(192, 168, 50, 1);
unsigned int pcPort = 9999;
unsigned long lastSendTime = 0;
const int sendInterval = 100;

// =======================================================
// [전역 변수] - 💡 변수들을 바깥으로 빼서 에러 해결!
// =======================================================
float currentRoll = 0.0;
float currentPitch = 0.0;
float currentAx = 0.0;
float currentAy = 0.0;
float currentAz = 0.0;
unsigned long lastTime;

// =======================================================
// [Main] 자세 추정 및 데이터 송신
// =======================================================
void setup() {
  Serial.begin(115200);
  delay(3000); 
  
  Serial.println("\n--- [Arduino 2] 부팅 완료 ---");
  Serial.println("IMU 초기화 시작...");
  if (!IMU.begin()) {
    Serial.println("IMU 초기화 실패! (센서 연결 확인 필요)");
    while (1);
  }
  Serial.println("IMU 초기화 성공!");

  Serial.println("\nWi-Fi 연결 시도 중...");
  while (status != WL_CONNECTED) {
    status = WiFi.begin(ssid, pass);
    Serial.print(".");
    delay(2000); 
  }
  
  Serial.println("\nWi-Fi 연결 완료!");
  Serial.print("Assigned IP: ");
  Serial.println(WiFi.localIP());
  
  Udp.begin(localPort);
  Serial.println("UDP 통신 시작 (포트: 8889)");
  lastTime = micros();
}

void loop() {
  // 1. 센서 값 실시간 업데이트
  if (IMU.accelerationAvailable() && IMU.gyroscopeAvailable()) {
    float Gx, Gy, Gz;
    
    // 전역 변수에 바로 가속도 값을 저장합니다.
    IMU.readAcceleration(currentAx, currentAy, currentAz);
    IMU.readGyroscope(Gx, Gy, Gz);

    unsigned long currentTime = micros();
    float dt = (currentTime - lastTime) / 1000000.0;
    lastTime = currentTime;

    // 가속도 기반 Roll/Pitch 계산
    float accelRoll = atan2(currentAy, currentAz) * 180.0 / PI;
    float accelPitch = atan2(-currentAx, sqrt(currentAx * currentAx + currentAz * currentAz)) * 180.0 / PI;

    // 상보 필터 적용
    currentRoll = 0.96 * (currentRoll + Gx * dt) + 0.04 * accelRoll;
    currentPitch = 0.96 * (currentPitch + Gy * dt) + 0.04 * accelPitch;
  }

  // 2. 0.1초(100ms)마다 데이터 송신
  if (millis() - lastSendTime >= sendInterval) {
    lastSendTime = millis();

    // 노트북으로 데이터 쏘기
    Udp.beginPacket(pcIP, pcPort);
    Udp.print("B,");
    Udp.print(currentRoll); Udp.print(",");
    Udp.print(currentPitch); Udp.print(",");
    Udp.print(currentAx); Udp.print(",");
    Udp.print(currentAy); Udp.print(",");
    Udp.print(currentAz);
    Udp.endPacket();
  }
}