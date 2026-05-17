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

// 원점 변수
volatile float roll_center = 0.0; 
volatile float pitch_center = 0.0;

volatile float target_roll_pos_shared = 0.0;
volatile float target_pitch_pos_shared = 0.0;

// 💡 [변경] 축별 독립적인 하드웨어 튜닝용 변수 분리
volatile uint16_t hw_p_gain_roll = 200; 
volatile uint16_t hw_d_gain_roll = 350; 
volatile uint16_t hw_p_gain_pitch = 1000; 
volatile uint16_t hw_d_gain_pitch = 100; 

volatile float filter_alpha = 0.20; 
volatile bool update_gain_flag = false; 

volatile float filtered_target_roll = 0.0;
volatile float filtered_target_pitch = 0.0;

volatile bool motor_init_done = false; 
unsigned long last_print_time = 0;

// ==========================================
// 🦾 코어 1: 다이나믹셀 위치 제어 전담
// ==========================================
void motorControlTask() {
  dxl.begin(1000000); 
  dxl.setPortProtocolVersion(DXL_PROTOCOL_VERSION);

  dxl.torqueOff(DXL_ID_ROLL);
  dxl.setOperatingMode(DXL_ID_ROLL, OP_POSITION);
  dxl.torqueOn(DXL_ID_ROLL);

  dxl.torqueOff(DXL_ID_PITCH);
  dxl.setOperatingMode(DXL_ID_PITCH, OP_POSITION);
  dxl.torqueOn(DXL_ID_PITCH);

  dxl.writeControlTableItem(ControlTableItem::PROFILE_ACCELERATION, DXL_ID_ROLL, 0); 
  dxl.writeControlTableItem(ControlTableItem::PROFILE_VELOCITY, DXL_ID_ROLL, 0); 
  dxl.writeControlTableItem(ControlTableItem::PROFILE_ACCELERATION, DXL_ID_PITCH, 0); 
  dxl.writeControlTableItem(ControlTableItem::PROFILE_VELOCITY, DXL_ID_PITCH, 0);

  // 초기 게인값 독립적 설정
  dxl.writeControlTableItem(ControlTableItem::POSITION_P_GAIN, DXL_ID_ROLL, hw_p_gain_roll); 
  dxl.writeControlTableItem(ControlTableItem::POSITION_D_GAIN, DXL_ID_ROLL, hw_d_gain_roll); 
  dxl.writeControlTableItem(ControlTableItem::POSITION_P_GAIN, DXL_ID_PITCH, hw_p_gain_pitch); 
  dxl.writeControlTableItem(ControlTableItem::POSITION_D_GAIN, DXL_ID_PITCH, hw_d_gain_pitch);

  roll_center = dxl.getPresentPosition(DXL_ID_ROLL, UNIT_DEGREE);
  pitch_center = dxl.getPresentPosition(DXL_ID_PITCH, UNIT_DEGREE);
  
  target_roll_pos_shared = roll_center;
  target_pitch_pos_shared = pitch_center;
  filtered_target_roll = roll_center;  
  filtered_target_pitch = pitch_center;

  motor_init_done = true; 

  while (true) {
    // 💡 깃발이 올라오면 분리된 변수들을 각각의 모터에 업데이트
    if (update_gain_flag) {
      dxl.writeControlTableItem(ControlTableItem::POSITION_P_GAIN, DXL_ID_ROLL, hw_p_gain_roll); 
      dxl.writeControlTableItem(ControlTableItem::POSITION_D_GAIN, DXL_ID_ROLL, hw_d_gain_roll); 
      dxl.writeControlTableItem(ControlTableItem::POSITION_P_GAIN, DXL_ID_PITCH, hw_p_gain_pitch); 
      dxl.writeControlTableItem(ControlTableItem::POSITION_D_GAIN, DXL_ID_PITCH, hw_d_gain_pitch);
      update_gain_flag = false;
    }

    dxl.setGoalPosition(DXL_ID_ROLL, target_roll_pos_shared, UNIT_DEGREE);
    dxl.setGoalPosition(DXL_ID_PITCH, target_pitch_pos_shared, UNIT_DEGREE);
    rtos::ThisThread::sleep_for(2); 
  }
}

