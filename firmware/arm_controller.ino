/*
  ArmGenius — Arm Controller
  Receives named actions via HTTP and moves servos accordingly.

  This is the "DUM-E" pattern: the LLM (running on a laptop/server) decides
  WHAT the arm should do; this firmware just executes those decisions as fast
  servo moves. Keeping firmware dumb means you can swap in any "brain" without
  reflashing the board.

  WIRING:
    Servo 1 (base rotation): GPIO 13
    Servo 2 (arm tilt, if available): GPIO 12
    Servo 3 (claw/gripper, if available): GPIO 14

  Power note: for 2+ servos, use a separate 5V supply — the ESP32 USB
  power cannot reliably drive multiple servos simultaneously. Large servos
  (MG996R) can pull 1-2A each and will brown out the board if powered
  from the USB rail. Share GND between the external supply and the ESP32.

  LIBRARIES TO INSTALL (Arduino IDE -> Library Manager):
    - "ESP32Servo" by Kevin Harrington / madhephaestus

  ADDING MORE SERVOS:
    1. Declare another Servo object (e.g. wristServo)
    2. Attach it to a free GPIO in setup()
    3. Add new action branches in doAction()
    4. Call it from the Flask backend with the new action name

  USAGE:
    After flashing, open Serial Monitor at 115200 baud.
    The board prints its IP address once connected to WiFi.
    Set ARM_URL=http://<that-ip> in backend/.env and restart Flask.

    Manual test:
      curl "http://<ip>/action?name=wave"
      curl "http://<ip>/action?name=grab"
*/

#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>

// ---- CONFIGURE THESE ----
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
// --------------------------

Servo baseServo;   // GPIO 13 — rotates the arm left/right
Servo tiltServo;   // GPIO 12 — tilts the arm up/down (bow action)
Servo clawServo;   // GPIO 14 — opens/closes the gripper

WebServer server(80);

// ---------------------------------------------------------------------------
// doAction — map a named action to servo moves
// ---------------------------------------------------------------------------
void doAction(String action) {
  Serial.println("Action: " + action);

  if (action == "point_left") {
    baseServo.write(30);
    delay(500);

  } else if (action == "point_right") {
    baseServo.write(150);
    delay(500);

  } else if (action == "center") {
    baseServo.write(90);
    delay(500);

  } else if (action == "wave") {
    // Rock the base servo back and forth three times
    for (int i = 0; i < 3; i++) {
      baseServo.write(60);
      delay(400);
      baseServo.write(120);
      delay(400);
    }
    baseServo.write(90);   // return to centre

  } else if (action == "grab") {
    clawServo.write(10);   // close the claw
    delay(500);

  } else if (action == "release") {
    clawServo.write(80);   // open the claw
    delay(500);

  } else if (action == "bow") {
    tiltServo.write(130);  // tilt forward
    delay(600);
    tiltServo.write(90);   // return to upright
    delay(400);

  } else {
    // Unknown action — do nothing, return success anyway
    Serial.println("Unknown action (ignored): " + action);
  }
}

// ---------------------------------------------------------------------------
// HTTP handler — GET /action?name=<action>
// ---------------------------------------------------------------------------
void handleAction() {
  String action = server.hasArg("name") ? server.arg("name") : "center";
  doAction(action);
  server.send(
    200,
    "application/json",
    "{\"status\":\"ok\",\"action\":\"" + action + "\"}"
  );
}

void handleRoot() {
  server.send(
    200,
    "text/plain",
    "ArmGenius controller online.\n"
    "Try: /action?name=wave\n"
    "Actions: point_left, point_right, center, wave, grab, release, bow"
  );
}

// ---------------------------------------------------------------------------
// setup
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  // Attach servos with the standard 500-2400 µs pulse range (SG90/MG996R)
  baseServo.attach(13, 500, 2400);
  tiltServo.attach(12, 500, 2400);
  clawServo.attach(14, 500, 2400);

  // Park all servos at neutral positions on boot
  baseServo.write(90);   // centre
  tiltServo.write(90);   // upright
  clawServo.write(80);   // open

  // Connect to WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("ArmGenius controller ready!");
  Serial.print("Put this in backend/.env as ARM_URL: http://");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.on("/action", handleAction);
  server.begin();
}

// ---------------------------------------------------------------------------
// loop
// ---------------------------------------------------------------------------
void loop() {
  server.handleClient();
}
