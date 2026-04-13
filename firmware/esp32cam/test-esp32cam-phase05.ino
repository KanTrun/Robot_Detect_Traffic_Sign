// esp32cam_production_sender.ino (Phase 02)
// Canonical protocol: SIGN:<class_id>:<confidence>\n
#include <Arduino.h>
#include <TensorFlowLite_ESP32.h>
#include "esp_camera.h"
#include "img_converters.h"
#include <esp_heap_caps.h>
#include <WiFi.h>
#include "esp_http_server.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

#include "tensorflow/lite/micro/all_ops_resolver.h"
#include "tensorflow/lite/micro/micro_error_reporter.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "model_data.h"

constexpr char FW_VERSION[] = "esp32-cam-prod-v2.0";
constexpr char PROTO_VERSION[] = "sign-v1";
constexpr uint8_t MODEL_CLASS_COUNT = 16;
constexpr uint8_t MODEL_CLASS_MAX_ID = MODEL_CLASS_COUNT - 1;
constexpr uint8_t BACKGROUND_CLASS_ID = 0;
constexpr uint8_t SIGN_CLASS_MIN_ID = 1;
constexpr uint8_t SIGN_CLASS_MAX_ID = 15;
constexpr uint8_t FOMO_GRID_SIZE = 12;  // FOMO output grid
constexpr uint8_t FOMO_BG_CLASS = BACKGROUND_CLASS_ID;
constexpr float FOMO_CELL_THRESHOLD = 0.4f;  // Min confidence per grid cell

constexpr char WIFI_SSID[] = "YOUR_WIFI_SSID";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";
constexpr uint16_t CAMERA_STREAM_PORT = 81;
constexpr uint8_t STREAM_FRAME_SIZE = FRAMESIZE_VGA;
constexpr uint8_t STREAM_JPEG_QUALITY = 12;
constexpr int8_t CAMERA_VFLIP = 1;
constexpr int8_t CAMERA_HMIRROR = 0;

constexpr uint8_t MIN_EMIT_CONF100 = 30;
constexpr uint8_t MIN_MARGIN_CONF100 = 0;
constexpr uint16_t DUPLICATE_DEBOUNCE_MS = 400;
constexpr uint32_t STATS_PERIOD_MS = 5000;
constexpr size_t TENSOR_ARENA_SIZE = 512 * 1024;  // alpha=0.5 model needs ~512KB
constexpr bool INPUT_EXPECTS_0_TO_1 = true;
constexpr float CENTER_CROP_RATIO = 0.5f;  // Crop center 50% of frame for inference
                                            // Sign at 50cm fills ~60-80% of input
constexpr uint8_t STABILITY_WINDOW = 3;
constexpr uint8_t STABILITY_REQUIRE = 2;
constexpr float CONF_EMA_ALPHA = 0.6f;

// Per-class thresholds (index 0 is background and should never emit SIGN)
static const uint8_t MIN_EMIT_CONF100_BY_CLASS[MODEL_CLASS_COUNT] = {
//bg   ahead child end_r keep_l keep_r no_en ped   road  round sp20  sp30  sp50  stop  tl    tr
  100, 40,   60,   30,   30,    40,    55,   60,   35,   30,   30,   60,   60,   30,   50,   30
};

static const uint8_t MIN_MARGIN_CONF100_BY_CLASS[MODEL_CLASS_COUNT] = {
//bg   ahead child end_r keep_l keep_r no_en ped   road  round sp20  sp30  sp50  stop  tl    tr
  100, 0,    0,    0,    0,     0,     0,    0,    0,    0,    0,    0,    0,    0,    0,    0
};

constexpr int PWDN_GPIO_NUM = 32;
constexpr int RESET_GPIO_NUM = -1;
constexpr int XCLK_GPIO_NUM = 0;
constexpr int SIOD_GPIO_NUM = 26;
constexpr int SIOC_GPIO_NUM = 27;
constexpr int Y9_GPIO_NUM = 35;
constexpr int Y8_GPIO_NUM = 34;
constexpr int Y7_GPIO_NUM = 39;
constexpr int Y6_GPIO_NUM = 36;
constexpr int Y5_GPIO_NUM = 21;
constexpr int Y4_GPIO_NUM = 19;
constexpr int Y3_GPIO_NUM = 18;
constexpr int Y2_GPIO_NUM = 5;
constexpr int VSYNC_GPIO_NUM = 25;
constexpr int HREF_GPIO_NUM = 23;
constexpr int PCLK_GPIO_NUM = 22;

static const char* CLASS_LABELS[MODEL_CLASS_COUNT] = {
  "_background_",
  "ahead_only",
  "children_crossing",
  "end_restriction",
  "keep_left",
  "keep_right",
  "no_entry",
  "pedestrian_crossing",
  "road_work",
  "roundabout",
  "speed_limit_20",
  "speed_limit_30",
  "speed_limit_50",
  "stop",
  "turn_left_ahead",
  "turn_right_ahead"
};

namespace {
tflite::ErrorReporter* error_reporter = nullptr;
const tflite::Model* model = nullptr;
tflite::MicroInterpreter* interpreter = nullptr;
TfLiteTensor* input = nullptr;
TfLiteTensor* output = nullptr;
uint8_t* tensor_arena = nullptr;
}

static uint32_t sent = 0;
static uint32_t dropped_invalid = 0;
static uint32_t parse_internal_fail = 0;
static uint32_t dropped_no_sign = 0;
static uint32_t dropped_low_conf = 0;
static uint8_t last_class = 255;
static uint32_t last_sent_ms = 0;
static uint32_t last_stats_ms = 0;
static uint32_t last_error_log_ms = 0;
static uint32_t last_no_sign_log_ms = 0;
static uint8_t history_class[STABILITY_WINDOW] = {255, 255, 255};
static uint8_t history_conf[STABILITY_WINDOW] = {0, 0, 0};
static uint8_t history_margin[STABILITY_WINDOW] = {0, 0, 0};
static uint8_t history_pos = 0;
static uint8_t history_count = 0;
static float conf_ema_by_class[MODEL_CLASS_COUNT] = {0};
static uint32_t last_stream_infer_attempt_ms = 0;

