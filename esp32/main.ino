// ESP32 PMSA003 Air Quality Monitor with MQTT and Buzzer Control
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

// Configuration
#define DEVICE_ID "air_sensor_with_buzzer"
#define DEBUG_MODE false  // Set to true only when connected to serial

// WiFi Configuration
const char* WIFI_SSID = "Hyperoptic Fibre BE97";
const char* WIFI_PASSWORD = "t3esGbsSEAG6tA";

// MQTT Configuration
const char* MQTT_SERVER = "192.168.1.114";  // Your MQTT broker IP
const int MQTT_PORT = 1883;
const char* MQTT_USER = "";  // Leave empty if no auth
const char* MQTT_PASSWORD = "";

// Alternative: Create a config.h file with your credentials
// #include "config.h"  // Uncomment this and comment out the above

// MQTT Topics
const char* TOPIC_DATA = "airquality/sensor/data";
const char* TOPIC_COMMAND = "airquality/sensor/command";
const char* TOPIC_STATUS = "airquality/sensor/status";
const char* TOPIC_RESPONSE = "airquality/sensor/response";

// Hardware Configuration
#define BUZZER_PIN 23  // GPIO23 connected to NPN transistor
#define LED_PIN 2      // GPIO2 - Built-in LED on most ESP32 boards (change as needed)

// PMSA003 Protocol Constants
#define PMSA003_START_BYTE_1 0x42
#define PMSA003_START_BYTE_2 0x4D
#define PMSA003_FRAME_LENGTH 32
#define PMSA003_PAYLOAD_LENGTH 30

// Timing
unsigned long lastSensorRead = 0;
unsigned long lastMqttReconnect = 0;
unsigned long lastBuzzerUpdate = 0;
const unsigned long SENSOR_READ_INTERVAL = 100;  // 100ms = 10Hz
const unsigned long MQTT_RECONNECT_INTERVAL = 5000;
const unsigned long BUZZER_UPDATE_INTERVAL = 10;  // 10ms for smooth buzzer control

// Buzzer control variables
float buzzerDutyCycle = 0.0;  // 0.0 = off, 1.0 = always on
float buzzerPeriod = 1.0;      // Period in seconds
unsigned long buzzerCycleStart = 0;
bool buzzerState = false;

// Objects
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// Data buffer
uint8_t dataBuffer[PMSA003_FRAME_LENGTH];
int bufferIndex = 0;

// Structure to hold sensor data
struct PMSensorData {
  uint16_t pm1_0_cf1;
  uint16_t pm2_5_cf1;
  uint16_t pm10_cf1;
  uint16_t pm1_0_atm;
  uint16_t pm2_5_atm;
  uint16_t pm10_atm;
  uint16_t particles_03;
  uint16_t particles_05;
  uint16_t particles_10;
  uint16_t particles_25;
  uint16_t particles_50;
  uint16_t particles_100;
  uint8_t version;
  uint8_t errorCode;
};

PMSensorData sensorData;
bool hasNewData = false;

// Debug print macro
#if DEBUG_MODE
  #define DEBUG_PRINT(x) Serial.print(x)
  #define DEBUG_PRINTLN(x) Serial.println(x)
#else
  #define DEBUG_PRINT(x)
  #define DEBUG_PRINTLN(x)
#endif

void setup() {
  #if DEBUG_MODE
    Serial.begin(115200);
    while (!Serial) { ; }
  #endif

  // Initialize buzzer pin
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  // Initialize LED pin for visual feedback
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Initialize sensor serial
  Serial2.begin(9600);

  // Initialize WiFi
  setupWiFi();

  // Initialize MQTT
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(512);  // Increase buffer for JSON

  // Configure time for UK timezone (though timestamps are output in UTC)
  configTime(0, 3600, "pool.ntp.org", "time.nist.gov");  // GMT+0 with DST
  setenv("TZ", "GMT0BST,M3.5.0/1,M10.5.0", 1);  // UK timezone with BST
  tzset();

  // Connect to MQTT
  connectMQTT();

  // Send startup status
  sendStatus("started");
}

void loop() {
  // Maintain MQTT connection
  if (!mqttClient.connected()) {
    unsigned long now = millis();
    if (now - lastMqttReconnect >= MQTT_RECONNECT_INTERVAL) {
      lastMqttReconnect = now;
      connectMQTT();
    }
  }
  mqttClient.loop();

  // Update buzzer state frequently for smooth control
  unsigned long now = millis();
  if (now - lastBuzzerUpdate >= BUZZER_UPDATE_INTERVAL) {
    lastBuzzerUpdate = now;
    updateBuzzer();
  }

  // Read sensor data
  readSensorData();

  // Send data at 10Hz
  if (now - lastSensorRead >= SENSOR_READ_INTERVAL) {
    lastSensorRead = now;
    if (hasNewData) {
      sendSensorData();
      hasNewData = false;
    }
  }
}

