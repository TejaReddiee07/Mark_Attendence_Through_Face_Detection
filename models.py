from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    admission_no = db.Column(db.String(50), nullable=False, unique=True)
    phone = db.Column(db.String(20))
    branch = db.Column(db.String(50))          # CSE, AIML, AIDS, ECE, MECH
    specialization = db.Column(db.String(100))
    degree_type = db.Column(db.String(50))
    department = db.Column(db.String(50))
    semester = db.Column(db.String(20))
    email = db.Column(db.String(120), unique=True, nullable=False)
    face_enrolled = db.Column(db.Boolean, default=False)

    attendances = db.relationship(
        'Attendance',
        backref='student',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Student {self.id} {self.name}>'


class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id'),
        nullable=False
    )
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='PRESENT')

    def __repr__(self):
        return f'<Attendance {self.id} student={self.student_id} status={self.status}>'
