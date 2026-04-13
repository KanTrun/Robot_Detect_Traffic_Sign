#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <TinyGPSPlus.h>
#include <MPU6050_light.h>

// Canonical pin map (phase-03 freeze)
constexpr uint8_t IN1 = 4;
constexpr uint8_t IN2 = 5;
constexpr uint8_t IN3 = 6;
constexpr uint8_t IN4 = 7;
constexpr uint8_t ENA = 15;
constexpr uint8_t ENB = 16;

constexpr uint8_t TRIG_L = 10;
constexpr uint8_t ECHO_L = 11;
constexpr uint8_t TRIG_C = 12;
constexpr uint8_t ECHO_C = 13;
constexpr uint8_t TRIG_R = 14;
constexpr uint8_t ECHO_R = 21;

constexpr uint8_t I2C_SDA = 8;
constexpr uint8_t I2C_SCL = 9;
constexpr uint8_t GPS_RX = 17;
constexpr uint8_t GPS_TX = 18;
constexpr uint8_t CAM_RX = 41;
constexpr uint8_t CAM_TX = 42;
constexpr uint8_t DF_RX = 47;
constexpr uint8_t DF_TX = 48;

constexpr uint32_t CAM_BAUD = 115200;
constexpr uint32_t DF_BAUD = 9600;
constexpr uint8_t DFPLAYER_DEFAULT_VOLUME = 30;
constexpr uint32_t GPS_BAUD = 9600;

constexpr uint8_t MAX_CANONICAL_BYTES = 20; // include LF
constexpr uint8_t CANONICAL_CLASS_MAX_ID = 4;
constexpr unsigned long AUDIO_COOLDOWN_MS = 1200;
constexpr unsigned long SIGN_HOLD_MS = 1500;
constexpr uint8_t SIGN_REPLACE_MARGIN_CONF100 = 15;
constexpr unsigned long TELEMETRY_PERIOD_MS = 500;

constexpr uint8_t SONAR_COUNT = 3;
constexpr uint8_t SONAR_MEDIAN_WINDOW = 3;
constexpr uint8_t SONAR_SCAN_SEQUENCE[] = {1, 0, 1, 2};
constexpr uint8_t SONAR_SCAN_SEQUENCE_LEN = sizeof(SONAR_SCAN_SEQUENCE) / sizeof(SONAR_SCAN_SEQUENCE[0]);
constexpr uint16_t SONAR_MAX_VALID_CM = 220;
constexpr unsigned long SONAR_INVALID_HOLD_MS = 350;
constexpr unsigned long SONAR_STALE_AFTER_MS = 120;
constexpr unsigned long SONAR_ALL_INVALID_RECOVER_MS = 250;
constexpr unsigned long SONAR_ECHO_TIMEOUT_US = 12000UL;
constexpr unsigned long STARTUP_WARMUP_MS = 1200;
constexpr unsigned long STARTUP_PRIME_MS = 220;
constexpr float IMPACT_DELTA_DEG = 8.0f;
constexpr unsigned long IMPACT_COOLDOWN_MS = 500;
constexpr uint8_t IMPACT_MIN_PWM = 180;
constexpr uint16_t FRONT_WARN_CM = 28;
constexpr unsigned long CENTER_OBSTACLE_LATCH_MS = 220;
constexpr unsigned long FRONT_RISK_PERSIST_MS = 180;
constexpr unsigned long IMPACT_CONFIRM_WINDOW_MS = 150;
constexpr uint16_t SIDE_PRESSURE_CM = 14;
constexpr uint16_t SIDE_CLEAR_CM = 20;
constexpr unsigned long LAST_FRONT_BLOCKED_MEMORY_MS = 600;
constexpr unsigned long BRAKE_HOLD_MS = 90;
constexpr unsigned long ESCAPE_REVERSE_MAX_MS = 900;

constexpr uint8_t OLED_I2C_ADDR = 0x3C;
constexpr uint16_t OLED_WIDTH = 128;
constexpr uint16_t OLED_HEIGHT = 64;
constexpr uint8_t GPS_PARSE_BUDGET_BYTES = 96;
constexpr unsigned long MPU_SAMPLE_PERIOD_MS = 40;
constexpr unsigned long GPS_DISPLAY_PERIOD_MS = 1000;
constexpr unsigned long GPS_FRESH_FIX_MS = 2000;
constexpr float MPU_EMA_ALPHA = 0.25f;

constexpr uint32_t MOTOR_PWM_FREQ = 2000;

struct QuickPatchConfig {
  uint8_t pwm_cap;
  uint8_t ramp_step;
  unsigned long ramp_interval_ms;
  unsigned long sample_interval_ms;
  uint8_t median_window;
  uint16_t outlier_reject_cm;
  uint16_t front_stop_cm;
  uint16_t front_resume_cm;
  uint16_t side_near_cm;
  uint16_t side_clear_cm;
  uint8_t hysteresis_cm;
  uint8_t cruise_pwm;
  uint8_t crawl_pwm_outer;
  uint8_t steer_pwm_inner;
  uint8_t steer_pwm_outer;
  uint8_t reverse_arc_pwm_inner;
  uint8_t reverse_arc_pwm_outer;
  unsigned long reverse_arc_ms;
  unsigned long direction_switch_gap_ms;
  unsigned long oled_refresh_ms;
  uint8_t oled_quantize_cm;
  uint8_t startup_straight_pwm;
  uint8_t turn_settle_pwm;
  uint8_t heading_trim_limit;
  int8_t left_bias_pwm;
  int8_t right_bias_pwm;
  unsigned long startup_straight_ms;
  unsigned long turn_settle_ms;
  float heading_kp;
  float heading_kd;
  float heading_deadband_deg;
  int8_t heading_trim_sign;
};

constexpr QuickPatchConfig QUICK_PATCH_CONFIG = {
  235, 18, 5,
  14, SONAR_MEDIAN_WINDOW, 140,
  22, 36, SIDE_PRESSURE_CM, SIDE_CLEAR_CM,
  8,
  198,
  174,
  130,
  188,
  184,
  220,
  320,
  14,
  250, 2,
  164,
  150,
  20,
  0,
  0,
  420,
  280,
  2.2f,
  0.35f,
  1.2f,
  1
};

struct RangeState {
  uint16_t raw_cm;
  uint16_t filtered_cm;
  uint16_t last_valid_cm;
  unsigned long last_valid_ms;
  bool valid;
  bool stale;
  uint16_t history[SONAR_MEDIAN_WINDOW];
  uint8_t history_count;
  uint8_t history_pos;
  uint16_t reject_count;
  uint8_t miss_count;
};

struct MotionTimers {
  unsigned long all_invalid_since_ms;
  unsigned long front_risk_since_ms;
  unsigned long last_front_blocked_ms;
};

struct StopSafeContext {
  unsigned long entered_ms;
  bool entered_after_run;
  uint8_t auto_recover_attempts;
  const char* last_reason;
};

struct ScanState {
  uint8_t index;
  unsigned long last_full_sweep_ms;
};

struct CenterObstacleLatch {
  unsigned long latched_until_ms;
  uint16_t last_block_cm;
};

struct SignState {
  uint8_t classId;
  uint8_t conf100;
  unsigned long holdUntilMs;
  unsigned long lastAudioMs;
  unsigned long lastUpdateMs;
  bool active;
};

struct SignAudioProfile {
  const char* classLabel;
  uint8_t track;
  const char* clipFile;
  const char* spokenPhrase;
};

struct GpsCache {
  bool hasFix;
  double lat;
  double lng;
  unsigned long lastFixMs;
  unsigned long lastDisplayMs;
  char line[24];
};

struct ImuFilterState {
  float pitch;
  float roll;
  float yaw;
  bool initialized;
};

struct HeadingHoldState {
  float reference_yaw;
  float yaw_error;
  float last_error;
  int16_t trim_pwm;
  unsigned long last_error_ms;
  bool reference_valid;
};

struct ImpactState {
  float last_pitch;
  float last_roll;
  unsigned long last_candidate_ms;
  unsigned long last_impact_ms;
  uint8_t consecutive_hits;
  bool latched;
};

enum WheelDir : uint8_t {
  WHEEL_STOP = 0,
  WHEEL_FWD = 1,
  WHEEL_REV = 2,
};

struct MotorMixCommand {
  WheelDir leftDir;
  WheelDir rightDir;
  uint8_t leftPwm;
  uint8_t rightPwm;
};