void setupWiFi() {
  DEBUG_PRINTLN("Connecting to WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    DEBUG_PRINT(".");
  }

  DEBUG_PRINTLN("\nWiFi connected");
  DEBUG_PRINT("IP address: ");
  DEBUG_PRINTLN(WiFi.localIP());
}

void connectMQTT() {
  DEBUG_PRINTLN("Connecting to MQTT...");

  String clientId = String(DEVICE_ID) + "_" + String(random(0xffff), HEX);

  bool connected = false;
  if (strlen(MQTT_USER) > 0) {
    connected = mqttClient.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD);
  } else {
    connected = mqttClient.connect(clientId.c_str());
  }

  if (connected) {
    DEBUG_PRINTLN("MQTT connected");
    mqttClient.subscribe(TOPIC_COMMAND);
    sendStatus("connected");
  } else {
    DEBUG_PRINT("MQTT failed, rc=");
    DEBUG_PRINTLN(mqttClient.state());
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, payload, length);

  if (error) {
    DEBUG_PRINT("JSON parse failed: ");
    DEBUG_PRINTLN(error.c_str());
    return;
  }

  const char* type = doc["type"] | "";
  const char* command = doc["command"] | "";
  const char* cmdId = doc["id"] | "unknown";

  StaticJsonDocument<256> response;
  response["id"] = cmdId;
  response["device_id"] = DEVICE_ID;

  // Handle buzzer commands
  if (strcmp(type, "buzzer") == 0) {
    if (doc.containsKey("duty_cycle") && doc.containsKey("period")) {
      buzzerDutyCycle = doc["duty_cycle"].as<float>();
      buzzerPeriod = doc["period"].as<float>();

      // Constrain values
      buzzerDutyCycle = constrain(buzzerDutyCycle, 0.0, 1.0);
      if (buzzerPeriod < 0.01) {
        buzzerPeriod = 0.01;  // Minimum 10ms period
      }

      // Reset cycle start time
      buzzerCycleStart = millis();

      response["status"] = "ok";
      response["message"] = "Buzzer settings updated";
      response["duty_cycle"] = buzzerDutyCycle;
      response["period"] = buzzerPeriod;
    } else {
      response["status"] = "error";
      response["message"] = "Missing duty_cycle or period";
    }
  }
  // Handle legacy commands
  else if (strcmp(command, "set_pin") == 0) {
    int pin = doc["pin"];
    int value = doc["value"];
    pinMode(pin, OUTPUT);
    digitalWrite(pin, value);
    response["status"] = "ok";
    response["message"] = "Pin set";
  }
  else if (strcmp(command, "get_status") == 0) {
    response["status"] = "ok";
    response["wifi_rssi"] = WiFi.RSSI();
    response["free_heap"] = ESP.getFreeHeap();
    response["uptime"] = millis();
    response["buzzer_duty_cycle"] = buzzerDutyCycle;
    response["buzzer_period"] = buzzerPeriod;
  }
  else if (strcmp(command, "reboot") == 0) {
    response["status"] = "ok";
    response["message"] = "Rebooting...";
    sendJsonMessage(TOPIC_RESPONSE, response);
    delay(1000);
    ESP.restart();
  }
  else {
    response["status"] = "error";
    response["message"] = "Unknown command";
  }

  sendJsonMessage(TOPIC_RESPONSE, response);
}

void updateBuzzer() {
  if (buzzerDutyCycle <= 0.0) {
    // Buzzer and LED off
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(LED_PIN, LOW);
    buzzerState = false;
  } else if (buzzerDutyCycle >= 1.0) {
    // Buzzer and LED always on
    digitalWrite(BUZZER_PIN, HIGH);
    digitalWrite(LED_PIN, HIGH);
    buzzerState = true;
  } else {
    // PWM-like control
    unsigned long cycleTime = millis() - buzzerCycleStart;
    float cyclePosition = (cycleTime % (unsigned long)(buzzerPeriod * 1000)) / (buzzerPeriod * 1000.0);

    bool shouldBeOn = cyclePosition < buzzerDutyCycle;

    if (shouldBeOn != buzzerState) {
      digitalWrite(BUZZER_PIN, shouldBeOn ? HIGH : LOW);
      digitalWrite(LED_PIN, shouldBeOn ? HIGH : LOW);
      buzzerState = shouldBeOn;
    }
  }
}

