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

volatile float Kp_roll  = 1.0; 
volatile float Kd_roll  = 0.05;
volatile float Kp_pitch = 1.6; 
volatile float Kd_pitch = 0.06;

volatile float target_roll_vel = 0.0;
volatile float target_pitch_vel = 0.0;

// 초기값은 0으로 두고, setup 단계에서 덮어씌움
volatile float roll_center = 0.0; 
volatile float pitch_center = 0.0;

volatile float current_roll_pos_shared = 0.0;
volatile float current_pitch_pos_shared = 0.0;

volatile float current_imu_roll_shared = 0.0;
volatile float current_imu_pitch_shared = 0.0;
volatile bool motor_init_done = false; 

unsigned long last_print_time = 0;
unsigned long last_pid_time = 0;
float last_roll_error = 0.0;
float last_pitch_error = 0.0;

// ==========================================
// 🦾 코어 1: 다이나믹셀 통신 및 제어
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

  // 💡 [핵심 변경] 모터 토크를 켠 직후, 현재 각도를 읽어 영구적인 원점으로 설정
  roll_center = dxl.getPresentPosition(DXL_ID_ROLL, UNIT_DEGREE);
  pitch_center = dxl.getPresentPosition(DXL_ID_PITCH, UNIT_DEGREE);

  // 모터 초기화 및 원점 설정 완료를 메인 루프에 알림
  motor_init_done = true; 

  while (true) {
    float current_roll_pos = dxl.getPresentPosition(DXL_ID_ROLL, UNIT_DEGREE);
    float current_pitch_pos = dxl.getPresentPosition(DXL_ID_PITCH, UNIT_DEGREE);

    current_roll_pos_shared = current_roll_pos;
    current_pitch_pos_shared = current_pitch_pos;

    // 소프트웨어 리미트 적용
    float ROLL_MAX = roll_center + (30.0 * 3.5);
    float ROLL_MIN = roll_center - (30.0 * 3.5);
    float PITCH_MAX = pitch_center + (30.0 * 1.5);
    float PITCH_MIN = pitch_center - (180.0 * 1.5);

    float r_vel = constrain(target_roll_vel, -50.0, 50.0);
    float p_vel = constrain(target_pitch_vel, -50.0, 50.0);

    if (current_roll_pos >= ROLL_MAX && r_vel > 0) r_vel = 0.0;
    if (current_roll_pos <= ROLL_MIN && r_vel < 0) r_vel = 0.0;
    if (current_pitch_pos >= PITCH_MAX && p_vel > 0) p_vel = 0.0;
    if (current_pitch_pos <= PITCH_MIN && p_vel < 0) p_vel = 0.0;

    dxl.setGoalVelocity(DXL_ID_ROLL, r_vel, UNIT_RPM);
    dxl.setGoalVelocity(DXL_ID_PITCH, p_vel, UNIT_RPM);

    rtos::ThisThread::sleep_for(2); 
  }
}

// ==========================================
// 🧠 코어 0: 초기화 검증, IMU 연산 및 디버깅 출력
// ==========================================
void setup() {
  Serial.begin(115200);  
  delay(2000); 

  Serial.println("\n====== 🛠️ 시스템 부팅 시작 ======");
  Serial.print("[단계 1] IMU 센서 초기화... ");
  if (!IMU.begin()) {
    Serial.println("❌ 실패! (IMU 센서 응답 없음)");
    while (1); 
  }
  Serial.println("✅ 성공");

  Serial.print("[단계 2] 모터 스레드 통신 연결 및 자동 원점 설정... ");
  motorThread.start(motorControlTask);
  
  unsigned long wait_time = millis();
  while (!motor_init_done) {
    if (millis() - wait_time > 3000) {
      Serial.println("❌ 시간 초과! (모터 전원/통신선 확인 필요)");
      break; 
    }
    delay(10);
  }
  if (motor_init_done) {
    Serial.println("✅ 성공");
    Serial.print("🎯 설정된 원점 | Roll: "); Serial.print(roll_center);
    Serial.print("° / Pitch: "); Serial.println(pitch_center);
  }

  Serial.println("🚀 정상적으로 메인 루프에 진입합니다!\n");
  last_pid_time = millis();
}

void loop() {
  // 시리얼 입력 대기(request_origin) 로직 완전 삭제

  float ax, ay, az;
  if (IMU.accelerationAvailable()) {
    IMU.readAcceleration(ax, ay, az);

    unsigned long current_time = millis();
    float dt = (current_time - last_pid_time) / 1000.0;

    if (dt > 0) {
      float imu_roll  = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;
      float imu_pitch = atan2(ay, az) * 180.0 / PI;
      
      current_imu_roll_shared = imu_roll;
      current_imu_pitch_shared = imu_pitch;

      float target_motor_roll = roll_center - (imu_roll * 3.5);
      float target_motor_pitch = pitch_center + (-imu_pitch * 1.5);

      float roll_error = target_motor_roll - current_roll_pos_shared;
      float pitch_error = target_motor_pitch - current_pitch_pos_shared;

      float d_roll_error = (roll_error - last_roll_error) / dt;
      float d_pitch_error = (pitch_error - last_pitch_error) / dt;

      target_roll_vel = (Kp_roll * roll_error) + (Kd_roll * d_roll_error);
      target_pitch_vel = (Kp_pitch * pitch_error) + (Kd_pitch * d_pitch_error); 

      last_roll_error = roll_error;
      last_pitch_error = pitch_error;
      last_pid_time = current_time;
    }
  } 
  
  if (millis() - last_print_time >= 1000) {
    last_print_time = millis();
    
    Serial.println("📊 [실시간 상태 리포트]");
    Serial.print("  ▶ IMU 기울기 | Roll: "); Serial.print(current_imu_roll_shared, 2); 
    Serial.print("° \tPitch: "); Serial.print(current_imu_pitch_shared, 2); Serial.println("°");
    
    Serial.print("  ▶ 모터 각도  | Roll: "); Serial.print(current_roll_pos_shared, 2);
    Serial.print("° \tPitch: "); Serial.print(current_pitch_pos_shared, 2); Serial.println("°");

    Serial.print("  ▶ 출력 RPM   | Roll: "); Serial.print(target_roll_vel, 2);
    Serial.print(" \t\tPitch: "); Serial.println(target_pitch_vel, 2);
    Serial.println("----------------------------------------");
  }
  
  delay(10);
}