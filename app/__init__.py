from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from .config import Config
from flask_wtf.csrf import CSRFProtect


# Extensions — instantiated here, initialised in create_app()
db           = SQLAlchemy()
login_manager = LoginManager()
bcrypt       = Bcrypt()
csrf          = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    csrf.init_app(app)

    # Initialise extensions with the app
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access PokéScan.'
    login_manager.login_message_category = 'warning'

    # User loader for Flask-Login
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from .auth.routes      import auth_bp
    from .scanner.routes   import scanner_bp
    from .collection.routes import collection_bp
    from .admin.routes     import admin_bp
    from .profile.routes import profile_bp
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(auth_bp,       url_prefix='/auth')
    app.register_blueprint(scanner_bp,    url_prefix='/scanner')
    app.register_blueprint(collection_bp, url_prefix='/collection')
    app.register_blueprint(admin_bp,      url_prefix='/admin')

    # Root redirect
    from flask import redirect, url_for

    @app.route('/')
    def index():
        return redirect(url_for('scanner.home'))

    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
        _seed_admin()

    return app


def _seed_admin():
    """Create a default admin account on first run if none exists."""
    from .models import User
    from . import bcrypt

    if not User.query.filter_by(role='admin').first():
        admin = User(
            username='admin',
            email='admin@pokescan.local',
            role='admin'
        )
        admin.set_password('admin1234')
        db.session.add(admin)
        db.session.commit()
        print('[PokéScan] Default admin created: admin / admin1234')