void readSensorData() {
  while (Serial2.available()) {
    uint8_t byte = Serial2.read();

    // Look for start bytes
    if (bufferIndex == 0 && byte != PMSA003_START_BYTE_1) {
      continue;
    }
    if (bufferIndex == 1 && byte != PMSA003_START_BYTE_2) {
      bufferIndex = 0;
      continue;
    }

    // Store byte in buffer
    dataBuffer[bufferIndex] = byte;
    bufferIndex++;

    // Check if we have a complete frame
    if (bufferIndex >= PMSA003_FRAME_LENGTH) {
      if (processFrame()) {
        hasNewData = true;
      }
      bufferIndex = 0;
    }
  }
}

bool processFrame() {
  // Verify start bytes
  if (dataBuffer[0] != PMSA003_START_BYTE_1 || dataBuffer[1] != PMSA003_START_BYTE_2) {
    return false;
  }

  // Calculate checksum
  uint16_t calculatedChecksum = 0;
  for (int i = 0; i < PMSA003_PAYLOAD_LENGTH; i++) {
    calculatedChecksum += dataBuffer[i];
  }

  // Extract and verify checksum
  uint16_t receivedChecksum = (dataBuffer[30] << 8) | dataBuffer[31];
  if (calculatedChecksum != receivedChecksum) {
    return false;
  }

  // Extract data (all data is big-endian)
  sensorData.pm1_0_cf1 = (dataBuffer[4] << 8) | dataBuffer[5];
  sensorData.pm2_5_cf1 = (dataBuffer[6] << 8) | dataBuffer[7];
  sensorData.pm10_cf1 = (dataBuffer[8] << 8) | dataBuffer[9];
  sensorData.pm1_0_atm = (dataBuffer[10] << 8) | dataBuffer[11];
  sensorData.pm2_5_atm = (dataBuffer[12] << 8) | dataBuffer[13];
  sensorData.pm10_atm = (dataBuffer[14] << 8) | dataBuffer[15];
  sensorData.particles_03 = (dataBuffer[16] << 8) | dataBuffer[17];
  sensorData.particles_05 = (dataBuffer[18] << 8) | dataBuffer[19];
  sensorData.particles_10 = (dataBuffer[20] << 8) | dataBuffer[21];
  sensorData.particles_25 = (dataBuffer[22] << 8) | dataBuffer[23];
  sensorData.particles_50 = (dataBuffer[24] << 8) | dataBuffer[25];
  sensorData.particles_100 = (dataBuffer[26] << 8) | dataBuffer[27];
  sensorData.version = dataBuffer[28];
  sensorData.errorCode = dataBuffer[29];

  return true;
}

String getISO8601Timestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return "1970-01-01T00:00:00.000Z";
  }

  // Get milliseconds
  struct timeval tv;
  gettimeofday(&tv, NULL);
  int milliseconds = tv.tv_usec / 1000;

  // Convert to UTC for ISO 8601
  time_t now;
  time(&now);
  struct tm *utc_tm = gmtime(&now);

  char buffer[30];
  snprintf(buffer, sizeof(buffer), "%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
           utc_tm->tm_year + 1900,
           utc_tm->tm_mon + 1,
           utc_tm->tm_mday,
           utc_tm->tm_hour,
           utc_tm->tm_min,
           utc_tm->tm_sec,
           milliseconds);

  return String(buffer);
}

void sendSensorData() {
  StaticJsonDocument<512> doc;

  // Add formatted timestamp
  doc["timestamp"] = getISO8601Timestamp();
  doc["device_id"] = DEVICE_ID;

  // Add all sensor data
  doc["pm1_0_cf1"] = sensorData.pm1_0_cf1;
  doc["pm2_5_cf1"] = sensorData.pm2_5_cf1;
  doc["pm10_cf1"] = sensorData.pm10_cf1;
  doc["pm1_0_atm"] = sensorData.pm1_0_atm;
  doc["pm2_5_atm"] = sensorData.pm2_5_atm;
  doc["pm10_atm"] = sensorData.pm10_atm;
  doc["particles_03"] = sensorData.particles_03;
  doc["particles_05"] = sensorData.particles_05;
  doc["particles_10"] = sensorData.particles_10;
  doc["particles_25"] = sensorData.particles_25;
  doc["particles_50"] = sensorData.particles_50;
  doc["particles_100"] = sensorData.particles_100;
  doc["version"] = sensorData.version;
  doc["error_code"] = sensorData.errorCode;

  sendJsonMessage(TOPIC_DATA, doc);
}

void sendStatus(const char* status) {
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["status"] = status;
  doc["timestamp"] = getISO8601Timestamp();

  sendJsonMessage(TOPIC_STATUS, doc);
}

void sendJsonMessage(const char* topic, JsonDocument& doc) {
  char buffer[512];
  size_t n = serializeJson(doc, buffer);
  mqttClient.publish(topic, buffer, n);
}