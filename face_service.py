import os
from datetime import datetime, timedelta
from bson import ObjectId

import cv2
import numpy as np

# Global Mongo client; set from app.py with set_mongo_client(mongo.db)
mongo_client = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, 'dataset')
MODEL_PATH = os.path.join(BASE_DIR, 'face_model.yml')
HAAR_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'


def set_mongo_client(db_client):
    """Call from app.py: set_mongo_client(mongo.db)."""
    global mongo_client
    mongo_client = db_client


def _load_face_detector():
    if not os.path.exists(HAAR_PATH):
        raise RuntimeError('Haarcascade file not found at ' + HAAR_PATH)
    return cv2.CascadeClassifier(HAAR_PATH)


def _create_recognizer():
    """
    Create an LBPH recognizer.
    Requires opencv-contrib-python so that cv2.face exists.
    """
    if not hasattr(cv2, "face") or not hasattr(cv2.face, "LBPHFaceRecognizer_create"):
        print("⚠️ cv2.face.LBPHFaceRecognizer_create not available. "
              "Install opencv-contrib-python.")
        return None
    return cv2.face.LBPHFaceRecognizer_create()


def _load_recognizer():
    """
    Load trained model if it exists, otherwise return None.
    """
    recognizer = _create_recognizer()
    if recognizer is None:
        return None
    if not os.path.exists(MODEL_PATH):
        return None
    recognizer.read(MODEL_PATH)
    return recognizer


def train_model():
    """
    Train LBPH recognizer on images in dataset/<student_id>/.
    Each folder name is a MongoDB _id string of the student.
    """
    recognizer = _create_recognizer()
    if recognizer is None:
        return False

    if not os.path.isdir(DATASET_DIR):
        print("📂 Dataset folder not found, nothing to train.")
        return False

    face_cascade = _load_face_detector()

    faces = []
    labels = []

    # Map ObjectId string -> int label (LBPH needs int labels)
    id_to_label = {}
    label_to_id = {}
    current_label = 0

    for student_id_dir in os.listdir(DATASET_DIR):
        student_path = os.path.join(DATASET_DIR, student_id_dir)
        if not os.path.isdir(student_path):
            continue

        sid_str = str(student_id_dir)

        if sid_str not in id_to_label:
            id_to_label[sid_str] = current_label
            label_to_id[current_label] = sid_str
            current_label += 1

        label_int = id_to_label[sid_str]

        for img_name in os.listdir(student_path):
            if not img_name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            img_path = os.path.join(student_path, img_name)
            img = cv2.imread(img_path)
            if img is None:
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            detected = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60)
            )
            for (x, y, w, h) in detected:
                roi = gray[y:y + h, x:x + w]
                roi = cv2.resize(roi, (200, 200))
                roi = cv2.equalizeHist(roi)
                faces.append(roi)
                labels.append(label_int)

    if len(faces) == 0:
        print("❌ No faces found in dataset, cannot train.")
        return False

    faces_np = np.array(faces, dtype=np.uint8)
    labels_np = np.array(labels, dtype=np.int32)

    recognizer.train(faces_np, labels_np)
    recognizer.write(MODEL_PATH)
    print(f"✅ Model trained with {len(faces)} samples for {len(id_to_label)} students.")
    return True


