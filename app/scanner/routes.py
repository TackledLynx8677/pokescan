import requests
from flask import render_template, request, jsonify, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from . import scanner_bp
from ..models import Card, Scan, WishlistItem
from .. import db
from app import csrf

@scanner_bp.route('/')
@login_required
def home():
    """Main scanner page with camera feed."""
    # Pass card count so the template can show a stat
    total_cards = Card.query.count()
    user_scans  = len({s.card_id for s in current_user.scans})
    return render_template('scanner/scan.html',
                           total_cards=total_cards,
                           user_scans=user_scans)

@csrf.exempt
@scanner_bp.route('/detect', methods=['POST'])
@login_required
def detect():
    """
    Receives a base64 JPEG from the browser, forwards it to Roboflow,
    parses the predictions, and returns JSON with card details.
    """
    data = request.get_json(silent=True)
    if not data or 'image' not in data:
        return jsonify({'success': False, 'message': 'No image received.'}), 400

    image_b64 = data['image']

    # ── Call Roboflow inference API ────────────────────────────────────────────
    try:
        rf_response = requests.post(
            current_app.config['ROBOFLOW_MODEL_URL'],
            params={'api_key': current_app.config['ROBOFLOW_API_KEY']},
            data=image_b64,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10
        )
        rf_response.raise_for_status()
        predictions = rf_response.json().get('predictions', [])
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'message': 'Detection service timed out. Try again.'}), 503
    except Exception as e:
        current_app.logger.error(f'Roboflow error: {e}')
        return jsonify({'success': False, 'message': 'Detection service error.'}), 503

    # ── No detections at all ───────────────────────────────────────────────────
    if not predictions:
        return jsonify({
            'success': False,
            'message': 'No card detected — make sure the card fills the frame.',
            'tip': 'Try better lighting or hold the card steady.'
        })

    # ── Filter by confidence threshold ────────────────────────────────────────
    threshold = current_app.config['CONFIDENCE_THRESHOLD']
    confident  = [p for p in predictions if p['confidence'] >= threshold]

    if not confident:
        best = max(predictions, key=lambda p: p['confidence'])
        return jsonify({
            'success': False,
            'message': f"Card detected but confidence too low ({round(best['confidence'] * 100)}%). Try better lighting.",
            'confidence': best['confidence'],
            'tip': 'Hold the card flat, avoid glare, and ensure good lighting.'
        })

    # ── Build results for all high-confidence detections ──────────────────────
    results = []
    for pred in confident:
        card = Card.query.filter_by(roboflow_class=pred['class']).first()
        if not card:
            continue  # Card exists in model but not in DB — skip

        # Check if user already owns this card
        already_owned = any(s.card_id == card.id for s in current_user.scans)

        # Check if card is on user's wishlist — remove it if so
        wishlist_item = WishlistItem.query.filter_by(
            user_id=current_user.id, card_id=card.id
        ).first()
        wishlist_cleared = False
        if wishlist_item:
            db.session.delete(wishlist_item)
            wishlist_cleared = True

        # Log the scan
        scan = Scan(
            user_id=current_user.id,
            card_id=card.id,
            confidence=pred['confidence']
        )
        db.session.add(scan)

        results.append({
            'card': {
                'id':           card.id,
                'name':         card.name,
                'set_name':     card.set_name,
                'set_number':   card.set_number,
                'rarity':       card.rarity,
                'card_type':    card.card_type,
                'hp':           card.hp,
                'pokemon_type': card.pokemon_type,
                'description':  card.description,
                'image_url':    card.image_url,
                'market_value': card.market_value,
                'rarity_class': card.rarity_colour,
            },
            'confidence':      round(pred['confidence'] * 100, 1),
            'already_owned':   already_owned,
            'wishlist_cleared': wishlist_cleared,
            # Bounding box for canvas overlay (Roboflow gives centre x,y)
            'bbox': {
                'x':      pred['x'],
                'y':      pred['y'],
                'width':  pred['width'],
                'height': pred['height'],
            }
        })

    if not results:
        return jsonify({
            'success': False,
            'message': 'Card detected but not found in database. Ask your admin to add it!'
        })

    db.session.commit()
    return jsonify({'success': True, 'detections': results})


@scanner_bp.route('/add_to_deck/<int:card_id>', methods=['POST'])
@login_required
def quick_add_wishlist(card_id):
    """Add a just-scanned card to the wishlist from the scan result page."""
    card = Card.query.get_or_404(card_id)
    existing = WishlistItem.query.filter_by(
        user_id=current_user.id, card_id=card_id
    ).first()

    if existing:
        return jsonify({'success': False, 'message': 'Already on your wishlist.'})

    item = WishlistItem(user_id=current_user.id, card_id=card_id)
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'message': f'{card.name} added to wishlist!'})