static void logErrorRateLimited(const char* msg);
static bool isStreamSessionActive();
static void beginStreamSession();
static void endStreamSession();
static void printClassMap();
static bool initCamera();
static bool initTflm();
static bool initWiFi();
static bool switch_camera_mode(uint8_t targetMode);
static void applyInferenceSensorMode();
static void applyStreamSensorMode();
static esp_err_t stream_handler(httpd_req_t* req);
static esp_err_t capture_handler(httpd_req_t* req);
static bool startStreamServer();
static float mapPixelToModelReal(uint8_t value, float scale);
static int8_t quantizeToInt8(uint8_t value, float scale, int32_t zero_point);
static uint8_t quantizeToUInt8(uint8_t value, float scale, int32_t zero_point);
static bool fillModelInput();
static void printDiagnostics();
static void pushHistory(uint8_t class_id, uint8_t conf100, uint8_t margin_conf100);
static bool isTemporallyStable(uint8_t class_id, uint8_t& hits_out, uint8_t& valid_out);
static float readOutputScore(int idx);
static bool decodeTopClass(uint8_t& class_id, uint8_t& conf100, uint8_t& runner_conf100);
static void emitSign(uint8_t class_id, uint8_t conf100, uint8_t runner_conf100);
static void printStats();
void setup();
void loop();
static void logErrorRateLimited(const char* msg) {
  uint32_t now = millis();
  if (now - last_error_log_ms < 2000) return;
  Serial.print("DBG:");
  Serial.println(msg);
  last_error_log_ms = now;
}

static bool cameraReady = false;
static bool modelReady = false;
static bool wifiReady = false;
static bool streamReady = false;
static volatile uint8_t stream_session_count = 0;

static portMUX_TYPE stream_state_mux = portMUX_INITIALIZER_UNLOCKED;

enum CameraMode : uint8_t {
  CAMERA_MODE_UNKNOWN = 0,
  CAMERA_MODE_INFERENCE = 1,
};

static CameraMode currentCameraMode = CAMERA_MODE_UNKNOWN;
static sensor_t* cameraSensor = nullptr;
static httpd_handle_t stream_httpd = nullptr;
static SemaphoreHandle_t camera_mutex = nullptr;
static const char* STREAM_BOUNDARY = "123456789000000000000987654321";
static const char* STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=123456789000000000000987654321";
static const char* STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static inline bool isStreamSessionActive() {
  portENTER_CRITICAL(&stream_state_mux);
  bool active = stream_session_count > 0;
  portEXIT_CRITICAL(&stream_state_mux);
  return active;
}

static inline void beginStreamSession() {
  portENTER_CRITICAL(&stream_state_mux);
  if (stream_session_count < 255) {
    stream_session_count++;
  }
  portEXIT_CRITICAL(&stream_state_mux);
}

static inline void endStreamSession() {
  portENTER_CRITICAL(&stream_state_mux);
  if (stream_session_count > 0) {
    stream_session_count--;
  }
  portEXIT_CRITICAL(&stream_state_mux);
}

static void printClassMap() {
  for (uint8_t i = 0; i <= MODEL_CLASS_MAX_ID; ++i) {
    Serial.printf("DBG:label:%u=%s\n", i, CLASS_LABELS[i]);
  }
}

static bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = static_cast<framesize_t>(STREAM_FRAME_SIZE);
  config.jpeg_quality = STREAM_JPEG_QUALITY;
  config.fb_count = psramFound() ? 2 : 1;
  config.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  config.grab_mode = psramFound() ? CAMERA_GRAB_LATEST : CAMERA_GRAB_WHEN_EMPTY;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    logErrorRateLimited("camera_init_failed");
    return false;
  }

  cameraSensor = esp_camera_sensor_get();
  if (cameraSensor == nullptr) {
    logErrorRateLimited("camera_sensor_null");
    return false;
  }
  cameraSensor->set_vflip(cameraSensor, CAMERA_VFLIP);
  cameraSensor->set_hmirror(cameraSensor, CAMERA_HMIRROR);
  cameraSensor->set_framesize(cameraSensor, static_cast<framesize_t>(STREAM_FRAME_SIZE));

  // Log sensor model for diagnostics
  Serial.printf("DBG:sensor_pid=0x%04X\n", cameraSensor->id.PID);

  // OV3660-specific: enable continuous auto-focus if available
  // OV3660 PID = 0x3660; without AF enable, lens stays out of focus → blurry stream
  if (cameraSensor->id.PID == 0x3660) {
    Serial.println("DBG:ov3660_detected, enabling auto-focus");
    // Download AF firmware and start continuous AF
    cameraSensor->set_reg(cameraSensor, 0x3022, 0xFF, 0x08);
    delay(100);
    // Trigger single AF first, then switch to continuous
    cameraSensor->set_reg(cameraSensor, 0x3022, 0xFF, 0x04);
    delay(300);
    cameraSensor->set_reg(cameraSensor, 0x3022, 0xFF, 0x08);
  }

  // Optimize sensor for SHARP real-world traffic sign recognition
  cameraSensor->set_whitebal(cameraSensor, 1);      // Auto white balance ON
  cameraSensor->set_awb_gain(cameraSensor, 1);       // AWB gain ON
  cameraSensor->set_wb_mode(cameraSensor, 0);        // Auto WB mode
  cameraSensor->set_exposure_ctrl(cameraSensor, 1);  // Auto exposure ON
  cameraSensor->set_aec2(cameraSensor, 0);           // AEC DSP OFF (reduce over-processing)
  cameraSensor->set_ae_level(cameraSensor, 0);       // Neutral AE level
  cameraSensor->set_gain_ctrl(cameraSensor, 1);      // Auto gain ON
  cameraSensor->set_agc_gain(cameraSensor, 0);       // AGC gain low (reduce noise)
  cameraSensor->set_gainceiling(cameraSensor, (gainceiling_t)2); // Medium gain ceiling (better indoor visibility)
  cameraSensor->set_brightness(cameraSensor, 1);     // Slight brightness boost
  cameraSensor->set_contrast(cameraSensor, 1);       // Moderate contrast (too high loses detail)
  cameraSensor->set_saturation(cameraSensor, 1);     // Slight saturation boost for sign colors
  cameraSensor->set_sharpness(cameraSensor, 2);      // Moderate sharpness (too high causes halo artifacts)
  cameraSensor->set_denoise(cameraSensor, 0);        // Denoise OFF (denoise blurs detail!)
  cameraSensor->set_special_effect(cameraSensor, 0); // No special effect
  cameraSensor->set_bpc(cameraSensor, 1);            // Bad pixel correction ON
  cameraSensor->set_wpc(cameraSensor, 1);            // White pixel correction ON
  cameraSensor->set_lenc(cameraSensor, 1);           // Lens correction ON (reduce edge blur)

  currentCameraMode = CAMERA_MODE_UNKNOWN;

  return true;
}