enum DriveMode : uint8_t {
  DRIVE_STARTUP_STRAIGHT = 0,
  DRIVE_CRAWL = 1,
  DRIVE_CRUISE = 2,
  DRIVE_STEER_LEFT = 3,
  DRIVE_STEER_RIGHT = 4,
  DRIVE_ESCAPE_REVERSE_ARC = 5,
  DRIVE_TURN_SETTLE = 6,
};

struct DirectionSwitchGuard {
  WheelDir activeDir;
  WheelDir pendingDir;
  unsigned long gapStartedMs;
  bool inGap;
};

constexpr char FW_VERSION[] = "esp32-s3-prod-v1.4";
constexpr char PROTO_VERSION[] = "sign-v1";

HardwareSerial camSerial(0);
HardwareSerial dfSerial(1);
HardwareSerial gpsSerial(2);

Adafruit_SSD1306 oled(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);
TinyGPSPlus gps;
MPU6050 mpu(Wire);
bool oledReady = false;
bool mpuReady = false;
float mpuPitch = 0.0f;
float mpuRoll = 0.0f;
float mpuYaw = 0.0f;
unsigned long lastMpuSampleMs = 0;
unsigned long lastOledRenderMs = 0;
unsigned long lastTelemetryMs = 0;
uint8_t lastSignClass = 0;
uint8_t lastSignConf100 = 0;
bool hasLastSign = false;
unsigned long bootMs = 0;

char lineBuf[MAX_CANONICAL_BYTES];
uint8_t lineLen = 0;
bool dropUntilLf = false;

unsigned long acceptedSigns = 0;
unsigned long droppedInvalid = 0;
unsigned long parseInternalFail = 0;
unsigned long uartOverflow = 0;

uint8_t lastTrack = 0;

uint16_t distL = 0;
uint16_t distC = 0;
uint16_t distR = 0;
uint16_t shownDistL = 0;
uint16_t shownDistC = 0;
uint16_t shownDistR = 0;
RangeState rangeStates[SONAR_COUNT] = {};
uint8_t sonarSampleIndex = 0;
unsigned long lastSonarSampleMs = 0;
bool centerSampleFresh = false;
ScanState scanState = {0, 0};

uint8_t targetPwmLeft = 0;
uint8_t targetPwmRight = 0;
uint8_t appliedPwmLeft = 0;
uint8_t appliedPwmRight = 0;
unsigned long lastRampMs = 0;

enum DriveCommand : uint8_t {
  DRIVE_CMD_STOP = 0,
  DRIVE_CMD_FORWARD = 1,
  DRIVE_CMD_REVERSE = 2,
  DRIVE_CMD_LEFT = 3,
  DRIVE_CMD_RIGHT = 4,
};

DriveCommand driveCommand = DRIVE_CMD_STOP;
unsigned long lastMotorDebugMs = 0;
DriveMode driveMode = DRIVE_STARTUP_STRAIGHT;
unsigned long driveModeEnteredMs = 0;
MotorMixCommand desiredMotorMix = {WHEEL_STOP, WHEEL_STOP, 0, 0};
DirectionSwitchGuard leftSwitchGuard = {WHEEL_STOP, WHEEL_STOP, 0, false};
DirectionSwitchGuard rightSwitchGuard = {WHEEL_STOP, WHEEL_STOP, 0, false};
bool motorGapActive = false;
const char* brakeTargetReason = "front_block";

enum MotionState : uint8_t {
  MOTION_RUN = 0,
  MOTION_BRAKE = 1,
  MOTION_STOP_SAFE = 2,
  MOTION_RECOVER = 3,
  MOTION_ESCAPE_REVERSE = 4,
  MOTION_ESCAPE_TURN = 5,
  MOTION_TURN_SETTLE = 6,
};

MotionState motionState = MOTION_STOP_SAFE;
unsigned long stateEnteredMs = 0;
uint16_t stopDynamicCm = QUICK_PATCH_CONFIG.front_stop_cm;
uint16_t resumeDynamicCm = QUICK_PATCH_CONFIG.front_resume_cm;
const char* motionReason = "warmup";
uint8_t escapeRetryCount = 0;
bool preferLeftTurn = true;
MotionTimers motionTimers = {};
StopSafeContext stopSafe = {0, false, 0, "warmup"};
CenterObstacleLatch centerLatch = {0, 0};
SignState signState = {};
GpsCache gpsCache = {false, 0.0, 0.0, 0, 0, "GPS NO FIX"};
ImuFilterState imuState = {};
HeadingHoldState headingHold = {};
ImpactState impactState = {0.0f, 0.0f, 0, 0, 0, false};
bool hasEnteredRun = false;

constexpr SignAudioProfile SIGN_AUDIO_TABLE[CANONICAL_CLASS_MAX_ID + 1] = {
  {"_background_", 1, "MP3/0001.mp3", "unused_test"},
  {"stop", 2, "MP3/0002.mp3", "Bien dung lai"},
  {"speed_limit", 3, "MP3/0003.mp3", "Bien gioi han toc do"},
  {"warning", 4, "MP3/0004.mp3", "Bien canh bao phia truoc"},
  {"other_reg", 5, "MP3/0005.mp3", "Bien chi dan hoac bien cam"},
};

static inline const SignAudioProfile& signAudioProfileForClass(uint8_t classId) {
  if (classId > CANONICAL_CLASS_MAX_ID) {
    return SIGN_AUDIO_TABLE[0];
  }
  return SIGN_AUDIO_TABLE[classId];
}

void printSignAudioMap() {
  for (uint8_t classId = 0; classId <= CANONICAL_CLASS_MAX_ID; ++classId) {
    const SignAudioProfile& profile = signAudioProfileForClass(classId);
    Serial.printf("AUDMAP class=%u label=%s track=%u file=%s phrase=%s\n",
                  classId,
                  profile.classLabel,
                  profile.track,
                  profile.clipFile,
                  profile.spokenPhrase);
  }
}

void dfSendCommand(uint8_t command, uint16_t param) {
  uint8_t frame[10] = {0x7E, 0xFF, 0x06, command, 0x00, (uint8_t)(param >> 8), (uint8_t)(param & 0xFF), 0x00, 0x00, 0xEF};
  uint16_t sum = frame[1] + frame[2] + frame[3] + frame[4] + frame[5] + frame[6];
  uint16_t checksum = 0U - sum;
  frame[7] = (uint8_t)(checksum >> 8);
  frame[8] = (uint8_t)(checksum & 0xFF);
  dfSerial.write(frame, sizeof(frame));
}

void setDfVolume(uint8_t volume) {
  if (volume > 30) volume = 30;
  dfSendCommand(0x06, volume);
}

void playMp3Folder(uint8_t track) {
  if (track < 1 || track > (CANONICAL_CLASS_MAX_ID + 1)) {
    parseInternalFail++;
    return;
  }
  // Some DFPlayer clones ignore the first boot-time volume command until playback starts.
  setDfVolume(DFPLAYER_DEFAULT_VOLUME);
  delay(80);
  dfSendCommand(0x12, track);
}

void setupMotors() {
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);
  analogWriteResolution(8);
  analogWriteFrequency(MOTOR_PWM_FREQ);
}

static inline void writeMotorPwm(uint8_t pwm) {
  analogWrite(ENA, pwm);
  analogWrite(ENB, pwm);
}

static inline void writeMotorPwm(uint8_t leftPwm, uint8_t rightPwm) {
  analogWrite(ENA, leftPwm);
  analogWrite(ENB, rightPwm);
}

static inline void applyWheelDirection(uint8_t pinA, uint8_t pinB, WheelDir dir) {
  if (dir == WHEEL_FWD) {
    digitalWrite(pinA, HIGH);
    digitalWrite(pinB, LOW);
    return;
  }
  if (dir == WHEEL_REV) {
    digitalWrite(pinA, LOW);
    digitalWrite(pinB, HIGH);
    return;
  }
  digitalWrite(pinA, LOW);
  digitalWrite(pinB, LOW);
}

static inline uint8_t clampMotorPwm(uint8_t pwm) {
  return (pwm > QUICK_PATCH_CONFIG.pwm_cap) ? QUICK_PATCH_CONFIG.pwm_cap : pwm;
}

static inline bool driveModeUsesHeadingHold(DriveMode mode) {
  return mode == DRIVE_STARTUP_STRAIGHT ||
         mode == DRIVE_CRAWL ||
         mode == DRIVE_CRUISE ||
         mode == DRIVE_TURN_SETTLE;
}

void clearHeadingHold(bool keepReference = false) {
  if (!keepReference) {
    headingHold.reference_valid = false;
    headingHold.reference_yaw = 0.0f;
  }
  headingHold.yaw_error = 0.0f;
  headingHold.last_error = 0.0f;
  headingHold.trim_pwm = 0;
  headingHold.last_error_ms = 0;
}