def recognize_and_mark_attendance():
    """
    Fast attendance with time slot checking:
    - AM: 9:00-12:59 IST
    - PM: 14:00-15:59 IST
    - Mark attendance only ONCE per session per student
    - Store all records with timestamp for export
    """
    if mongo_client is None:
        return False, "MongoDB not initialized. Call set_mongo_client(mongo.db) first."

    # Get current IST time (UTC+5:30)
    utc_now = datetime.utcnow()
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    ist_hour = ist_now.hour
    ist_date = ist_now.date()

    # Determine session
    if 9 <= ist_hour < 13:
        current_session = 'AM'
        session_start_ist = ist_now.replace(hour=9, minute=0, second=0, microsecond=0)
        session_end_ist = ist_now.replace(hour=13, minute=0, second=0, microsecond=0)
    elif 14 <= ist_hour < 16:
        current_session = 'PM'
        session_start_ist = ist_now.replace(hour=14, minute=0, second=0, microsecond=0)
        session_end_ist = ist_now.replace(hour=16, minute=0, second=0, microsecond=0)
    else:
        return False, f'❌ Attendance closed. Open slots: 9 AM-1 PM (AM) and 2 PM-4 PM (PM). Current IST time: {ist_now.strftime("%H:%M")}'

    # Convert session times back to UTC for MongoDB query
    session_start_utc = session_start_ist - timedelta(hours=5, minutes=30)
    session_end_utc = session_end_ist - timedelta(hours=5, minutes=30)

    recognizer = _load_recognizer()
    if recognizer is None:
        return False, "Face model is not trained yet. Enroll students and train first."

    face_cascade = _load_face_detector()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return False, "Cannot access camera."

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    recognized_labels = set()
    start_time = datetime.now()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(60, 60)
            )

            for (x, y, w, h) in faces:
                roi = gray[y:y + h, x:x + w]
                roi = cv2.resize(roi, (200, 200))
                roi = cv2.equalizeHist(roi)

                label_int, conf = recognizer.predict(roi)
                print("Predicted label:", label_int, "conf:", conf)

                if conf < 75:
                    recognized_labels.add(label_int)
                    color = (0, 255, 0)
                    text = f"ID {label_int}"
                else:
                    color = (0, 0, 255)
                    text = "Unknown"

                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(
                    frame, text, (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                )

            cv2.imshow("Attendance (fast)", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if (datetime.now() - start_time).total_seconds() > 0.7:
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not recognized_labels:
        return False, "No known faces recognized. Attendance not marked."

    # Rebuild label to ID mapping
    label_to_id = {}
    current_label = 0
    for student_id_dir in os.listdir(DATASET_DIR):
        student_path = os.path.join(DATASET_DIR, student_id_dir)
        if not os.path.isdir(student_path):
            continue
        label_to_id[current_label] = str(student_id_dir)
        current_label += 1

    try:
        count = 0
        marked_names = []
        already_marked = []

        for label_int in recognized_labels:
            sid_str = label_to_id.get(label_int)
            if not sid_str:
                print("No mapping for label:", label_int)
                continue

            try:
                student = mongo_client.students.find_one({"_id": ObjectId(sid_str)})
            except Exception as e:
                print("Invalid ObjectId from label:", sid_str, e)
                continue

            if not student:
                print("No student found for id:", sid_str)
                continue

            # CRITICAL: Check if already marked in THIS session (UTC time range)
            existing = mongo_client.attendance.find_one({
                "student_id": student["_id"],
                "timestamp": {
                    "$gte": session_start_utc,
                    "$lt": session_end_utc
                },
                "session": current_session
            })

            if existing:
                print(f"Already marked in {current_session} session for {student['name']}")
                already_marked.append(f"{student['name']} ({current_session})")
                continue

            # Insert attendance record with UTC timestamp (for storage/export)
            mongo_client.attendance.insert_one({
                "student_id": student["_id"],
                "timestamp": utc_now,  # Store UTC for consistency
                "status": "PRESENT",
                "session": current_session,
                "date": ist_date.isoformat()  # Convert date to ISO string format
            })

            count += 1
            marked_names.append(student["name"])

        if count == 0 and already_marked:
            return False, f"✅ Already marked: {', '.join(already_marked)}"
        elif count == 0:
            return False, "No valid students found or all already marked."

        msg = f"✅ {current_session} Session ({ist_now.strftime('%d-%m-%Y %H:%M')}): {count} marked - {', '.join(marked_names)}"
        return True, msg

    except Exception as e:
        print("Error saving attendance:", e)
        return False, f"Error saving attendance: {e}"
