import os

class Config:
    # Secret key for session signing — change this on PythonAnywhere!
    SECRET_KEY = os.environ.get('SECRET_KEY', 'pokescan-dev-secret-change-in-production')

    # SQLite database in the project root
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, '..', 'pokescan.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Roboflow settings — fill these in after training your model
    ROBOFLOW_API_KEY = os.environ.get('ROBOFLOW_API_KEY', 'cRnarCQGpPy4OAxfv9wY')
    ROBOFLOW_MODEL_URL = os.environ.get(
        'ROBOFLOW_MODEL_URL',
        'https://detect.roboflow.com/pokemon-tcg-scanner/1'
    )

    # Confidence threshold — detections below this are rejected
    CONFIDENCE_THRESHOLD = 0.72

    # Max cards allowed in a single deck
    MAX_DECK_SIZE = 60
    MAX_COPIES_PER_CARD = 4
