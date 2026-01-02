import os
import cv2
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, 'dataset')
HAAR_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'

# Thread-local storage for progress (avoids global race conditions)
local = threading.local()

def capture_faces(student_id, max_images=100):
    """
    Thread-safe, Windows-safe face capture.
    Saves up to max_images face ROIs to dataset/<student_id>/.
    student_id: MongoDB ObjectId string.
    Returns: number of images captured.
    """
    os.makedirs(DATASET_DIR, exist_ok=True)

    # Ensure string folder name
    student_id_str = str(student_id)
    student_folder = os.path.join(DATASET_DIR, student_id_str)
    os.makedirs(student_folder, exist_ok=True)

    print(f"🚀 Starting face capture: {student_id_str} -> {student_folder}")

    progress = {'count': 0, 'max': max_images, 'done': False, 'error': None}

    def capture_worker():
        cap = None
        try:
            cascade = cv2.CascadeClassifier(HAAR_PATH)
            if cascade.empty():
                progress['error'] = 'Haar cascade load failed'
                return

            # Camera retry logic
            for attempt in range(3):
                cap = cv2.VideoCapture(0)
                if cap.isOpened():
                    break
                time.sleep(0.5)
                print(f"Camera attempt {attempt + 1}/3")

            if not cap or not cap.isOpened():
                progress['error'] = 'Camera access failed after retries'
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FPS, 30)

            count = 0
            print(f"📸 Window open: Capture {max_images} faces (q=quit)")

            while count < max_images:
                ret, frame = cap.read()
                if not ret:
                    print("Frame read failed")
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, 1.1, 5, 0, (60, 60))

                # Save first face detected
                if len(faces) > 0:
                    x, y, w, h = faces[0]
                    roi = gray[y:y + h, x:x + w]
                    roi = cv2.resize(roi, (200, 200))
                    roi = cv2.equalizeHist(roi)

                    img_path = os.path.join(student_folder, f'{count + 1:03d}.jpg')
                    if cv2.imwrite(img_path, roi):
                        count += 1
                        progress['count'] = count
                        print(f"💾 {count}/{max_images}: {os.path.basename(img_path)}")

                # Draw UI
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                cv2.putText(frame, f'{progress["count"]}/{max_images}', (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(frame, f'ID: {student_id_str[:8]}...', (10, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                cv2.putText(frame, 'q=QUIT', (10, frame.shape[0] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                cv2.imshow(f'Capture {student_id_str[:8]}...', frame)

                key = cv2.waitKey(33) & 0xFF
                if key == ord('q'):
                    print("🛑 Manual quit")
                    break

        except Exception as e:
            progress['error'] = str(e)
            print(f"❌ Capture error: {e}")
        finally:
            if cap:
                cap.release()
            cv2.destroyAllWindows()
            progress['count'] = locals().get('count', 0)
            progress['done'] = True
            print(f"✅ Capture done: {progress['count']} images")

    thread = threading.Thread(target=capture_worker, daemon=True)
    thread.start()
    thread.join(timeout=150)

    if progress['error']:
        print(f"⚠️ Error: {progress['error']}")
        return 0

    print(f"🎉 SUCCESS: {progress['count']}/{max_images} faces captured")
    return progress['count']

def get_capture_progress(student_id):
    """Frontend polling: return current image count."""
    student_folder = os.path.join(DATASET_DIR, str(student_id))
    if os.path.exists(student_folder):
        return len([f for f in os.listdir(student_folder) if f.lower().endswith('.jpg')])
    return 0
