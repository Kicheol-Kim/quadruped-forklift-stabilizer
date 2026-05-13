#include <Dynamixel2Arduino.h>
#include <Arduino_LSM6DSOX.h>
#include <mbed.h>
#include <rtos.h>

#define DXL_SERIAL   Serial1
#define DIR_PIN      2

const uint8_t DXL_ID_ROLL = 1;  
const uint8_t DXL_ID_PITCH = 2; 
const float DXL_PROTOCOL_VERSION = 2.0;

Dynamixel2Arduino dxl(DXL_SERIAL, DIR_PIN);
rtos::Thread motorThread;

// --- Roll 전용 PD 제어 변수 ---
volatile float Kp_roll = 2.5; // Roll은 기어비가 커서 초기 P값을 조금 더 크게 잡습니다.
volatile float Kd_roll = 0.05; 

volatile float target_roll_vel = 0.0;

volatile float roll_center = 180.0;
volatile float pitch_center = 180.0;
volatile bool request_origin = false;

volatile float current_roll_pos_shared = 180.0; 

unsigned long last_print_time = 0;
unsigned long last_pid_time = 0;
float last_roll_error = 0.0;

// ==========================================
// 🦾 코어 1: 다이나믹셀 제어 (Pitch는 잠금, Roll만 제어)
// ==========================================
void motorControlTask() {
  dxl.begin(1000000); 
  dxl.setPortProtocolVersion(DXL_PROTOCOL_VERSION);

  dxl.torqueOff(DXL_ID_ROLL);
  dxl.setOperatingMode(DXL_ID_ROLL, OP_VELOCITY);
  dxl.torqueOn(DXL_ID_ROLL);

  dxl.torqueOff(DXL_ID_PITCH);
  dxl.setOperatingMode(DXL_ID_PITCH, OP_VELOCITY);
  dxl.torqueOn(DXL_ID_PITCH);

  while (true) {
    float current_roll_pos = dxl.getPresentPosition(DXL_ID_ROLL, UNIT_DEGREE);
    current_roll_pos_shared = current_roll_pos; 

    if (request_origin) {
      roll_center = current_roll_pos;
      request_origin = false;
    }

    // Roll 소프트웨어 리미트 (물리각 ±30도, 기어비 3.5배)
    float ROLL_MAX = roll_center + (30.0 * 3.5);
    float ROLL_MIN = roll_center - (30.0 * 3.5);

    float r_vel = constrain(target_roll_vel, -50.0, 50.0);

    if (current_roll_pos >= ROLL_MAX && r_vel > 0) r_vel = 0.0;
    if (current_roll_pos <= ROLL_MIN && r_vel < 0) r_vel = 0.0;

    // Pitch 축은 움직이지 않도록 0 RPM으로 단단히 고정 (락)
    dxl.setGoalVelocity(DXL_ID_PITCH, 0.0, UNIT_RPM);
    dxl.setGoalVelocity(DXL_ID_ROLL, r_vel, UNIT_RPM);

    rtos::ThisThread::sleep_for(2); 
  }
}

// ==========================================
// 🧠 코어 0: IMU 기반 PD 연산 및 UI
// ==========================================
void setup() {
  Serial.begin(115200);
  if (!IMU.begin()) {
    Serial.println("❌ IMU 초기화 실패!");
    while (1);
  }
  
  motorThread.start(motorControlTask);
  last_pid_time = millis();
}

void loop() {
  // 1. 게인값 실시간 조절
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    input.toUpperCase(); 

    if (input == "O") {
      request_origin = true; 
      Serial.println("✅ 원점 재설정 됨!");
    } 
    else if (input == "P+") Kp_roll += 0.1;
    else if (input == "P-") Kp_roll -= 0.1;
    else if (input == "D+") Kd_roll += 0.01;
    else if (input == "D-") Kd_roll -= 0.01;
    
    if(Kp_roll < 0) Kp_roll = 0;
    if(Kd_roll < 0) Kd_roll = 0;
  }

  // 2. 1초마다 현재 상태 출력
  if (millis() - last_print_time >= 1000) {
    last_print_time = millis();
    Serial.print("⏱️ Roll 게인 | P: "); Serial.print(Kp_roll);
    Serial.print("  D: "); Serial.println(Kd_roll);
  }

  // 3. PD 제어기 연산
  float ax, ay, az;
  if (IMU.accelerationAvailable()) {
    IMU.readAcceleration(ax, ay, az);

    unsigned long current_time = millis();
    float dt = (current_time - last_pid_time) / 1000.0;

    if (dt > 0) {
      // 확인된 IMU Roll 축 방향 계산
      float imu_roll = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;

      // 💡 1. 목표 모터 각도 계산 (기어비 3.5 및 역방향 부호 '-' 적용)
      float target_motor_roll = roll_center - (imu_roll * 3.5);

      // 💡 2. 진짜 에러 = 목표 모터 각도 - 현재 모터 각도
      float roll_error = target_motor_roll - current_roll_pos_shared;

      // 에러의 변화량 (미분)
      float d_error = (roll_error - last_roll_error) / dt;

      // 3. PD 제어 출력
      target_roll_vel = (Kp_roll * roll_error) + (Kd_roll * d_error); 4

      last_roll_error = roll_error;
      last_pid_time = current_time;
    }
  }
  delay(10); 
}