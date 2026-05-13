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

volatile float Kp_pitch = 1.5; 
volatile float Kd_pitch = 0.05; 

volatile float target_pitch_vel = 0.0;

volatile float roll_center = 180.0;
volatile float pitch_center = 180.0;
volatile bool request_origin = false;

// 💡 코어 간 현재 각도 공유용 변수 추가
volatile float current_pitch_pos_shared = 180.0; 

unsigned long last_print_time = 0;
unsigned long last_pid_time = 0;
float last_pitch_error = 0.0;

// ==========================================
// 🦾 코어 1: 다이나믹셀 제어
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
    float current_pitch_pos = dxl.getPresentPosition(DXL_ID_PITCH, UNIT_DEGREE);
    
    // 💡 코어 0에서 에러를 계산할 수 있도록 현재 위치 전달
    current_pitch_pos_shared = current_pitch_pos; 

    if (request_origin) {
      pitch_center = current_pitch_pos;
      request_origin = false;
    }

    float PITCH_MAX = pitch_center + (30.0 * 1.5);
    float PITCH_MIN = pitch_center - (180.0 * 1.5);

    float p_vel = constrain(target_pitch_vel, -50.0, 50.0);

    if (current_pitch_pos >= PITCH_MAX && p_vel > 0) p_vel = 0.0;
    if (current_pitch_pos <= PITCH_MIN && p_vel < 0) p_vel = 0.0;

    dxl.setGoalVelocity(DXL_ID_ROLL, 0.0, UNIT_RPM); // Roll 잠금
    dxl.setGoalVelocity(DXL_ID_PITCH, p_vel, UNIT_RPM);

    rtos::ThisThread::sleep_for(2); 
  }
}

// ==========================================
// 🧠 코어 0: 목표 각도 기반 PD 연산
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
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    input.toUpperCase(); 

    if (input == "O") {
      request_origin = true; 
      Serial.println("✅ 원점 재설정 됨!");
    } 
    else if (input == "P+") Kp_pitch += 0.1;
    else if (input == "P-") Kp_pitch -= 0.1;
    else if (input == "D+") Kd_pitch += 0.01;
    else if (input == "D-") Kd_pitch -= 0.01;
    
    if(Kp_pitch < 0) Kp_pitch = 0;
    if(Kd_pitch < 0) Kd_pitch = 0;
  }

  if (millis() - last_print_time >= 1000) {
    last_print_time = millis();
    Serial.print("⏱️ Pitch 게인 | P: "); Serial.print(Kp_pitch);
    Serial.print("  D: "); Serial.println(Kd_pitch);
  }

  float ax, ay, az;
  if (IMU.accelerationAvailable()) {
    IMU.readAcceleration(ax, ay, az);

    unsigned long current_time = millis();
    float dt = (current_time - last_pid_time) / 1000.0;

    if (dt > 0) {
      float imu_pitch = atan2(ay, az) * 180.0 / PI;

      // 💡 1. 베이스 기울기(IMU)를 상쇄하기 위한 '목표 모터 각도' 계산 (기어비 1.5 적용)
      float target_motor_pitch = pitch_center + (-imu_pitch * 1.5);

      // 💡 2. 진짜 에러 = 목표 모터 각도 - 현재 모터 각도
      // 이제 모터가 돌면 current_pitch_pos_shared가 변하므로 에러가 0에 수렴함!
      float pitch_error = target_motor_pitch - current_pitch_pos_shared;

      float d_error = (pitch_error - last_pitch_error) / dt;

      // 3. PD 제어 출력
      target_pitch_vel = (Kp_pitch * pitch_error) + (Kd_pitch * d_error); 

      last_pitch_error = pitch_error;
      last_pid_time = current_time;
    }
  }
  delay(10); 
}