void resetHeadingReference(const char* reason) {
  if (!mpuReady || !imuState.initialized) {
    clearHeadingHold(false);
    return;
  }

  headingHold.reference_yaw = imuState.yaw;
  headingHold.reference_valid = true;
  headingHold.yaw_error = 0.0f;
  headingHold.last_error = 0.0f;
  headingHold.trim_pwm = 0;
  headingHold.last_error_ms = millis();
  Serial.printf("EVT:heading_ref,yaw=%.2f,reason=%s\n", headingHold.reference_yaw, reason);
}

int16_t computeHeadingTrim(unsigned long now) {
  if (!mpuReady || !imuState.initialized) {
    clearHeadingHold(false);
    return 0;
  }

  if (!headingHold.reference_valid) {
    resetHeadingReference("auto_ref");
  }

  float error = wrapAngle180(headingHold.reference_yaw - imuState.yaw);
  if (fabsf(error) < QUICK_PATCH_CONFIG.heading_deadband_deg) {
    error = 0.0f;
  }

  float derivative = 0.0f;
  if (headingHold.last_error_ms != 0 && now > headingHold.last_error_ms) {
    float dt = (now - headingHold.last_error_ms) * 1e-3f;
    if (dt > 0.0f) {
      derivative = (error - headingHold.last_error) / dt;
    }
  }

  headingHold.last_error_ms = now;
  headingHold.last_error = error;
  headingHold.yaw_error = error;

  float trimFloat = (QUICK_PATCH_CONFIG.heading_kp * error) + (QUICK_PATCH_CONFIG.heading_kd * derivative);
  trimFloat *= QUICK_PATCH_CONFIG.heading_trim_sign;
  int16_t trim = (int16_t)roundf(trimFloat);
  trim = clampI16(trim, -(int16_t)QUICK_PATCH_CONFIG.heading_trim_limit, (int16_t)QUICK_PATCH_CONFIG.heading_trim_limit);
  headingHold.trim_pwm = trim;
  return trim;
}

MotorMixCommand applyHeadingCompensation(const MotorMixCommand& cmd, unsigned long now) {
  if (cmd.leftDir != WHEEL_FWD || cmd.rightDir != WHEEL_FWD || !driveModeUsesHeadingHold(driveMode)) {
    clearHeadingHold(false);
    return cmd;
  }

  int16_t trim = computeHeadingTrim(now);
  int16_t leftPwm = (int16_t)cmd.leftPwm + QUICK_PATCH_CONFIG.left_bias_pwm - trim;
  int16_t rightPwm = (int16_t)cmd.rightPwm + QUICK_PATCH_CONFIG.right_bias_pwm + trim;

  MotorMixCommand adjusted = cmd;
  adjusted.leftPwm = clampPwmSigned(leftPwm);
  adjusted.rightPwm = clampPwmSigned(rightPwm);
  return adjusted;
}

void setMotorMix(const MotorMixCommand& cmd) {
  MotorMixCommand adjusted = applyHeadingCompensation(cmd, millis());

  desiredMotorMix.leftDir = adjusted.leftDir;
  desiredMotorMix.rightDir = adjusted.rightDir;
  targetPwmLeft = clampMotorPwm(adjusted.leftPwm);
  targetPwmRight = clampMotorPwm(adjusted.rightPwm);

  if (desiredMotorMix.leftDir == WHEEL_STOP) targetPwmLeft = 0;
  if (desiredMotorMix.rightDir == WHEEL_STOP) targetPwmRight = 0;

  if (desiredMotorMix.leftDir == WHEEL_FWD && desiredMotorMix.rightDir == WHEEL_FWD) {
    driveCommand = DRIVE_CMD_FORWARD;
  } else if (desiredMotorMix.leftDir == WHEEL_REV && desiredMotorMix.rightDir == WHEEL_REV) {
    driveCommand = DRIVE_CMD_REVERSE;
  } else if (desiredMotorMix.leftDir == WHEEL_REV && desiredMotorMix.rightDir == WHEEL_FWD) {
    driveCommand = DRIVE_CMD_LEFT;
  } else if (desiredMotorMix.leftDir == WHEEL_FWD && desiredMotorMix.rightDir == WHEEL_REV) {
    driveCommand = DRIVE_CMD_RIGHT;
  } else {
    driveCommand = DRIVE_CMD_STOP;
  }
}

void forceStopDrive() {
  desiredMotorMix = {WHEEL_STOP, WHEEL_STOP, 0, 0};
  targetPwmLeft = 0;
  targetPwmRight = 0;
  appliedPwmLeft = 0;
  appliedPwmRight = 0;
  leftSwitchGuard = {WHEEL_STOP, WHEEL_STOP, 0, false};
  rightSwitchGuard = {WHEEL_STOP, WHEEL_STOP, 0, false};
  motorGapActive = false;
  writeMotorPwm(0, 0);
  applyWheelDirection(IN1, IN2, WHEEL_STOP);
  applyWheelDirection(IN3, IN4, WHEEL_STOP);
  driveCommand = DRIVE_CMD_STOP;
  clearHeadingHold(false);
}

static inline void rampWheelPwm(uint8_t& appliedPwm, uint8_t targetPwm) {
  if (appliedPwm < targetPwm) {
    uint16_t next = (uint16_t)appliedPwm + QUICK_PATCH_CONFIG.ramp_step;
    appliedPwm = (next > targetPwm) ? targetPwm : (uint8_t)next;
  } else if (appliedPwm > targetPwm) {
    uint8_t step = QUICK_PATCH_CONFIG.ramp_step;
    if (appliedPwm <= step || (appliedPwm - step) < targetPwm) {
      appliedPwm = targetPwm;
    } else {
      appliedPwm = (uint8_t)(appliedPwm - step);
    }
  }
}

void updateWheelOutput(
  DirectionSwitchGuard& guard,
  WheelDir desiredDir,
  uint8_t targetPwm,
  uint8_t& appliedPwm,
  uint8_t pinA,
  uint8_t pinB
) {
  unsigned long now = millis();

  if (desiredDir == WHEEL_STOP || targetPwm == 0) {
    guard.activeDir = WHEEL_STOP;
    guard.pendingDir = WHEEL_STOP;
    guard.inGap = false;
    appliedPwm = 0;
    applyWheelDirection(pinA, pinB, WHEEL_STOP);
    return;
  }

  if (guard.activeDir == WHEEL_STOP) {
    guard.activeDir = desiredDir;
    guard.pendingDir = desiredDir;
    guard.inGap = false;
  } else if (guard.activeDir != desiredDir) {
    if (!guard.inGap) {
      guard.inGap = true;
      guard.pendingDir = desiredDir;
      guard.gapStartedMs = now;
    }

    if ((now - guard.gapStartedMs) < QUICK_PATCH_CONFIG.direction_switch_gap_ms) {
      appliedPwm = 0;
      applyWheelDirection(pinA, pinB, WHEEL_STOP);
      return;
    }

    guard.activeDir = guard.pendingDir;
    guard.inGap = false;
  }

  applyWheelDirection(pinA, pinB, guard.activeDir);
  rampWheelPwm(appliedPwm, targetPwm);
}

void updateMotorRamp(unsigned long now) {
  motorGapActive = leftSwitchGuard.inGap || rightSwitchGuard.inGap;
  if ((now - lastRampMs) < QUICK_PATCH_CONFIG.ramp_interval_ms) {
    if (motorGapActive) {
      writeMotorPwm(0, 0);
    }
    return;
  }
  lastRampMs = now;

  updateWheelOutput(leftSwitchGuard, desiredMotorMix.leftDir, targetPwmLeft, appliedPwmLeft, IN1, IN2);
  updateWheelOutput(rightSwitchGuard, desiredMotorMix.rightDir, targetPwmRight, appliedPwmRight, IN3, IN4);
  motorGapActive = leftSwitchGuard.inGap || rightSwitchGuard.inGap;
  writeMotorPwm(appliedPwmLeft, appliedPwmRight);
}

void setupSonar() {
  pinMode(TRIG_L, OUTPUT); pinMode(ECHO_L, INPUT);
  pinMode(TRIG_C, OUTPUT); pinMode(ECHO_C, INPUT);
  pinMode(TRIG_R, OUTPUT); pinMode(ECHO_R, INPUT);
  digitalWrite(TRIG_L, LOW);
  digitalWrite(TRIG_C, LOW);
  digitalWrite(TRIG_R, LOW);
}

