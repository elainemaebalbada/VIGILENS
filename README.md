# VIGILENS
**Visual Monitoring for Driver Alertness**

VIGILENS is an educational Python desktop application that uses a webcam and classical computer-vision techniques to monitor visible facial indicators associated with possible drowsiness. It detects faces using OpenCV Haar Cascade, estimates 68 facial landmarks using dlib, calculates Eye Aspect Ratio (EAR) and Mouth Aspect Ratio (MAR), and monitors prolonged eye closure over time.

> **Safety Notice:** VIGILENS is an educational prototype. It is not a medical diagnostic tool or certified driver-safety system, and it cannot guarantee accident prevention. It must not be used as a substitute for adequate rest or responsible driving decisions.

## 1. Features

- **Real-Time Webcam Monitoring** – Captures and processes webcam frames to monitor visible facial indicators.
- **Face Detection** – Uses OpenCV Haar Cascade Classifier to locate the face.
- **Facial Landmark Detection** – Uses dlib's pretrained 68-point facial landmark predictor to identify facial feature positions.
- **Eye Aspect Ratio (EAR)** – Measures eye openness to identify possible eye closure.
- **Mouth Aspect Ratio (MAR)** – Measures mouth opening to identify possible yawning.
- **Time-Based Drowsiness Detection** – Monitors prolonged eye closure before generating a drowsiness alert.
- **Visual and Audio Alerts** – Provides visual status indicators and optional audio notifications.
- **Session Recording** – Stores completed monitoring sessions and their detection events.
- **Session History** – Allows users to review recorded sessions and their associated events.
- **Analytics** – Presents summaries, event statistics, and EAR measurements from recorded sessions.
- **Configurable Settings** – Allows users to adjust detection thresholds, eye-closure duration, camera index, and audio preferences.

## 2. Computer Vision Topics Implemented

VIGILENS implements four computer-vision topics using Python and classical computer-vision techniques.

### 2.1 Image Operations

Image operations are applied to webcam frames before and during processing.

Implemented operations include:
- Grayscale conversion for face detection.
- Image resizing to manage frame dimensions and processing.
- Histogram equalization to improve image contrast.
- Image annotation and overlays for displaying detection results.

### 2.2 Haar Cascade Classifier

The application uses OpenCV's Haar Cascade Classifier for face detection.

The classifier processes grayscale webcam frames to locate visible faces. The detected face region is used as the basis for subsequent facial landmark detection.

### 2.3 Image Analysis and Transformation

VIGILENS analyzes facial measurements using geometric calculations.

**Eye Aspect Ratio (EAR)**

EAR estimates eye openness using distances between selected eye landmarks. A lower EAR value can indicate that the eyes are closing.

**Mouth Aspect Ratio (MAR)**

MAR estimates mouth opening using selected mouth landmarks. A higher MAR value can indicate a possible yawning event.

The application also monitors eye-closure duration to determine whether prolonged eye closure should trigger a drowsiness alert.

### 2.4 Facial Landmark Detection

The application uses dlib's pretrained 68-point facial landmark predictor.

The predictor identifies facial landmark positions, including points around the eyes, eyebrows, nose, and mouth. These landmarks provide the coordinates used for EAR and MAR calculations.

**Note:** Image segmentation and motion/object tracking are not claimed as implemented features.

## 3. How the Application Works

The VIGILENS monitoring process follows these steps:

1. **Webcam Capture** – The application captures video frames from the selected webcam.
2. **Image Preprocessing** – Frames are converted to grayscale and prepared for face detection.
3. **Face Detection** – Haar Cascade identifies the face region.
4. **Facial Landmark Detection** – dlib estimates the 68 facial landmark positions.
5. **Measurement Calculation** – EAR and MAR are calculated using the detected landmarks.
6. **Drowsiness Monitoring** – The application monitors eye-closure duration over time.
7. **Alert Generation** – A drowsiness alert is generated when the configured eye-closure condition is met.
8. **Event and Session Recording** – Monitoring events and session information are stored in the local SQLite database.

Yawning is recorded as a possible secondary indicator and does not independently trigger a drowsiness alert.

## 4. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| OpenCV | Image processing and Haar Cascade face detection |
| dlib | Facial landmark detection |
| NumPy | Numerical and geometric calculations |
| CustomTkinter | Desktop graphical user interface |
| Tkinter | Supporting GUI components |
| Pillow | Image handling and webcam preview |
| Matplotlib | Analytics charts |
| SQLite | Local database storage |
| pygame | Audio alert playback |

## 5. System Requirements

- Windows 10 or Windows 11 recommended.
- Python 3.10 or 3.11 recommended for compatibility with dlib.
- A working webcam.
- Microphone access is not required.
- Speakers or headphones are recommended for audio alerts.
- Sufficient storage for the application, dependencies, and facial landmark model.

## 6. Installation and Setup

### 6.1 Extract the Project

Extract the complete VIGILENS project folder and open it in Visual Studio Code.