// ==========================================
// 🧠 코어 0: IMU 연산, 독립 튜닝 인터페이스 처리
// ==========================================
void setup() {
  Serial.begin(115200);  
  delay(2000); 

  if (!IMU.begin()) {
    Serial.println("❌ IMU 센서 초기화 실패!");
    while (1); 
  }
  
  motorThread.start(motorControlTask);
  
  while (!motor_init_done) {
    delay(10);
  }
  Serial.println("✅ 위치 제어 기반 스태빌라이저 (독립 튜닝) 준비 완료!");
  Serial.println("⌨️ 명령어: RP+ RP- RD+ RD- (Roll축) | PP+ PP- PD+ PD- (Pitch축) | F+ F- (필터)");
}

void loop() {
  // 1. 실시간 시리얼 독립 튜닝 명령어 처리
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    input.toUpperCase();

    // Roll 축 게인 조절
    if (input == "RP+") { hw_p_gain_roll += 50; update_gain_flag = true; }
    else if (input == "RP-") { if(hw_p_gain_roll >= 50) hw_p_gain_roll -= 50; else hw_p_gain_roll = 0; update_gain_flag = true; }
    else if (input == "RD+") { hw_d_gain_roll += 10; update_gain_flag = true; }
    else if (input == "RD-") { if(hw_d_gain_roll >= 10) hw_d_gain_roll -= 10; else hw_d_gain_roll = 0; update_gain_flag = true; }
    
    // Pitch 축 게인 조절
    else if (input == "PP+") { hw_p_gain_pitch += 50; update_gain_flag = true; }
    else if (input == "PP-") { if(hw_p_gain_pitch >= 50) hw_p_gain_pitch -= 50; else hw_p_gain_pitch = 0; update_gain_flag = true; }
    else if (input == "PD+") { hw_d_gain_pitch += 10; update_gain_flag = true; }
    else if (input == "PD-") { if(hw_d_gain_pitch >= 10) hw_d_gain_pitch -= 10; else hw_d_gain_pitch = 0; update_gain_flag = true; }
    
    // 필터 조절 (양축 공통 적용)
    else if (input == "F+") { filter_alpha += 0.05; if(filter_alpha > 1.0) filter_alpha = 1.0; }
    else if (input == "F-") { filter_alpha -= 0.05; if(filter_alpha < 0.01) filter_alpha = 0.01; }
  }

  // 2. 1초마다 현재 튜닝 상태 출력
  if (millis() - last_print_time >= 1000) {
    last_print_time = millis();
    Serial.print("🛠️ Roll  [P: "); Serial.print(hw_p_gain_roll); Serial.print(" / D: "); Serial.print(hw_d_gain_roll); Serial.print("]  |  ");
    Serial.print("Pitch [P: "); Serial.print(hw_p_gain_pitch); Serial.print(" / D: "); Serial.print(hw_d_gain_pitch); Serial.print("]  |  ");
    Serial.print("Filter: "); Serial.println(filter_alpha, 2);
  }

  // 3. IMU 및 필터 연산
  float ax, ay, az;
  if (IMU.accelerationAvailable()) {
    IMU.readAcceleration(ax, ay, az);

    float imu_roll  = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;
    float imu_pitch = atan2(ay, az) * 180.0 / PI;
    
    float raw_target_roll = roll_center - (imu_roll * 3.5);
    float raw_target_pitch = pitch_center + (-imu_pitch * 1.5);

    filtered_target_roll = (filter_alpha * raw_target_roll) + ((1.0 - filter_alpha) * filtered_target_roll);
    filtered_target_pitch = (filter_alpha * raw_target_pitch) + ((1.0 - filter_alpha) * filtered_target_pitch);

    float ROLL_MAX = roll_center + (30.0 * 3.5);
    float ROLL_MIN = roll_center - (30.0 * 3.5);
    float PITCH_MAX = pitch_center + (30.0 * 1.5);
    float PITCH_MIN = pitch_center - (180.0 * 1.5);

    target_roll_pos_shared = constrain(filtered_target_roll, ROLL_MIN, ROLL_MAX);
    target_pitch_pos_shared = constrain(filtered_target_pitch, PITCH_MIN, PITCH_MAX);
  }

  // PC(파이썬)로 현재 스태빌라이저의 Roll, Pitch 전송 (115200bps 권장)
  Serial.print("STAB,");
  Serial.print(stab_roll);  // 계산된 아두이노 Roll 변수
  Serial.print(",");
  Serial.println(stab_pitch); // 계산된 아두이노 Pitch 변수
  
  delay(10); 
}