uint16_t readSonarCm(uint8_t trigPin, uint8_t echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  unsigned long durationUs = pulseIn(echoPin, HIGH, SONAR_ECHO_TIMEOUT_US);
  if (durationUs == 0) return 0;
  return (uint16_t)(durationUs / 58UL);
}

uint16_t sortAndMedian3(uint16_t a, uint16_t b, uint16_t c) {
  if (a > b) {
    uint16_t t = a;
    a = b;
    b = t;
  }
  if (b > c) {
    uint16_t t = b;
    b = c;
    c = t;
  }
  if (a > b) {
    uint16_t t = a;
    a = b;
    b = t;
  }
  return b;
}

static inline uint16_t absDiffU16(uint16_t a, uint16_t b) {
  return (a > b) ? (uint16_t)(a - b) : (uint16_t)(b - a);
}

static inline uint16_t clampU16(uint16_t value, uint16_t minValue, uint16_t maxValue) {
  if (value < minValue) return minValue;
  if (value > maxValue) return maxValue;
  return value;
}

static inline int16_t clampI16(int16_t value, int16_t minValue, int16_t maxValue) {
  if (value < minValue) return minValue;
  if (value > maxValue) return maxValue;
  return value;
}

static inline float wrapAngle180(float angleDeg) {
  while (angleDeg > 180.0f) angleDeg -= 360.0f;
  while (angleDeg < -180.0f) angleDeg += 360.0f;
  return angleDeg;
}

static inline uint8_t clampPwmSigned(int16_t pwm) {
  if (pwm <= 0) return 0;
  if (pwm >= QUICK_PATCH_CONFIG.pwm_cap) return QUICK_PATCH_CONFIG.pwm_cap;
  return (uint8_t)pwm;
}

static inline uint16_t quantizeDistanceCm(uint16_t value) {
  if (value < QUICK_PATCH_CONFIG.oled_quantize_cm) return value;
  uint8_t step = QUICK_PATCH_CONFIG.oled_quantize_cm;
  return (uint16_t)(((value + (step / 2)) / step) * step);
}

static inline unsigned long rangeAgeMs(const RangeState& range, unsigned long now) {
  if (range.last_valid_ms == 0) return 9999;
  return now - range.last_valid_ms;
}

static inline char rangeQualityCode(const RangeState& range) {
  if (!range.valid) return 'I';
  return range.stale ? 'S' : 'V';
}

static inline uint16_t rangePreferenceCm(const RangeState& range) {
  if (range.valid && range.filtered_cm > 0) return range.filtered_cm;
  return range.last_valid_cm;
}

static inline bool rangeIsBlocked(const RangeState& range, uint16_t thresholdCm) {
  return range.valid && !range.stale && range.filtered_cm > 0 && range.filtered_cm <= thresholdCm;
}

static inline bool rangeIsFreshClear(const RangeState& range, uint16_t thresholdCm) {
  return range.valid && !range.stale && range.filtered_cm >= thresholdCm;
}

static inline bool rangeHasMotionData(const RangeState& range) {
  return range.valid && !range.stale && range.filtered_cm > 0;
}

static inline bool rangeIsFrontWarn(const RangeState& range) {
  return range.valid && !range.stale && range.filtered_cm > 0 && range.filtered_cm <= FRONT_WARN_CM;
}

static inline uint8_t countClearSensors(uint16_t frontClearCm, uint16_t sideClearCm) {
  uint8_t clearCount = 0;
  if (rangeIsFreshClear(rangeStates[0], sideClearCm)) clearCount++;
  if (rangeIsFreshClear(rangeStates[1], frontClearCm)) clearCount++;
  if (rangeIsFreshClear(rangeStates[2], sideClearCm)) clearCount++;
  return clearCount;
}

static inline unsigned long stopSafeHoldAgeMs(unsigned long now) {
  if (stopSafe.entered_ms == 0) return 0;
  return now - stopSafe.entered_ms;
}

static inline unsigned long scanSweepAgeMs(unsigned long now) {
  if (scanState.last_full_sweep_ms == 0) return 0;
  return now - scanState.last_full_sweep_ms;
}

static inline bool centerObstacleLatched(unsigned long now) {
  return centerLatch.latched_until_ms != 0 && now < centerLatch.latched_until_ms;
}

static inline void clearCenterObstacleLatch() {
  centerLatch.latched_until_ms = 0;
  centerLatch.last_block_cm = 0;
}

void formatRangeForOled(char* out, size_t outSize, const RangeState& range) {
  if (!range.valid || range.filtered_cm == 0) {
    snprintf(out, outSize, "--");
    return;
  }

  snprintf(out, outSize, "%u", quantizeDistanceCm(range.filtered_cm));
}

void syncRangeDistances() {
  distL = rangeStates[0].filtered_cm;
  distC = rangeStates[1].filtered_cm;
  distR = rangeStates[2].filtered_cm;
}

void updateGpsDisplayLine(unsigned long now) {
  if ((now - gpsCache.lastDisplayMs) < GPS_DISPLAY_PERIOD_MS) return;
  gpsCache.lastDisplayMs = now;

  if (!gpsCache.hasFix) {
    snprintf(gpsCache.line, sizeof(gpsCache.line), "GPS NO FIX");
    return;
  }

  unsigned long ageMs = now - gpsCache.lastFixMs;
  if (ageMs > GPS_FRESH_FIX_MS) {
    snprintf(gpsCache.line, sizeof(gpsCache.line), "GPS STALE %lus", ageMs / 1000UL);
    return;
  }

  snprintf(gpsCache.line, sizeof(gpsCache.line), "GPS %.4f %.4f", gpsCache.lat, gpsCache.lng);
}

void updateDynamicThresholds() {
  stopDynamicCm = QUICK_PATCH_CONFIG.front_stop_cm;
  resumeDynamicCm = QUICK_PATCH_CONFIG.front_resume_cm;
}

const char* motionStateName(MotionState state) {
  if (state == MOTION_RUN) return "RUN";
  if (state == MOTION_BRAKE) return "BRAKE";
  if (state == MOTION_STOP_SAFE) return "STOP_SAFE";
  if (state == MOTION_RECOVER) return "RECOVER";
  if (state == MOTION_ESCAPE_REVERSE) return "ESC_REV";
  if (state == MOTION_ESCAPE_TURN) return "ESC_TURN";
  return "TURN_SET";
}

const char* driveCommandName(DriveCommand cmd) {
  if (cmd == DRIVE_CMD_FORWARD) return "FWD";
  if (cmd == DRIVE_CMD_REVERSE) return "REV";
  if (cmd == DRIVE_CMD_LEFT) return "LEFT";
  if (cmd == DRIVE_CMD_RIGHT) return "RIGHT";
  return "STOP";
}

uint16_t applySonarFilter(uint8_t idx, uint16_t rawCm, unsigned long now) {
  RangeState& range = rangeStates[idx];
  if (rawCm > SONAR_MAX_VALID_CM) rawCm = 0;
  range.raw_cm = rawCm;

  uint16_t ref = range.filtered_cm;
  bool allowCenterClearJump =
    idx == 1 &&
    rawCm >= QUICK_PATCH_CONFIG.front_resume_cm &&
    ref > 0 &&
    ref <= QUICK_PATCH_CONFIG.front_stop_cm;
  if (!allowCenterClearJump &&
      rawCm > 0 &&
      ref > 0 &&
      rawCm > ref &&
      absDiffU16(rawCm, ref) > QUICK_PATCH_CONFIG.outlier_reject_cm) {
    rawCm = 0;
    range.reject_count++;
  }

  if (rawCm > 0) {
    range.miss_count = 0;
    uint8_t window = QUICK_PATCH_CONFIG.median_window;
    if (window == 0 || window > SONAR_MEDIAN_WINDOW) window = SONAR_MEDIAN_WINDOW;

    uint8_t slot = range.history_pos;
    range.history[slot] = rawCm;
    range.history_pos = (uint8_t)((slot + 1) % window);
    if (range.history_count < window) {
      range.history_count++;
    }
    range.last_valid_ms = now;

    bool centerFastPath = idx == 1 && rawCm <= FRONT_WARN_CM;
    if (centerFastPath) {
      range.filtered_cm = rawCm;
    } else if (window == SONAR_MEDIAN_WINDOW && range.history_count >= window) {
      range.filtered_cm = sortAndMedian3(
        range.history[0],
        range.history[1],
        range.history[2]
      );
    } else {
      range.filtered_cm = rawCm;
    }
    range.last_valid_cm = range.filtered_cm;
    range.valid = true;
    range.stale = false;

    if (idx == 1) {
      if (rawCm <= stopDynamicCm) {
        bool wasLatched = centerObstacleLatched(now);
        centerLatch.latched_until_ms = now + CENTER_OBSTACLE_LATCH_MS;
        centerLatch.last_block_cm = rawCm;
        if (!wasLatched || rawCm < range.last_valid_cm) {
          Serial.printf("EVT:center_latch,cm=%u\n", rawCm);
        }
      } else if (rawCm >= QUICK_PATCH_CONFIG.front_resume_cm) {
        clearCenterObstacleLatch();
      }
    }
    return range.filtered_cm;
  }

  if (range.miss_count < 250) range.miss_count++;
  unsigned long ageMs = rangeAgeMs(range, now);
  bool holdActive = ageMs <= SONAR_INVALID_HOLD_MS;

  if (range.last_valid_cm > 0 && holdActive) {
    range.filtered_cm = range.last_valid_cm;
    range.valid = true;
    range.stale = ageMs > SONAR_STALE_AFTER_MS;
    return range.filtered_cm;
  }

  range.filtered_cm = 0;
  range.valid = false;
  range.stale = false;
  return 0;
}

