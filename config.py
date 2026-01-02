import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Flask secret key (use env var in production)
    SECRET_KEY = 'face-attendance-2025'

    # MongoDB configuration (used by Flask-PyMongo in app.py)
    # Local Mongo instance:
    MONGO_URI = 'mongodb://localhost:27017/face_attendance'
    # If you later use Atlas, replace with:
    # MONGO_URI = 'mongodb+srv://<user>:<password>@<cluster>/<db>?retryWrites=true&w=majority'

    # Legacy SQLAlchemy settings removed (no SQLite)
    # SQLALCHEMY_DATABASE_URI = ...
    # SQLALCHEMY_TRACK_MODIFICATIONS = ...

# paths for dataset and models
DATASET_DIR = os.path.join(BASE_DIR, 'dataset')
MODELS_DIR = os.path.join(BASE_DIR, 'models_store')

os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)
