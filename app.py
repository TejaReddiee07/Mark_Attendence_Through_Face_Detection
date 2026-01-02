from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
from flask_pymongo import PyMongo
from bson import ObjectId
from werkzeug.exceptions import NotFound
import signal
import sys
from datetime import datetime, timedelta
from config import Config  # Keep for other settings if needed

# Camera & Face recognition
from camera import capture_faces
from face_service import train_model, recognize_and_mark_attendance, set_mongo_client

app = Flask(__name__)
app.secret_key = 'face-attendance-2025'  # Required for sessions
app.config.from_object(Config)
app.config["MONGO_URI"] = "mongodb://localhost:27017/face_attendance"  # Local MongoDB

mongo = PyMongo(app)

# Initialize face service
set_mongo_client(mongo.db)

# Graceful shutdown handler
def signal_handler(sig, frame):
    print("\n🛑 Shutting down cleanly...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ---------- DB Initialization ----------
with app.app_context():
    # Indexes for performance
    mongo.db.students.create_index("email", unique=True)
    mongo.db.students.create_index("admission_no", unique=True)
    mongo.db.attendance.create_index("timestamp")

    # Default admin
    admin = mongo.db.students.find_one({"email": "nagatejareddygoli@gmail.com"})
    if not admin:
        mongo.db.students.insert_one({
            "name": "Admin",
            "admission_no": "ADM-0000",
            "phone": "",
            "branch": "Admin",
            "specialization": "System",
            "degree_type": "Staff",
            "email": "nagatejareddygoli@gmail.com",
            "department": "Admin",
            "semester": "N/A",
            "face_enrolled": False
        })
        print("👤 Admin user created")

# ---------- Authentication ----------
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        if email == 'nagatejareddygoli@gmail.com' and password == '@Nagateja07':
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        error = 'Invalid credentials.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------- Dashboard ----------
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    total_students = mongo.db.students.count_documents({
        "email": {"$ne": "nagatejareddygoli@gmail.com"}
    })
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())
    today_attendance = mongo.db.attendance.count_documents({
        "timestamp": {"$gte": today_start}
    })

    return render_template(
        'dashboard.html',
        total_students=total_students,
        today_attendance=today_attendance
    )

# ---------- Students Management ----------
@app.route('/students', methods=['GET', 'POST'])
def students_page():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    error = None

    if request.method == 'POST':
        data = {
            "name": request.form.get('name', '').strip(),
            "admission_no": request.form.get('admission_no', '').strip(),
            "phone": request.form.get('phone', '').strip(),
            "branch": request.form.get('branch', 'CSE').strip(),
            "degree_type": request.form.get('degree_type', '').strip(),
            "semester": request.form.get('sem', '').strip(),
            "email": request.form.get('email', '').strip(),
            "department": request.form.get('branch', 'CSE').strip(),
            "specialization": None,
            "face_enrolled": False
        }

        if data["name"] and data["admission_no"] and data["email"]:
            existing_email = mongo.db.students.find_one({"email": data["email"]})
            existing_adm = mongo.db.students.find_one({"admission_no": data["admission_no"]})

            if existing_email:
                error = "Email already exists. Use a different email."
            elif existing_adm:
                error = "Admission number already exists."
            else:
                mongo.db.students.insert_one(data)
                return redirect(url_for('students_page', branch=data["branch"] or 'CSE'))
        else:
            error = "Name, admission number, and email are required."

    branch_filter = request.args.get('branch', 'CSE').upper()
    students = list(
        mongo.db.students.find({
            "email": {"$ne": "nagatejareddygoli@gmail.com"},
            "branch": {"$regex": branch_filter, "$options": "i"}
        }).sort("name", 1)
    )

    # Sort by last 3 digits of admission number (smallest to highest)
    students.sort(key=lambda s: int(s.get('admission_no', '0')[-3:]) if s.get('admission_no') and s.get('admission_no')[-3:].isdigit() else 999)

    return render_template(
        'students.html',
        students=students,
        current_branch=branch_filter,
        error=error
    )