void updateSonarSample() {
  centerSampleFresh = false;
  unsigned long now = millis();
  if ((now - lastSonarSampleMs) < QUICK_PATCH_CONFIG.sample_interval_ms) return;

  uint8_t idx = SONAR_SCAN_SEQUENCE[sonarSampleIndex];
  scanState.index = idx;
  sonarSampleIndex = (uint8_t)((sonarSampleIndex + 1) % SONAR_SCAN_SEQUENCE_LEN);
  if (sonarSampleIndex == 0) {
    scanState.last_full_sweep_ms = now;
  }

  uint16_t filtered = 0;
  if (idx == 0) {
    filtered = applySonarFilter(0, readSonarCm(TRIG_L, ECHO_L), now);
    distL = filtered;
  } else if (idx == 1) {
    centerSampleFresh = true;
    filtered = applySonarFilter(1, readSonarCm(TRIG_C, ECHO_C), now);
    distC = filtered;
  } else {
    filtered = applySonarFilter(2, readSonarCm(TRIG_R, ECHO_R), now);
    distR = filtered;
  }

  lastSonarSampleMs = now;
  syncRangeDistances();
}

void setMotionState(MotionState next, const char* reason) {
  if (motionState == next && strcmp(motionReason, reason) == 0) return;
  Serial.printf("EVT:%s->%s,reason=%s\n", motionStateName(motionState), motionStateName(next), reason);
  motionState = next;
  motionReason = reason;
  unsigned long now = millis();
  stateEnteredMs = now;
  if (next == MOTION_STOP_SAFE) {
    stopSafe.entered_ms = now;
    stopSafe.entered_after_run = hasEnteredRun;
    stopSafe.last_reason = reason;
    clearHeadingHold(false);
  }
  if (next == MOTION_RUN) {
    hasEnteredRun = true;
    stopSafe.auto_recover_attempts = 0;
    clearCenterObstacleLatch();
    motionTimers.all_invalid_since_ms = 0;
    motionTimers.front_risk_since_ms = 0;
    escapeRetryCount = 0;
  }
}

const char* driveModeName(DriveMode mode) {
  if (mode == DRIVE_STARTUP_STRAIGHT) return "ALIGN";
  if (mode == DRIVE_CRUISE) return "CRUISE";
  if (mode == DRIVE_CRAWL) return "CRAWL";
  if (mode == DRIVE_STEER_LEFT) return "ST_L";
  if (mode == DRIVE_STEER_RIGHT) return "ST_R";
  if (mode == DRIVE_TURN_SETTLE) return "SETTLE";
  return "REV_ARC";
}

char wheelDirCode(WheelDir dir) {
  if (dir == WHEEL_FWD) return 'F';
  if (dir == WHEEL_REV) return 'R';
  return 'S';
}

void setDriveMode(DriveMode next, const char* reason) {
  if (driveMode == next && strcmp(motionReason, reason) == 0) {
    motionReason = reason;
    return;
  }
  Serial.printf("EVT:mode_%s->%s,reason=%s\n", driveModeName(driveMode), driveModeName(next), reason);
  driveMode = next;
  driveModeEnteredMs = millis();
  motionReason = reason;
}

bool chooseTurnLeftBySpace() {
  uint16_t l = rangeHasMotionData(rangeStates[0]) ? rangeStates[0].filtered_cm : rangeStates[0].last_valid_cm;
  uint16_t r = rangeHasMotionData(rangeStates[2]) ? rangeStates[2].filtered_cm : rangeStates[2].last_valid_cm;
  const uint16_t marginCm = 6;

  if (l == 0 && r == 0) return preferLeftTurn;
  if (l == 0) return false;
  if (r == 0) return true;

  if (l > (uint16_t)(r + marginCm)) return true;
  if (r > (uint16_t)(l + marginCm)) return false;

  return preferLeftTurn;
}

MotorMixCommand buildMotorMixForMode(DriveMode mode) {
  if (mode == DRIVE_STARTUP_STRAIGHT) {
    return {WHEEL_FWD, WHEEL_FWD, QUICK_PATCH_CONFIG.startup_straight_pwm, QUICK_PATCH_CONFIG.startup_straight_pwm};
  }
  if (mode == DRIVE_CRUISE) {
    return {WHEEL_FWD, WHEEL_FWD, QUICK_PATCH_CONFIG.cruise_pwm, QUICK_PATCH_CONFIG.cruise_pwm};
  }
  if (mode == DRIVE_CRAWL) {
    return {WHEEL_FWD, WHEEL_FWD, QUICK_PATCH_CONFIG.crawl_pwm_outer, QUICK_PATCH_CONFIG.crawl_pwm_outer};
  }
  if (mode == DRIVE_TURN_SETTLE) {
    if (preferLeftTurn) {
      return {WHEEL_FWD, WHEEL_FWD, QUICK_PATCH_CONFIG.turn_settle_pwm, QUICK_PATCH_CONFIG.steer_pwm_outer};
    }
    return {WHEEL_FWD, WHEEL_FWD, QUICK_PATCH_CONFIG.steer_pwm_outer, QUICK_PATCH_CONFIG.turn_settle_pwm};
  }
  if (mode == DRIVE_STEER_LEFT) {
    return {WHEEL_FWD, WHEEL_FWD, QUICK_PATCH_CONFIG.steer_pwm_inner, QUICK_PATCH_CONFIG.steer_pwm_outer};
  }
  if (mode == DRIVE_STEER_RIGHT) {
    return {WHEEL_FWD, WHEEL_FWD, QUICK_PATCH_CONFIG.steer_pwm_outer, QUICK_PATCH_CONFIG.steer_pwm_inner};
  }
  if (preferLeftTurn) {
    return {WHEEL_REV, WHEEL_REV, QUICK_PATCH_CONFIG.reverse_arc_pwm_outer, QUICK_PATCH_CONFIG.reverse_arc_pwm_inner};
  }
  return {WHEEL_REV, WHEEL_REV, QUICK_PATCH_CONFIG.reverse_arc_pwm_inner, QUICK_PATCH_CONFIG.reverse_arc_pwm_outer};
}