static bool initTflm() {
  if (tensor_arena == nullptr) {
    tensor_arena = (uint8_t*)heap_caps_malloc(TENSOR_ARENA_SIZE, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (tensor_arena == nullptr) {
      tensor_arena = (uint8_t*)heap_caps_malloc(TENSOR_ARENA_SIZE, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    }
  }
  if (tensor_arena == nullptr) {
    logErrorRateLimited("tensor_arena_alloc_failed");
    return false;
  }

  model = tflite::GetModel(model_data);
  if (model->version() != TFLITE_SCHEMA_VERSION) {
    logErrorRateLimited("model_schema_mismatch");
    return false;
  }

  static tflite::AllOpsResolver resolver;
  static tflite::MicroInterpreter static_interpreter(model, resolver, tensor_arena, TENSOR_ARENA_SIZE, error_reporter);
  interpreter = &static_interpreter;

  if (interpreter->AllocateTensors() != kTfLiteOk) {
    logErrorRateLimited("allocate_tensors_failed");
    return false;
  }

  input = interpreter->input(0);
  output = interpreter->output(0);
  if (input == nullptr || output == nullptr) {
    logErrorRateLimited("tensor_ptr_null");
    return false;
  }

  return true;
}

static bool initWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    if (millis() - start > 15000) {
      logErrorRateLimited("wifi_connect_timeout");
      return false;
    }
  }
  return true;
}

static inline bool switch_camera_mode(uint8_t targetMode) {
  if (cameraSensor == nullptr) {
    return false;
  }

  if (targetMode != CAMERA_MODE_INFERENCE) {
    return false;
  }

  currentCameraMode = CAMERA_MODE_INFERENCE;
  return true;
}

static inline void applyInferenceSensorMode() {
  switch_camera_mode(CAMERA_MODE_INFERENCE);
}

static inline void applyStreamSensorMode() {
  switch_camera_mode(CAMERA_MODE_INFERENCE);
}

static esp_err_t stream_handler(httpd_req_t* req) {
  if (camera_mutex == nullptr) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  esp_err_t res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) {
    return res;
  }

  beginStreamSession();
  bool sent_first_boundary = false;
  while (true) {
    if (xSemaphoreTake(camera_mutex, pdMS_TO_TICKS(60)) != pdTRUE) {
      vTaskDelay(pdMS_TO_TICKS(5));
      continue;
    }

    applyStreamSensorMode();

    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      xSemaphoreGive(camera_mutex);
      endStreamSession();
      logErrorRateLimited("stream_camera_capture_failed");
      return ESP_FAIL;
    }

    uint8_t* out_buf = nullptr;
    size_t out_len = 0;

    if (fb->format == PIXFORMAT_JPEG) {
      out_len = fb->len;
      out_buf = static_cast<uint8_t*>(malloc(out_len));
      if (out_buf == nullptr) {
        esp_camera_fb_return(fb);
        xSemaphoreGive(camera_mutex);
        endStreamSession();
        logErrorRateLimited("stream_copy_alloc_failed");
        return ESP_FAIL;
      }
      memcpy(out_buf, fb->buf, out_len);
    } else {
      if (!frame2jpg(fb, STREAM_JPEG_QUALITY, &out_buf, &out_len) || out_buf == nullptr) {
        esp_camera_fb_return(fb);
        xSemaphoreGive(camera_mutex);
        endStreamSession();
        logErrorRateLimited("stream_jpeg_encode_failed");
        return ESP_FAIL;
      }
    }

    esp_camera_fb_return(fb);
    xSemaphoreGive(camera_mutex);

    char part[64];
    int hlen = snprintf(part, sizeof(part), STREAM_PART, static_cast<unsigned>(out_len));
    if (hlen <= 0 || hlen >= static_cast<int>(sizeof(part))) {
      free(out_buf);
      endStreamSession();
      logErrorRateLimited("stream_part_header_invalid");
      return ESP_FAIL;
    }

    bool send_fail = false;
    if (sent_first_boundary) {
      send_fail = httpd_resp_send_chunk(req, "\r\n", 2) != ESP_OK;
    }
    send_fail =
        send_fail || httpd_resp_send_chunk(req, "--", 2) != ESP_OK ||
        httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY)) != ESP_OK ||
        httpd_resp_send_chunk(req, "\r\n", 2) != ESP_OK ||
        httpd_resp_send_chunk(req, part, hlen) != ESP_OK ||
        httpd_resp_send_chunk(req, reinterpret_cast<const char*>(out_buf), out_len) != ESP_OK;

    free(out_buf);

    if (send_fail) {
      endStreamSession();
      return ESP_FAIL;
    }

    sent_first_boundary = true;
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