### 6.2 Create a Virtual Environment

Open the VS Code terminal and run:

```powershell
py -3.11 -m venv .venv
```

### 6.3 Activate the Virtual Environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Then activate the environment again.

### 6.4 Install Dependencies

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install the required packages:

```powershell
pip install -r requirements.txt
```

### 6.5 dlib Installation Note

On Windows, dlib may require CMake and Microsoft Visual C++ Build Tools if a compatible prebuilt package is unavailable.

If installation fails, install the required C++ build tools and CMake, then retry the installation. Use a Python version compatible with the available dlib build environment.

## 7. Facial Landmark Model

VIGILENS uses the pretrained dlib 68-point facial landmark predictor:

`shape_predictor_68_face_landmarks.dat`

The model is included in the supplied project archive under:

```text
VIGILENS/
└── models/
    └── shape_predictor_68_face_landmarks.dat
```

The model is required for facial landmark detection and live monitoring. Do not delete or rename this file.

## 8. Running the Application

Make sure the virtual environment is activated and all dependencies are installed.

From the project root, run:

```powershell
python main.py
```

The application will open the VIGILENS desktop interface.

The SQLite database is created automatically at:

```text
data/vigilens.db
```

The database stores local application settings, monitoring sessions, detection events, and periodic EAR samples.

## 9. Using VIGILENS

1. Open **Settings** to review the camera index and detection thresholds.
2. Select **Live Monitoring** from the sidebar.
3. Press **Start Monitoring** to initialize the webcam and facial landmark model.
4. Position your face within the camera view and ensure adequate lighting.
5. Observe the displayed facial measurements and monitoring status.
6. Press **Stop Monitoring** to end the session and save its recorded information.
7. Open **Session History** to review completed sessions and their events.
8. Open **Analytics** to review session statistics and measurement charts.

Detection thresholds are configurable starting values and are not universal measurements. They should be evaluated under controlled conditions using the intended webcam and lighting environment.

## 10. Application Pages

| Page | Description |
|---|---|
| Dashboard | Displays completed-session statistics, recorded events, camera status, and the latest completed session. |
| Live Monitoring | Displays the webcam preview, facial measurements, eye status, monitoring status, and alert controls. |
| Session History | Displays completed monitoring sessions and their recorded detection events. |
| Analytics | Presents session summaries, event statistics, and EAR trend charts. |
| Settings | Allows users to configure detection thresholds, camera index, and audio preferences. |
| About | Provides the project overview, objectives, implemented computer-vision topics, technologies, instructions, and limitations. |

## 11. Database and Session Management

VIGILENS uses SQLite for local data storage.

The database includes records for:
- Monitoring sessions.
- Detection events.
- Periodic EAR measurements.
- Application settings.

Only completed sessions are included in the completed-session statistics.

Session IDs are automatically generated by SQLite. Consequently, session IDs may not match the total number of currently stored sessions, particularly when records have been deleted. This is expected database behavior.

The database is stored locally and is not automatically synchronized with an external server.

## 12. Testing

The project includes automated tests for its supporting components.

To run the tests, execute:

```powershell
pytest -v
```

The tests cover:
- EAR calculations.
- MAR calculations.
- Drowsiness detection logic.
- Database operations.
- Session management.
- Monitoring service behavior.
- Settings validation.
- Alert service behavior.
- UI structure.

Automated tests do not replace testing with an actual webcam, the supplied facial landmark model, and real audio hardware.

## 13. Known Limitations

VIGILENS is an educational computer-vision prototype and has the following limitations:

- Detection performance may be affected by poor lighting.
- Glasses, reflections, and facial occlusion may affect landmark detection.
- Head rotation and camera positioning may reduce detection reliability.
- Webcam quality and individual facial differences may affect measurements.
- The application is designed for single-face monitoring.
- Yawning is treated as a secondary indicator and does not independently trigger a drowsiness alert.
- EAR and MAR values are visual measurements and do not establish a medical diagnosis.
- The system cannot guarantee that a driver is alert or prevent accidents.

## 14. Privacy

VIGILENS stores session summaries, detection events, application settings, and periodic EAR measurements in a local SQLite database.

The application does not intentionally save webcam video recordings or facial photographs.

Users are responsible for protecting the local project folder and database files.

## 15. Project Structure

```text
VIGILENS/
│
├── main.py
├── config.py
├── requirements.txt
├── README.md
│
├── assets/
│   └── sounds/
│       ├── alarm.wav
│       └── beep.wav
│
├── models/
│   └── shape_predictor_68_face_landmarks.dat
│
├── database/
│   ├── database.py
│   └── schema.sql
│
├── services/
│
├── vision/
│
├── ui/
│   └── app.py
│ 
├── tests/
│
└── data/
    └── vigilens.db
```

The `data/` directory and SQLite database are generated locally when the application runs for the first time.

---

**VIGILENS — Visual Monitoring for Driver Alertness**

*Educational Computer Vision Project | CSC 126*