void updateMotion() {
  updateSonarSample();
  unsigned long now = millis();
  updateDynamicThresholds();
  RangeState& left = rangeStates[0];
  RangeState& center = rangeStates[1];
  RangeState& right = rangeStates[2];

  bool centerBlocked = rangeIsBlocked(center, stopDynamicCm);
  bool centerWarn = rangeIsFrontWarn(center);
  bool centerLatched = centerObstacleLatched(now);
  bool frontBlocked = centerBlocked || centerLatched;
  bool frontWarn = centerWarn && !frontBlocked;
  bool leftBlocked = rangeIsBlocked(left, QUICK_PATCH_CONFIG.side_near_cm);
  bool rightBlocked = rangeIsBlocked(right, QUICK_PATCH_CONFIG.side_near_cm);
  bool bothSidePressure = leftBlocked && rightBlocked;
  bool frontFreshClear = rangeIsFreshClear(center, resumeDynamicCm) && !centerLatched;
  bool leftFresh = rangeHasMotionData(left);
  bool centerFresh = rangeHasMotionData(center);
  bool rightFresh = rangeHasMotionData(right);
  bool allMotionBlind = !leftFresh && !centerFresh && !rightFresh;
  bool startupPrimeDone = !hasEnteredRun && ((now - bootMs) >= STARTUP_PRIME_MS);
  bool startupWarmupActive = !hasEnteredRun && ((now - bootMs) < STARTUP_WARMUP_MS);
  bool startupWarmupDone = !hasEnteredRun && !startupWarmupActive;
  uint8_t clearSensorCount = countClearSensors(resumeDynamicCm, QUICK_PATCH_CONFIG.side_clear_cm);
  bool impactPending = impactState.latched;

  if (allMotionBlind) {
    if (motionTimers.all_invalid_since_ms == 0) {
      motionTimers.all_invalid_since_ms = now;
    }
  } else {
    motionTimers.all_invalid_since_ms = 0;
  }

  bool blindRecoverNeeded =
    hasEnteredRun &&
    motionTimers.all_invalid_since_ms != 0 &&
    (now - motionTimers.all_invalid_since_ms) >= SONAR_ALL_INVALID_RECOVER_MS &&
    motionTimers.last_front_blocked_ms != 0 &&
    (now - motionTimers.last_front_blocked_ms) <= LAST_FRONT_BLOCKED_MEMORY_MS;

  if (frontFreshClear && center.filtered_cm >= QUICK_PATCH_CONFIG.front_resume_cm) {
    clearCenterObstacleLatch();
    centerLatched = false;
    frontFreshClear = true;
    frontBlocked = centerBlocked;
    frontWarn = centerWarn && !frontBlocked;
  }

  if (frontBlocked) {
    if (motionTimers.front_risk_since_ms == 0) {
      motionTimers.front_risk_since_ms = now;
    }
  } else {
    motionTimers.front_risk_since_ms = 0;
  }

  if (centerBlocked) {
    motionTimers.last_front_blocked_ms = now;
  }

  bool frontRiskPersistent =
    motionTimers.front_risk_since_ms != 0 &&
    (now - motionTimers.front_risk_since_ms) >= FRONT_RISK_PERSIST_MS;

  bool impactConfirmed =
    impactState.latched &&
    frontBlocked &&
    (now - impactState.last_impact_ms) <= IMPACT_CONFIRM_WINDOW_MS;
  const char* escapeReason = nullptr;

  if (impactState.latched && (now - impactState.last_impact_ms) > IMPACT_CONFIRM_WINDOW_MS) {
    impactState.latched = false;
  }

  if (centerBlocked) {
    escapeReason = "front_block";
  } else if (impactConfirmed) {
    escapeReason = "impact_confirm";
  } else if (blindRecoverNeeded) {
    escapeReason = "blind_blocked";
  } else if (frontRiskPersistent) {
    escapeReason = "front_block_hold";
  }

  if (motionState == MOTION_STOP_SAFE) {
    setMotorMix({WHEEL_STOP, WHEEL_STOP, 0, 0});

    bool startupValidFrontBlock = centerFresh && centerBlocked;
    if (!hasEnteredRun && frontFreshClear && !leftBlocked && !rightBlocked) {
      setMotionState(MOTION_RUN, "center_ready");
      resetHeadingReference("startup_release");
      setDriveMode(DRIVE_STARTUP_STRAIGHT, "startup_align");
      setMotorMix(buildMotorMixForMode(DRIVE_STARTUP_STRAIGHT));
    } else if (!hasEnteredRun && startupPrimeDone && centerFresh && !startupValidFrontBlock && clearSensorCount >= 1) {
      setMotionState(MOTION_RUN, "startup_prime");
      resetHeadingReference("startup_prime");
      setDriveMode(DRIVE_STARTUP_STRAIGHT, "startup_align");
      setMotorMix(buildMotorMixForMode(DRIVE_STARTUP_STRAIGHT));
    } else if (!hasEnteredRun && startupWarmupDone && startupValidFrontBlock) {
      preferLeftTurn = chooseTurnLeftBySpace();
      setMotionState(MOTION_RUN, "startup_escape");
      setDriveMode(DRIVE_ESCAPE_REVERSE_ARC, "startup_escape");
      setMotorMix(buildMotorMixForMode(DRIVE_ESCAPE_REVERSE_ARC));
    } else if (!hasEnteredRun && startupWarmupDone && clearSensorCount >= 1) {
      setMotionState(MOTION_RUN, "warmup_force");
      resetHeadingReference("warmup_force");
      setDriveMode(DRIVE_STARTUP_STRAIGHT, "startup_align");
      setMotorMix(buildMotorMixForMode(DRIVE_STARTUP_STRAIGHT));
    } else if (hasEnteredRun) {
      setMotionState(MOTION_RUN, "runtime_resume");
      resetHeadingReference("runtime_resume");
      setDriveMode(DRIVE_CRAWL, "runtime_resume");
      setMotorMix(buildMotorMixForMode(DRIVE_CRAWL));
    }

    updateMotorRamp(now);
    return;
  }
  if (!hasEnteredRun) {
    setMotorMix({WHEEL_STOP, WHEEL_STOP, 0, 0});
    updateMotorRamp(now);
    return;
  }

  if (motionState == MOTION_BRAKE) {
    if ((now - stateEnteredMs) >= BRAKE_HOLD_MS) {
      preferLeftTurn = chooseTurnLeftBySpace();
      setMotionState(MOTION_RUN, "brake_release");
      setDriveMode(DRIVE_ESCAPE_REVERSE_ARC, brakeTargetReason);
      setMotorMix(buildMotorMixForMode(DRIVE_ESCAPE_REVERSE_ARC));
    } else {
      setMotorMix({WHEEL_STOP, WHEEL_STOP, 0, 0});
    }
    updateMotorRamp(now);
    return;
  }

  if (escapeReason != nullptr && driveMode != DRIVE_ESCAPE_REVERSE_ARC) {
    preferLeftTurn = chooseTurnLeftBySpace();
    brakeTargetReason = escapeReason;
    if (impactConfirmed || centerBlocked) {
      impactState.latched = false;
    }
    setMotionState(MOTION_BRAKE, escapeReason);
    setMotorMix({WHEEL_STOP, WHEEL_STOP, 0, 0});
    updateMotorRamp(now);
    return;
  }

  if (motionState != MOTION_RUN) {
    setMotionState(MOTION_RUN, "continuous_drive");
  }

  if (!frontBlocked && !frontWarn) {
    if (leftBlocked && !rightBlocked) preferLeftTurn = false;
    if (rightBlocked && !leftBlocked) preferLeftTurn = true;
  }

  DriveMode nextMode = driveMode;
  const char* nextReason = motionReason;

  if (driveMode == DRIVE_STARTUP_STRAIGHT &&
      (now - driveModeEnteredMs) < QUICK_PATCH_CONFIG.startup_straight_ms) {
    nextMode = DRIVE_STARTUP_STRAIGHT;
    nextReason = "startup_align";
  } else if (driveMode == DRIVE_TURN_SETTLE &&
             (now - driveModeEnteredMs) < QUICK_PATCH_CONFIG.turn_settle_ms) {
    nextMode = DRIVE_TURN_SETTLE;
    nextReason = "turn_settle";
  } else if (driveMode == DRIVE_ESCAPE_REVERSE_ARC &&
             (now - driveModeEnteredMs) < QUICK_PATCH_CONFIG.reverse_arc_ms) {
    nextMode = DRIVE_ESCAPE_REVERSE_ARC;
  } else {
    bool reverseArcTimedOut =
      driveMode == DRIVE_ESCAPE_REVERSE_ARC &&
      (now - driveModeEnteredMs) >= ESCAPE_REVERSE_MAX_MS;

    if (driveMode == DRIVE_ESCAPE_REVERSE_ARC && !frontFreshClear && !reverseArcTimedOut) {
      nextMode = DRIVE_ESCAPE_REVERSE_ARC;
      nextReason = "escape_extend";
    } else if (centerBlocked) {
      preferLeftTurn = chooseTurnLeftBySpace();
      nextMode = DRIVE_ESCAPE_REVERSE_ARC;
      nextReason = "front_block";
      impactState.latched = false;
    } else if (impactConfirmed) {
      preferLeftTurn = chooseTurnLeftBySpace();
      nextMode = DRIVE_ESCAPE_REVERSE_ARC;
      nextReason = "impact_confirm";
      impactState.latched = false;
    } else if (blindRecoverNeeded) {
      preferLeftTurn = chooseTurnLeftBySpace();
      nextMode = DRIVE_ESCAPE_REVERSE_ARC;
      nextReason = "blind_blocked";
    } else if (frontRiskPersistent) {
      preferLeftTurn = chooseTurnLeftBySpace();
      nextMode = DRIVE_ESCAPE_REVERSE_ARC;
      nextReason = "front_block_hold";
    } else if (frontWarn) {
      nextMode = DRIVE_CRAWL;
      nextReason = "front_warn";
    } else if (bothSidePressure) {
      nextMode = DRIVE_CRAWL;
      nextReason = "corridor";
    } else if (leftBlocked && !rightBlocked) {
      preferLeftTurn = false;
      nextMode = DRIVE_STEER_RIGHT;
      nextReason = "left_pressure";
    } else if (rightBlocked && !leftBlocked) {
      preferLeftTurn = true;
      nextMode = DRIVE_STEER_LEFT;
      nextReason = "right_pressure";
    } else {
      nextMode = DRIVE_CRUISE;
      nextReason = "clear";
    }
  }

  bool cameFromReverseArc = driveMode == DRIVE_ESCAPE_REVERSE_ARC;
  bool cameFromSteer = driveMode == DRIVE_STEER_LEFT || driveMode == DRIVE_STEER_RIGHT;
  bool headingModeResume = nextMode == DRIVE_CRUISE || nextMode == DRIVE_CRAWL;

  if ((cameFromReverseArc || cameFromSteer) && headingModeResume) {
    resetHeadingReference(cameFromReverseArc ? "reverse_settle" : "steer_settle");
    nextMode = DRIVE_TURN_SETTLE;
    nextReason = "turn_settle";
  }

  setDriveMode(nextMode, nextReason);
  setMotorMix(buildMotorMixForMode(nextMode));
  updateMotorRamp(now);
}

