from functools import wraps
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from . import admin_bp
from ..models import Card, User, Scan, Deck
from .. import db
from datetime import datetime, timedelta


# ── Admin guard decorator ─────────────────────────────────────────────────────

def admin_required(f):
    """Decorator that restricts a route to admin users only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('scanner.home'))
        return f(*args, **kwargs)
    return login_required(decorated)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_required
def dashboard():
    """Overview stats for the admin."""
    total_users = User.query.filter_by(role='user').count()
    total_cards = Card.query.count()
    total_scans = Scan.query.count()
    total_decks = Deck.query.count()

    # Most scanned cards (top 5)
    popular_cards = db.session.query(
        Card, db.func.count(Scan.id).label('scan_count')
    ).join(Scan).group_by(Card.id)\
     .order_by(db.text('scan_count DESC')).limit(5).all()

    # Recent activity (last 10 scans)
    recent_scans = Scan.query.order_by(Scan.scanned_at.desc()).limit(10).all()

    # Scans per day for the last 7 days
    scan_history = []
    for i in range(6, -1, -1):
        day  = datetime.utcnow() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        count = Scan.query.filter(
            Scan.scanned_at >= day_start,
            Scan.scanned_at < day_end
        ).count()
        scan_history.append({'date': day.strftime('%a'), 'count': count})

    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_cards=total_cards,
                           total_scans=total_scans,
                           total_decks=total_decks,
                           popular_cards=popular_cards,
                           recent_scans=recent_scans,
                           scan_history=scan_history)


# ── Card Management ───────────────────────────────────────────────────────────

@admin_bp.route('/cards')
@admin_required
def manage_cards():
    """List all cards with edit/delete options."""
    cards = Card.query.order_by(Card.name).all()
    return render_template('admin/manage_cards.html', cards=cards)


@admin_bp.route('/cards/add', methods=['GET', 'POST'])
@admin_required
def add_card():
    """Add a new card to the catalogue."""
    if request.method == 'POST':
        # Validate required fields
        name           = request.form.get('name', '').strip()
        roboflow_class = request.form.get('roboflow_class', '').strip()
        set_name       = request.form.get('set_name', '').strip()

        if not all([name, roboflow_class, set_name]):
            flash('Name, Roboflow class, and Set are required.', 'danger')
            return redirect(url_for('admin.add_card'))

        if Card.query.filter_by(roboflow_class=roboflow_class).first():
            flash(f'A card with Roboflow class "{roboflow_class}" already exists.', 'danger')
            return redirect(url_for('admin.add_card'))

        card = Card(
            name           = name,
            set_name       = set_name,
            set_number     = request.form.get('set_number', '').strip() or None,
            rarity         = request.form.get('rarity', '').strip() or None,
            card_type      = request.form.get('card_type', 'Pokemon').strip(),
            hp             = request.form.get('hp', type=int),
            pokemon_type   = request.form.get('pokemon_type', '').strip() or None,
            description    = request.form.get('description', '').strip() or None,
            image_url      = request.form.get('image_url', '').strip() or None,
            market_value   = request.form.get('market_value', type=float) or 0.0,
            roboflow_class = roboflow_class,
        )
        db.session.add(card)
        db.session.commit()
        flash(f'"{name}" added to the catalogue!', 'success')
        return redirect(url_for('admin.manage_cards'))

    return render_template('admin/add_card.html')


@admin_bp.route('/cards/edit/<int:card_id>', methods=['GET', 'POST'])
@admin_required
def edit_card(card_id):
    """Edit an existing card."""
    card = Card.query.get_or_404(card_id)

    if request.method == 'POST':
        card.name          = request.form.get('name', '').strip()
        card.set_name      = request.form.get('set_name', '').strip()
        card.set_number    = request.form.get('set_number', '').strip() or None
        card.rarity        = request.form.get('rarity', '').strip() or None
        card.card_type     = request.form.get('card_type', 'Pokemon').strip()
        card.hp            = request.form.get('hp', type=int)
        card.pokemon_type  = request.form.get('pokemon_type', '').strip() or None
        card.description   = request.form.get('description', '').strip() or None
        card.image_url     = request.form.get('image_url', '').strip() or None
        card.market_value  = request.form.get('market_value', type=float) or 0.0
        card.roboflow_class = request.form.get('roboflow_class', '').strip()

        db.session.commit()
        flash(f'"{card.name}" updated!', 'success')
        return redirect(url_for('admin.manage_cards'))

    return render_template('admin/add_card.html', card=card)


@admin_bp.route('/cards/delete/<int:card_id>', methods=['POST'])
@admin_required
def delete_card(card_id):
    """Delete a card from the catalogue."""
    card = Card.query.get_or_404(card_id)
    name = card.name
    db.session.delete(card)
    db.session.commit()
    flash(f'"{name}" deleted from catalogue.', 'info')
    return redirect(url_for('admin.manage_cards'))


# ── User Management ───────────────────────────────────────────────────────────

@admin_bp.route('/users')
@admin_required
def manage_users():
    """List all registered users."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/manage_users.html', users=users)


@admin_bp.route('/users/toggle_admin/<int:user_id>', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    """Promote or demote a user's role."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You can't change your own role.", 'warning')
        return redirect(url_for('admin.manage_users'))
    user.role = 'user' if user.is_admin else 'admin'
    db.session.commit()
    flash(f'{user.username} is now {"admin" if user.is_admin else "user"}.', 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user account."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You can't delete your own account here.", 'warning')
        return redirect(url_for('admin.manage_users'))
    name = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{name}" deleted.', 'info')
    return redirect(url_for('admin.manage_users'))