@app.route('/students/<student_id>/edit', methods=['GET', 'POST'])
def edit_student(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        student = mongo.db.students.find_one({"_id": ObjectId(student_id)})
    except Exception:
        return NotFound("Invalid student")

    if not student or student["email"] == 'nagatejareddygoli@gmail.com':
        return redirect(url_for('students_page'))

    if request.method == 'POST':
        update_data = {
            "name": request.form.get('name', student['name']).strip(),
            "admission_no": request.form.get('admission_no', student['admission_no']).strip(),
            "phone": request.form.get('phone', student.get('phone', '')).strip(),
            "branch": request.form.get('branch', student['branch']).strip(),
            "degree_type": request.form.get('degree_type', student.get('degree_type', '')).strip(),
            "semester": request.form.get('sem', student.get('semester', '')).strip(),
            "email": request.form.get('email', student['email']).strip(),
            "department": request.form.get('branch', student['branch']).strip()
        }
        mongo.db.students.update_one({"_id": student["_id"]}, {"$set": update_data})
        return redirect(url_for('students_page', branch=update_data["branch"]))

    return render_template('edit_student.html', student=student)

@app.route('/students/<student_id>/delete', methods=['POST'])
def delete_student(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        student = mongo.db.students.find_one({"_id": ObjectId(student_id)})
        if student and student["email"] != 'nagatejareddygoli@gmail.com':
            mongo.db.students.delete_one({"_id": student["_id"]})
    except Exception:
        pass

    branch = request.args.get('branch', 'CSE')
    return redirect(url_for('students_page', branch=branch))

# ---------- Face Enrollment ----------
@app.route('/enroll/<student_id>')
def enroll(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        student = mongo.db.students.find_one({"_id": ObjectId(student_id)})
    except Exception:
        return NotFound("Invalid student ID")

    if not student or student["email"] == 'nagatejareddygoli@gmail.com':
        return redirect(url_for('students_page'))

    return render_template('enroll.html', student=student)

@app.route('/enroll/capture/<student_id>', methods=['POST'])
def enroll_capture(student_id):
    if not session.get('logged_in'):
        return jsonify({'success': False, 'msg': 'Not logged in'}), 401

    try:
        captured = capture_faces(student_id, max_images=100)

        if captured == 0:
            return jsonify({
                'success': False,
                'msg': 'No faces captured. Check camera and lighting.'
            })

        ok = train_model()
        if not ok:
            msg = (f'{captured} images saved, but model training is not available '
                   f'(cv2.face missing or no dataset).')
        else:
            msg = f'Enrollment complete. {captured} images captured and model updated.'

        mongo.db.students.update_one(
            {"_id": ObjectId(student_id)},
            {"$set": {"face_enrolled": True}}
        )

        return jsonify({'success': True, 'msg': msg})

    except Exception as e:
        print("Enroll error:", e)
        return jsonify({
            'success': False,
            'msg': f'Server error during enrollment: {str(e)}'
        }), 500

# ---------- Attendance ----------
from datetime import datetime, timedelta

# Update the take_attendance route to check time slots
@app.route('/take-attendance', methods=['POST'])
def take_attendance():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'msg': 'Not logged in'}), 401

    try:
        ok, msg = recognize_and_mark_attendance()
        return jsonify({'success': ok, 'msg': msg})
    except Exception as e:
        print(f"Attendance error: {e}")
        return jsonify({'success': False, 'msg': f'Error: {e}'}), 500


# Add new route to get time slot info
@app.route('/api/current-session')
def current_session():
    """Return current time slot: AM (9-13) or PM (14-16)"""
    now = datetime.now()
    hour = now.hour
    
    if 9 <= hour < 13:
        return jsonify({'session': 'AM', 'start': 9, 'end': 13})
    elif 14 <= hour < 16:
        return jsonify({'session': 'PM', 'start': 14, 'end': 16})
    else:
        return jsonify({'session': 'CLOSED', 'msg': 'Attendance slots are 9 AM-1 PM and 2 PM-4 PM only'})


from datetime import datetime, timedelta

@app.route('/attendance')
def attendance_page():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    branch_filter = request.args.get('branch', 'CSE').upper()
    pipeline = [
        {"$lookup": {
            "from": "students",
            "localField": "student_id",
            "foreignField": "_id",
            "as": "student"
        }},
        {"$unwind": "$student"},
        {"$match": {
            "student.email": {"$ne": "nagatejareddygoli@gmail.com"},
            "student.branch": {"$regex": branch_filter, "$options": "i"}
        }},
        {"$sort": {"timestamp": -1}},
        {"$limit": 100}
    ]
    records = list(mongo.db.attendance.aggregate(pipeline))

    # Convert UTC timestamps to IST (UTC+5:30)
    ist_offset = timedelta(hours=5, minutes=30)
    for rec in records:
        if rec.get('timestamp'):
            rec['timestamp'] = rec['timestamp'] + ist_offset

    return render_template('attendance.html', records=records, current_branch=branch_filter)


@app.route('/attendance/<attendance_id>/delete', methods=['POST'])
def delete_attendance(attendance_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    mongo.db.attendance.delete_one({"_id": ObjectId(attendance_id)})
    branch = request.args.get('branch', 'CSE')
    return redirect(url_for('attendance_page', branch=branch))


# ---------- Reports (stub) ----------
@app.route('/reports')
def reports():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('reports.html')

if __name__ == '__main__':
    print("🚀 AI Face Attendance System")
    print("📱 http://localhost:5000")
    app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)