void setupOled() {
  if (!oled.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) {
    Serial.println("OLED init fail");
    oledReady = false;
    return;
  }

  oledReady = true;
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 0);
  oled.println("ESP32-S3 READY");
  oled.println("SONAR/GPS/MPU");
  oled.println("AUTO DRIVE HUD");
  oled.display();
}

void setupMpu() {
  byte status = mpu.begin();
  if (status != 0) {
    Serial.printf("MPU init fail status=%u\n", status);
    mpuReady = false;
    return;
  }

  Serial.println("MPU calibrating... keep robot still");
  delay(40);
  mpu.calcGyroOffsets();
  for (uint8_t i = 0; i < 4; ++i) {
    mpu.update();
    delay(5);
  }

  imuState.initialized = false;
  clearHeadingHold(false);
  mpuReady = true;
  Serial.println("MPU ready");
}

void updateGpsNonBlocking() {
  uint8_t budget = GPS_PARSE_BUDGET_BYTES;
  while (budget > 0 && gpsSerial.available() > 0) {
    gps.encode((char)gpsSerial.read());
    if (gps.location.isUpdated() && gps.location.isValid()) {
      gpsCache.hasFix = true;
      gpsCache.lat = gps.location.lat();
      gpsCache.lng = gps.location.lng();
      gpsCache.lastFixMs = millis();
    }
    budget--;
  }

  updateGpsDisplayLine(millis());
}

void updateMpuSample() {
  if (!mpuReady) return;

  unsigned long now = millis();
  if ((now - lastMpuSampleMs) < MPU_SAMPLE_PERIOD_MS) return;

  lastMpuSampleMs = now;
  mpu.update();
  float rawPitch = mpu.getAngleX();
  float rawRoll = mpu.getAngleY();
  float rawYaw = mpu.getAngleZ();

  if (!imuState.initialized) {
    imuState.initialized = true;
    imuState.pitch = rawPitch;
    imuState.roll = rawRoll;
    imuState.yaw = rawYaw;
    impactState.last_pitch = rawPitch;
    impactState.last_roll = rawRoll;
  }

  float deltaPitch = fabsf(rawPitch - impactState.last_pitch);
  float deltaRoll = fabsf(rawRoll - impactState.last_roll);
  bool impactEligible =
    hasEnteredRun &&
    motionState == MOTION_RUN &&
    driveMode != DRIVE_ESCAPE_REVERSE_ARC &&
    leftSwitchGuard.activeDir == WHEEL_FWD &&
    rightSwitchGuard.activeDir == WHEEL_FWD &&
    (((uint16_t)appliedPwmLeft + (uint16_t)appliedPwmRight) / 2U) >= IMPACT_MIN_PWM &&
    (now - impactState.last_impact_ms) >= IMPACT_COOLDOWN_MS;

  bool impactSpike = deltaPitch >= IMPACT_DELTA_DEG || deltaRoll >= IMPACT_DELTA_DEG;
  if (impactEligible && impactSpike) {
    if ((now - impactState.last_candidate_ms) <= 90) {
      if (impactState.consecutive_hits < 250) {
        impactState.consecutive_hits++;
      }
    } else {
      impactState.consecutive_hits = 1;
    }
    impactState.last_candidate_ms = now;

    if (!impactState.latched && impactState.consecutive_hits >= 2) {
      impactState.latched = true;
      impactState.last_impact_ms = now;
      Serial.printf("EVT:impact,dp=%.1f,dr=%.1f,p=%.1f,r=%.1f\n", deltaPitch, deltaRoll, rawPitch, rawRoll);
    }
  } else if ((now - impactState.last_candidate_ms) > 90) {
    impactState.consecutive_hits = 0;
  }

  impactState.last_pitch = rawPitch;
  impactState.last_roll = rawRoll;

  imuState.pitch = (MPU_EMA_ALPHA * rawPitch) + ((1.0f - MPU_EMA_ALPHA) * imuState.pitch);
  imuState.roll = (MPU_EMA_ALPHA * rawRoll) + ((1.0f - MPU_EMA_ALPHA) * imuState.roll);
  imuState.yaw = rawYaw;

  mpuPitch = roundf(imuState.pitch);
  mpuRoll = roundf(imuState.roll);
  mpuYaw = roundf(imuState.yaw);
}

void renderOledDashboard() {
  unsigned long now = millis();
  bool stateChanged = false;
  static MotionState lastRenderedState = MOTION_STOP_SAFE;
  static DriveMode lastRenderedMode = DRIVE_CRAWL;
  bool warmupActive = !hasEnteredRun && ((now - bootMs) < STARTUP_WARMUP_MS);

  if (lastRenderedState != motionState || lastRenderedMode != driveMode) {
    stateChanged = true;
    lastRenderedState = motionState;
    lastRenderedMode = driveMode;
  }

  syncRangeDistances();

  bool distChanged =
    absDiffU16(quantizeDistanceCm(distL), shownDistL) >= QUICK_PATCH_CONFIG.oled_quantize_cm ||
    absDiffU16(quantizeDistanceCm(distC), shownDistC) >= QUICK_PATCH_CONFIG.oled_quantize_cm ||
    absDiffU16(quantizeDistanceCm(distR), shownDistR) >= QUICK_PATCH_CONFIG.oled_quantize_cm;

  if (!stateChanged && !distChanged && (now - lastOledRenderMs) < QUICK_PATCH_CONFIG.oled_refresh_ms) return;

  lastOledRenderMs = now;
  shownDistL = quantizeDistanceCm(distL);
  shownDistC = quantizeDistanceCm(distC);
  shownDistR = quantizeDistanceCm(distR);

  if (!oledReady) return;

  char leftText[6];
  char centerText[6];
  char rightText[6];
  formatRangeForOled(leftText, sizeof(leftText), rangeStates[0]);
  formatRangeForOled(centerText, sizeof(centerText), rangeStates[1]);
  formatRangeForOled(rightText, sizeof(rightText), rangeStates[2]);

  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);

  oled.setCursor(0, 0);
  oled.printf("L/C/R %s/%s/%s", leftText, centerText, rightText);

  oled.setCursor(0, 12);
  if (warmupActive) {
    oled.print("S SONAR WARMUP");
  } else {
    oled.printf("D %s %s", driveModeName(driveMode), motionReason);
  }

  oled.setCursor(0, 24);
  oled.print(gpsCache.line);

  oled.setCursor(0, 36);
  if (mpuReady) {
    oled.printf("Y%.0f E%.0f T%d", mpuYaw, headingHold.yaw_error, headingHold.trim_pwm);
  } else {
    oled.print("MPU init fail");
  }

  oled.setCursor(0, 48);
  if (signState.active && hasLastSign) {
    oled.printf("PRED %u %u.%02u", lastSignClass, lastSignConf100 / 100, lastSignConf100 % 100);
  } else {
    oled.print("PRED none");
  }

  oled.display();
}