static esp_err_t capture_handler(httpd_req_t* req) {
  if (camera_mutex == nullptr) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  if (xSemaphoreTake(camera_mutex, pdMS_TO_TICKS(120)) != pdTRUE) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  applyStreamSensorMode();

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    xSemaphoreGive(camera_mutex);
    logErrorRateLimited("capture_failed");
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  httpd_resp_set_type(req, "image/jpeg");
  if (fb->format == PIXFORMAT_JPEG) {
    esp_err_t res = httpd_resp_send(req, reinterpret_cast<const char*>(fb->buf), fb->len);
    esp_camera_fb_return(fb);
    xSemaphoreGive(camera_mutex);
    return res;
  }

  uint8_t* jpg_buf = nullptr;
  size_t jpg_len = 0;
  bool ok = frame2jpg(fb, STREAM_JPEG_QUALITY, &jpg_buf, &jpg_len);
  esp_camera_fb_return(fb);
  xSemaphoreGive(camera_mutex);
  if (!ok || jpg_buf == nullptr) {
    logErrorRateLimited("capture_jpeg_encode_failed");
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  esp_err_t res = httpd_resp_send(req, reinterpret_cast<const char*>(jpg_buf), jpg_len);
  free(jpg_buf);
  return res;
}

static bool startStreamServer() {
  if (stream_httpd != nullptr) {
    return true;
  }

  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = CAMERA_STREAM_PORT;
  config.ctrl_port = CAMERA_STREAM_PORT + 100;

  httpd_uri_t uri_stream = {
      .uri = "/stream",
      .method = HTTP_GET,
      .handler = stream_handler,
      .user_ctx = nullptr,
  };

  httpd_uri_t uri_capture = {
      .uri = "/capture",
      .method = HTTP_GET,
      .handler = capture_handler,
      .user_ctx = nullptr,
  };

  if (httpd_start(&stream_httpd, &config) != ESP_OK) {
    logErrorRateLimited("stream_server_start_failed");
    stream_httpd = nullptr;
    return false;
  }

  if (httpd_register_uri_handler(stream_httpd, &uri_stream) != ESP_OK ||
      httpd_register_uri_handler(stream_httpd, &uri_capture) != ESP_OK) {
    logErrorRateLimited("stream_uri_register_failed");
    httpd_stop(stream_httpd);
    stream_httpd = nullptr;
    return false;
  }

  return true;
}

static float mapPixelToModelReal(uint8_t value, float scale) {
  if (scale > 0.0f && scale <= 0.01f) {
    return static_cast<float>(value) / 255.0f;
  }
  return static_cast<float>(value);
}

static int8_t quantizeToInt8(uint8_t value, float scale, int32_t zero_point) {
  float real = mapPixelToModelReal(value, scale);
  int32_t q = 0;
  if (scale > 0.0f) {
    q = static_cast<int32_t>(roundf(real / scale)) + zero_point;
  } else {
    q = static_cast<int32_t>(value) + zero_point;
  }
  if (q < -128) q = -128;
  if (q > 127) q = 127;
  return static_cast<int8_t>(q);
}

static uint8_t quantizeToUInt8(uint8_t value, float scale, int32_t zero_point) {
  float real = mapPixelToModelReal(value, scale);
  int32_t q = 0;
  if (scale > 0.0f) {
    q = static_cast<int32_t>(roundf(real / scale)) + zero_point;
  } else {
    q = static_cast<int32_t>(value) + zero_point;
  }
  if (q < 0) q = 0;
  if (q > 255) q = 255;
  return static_cast<uint8_t>(q);
}

static bool fillModelInput() {
  if (camera_mutex == nullptr) {
    dropped_invalid++;
    logErrorRateLimited("camera_mutex_null");
    return false;
  }

  if (isStreamSessionActive()) {
    uint32_t now = millis();
    if (now - last_stream_infer_attempt_ms < 200) {
      vTaskDelay(pdMS_TO_TICKS(4));
      return false;
    }
    last_stream_infer_attempt_ms = now;
  }
  if (xSemaphoreTake(camera_mutex, pdMS_TO_TICKS(100)) != pdTRUE) {
    dropped_invalid++;
    logErrorRateLimited("camera_busy");
    return false;
  }

  applyInferenceSensorMode();

  camera_fb_t* fb = esp_camera_fb_get();
  if (fb == nullptr) {
    dropped_invalid++;
    xSemaphoreGive(camera_mutex);
    logErrorRateLimited("camera_capture_failed");
    return false;
  }

  if (input->dims == nullptr || input->dims->size < 4) {
    esp_camera_fb_return(fb);
    xSemaphoreGive(camera_mutex);
    parse_internal_fail++;
    logErrorRateLimited("input_dims_invalid");
    return false;
  }

  const int dim1 = input->dims->data[1];
  const int dim2 = input->dims->data[2];
  const int dim3 = input->dims->data[3];
  const bool chw = (dim1 == 3 && dim2 == 96 && dim3 == 96);
  const bool hwc = (dim1 == 96 && dim2 == 96 && dim3 == 3);
  const bool gray = (dim1 == 96 && dim2 == 96 && dim3 == 1);

  if (!chw && !hwc && !gray) {
    esp_camera_fb_return(fb);
    xSemaphoreGive(camera_mutex);
    parse_internal_fail++;
    logErrorRateLimited("unsupported_input_shape");
    return false;
  }

  if (input->type != kTfLiteUInt8 && input->type != kTfLiteInt8 && input->type != kTfLiteFloat32) {
    esp_camera_fb_return(fb);
    xSemaphoreGive(camera_mutex);
    parse_internal_fail++;
    logErrorRateLimited("unsupported_input_tensor_type");
    return false;
  }

  const int full_w = static_cast<int>(fb->width);
  const int full_h = static_cast<int>(fb->height);
  if (full_w <= 0 || full_h <= 0) {
    esp_camera_fb_return(fb);
    xSemaphoreGive(camera_mutex);
    dropped_invalid++;
    logErrorRateLimited("unexpected_frame_format_or_size");
    return false;
  }

  // ======================================================================
  // COLOR-BASED ROI DETECTION: Find traffic sign by color, then crop for classifier
  // Red signs: Stop, No Entry, Speed Limits (H<15 or H>160, S>80, V>60)
  // Blue signs: Keep Left/Right, Roundabout, Ahead Only (H:100-135, S>60, V>50)
  // Yellow signs: Road Work, Children Crossing (H:18-45, S>80, V>80)
  // ======================================================================

  // --- Decode full frame to RGB888 ---
  const size_t full_rgb_len = static_cast<size_t>(full_w) * static_cast<size_t>(full_h) * 3;
  uint8_t* full_rgb = (uint8_t*)heap_caps_malloc(full_rgb_len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (full_rgb == nullptr) {
    esp_camera_fb_return(fb);
    xSemaphoreGive(camera_mutex);
    dropped_invalid++;
    logErrorRateLimited("full_rgb_alloc_failed");
    return false;
  }

  bool decode_ok = false;
  if (fb->format == PIXFORMAT_JPEG) {
    decode_ok = fmt2rgb888(fb->buf, fb->len, PIXFORMAT_JPEG, full_rgb);
  } else if (fb->format == PIXFORMAT_RGB565) {
    decode_ok = fmt2rgb888(fb->buf, fb->len, PIXFORMAT_RGB565, full_rgb);
  }

  // Release camera frame ASAP
  esp_camera_fb_return(fb);
  xSemaphoreGive(camera_mutex);

  if (!decode_ok) {
    free(full_rgb);
    dropped_invalid++;
    logErrorRateLimited("frame_decode_failed");
    return false;
  }

  // --- Scan for sign-colored pixels (subsample every 4th pixel for speed) ---
  int roi_x0 = full_w, roi_y0 = full_h, roi_x1 = 0, roi_y1 = 0;
  int sign_pixel_count = 0;
  constexpr int SCAN_STEP = 4;  // Check every 4th pixel

  for (int y = 0; y < full_h; y += SCAN_STEP) {
    for (int x = 0; x < full_w; x += SCAN_STEP) {
      size_t px = (static_cast<size_t>(y) * full_w + x) * 3;
      uint8_t r = full_rgb[px], g = full_rgb[px+1], b = full_rgb[px+2];

      // RGB to HSV (simplified, H in 0-180 range like OpenCV)
      uint8_t cmax = r > g ? (r > b ? r : b) : (g > b ? g : b);
      uint8_t cmin = r < g ? (r < b ? r : b) : (g < b ? g : b);
      uint8_t delta = cmax - cmin;
      uint8_t v = cmax;
      uint8_t s = (cmax == 0) ? 0 : static_cast<uint8_t>((static_cast<uint16_t>(delta) * 255) / cmax);
      int16_t h = 0;
      if (delta == 0) {
        h = 0;
      } else if (cmax == r) {
        h = 30 * (static_cast<int16_t>(g) - static_cast<int16_t>(b)) / delta;
        if (h < 0) h += 180;
      } else if (cmax == g) {
        h = 60 + 30 * (static_cast<int16_t>(b) - static_cast<int16_t>(r)) / delta;
      } else {
        h = 120 + 30 * (static_cast<int16_t>(r) - static_cast<int16_t>(g)) / delta;
      }
      if (h < 0) h += 180;

      bool is_sign_color = false;
      // Red (wraps around 0/180)
      if ((h < 15 || h > 160) && s > 80 && v > 60) is_sign_color = true;
      // Blue
      else if (h >= 100 && h <= 135 && s > 60 && v > 50) is_sign_color = true;
      // Yellow
      else if (h >= 18 && h <= 45 && s > 80 && v > 80) is_sign_color = true;

      if (is_sign_color) {
        if (x < roi_x0) roi_x0 = x;
        if (y < roi_y0) roi_y0 = y;
        if (x > roi_x1) roi_x1 = x;
        if (y > roi_y1) roi_y1 = y;
        sign_pixel_count++;
      }
    }
  }

  // --- Determine crop region ---
  int crop_x0, crop_y0, src_w, src_h;
  constexpr int MIN_SIGN_PIXELS = 15;    // At least 15 colored pixels (subsampled)
  constexpr float ROI_PAD = 0.25f;       // 25% padding around detected ROI

  if (sign_pixel_count >= MIN_SIGN_PIXELS && roi_x1 > roi_x0 && roi_y1 > roi_y0) {
    // Sign-colored region found! Crop with padding
    int roi_w = roi_x1 - roi_x0;
    int roi_h = roi_y1 - roi_y0;
    int pad_x = static_cast<int>(roi_w * ROI_PAD);
    int pad_y = static_cast<int>(roi_h * ROI_PAD);

    crop_x0 = max(0, roi_x0 - pad_x);
    crop_y0 = max(0, roi_y0 - pad_y);
    int cx1 = min(full_w, roi_x1 + pad_x);
    int cy1 = min(full_h, roi_y1 + pad_y);
    src_w = cx1 - crop_x0;
    src_h = cy1 - crop_y0;

    // Make it square (classifier expects square input)
    int side = max(src_w, src_h);
    int cx = crop_x0 + src_w / 2;
    int cy = crop_y0 + src_h / 2;
    crop_x0 = max(0, cx - side / 2);
    crop_y0 = max(0, cy - side / 2);
    src_w = min(side, full_w - crop_x0);
    src_h = min(side, full_h - crop_y0);
  } else {
    // No sign color found → fallback to center-crop
    src_w = static_cast<int>(full_w * CENTER_CROP_RATIO);
    src_h = static_cast<int>(full_h * CENTER_CROP_RATIO);
    crop_x0 = (full_w - src_w) / 2;
    crop_y0 = (full_h - src_h) / 2;
  }

  // --- Copy cropped region to rgb_buf ---
  const size_t rgb_len = static_cast<size_t>(src_w) * static_cast<size_t>(src_h) * 3;
  uint8_t* rgb_buf = (uint8_t*)heap_caps_malloc(rgb_len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (rgb_buf == nullptr) {
    free(full_rgb);
    dropped_invalid++;
    logErrorRateLimited("rgb_buf_alloc_failed");
    return false;
  }

  for (int row = 0; row < src_h; ++row) {
    size_t so = (static_cast<size_t>(crop_y0 + row) * full_w + crop_x0) * 3;
    size_t do_ = static_cast<size_t>(row) * src_w * 3;
    memcpy(rgb_buf + do_, full_rgb + so, src_w * 3);
  }
  free(full_rgb);

  // --- Area-average downsampling from RGB888 to 96x96 ---
  // rgb_buf layout: [R, G, B, R, G, B, ...] row-major, 3 bytes per pixel
  for (int y = 0; y < 96; ++y) {
    int sy0 = (y * src_h) / 96;
    int sy1 = ((y + 1) * src_h) / 96;
    if (sy1 <= sy0) sy1 = sy0 + 1;
    if (sy1 > src_h) sy1 = src_h;

    for (int x = 0; x < 96; ++x) {
      int sx0 = (x * src_w) / 96;
      int sx1 = ((x + 1) * src_w) / 96;
      if (sx1 <= sx0) sx1 = sx0 + 1;
      if (sx1 > src_w) sx1 = src_w;

      int i = y * 96 + x;

      uint32_t accR = 0, accG = 0, accB = 0;
      uint16_t count = 0;
      for (int by = sy0; by < sy1; ++by) {
        for (int bx = sx0; bx < sx1; ++bx) {
          size_t px = (static_cast<size_t>(by) * static_cast<size_t>(src_w) + static_cast<size_t>(bx)) * 3;
          accR += rgb_buf[px + 0];
          accG += rgb_buf[px + 1];
          accB += rgb_buf[px + 2];
          count++;
        }
      }

      uint8_t r = static_cast<uint8_t>(accR / count);
      uint8_t g = static_cast<uint8_t>(accG / count);
      uint8_t b = static_cast<uint8_t>(accB / count);
      uint8_t grayPix = static_cast<uint8_t>((static_cast<uint16_t>(r) * 30 + static_cast<uint16_t>(g) * 59 + static_cast<uint16_t>(b) * 11) / 100);

      if (input->type == kTfLiteUInt8) {
        float s = input->params.scale;
        int32_t zp = input->params.zero_point;
        if (gray) {
          input->data.uint8[i] = quantizeToUInt8(grayPix, s, zp);
        } else if (hwc) {
          int idx = i * 3;
          input->data.uint8[idx + 0] = quantizeToUInt8(r, s, zp);
          input->data.uint8[idx + 1] = quantizeToUInt8(g, s, zp);
          input->data.uint8[idx + 2] = quantizeToUInt8(b, s, zp);
        } else {
          input->data.uint8[i] = quantizeToUInt8(r, s, zp);
          input->data.uint8[96 * 96 + i] = quantizeToUInt8(g, s, zp);
          input->data.uint8[2 * 96 * 96 + i] = quantizeToUInt8(b, s, zp);
        }
      } else if (input->type == kTfLiteInt8) {
        float s = input->params.scale;
        int32_t zp = input->params.zero_point;
        if (gray) {
          input->data.int8[i] = quantizeToInt8(grayPix, s, zp);
        } else if (hwc) {
          int idx = i * 3;
          input->data.int8[idx + 0] = quantizeToInt8(r, s, zp);
          input->data.int8[idx + 1] = quantizeToInt8(g, s, zp);
          input->data.int8[idx + 2] = quantizeToInt8(b, s, zp);
        } else {
          input->data.int8[i] = quantizeToInt8(r, s, zp);
          input->data.int8[96 * 96 + i] = quantizeToInt8(g, s, zp);
          input->data.int8[2 * 96 * 96 + i] = quantizeToInt8(b, s, zp);
        }
      } else {
        float rf = INPUT_EXPECTS_0_TO_1 ? (static_cast<float>(r) / 255.0f) : static_cast<float>(r);
        float gf = INPUT_EXPECTS_0_TO_1 ? (static_cast<float>(g) / 255.0f) : static_cast<float>(g);
        float bf = INPUT_EXPECTS_0_TO_1 ? (static_cast<float>(b) / 255.0f) : static_cast<float>(b);
        float grayf = INPUT_EXPECTS_0_TO_1 ? (static_cast<float>(grayPix) / 255.0f) : static_cast<float>(grayPix);
        if (gray) {
          input->data.f[i] = grayf;
        } else if (hwc) {
          int idx = i * 3;
          input->data.f[idx + 0] = rf;
          input->data.f[idx + 1] = gf;
          input->data.f[idx + 2] = bf;
        } else {
          input->data.f[i] = rf;
          input->data.f[96 * 96 + i] = gf;
          input->data.f[2 * 96 * 96 + i] = bf;
        }
      }
    }
  }

  free(rgb_buf);
  return true;
}

// Diagnostic: log raw model output scores every N seconds
static uint32_t last_diag_ms = 0;
static void printDiagnostics() {
  uint32_t now = millis();
  if (now - last_diag_ms < 5000) return;
  last_diag_ms = now;

  if (output == nullptr || input == nullptr) return;

  // Print model input tensor info
  Serial.printf("DBG:DIAG input_type=%d scale=%.6f zp=%d",
                input->type, input->params.scale, input->params.zero_point);
  // Print first 6 input bytes to verify data is not all zeros/garbage
  if (input->type == kTfLiteUInt8 && input->bytes >= 6) {
    Serial.printf(" first6=[%u,%u,%u,%u,%u,%u]",
                  input->data.uint8[0], input->data.uint8[1], input->data.uint8[2],
                  input->data.uint8[3], input->data.uint8[4], input->data.uint8[5]);
  }
  Serial.println();

  // Print ALL model output scores
  Serial.print("DBG:DIAG output_scores=");
  for (int i = 0; i < MODEL_CLASS_COUNT; ++i) {
    float score = 0.0f;
    if (output->type == kTfLiteUInt8) {
      score = (static_cast<int>(output->data.uint8[i]) - output->params.zero_point) * output->params.scale;
    } else if (output->type == kTfLiteInt8) {
      score = (static_cast<int>(output->data.int8[i]) - output->params.zero_point) * output->params.scale;
    } else if (output->type == kTfLiteFloat32) {
      score = output->data.f[i];
    }
    if (i > 0) Serial.print(',');
    Serial.printf("%d:%.4f", i, score);
  }
  Serial.println();
}

static void pushHistory(uint8_t class_id, uint8_t conf100, uint8_t margin_conf100) {
  history_class[history_pos] = class_id;
  history_conf[history_pos] = conf100;
  history_margin[history_pos] = margin_conf100;
  history_pos = (history_pos + 1) % STABILITY_WINDOW;
  if (history_count < STABILITY_WINDOW) {
    history_count++;
  }
}

static bool isTemporallyStable(uint8_t class_id, uint8_t& hits_out, uint8_t& valid_out) {
  uint8_t hits = 0;
  uint8_t valid = 0;
  for (uint8_t i = 0; i < history_count; ++i) {
    if (history_class[i] > MODEL_CLASS_MAX_ID) {
      continue;
    }
    valid++;
    if (history_class[i] == class_id) {
      hits++;
    }
  }
  hits_out = hits;
  valid_out = valid;
  return valid >= STABILITY_REQUIRE && hits >= STABILITY_REQUIRE;
}

// Helper: read one output element by index
static float readOutputScore(int idx) {
  if (output->type == kTfLiteUInt8) {
    return (static_cast<int>(output->data.uint8[idx]) - output->params.zero_point) * output->params.scale;
  } else if (output->type == kTfLiteInt8) {
    return (static_cast<int>(output->data.int8[idx]) - output->params.zero_point) * output->params.scale;
  } else {
    return output->data.f[idx];
  }
}

static bool decodeTopClass(uint8_t& class_id, uint8_t& conf100, uint8_t& runner_conf100) {
  int total_elements = 0;
  if (output->type == kTfLiteUInt8 || output->type == kTfLiteInt8) {
    total_elements = static_cast<int>(output->bytes);
  } else if (output->type == kTfLiteFloat32) {
    total_elements = static_cast<int>(output->bytes / sizeof(float));
  } else {
    parse_internal_fail++;
    logErrorRateLimited("unsupported_output_tensor_type");
    return false;
  }

  const int fomo_elements = FOMO_GRID_SIZE * FOMO_GRID_SIZE * MODEL_CLASS_COUNT;
  bool is_fomo = (total_elements == fomo_elements);
  bool is_classifier = (total_elements == MODEL_CLASS_COUNT);

  if (!is_fomo && !is_classifier) {
    parse_internal_fail++;
    logErrorRateLimited("output_size_unknown");
    return false;
  }

  float best = -1.0f;
  float second = -1.0f;
  int best_idx = -1;

  if (is_fomo) {
    // === FOMO grid: aggregate non-background votes by class id (1..15) ===
    uint16_t vote_count[MODEL_CLASS_COUNT] = {0};
    float vote_conf_sum[MODEL_CLASS_COUNT] = {0.0f};
    for (int cy = 0; cy < FOMO_GRID_SIZE; ++cy) {
      for (int cx = 0; cx < FOMO_GRID_SIZE; ++cx) {
        int base = (cy * FOMO_GRID_SIZE + cx) * MODEL_CLASS_COUNT;
        float cell_best = -1.0f;
        int cell_best_cls = 0;
        for (int c = 0; c < MODEL_CLASS_COUNT; ++c) {
          float s = readOutputScore(base + c);
          if (s > cell_best) {
            cell_best = s;
            cell_best_cls = c;
          }
        }
        if (cell_best_cls >= SIGN_CLASS_MIN_ID && cell_best_cls <= SIGN_CLASS_MAX_ID && cell_best >= FOMO_CELL_THRESHOLD) {
          vote_count[cell_best_cls]++;
          vote_conf_sum[cell_best_cls] += cell_best;
        }
      }
    }

    uint16_t max_votes = 0;
    for (int c = SIGN_CLASS_MIN_ID; c <= SIGN_CLASS_MAX_ID; ++c) {
      if (vote_count[c] > max_votes) {
        max_votes = vote_count[c];
      }
    }

    if (max_votes == 0) {
      class_id = BACKGROUND_CLASS_ID;
      conf100 = 100;
      runner_conf100 = 0;
      return true;
    }

    for (int c = SIGN_CLASS_MIN_ID; c <= SIGN_CLASS_MAX_ID; ++c) {
      if (vote_count[c] == 0) {
        continue;
      }
      float avg_conf = vote_conf_sum[c] / vote_count[c];
      if (avg_conf > best) {
        second = best;
        best = avg_conf;
        best_idx = c;
      } else if (avg_conf > second) {
        second = avg_conf;
      }
    }
  } else {
    // === Classifier fallback: read 1x16 distribution directly ===
    for (int i = 0; i <= MODEL_CLASS_MAX_ID; ++i) {
      float score = readOutputScore(i);
      if (score > best) {
        second = best;
        best = score;
        best_idx = i;
      } else if (score > second) {
        second = score;
      }
    }
  }

  if (best_idx < 0) {
    parse_internal_fail++;
    logErrorRateLimited("no_valid_best_class");
    return false;
  }

  if (best < 0.0f) best = 0.0f;
  if (best > 1.0f) best = 1.0f;
  if (second < 0.0f) second = 0.0f;
  if (second > 1.0f) second = 1.0f;

  class_id = static_cast<uint8_t>(best_idx);
  conf100 = static_cast<uint8_t>(roundf(best * 100.0f));
  runner_conf100 = static_cast<uint8_t>(roundf(second * 100.0f));
  if (conf100 > 100) conf100 = 100;
  if (runner_conf100 > 100) runner_conf100 = 100;
  return true;
}

static void emitSign(uint8_t class_id, uint8_t conf100, uint8_t runner_conf100) {
  if (class_id > MODEL_CLASS_MAX_ID || conf100 > 100 || runner_conf100 > 100) {
    dropped_invalid++;
    return;
  }

  uint8_t margin_conf100 = (conf100 >= runner_conf100) ? (conf100 - runner_conf100) : 0;

  float prev = conf_ema_by_class[class_id];
  float cur = static_cast<float>(conf100);
  float ema = (prev <= 0.0f) ? cur : (CONF_EMA_ALPHA * cur + (1.0f - CONF_EMA_ALPHA) * prev);
  conf_ema_by_class[class_id] = ema;
  uint8_t smooth_conf100 = static_cast<uint8_t>(roundf(ema));
  if (smooth_conf100 > 100) smooth_conf100 = 100;

  pushHistory(class_id, smooth_conf100, margin_conf100);

  if (class_id == BACKGROUND_CLASS_ID) {
    dropped_no_sign++;
    uint32_t now_ms = millis();
    if (now_ms - last_no_sign_log_ms >= 2000) {
      Serial.printf("DBG:no_sign top=%u conf=%u.%02u second=%u.%02u margin=%u.%02u\n",
                    class_id,
                    smooth_conf100 / 100,
                    smooth_conf100 % 100,
                    runner_conf100 / 100,
                    runner_conf100 % 100,
                    margin_conf100 / 100,
                    margin_conf100 % 100);
      last_no_sign_log_ms = now_ms;
    }
    return;
  }

  uint8_t required_conf = MIN_EMIT_CONF100;
  uint8_t required_margin = MIN_MARGIN_CONF100;
  if (class_id <= MODEL_CLASS_MAX_ID) {
    required_conf = MIN_EMIT_CONF100_BY_CLASS[class_id];
    required_margin = MIN_MARGIN_CONF100_BY_CLASS[class_id];
  }

  if (smooth_conf100 < required_conf || margin_conf100 < required_margin) {
    dropped_low_conf++;
    return;
  }

  uint8_t stable_hits = 0;
  uint8_t stable_valid = 0;
  bool stable = isTemporallyStable(class_id, stable_hits, stable_valid);
  if (!stable) {
    dropped_low_conf++;
    Serial.printf("DBG:unstable top=%u conf=%u.%02u margin=%u.%02u hits=%u/%u\n",
                  class_id,
                  smooth_conf100 / 100,
                  smooth_conf100 % 100,
                  margin_conf100 / 100,
                  margin_conf100 % 100,
                  stable_hits,
                  stable_valid);
    return;
  }

  if (class_id < SIGN_CLASS_MIN_ID || class_id > SIGN_CLASS_MAX_ID) {
    dropped_invalid++;
    return;
  }

  uint32_t now = millis();
  if (class_id == last_class && (now - last_sent_ms) < DUPLICATE_DEBOUNCE_MS) return;

  Serial.printf("SIGN:%u:%u.%02u", class_id, smooth_conf100 / 100, smooth_conf100 % 100);
  Serial.write('\n');
  Serial.printf("DBG:top=%u(%s) conf=%u.%02u second=%u.%02u margin=%u.%02u stable=%u\n",
                class_id,
                CLASS_LABELS[class_id],
                smooth_conf100 / 100,
                smooth_conf100 % 100,
                runner_conf100 / 100,
                runner_conf100 % 100,
                margin_conf100 / 100,
                margin_conf100 % 100,
                stable ? 1 : 0);

  sent++;
  last_class = class_id;
  last_sent_ms = now;
}

static void printStats() {
  uint32_t now = millis();
  if (now - last_stats_ms < STATS_PERIOD_MS) return;
  Serial.printf("DBG:sent=%lu no_sign=%lu low_conf=%lu drop=%lu parse_fail=%lu\n",
                (unsigned long)sent,
                (unsigned long)dropped_no_sign,
                (unsigned long)dropped_low_conf,
                (unsigned long)dropped_invalid,
                (unsigned long)parse_internal_fail);
  last_stats_ms = now;
}

void setup() {
  Serial.begin(115200);
  delay(300);

  static tflite::MicroErrorReporter micro_error_reporter;
  error_reporter = &micro_error_reporter;

  Serial.printf("DBG:FW=%s PROTO=%s\n", FW_VERSION, PROTO_VERSION);
  printClassMap();

  cameraReady = initCamera();
  if (cameraReady) {
    camera_mutex = xSemaphoreCreateMutex();
    if (camera_mutex == nullptr) {
      cameraReady = false;
      logErrorRateLimited("camera_mutex_create_failed");
    }
  }

  modelReady = initTflm();
  wifiReady = initWiFi();
  streamReady = wifiReady && startStreamServer();

  if (modelReady && input != nullptr && output != nullptr) {
    Serial.printf("DBG:input_type=%d output_type=%d input_scale_mode=%s min_emit_default=%u.%02u stable=%u/%u\n",
                  input->type,
                  output->type,
                  INPUT_EXPECTS_0_TO_1 ? "0_1" : "0_255",
                  MIN_EMIT_CONF100 / 100,
                  MIN_EMIT_CONF100 % 100,
                  STABILITY_REQUIRE,
                  STABILITY_WINDOW);

    int out_count = 0;
    if (output->type == kTfLiteUInt8 || output->type == kTfLiteInt8) {
      out_count = static_cast<int>(output->bytes);
    } else if (output->type == kTfLiteFloat32) {
      out_count = static_cast<int>(output->bytes / sizeof(float));
    }
    const int expected_classifier = MODEL_CLASS_COUNT;
    const int expected_fomo = FOMO_GRID_SIZE * FOMO_GRID_SIZE * MODEL_CLASS_COUNT;
    if (out_count != expected_classifier && out_count != expected_fomo) {
      logErrorRateLimited("output_class_contract_mismatch");
      modelReady = false;
    }
  }

  if (!cameraReady || !modelReady || !wifiReady || !streamReady) {
    Serial.printf("DBG:init_state camera=%u model=%u wifi=%u stream=%u\n",
                  cameraReady ? 1 : 0,
                  modelReady ? 1 : 0,
                  wifiReady ? 1 : 0,
                  streamReady ? 1 : 0);
  }

  if (wifiReady) {
    Serial.printf("DBG:stream_url=http://%s:%u/stream\n", WiFi.localIP().toString().c_str(), CAMERA_STREAM_PORT);
  }
}

void loop() {
  if (!wifiReady) {
    wifiReady = initWiFi();
    if (wifiReady) {
      Serial.printf("DBG:wifi_recovered ip=%s\n", WiFi.localIP().toString().c_str());
    }
    delay(250);
    return;
  }

  if (!streamReady) {
    streamReady = startStreamServer();
    if (streamReady) {
      Serial.printf("DBG:stream_recovered url=http://%s:%u/stream\n", WiFi.localIP().toString().c_str(), CAMERA_STREAM_PORT);
    }
    delay(250);
    return;
  }

  if (!cameraReady) {
    cameraReady = initCamera();
    if (cameraReady && camera_mutex == nullptr) {
      camera_mutex = xSemaphoreCreateMutex();
      if (camera_mutex == nullptr) {
        cameraReady = false;
        logErrorRateLimited("camera_mutex_create_failed");
      }
    }
    if (cameraReady) {
      Serial.println("DBG:camera_recovered");
    }
    delay(500);
    return;
  }

  if (!modelReady) {
    modelReady = initTflm();
    if (modelReady) {
      Serial.println("DBG:model_recovered");
    }
    delay(500);
    return;
  }

  if (interpreter == nullptr || input == nullptr || output == nullptr) {
    modelReady = false;
    delay(500);
    return;
  }

  if (!fillModelInput()) {
    delay(10);
    return;
  }

  if (interpreter->Invoke() != kTfLiteOk) {
    parse_internal_fail++;
    delay(10);
    return;
  }

  uint8_t class_id = 0;
  uint8_t conf100 = 0;
  uint8_t runner_conf100 = 0;
  if (decodeTopClass(class_id, conf100, runner_conf100)) {
    emitSign(class_id, conf100, runner_conf100);
  }

  printDiagnostics();
  printStats();
  delay(20);
}

