# ArmGenius

**Type a command in plain English. The arm moves.**

ArmGenius is a hackathon project that bridges natural language and physical motion. You type "wave hello to the judges", the LLM decides the best servo action, the Flask backend fires an HTTP request at an ESP32 servo controller, and the arm waves — all in under a second.

---

## The DUM-E Pattern

This project uses the same architecture as the winning "DUM-E" arm at Hack the North 2025:

```
User types text
      |
      v
  Flask backend
  (runs LLM, parses ACTION:{...})
      |
      v
  ESP32 arm controller
  (receives /action?name=wave, moves servos)
```

The LLM is the **brain** — it decides *what* to do and expresses that decision as a structured `ACTION:{...}` token at the end of its reply.

The ESP32 is the **muscle** — it executes named actions with no understanding of language. It just reads `?name=wave` and moves servos.

Splitting this way means you can:
- Swap in a different LLM (GPT, Gemini, Llama) without touching firmware
- Add voice input (Whisper) without touching firmware
- Add a camera (Template 2) as vision input without touching firmware
- Add more servos or actions without touching the LLM prompt (just add branches to `doAction()`)

---

## Supported Actions

| Action name    | What the arm does                              |
|----------------|------------------------------------------------|
| `point_left`   | Base servo rotates to 30° (leftward)           |
| `point_right`  | Base servo rotates to 150° (rightward)         |
| `center`       | Base servo returns to 90° (straight ahead)     |
| `wave`         | Base rocks 60°↔120° three times, then centers  |
| `grab`         | Claw servo closes to 10°                       |
| `release`      | Claw servo opens to 80°                        |
| `bow`          | Tilt servo dips to 130°, then returns to 90°   |
| `none`         | No movement (LLM is just talking)              |

---

## Wiring Diagram

```
ESP32                       Servo(s)
------                      --------
GPIO 13  ──── signal ────>  Base rotation servo (SG90 or MG996R)
GPIO 12  ──── signal ────>  Tilt / elbow servo
GPIO 14  ──── signal ────>  Claw / gripper servo

GND      ──── GND    ────>  All servo grounds
                             (and external 5V supply GND if using one)

[External 5V supply]
   +5V   ──── VCC    ────>  All servo power wires
```

**Power note:** the ESP32's USB 5V pin can drive a single small SG90. For two or more servos, or any MG996R, use a separate 5V 2A+ supply for the servos. Share the GND rail between the supply and the ESP32. Failing to do this causes brownouts that manifest as random reboots or WiFi drops during movement.

---

## Quick Start

### 1. Flash the firmware

1. Open `firmware/arm_controller.ino` in the Arduino IDE
2. Install the **ESP32Servo** library (Library Manager)
3. Set your WiFi credentials at the top of the file
4. Select your ESP32 board and port, then upload
5. Open Serial Monitor at 115200 baud
6. Copy the IP address the board prints

### 2. Configure the backend

```bash
cd backend
cp .env.example .env
# Edit .env:
#   OPENAI_API_KEY=sk-...   (or Groq key)
#   ARM_URL=http://<esp32-ip>
```

### 3. Run the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## Demo Script (for judges)

1. **"Wave hello!"** — base rocks back and forth three times
2. **"Point to the right"** — arm swings to the right
3. **"Pick something up"** — claw closes
4. **"Bow to the judges"** — arm dips forward and returns
5. **"What can you do?"** — LLM lists its capabilities; arm stays still (action = `none`)

---

## How to Extend

### Add a new servo

1. Wire the servo to a free GPIO (e.g. GPIO 27)
2. In `arm_controller.ino`:
   ```cpp
   Servo wristServo;
   // in setup():
   wristServo.attach(27, 500, 2400);
   wristServo.write(90);
   // in doAction():
   } else if (action == "twist_wrist") {
     wristServo.write(45);
     delay(500);
   }
   ```
3. Add `twist_wrist` to the action list in the system prompt in `.env`
4. The LLM will start using it automatically — no backend code changes needed

### Run without hardware

Set `ARM_URL=` (leave blank) in `.env`. The backend still parses the LLM's `ACTION:{...}` response and returns `arm_action` in the JSON — the frontend shows the "Arm executing" indicator even without a physical arm. Good for demoing the AI logic remotely.

### Use Groq for lower latency

```env
OPENAI_API_KEY=gsk_...
OPENAI_BASE_URL=https://api.groq.com/openai/v1
MODEL_NAME=llama-3.3-70b-versatile
```

Groq's free tier delivers responses in ~200ms which makes the arm feel nearly instant.

---

## Project Structure

```
armgenius/
  firmware/
    arm_controller.ino    # ESP32 WebServer — receives named actions, moves servos
  backend/
    app.py                # Flask — LLM chat, ACTION parser, arm HTTP relay
    requirements.txt
    .env.example
    data/                 # Drop .txt/.md files here for RAG context
  frontend/
    src/
      App.jsx             # Chat UI with arm status indicator and starter chips
      index.css           # Mechanical blue/gray design tokens
      main.jsx
    index.html
    package.json
    vite.config.js
  README.md
  .gitignore
```