bool parseSignLine(const char* line, uint8_t& classId, uint8_t& conf100) {
  if (strncmp(line, "SIGN:", 5) != 0) return false;

  const char* classPart = line + 5;
  const char* sep = strchr(classPart, ':');
  if (sep == nullptr) return false;
  if (strchr(sep + 1, ':') != nullptr) return false;

  size_t classLen = (size_t)(sep - classPart);
  if (classLen == 1 && classPart[0] >= '0' && classPart[0] <= '9') {
    classId = (uint8_t)(classPart[0] - '0');
  } else {
    return false;
  }

  if (classId > CANONICAL_CLASS_MAX_ID) return false;

  const char* confPart = sep + 1;
  if (strlen(confPart) != 4) return false;

  if (confPart[0] == '1') {
    if (strcmp(confPart, "1.00") != 0) return false;
    conf100 = 100;
    return true;
  }

  if (confPart[0] != '0' || confPart[1] != '.') return false;
  if (confPart[2] < '0' || confPart[2] > '9' || confPart[3] < '0' || confPart[3] > '9') return false;

  conf100 = (uint8_t)((confPart[2] - '0') * 10 + (confPart[3] - '0'));
  return true;
}

void handleValidSign(uint8_t classId, uint8_t conf100) {
  const SignAudioProfile& profile = signAudioProfileForClass(classId);
  uint8_t track = profile.track;
  unsigned long now = millis();
  bool strongerDifferentClass = signState.active &&
    classId != signState.classId &&
    conf100 >= (uint8_t)(signState.conf100 + SIGN_REPLACE_MARGIN_CONF100);
  bool withinHold = signState.active && now < signState.holdUntilMs;

  if (withinHold && !strongerDifferentClass && conf100 <= signState.conf100) {
    return;
  }

  signState.active = true;
  signState.classId = classId;
  signState.conf100 = conf100;
  signState.holdUntilMs = now + SIGN_HOLD_MS;
  signState.lastUpdateMs = now;
  hasLastSign = true;
  lastSignClass = classId;
  lastSignConf100 = conf100;
  acceptedSigns++;

  if ((now - signState.lastAudioMs) >= AUDIO_COOLDOWN_MS || track != lastTrack) {
    playMp3Folder(track);
    lastTrack = track;
    signState.lastAudioMs = now;
  }

  Serial.printf("SIGN_OK class=%u label=%s conf=%u.%02u track=%u file=%s phrase=%s\n",
                classId,
                profile.classLabel,
                conf100 / 100,
                conf100 % 100,
                track,
                profile.clipFile,
                profile.spokenPhrase);
}

void consumeCamByte(char b) {
  if (dropUntilLf) {
    if (b == '\n') {
      dropUntilLf = false;
      lineLen = 0;
    }
    return;
  }

  if (b == '\r') {
    droppedInvalid++;
    dropUntilLf = true;
    lineLen = 0;
    return;
  }

  if (b == '\n') {
    lineBuf[lineLen] = '\0';
    uint8_t classId = 0;
    uint8_t conf100 = 0;
    if (parseSignLine(lineBuf, classId, conf100)) {
      handleValidSign(classId, conf100);
    } else {
      droppedInvalid++;
    }
    lineLen = 0;
    return;
  }

  if (lineLen >= (MAX_CANONICAL_BYTES - 1)) {
    uartOverflow++;
    droppedInvalid++;
    dropUntilLf = true;
    lineLen = 0;
    return;
  }

  lineBuf[lineLen++] = b;
}

void emitTelemetry(unsigned long now) {
  if ((now - lastTelemetryMs) < TELEMETRY_PERIOD_MS) return;
  lastTelemetryMs = now;

  uint16_t rejectTotal = (uint16_t)(rangeStates[0].reject_count + rangeStates[1].reject_count + rangeStates[2].reject_count);
  bool leftPressure = rangeIsBlocked(rangeStates[0], SIDE_PRESSURE_CM);
  bool rightPressure = rangeIsBlocked(rangeStates[2], SIDE_PRESSURE_CM);
  char frontFlag = 'N';
  if (centerObstacleLatched(now)) {
    frontFlag = 'L';
  }
  if (rangeIsFrontWarn(rangeStates[1])) {
    frontFlag = 'W';
  }
  if (rangeIsBlocked(rangeStates[1], stopDynamicCm)) {
    frontFlag = 'B';
  }
  char sideFlag = 'N';
  if (leftPressure && rightPressure) {
    sideFlag = 'B';
  } else if (leftPressure) {
    sideFlag = 'L';
  } else if (rightPressure) {
    sideFlag = 'R';
  }
  bool blindFlag =
    motionTimers.all_invalid_since_ms != 0 &&
    (now - motionTimers.all_invalid_since_ms) >= SONAR_ALL_INVALID_RECOVER_MS;

  Serial.printf(
    "TEL:mode=%s,reason=%s,pwm=%u/%u,dist=%u/%u/%u,front=%c,side=%c,gap=%u,blind=%u,q=%c%c%c,age=%lu/%lu/%lu,raw=%u/%u/%u,scan=%u,sweep=%lu,rd=%u,ok=%lu,drop=%lu,yaw=%.1f,ref=%.1f,err=%.1f,trim=%d\n",
    driveModeName(driveMode),
    motionReason,
    appliedPwmLeft,
    appliedPwmRight,
    distL,
    distC,
    distR,
    frontFlag,
    sideFlag,
    motorGapActive ? 1U : 0U,
    blindFlag ? 1U : 0U,
    rangeQualityCode(rangeStates[0]),
    rangeQualityCode(rangeStates[1]),
    rangeQualityCode(rangeStates[2]),
    rangeAgeMs(rangeStates[0], now),
    rangeAgeMs(rangeStates[1], now),
    rangeAgeMs(rangeStates[2], now),
    rangeStates[0].raw_cm,
    rangeStates[1].raw_cm,
    rangeStates[2].raw_cm,
    scanState.index,
    scanSweepAgeMs(now),
    rejectTotal,
    acceptedSigns,
    droppedInvalid,
    imuState.yaw,
    headingHold.reference_yaw,
    headingHold.yaw_error,
    headingHold.trim_pwm
  );
}

void emitMotorDebug(unsigned long now) {
  if ((now - lastMotorDebugMs) < 500) return;
  lastMotorDebugMs = now;

  Serial.printf(
    "MOT:mode=%s,dl=%c,dr=%c,tp=%u/%u,ap=%u/%u,gap=%u,in=%u%u%u%u,trim=%d,yaw=%.1f,reason=%s\n",
    driveModeName(driveMode),
    wheelDirCode(leftSwitchGuard.activeDir),
    wheelDirCode(rightSwitchGuard.activeDir),
    targetPwmLeft,
    targetPwmRight,
    appliedPwmLeft,
    appliedPwmRight,
    motorGapActive ? 1U : 0U,
    (unsigned)digitalRead(IN1),
    (unsigned)digitalRead(IN2),
    (unsigned)digitalRead(IN3),
    (unsigned)digitalRead(IN4),
    headingHold.trim_pwm,
    imuState.yaw,
    motionReason
  );
}

void setup() {
  Serial.begin(115200);
  camSerial.begin(CAM_BAUD, SERIAL_8N1, CAM_RX, CAM_TX);
  dfSerial.begin(DF_BAUD, SERIAL_8N1, DF_RX, DF_TX);
  gpsSerial.begin(GPS_BAUD, SERIAL_8N1, GPS_RX, GPS_TX);
  Wire.begin(I2C_SDA, I2C_SCL);
  printSignAudioMap();

  setupMotors();
  setupSonar();
  setupOled();
  setupMpu();
  setDfVolume(DFPLAYER_DEFAULT_VOLUME);
  delay(150);
  setDfVolume(DFPLAYER_DEFAULT_VOLUME);
  forceStopDrive();
  bootMs = millis();
  stateEnteredMs = bootMs;
  driveModeEnteredMs = bootMs;
  lastRampMs = bootMs;
  scanState.last_full_sweep_ms = bootMs;
  gpsCache.lastDisplayMs = bootMs;
  updateSonarSample();
  updateMpuSample();
  updateGpsDisplayLine(bootMs);
  renderOledDashboard();

  Serial.printf("FW:%s PROTO:%s\n", FW_VERSION, PROTO_VERSION);
}

void loop() {
  unsigned long serialBudgetStart = millis();
  while (camSerial.available() > 0) {
    consumeCamByte((char)camSerial.read());
    if ((millis() - serialBudgetStart) >= 5) break;
  }

  updateGpsNonBlocking();
  updateMpuSample();
  updateMotion();
  renderOledDashboard();

  unsigned long now = millis();
  emitTelemetry(now);
  emitMotorDebug(now);

  delay(2);
}

