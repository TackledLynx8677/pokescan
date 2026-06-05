from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from . import collection_bp
from ..models import Card, Scan, Deck, DeckCard, WishlistItem, User, DeckRating
from .. import db
from ..config import Config
from .. import csrf
from datetime import timedelta




# ── Library ────

@collection_bp.route('/library')
@login_required
def library():
    """
    Shows all unique cards the user has ever scanned,
    along with scan count per card and total value.
    """
    # Get unique scanned card IDs with their scan count
    scanned = {}
    for scan in current_user.scans:
        scanned[scan.card_id] = scanned.get(scan.card_id, 0) + 1

    cards = []
    for card_id, count in scanned.items():
        card = Card.query.get(card_id)
        if card:
            cards.append({'card': card, 'scan_count': count})

    # Sort by most recently scanned
    cards.sort(key=lambda x: x['card'].id, reverse=True)

    return render_template('collection/library.html',
                           cards=cards,
                           total_value=current_user.collection_value)


# ── Leaderboard ─────────

@collection_bp.route('/leaderboard')
@login_required
def leaderboard():
    """Shows all users ranked by collection value."""
    users = User.query.filter_by(role='user').all()
    ranked = sorted(users, key=lambda u: u.collection_value, reverse=True)
    return render_template('collection/leaderboard.html', users=ranked)


# ── Decks ─────

@collection_bp.route('/decks')
@login_required
def decks():
    """List all user's decks."""
    return render_template('collection/decks.html', decks=current_user.decks)


@collection_bp.route('/decks/new', methods=['GET', 'POST'])
@login_required
def new_deck():
    """Create a new empty deck."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        desc = request.form.get('description', '').strip()
        if not name:
            flash('Deck name is required.', 'danger')
            return redirect(url_for('collection.new_deck'))

        deck = Deck(user_id=current_user.id, name=name, description=desc)
        db.session.add(deck)
        db.session.commit()
        flash(f'"{name}" deck created!', 'success')
        return redirect(url_for('collection.deck_detail', deck_id=deck.id))

    return render_template('collection/new_deck.html')


@collection_bp.route('/decks/<int:deck_id>')
@login_required
def deck_detail(deck_id):
    """View a deck's contents."""
    deck = Deck.query.get_or_404(deck_id)
    # Only owner can view their own deck
    if deck.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('collection.decks'))

    # Cards the user has scanned (available to add)
    scanned_ids = {s.card_id for s in current_user.scans}
    available   = Card.query.filter(Card.id.in_(scanned_ids)).all()

    return render_template('collection/deck_detail.html',
                           deck=deck,
                           available_cards=available,
                           max_deck=Config.MAX_DECK_SIZE,
                           max_copies=Config.MAX_COPIES_PER_CARD)

@csrf.exempt
@collection_bp.route('/decks/<int:deck_id>/add', methods=['POST'])
@login_required
def add_to_deck(deck_id):
    """Add a card to a deck (AJAX)."""
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied.'}), 403

    card_id = request.json.get('card_id')
    card    = Card.query.get_or_404(card_id)

    # Check deck size
    if deck.total_cards >= Config.MAX_DECK_SIZE:
        return jsonify({'success': False,
                        'message': f'Deck is full ({Config.MAX_DECK_SIZE} card limit).'})

    # Check per-card limit
    existing = DeckCard.query.filter_by(deck_id=deck_id, card_id=card_id).first()
    if existing:
        if existing.quantity >= Config.MAX_COPIES_PER_CARD:
            return jsonify({'success': False,
                            'message': f'Max {Config.MAX_COPIES_PER_CARD} copies of any card allowed.'})
        existing.quantity += 1
    else:
        db.session.add(DeckCard(deck_id=deck_id, card_id=card_id, quantity=1))

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'{card.name} added to {deck.name}!',
        'total_cards': deck.total_cards,
        'total_value': deck.total_value
    })


@csrf.exempt
@collection_bp.route('/decks/<int:deck_id>/remove', methods=['POST'])
@login_required
def remove_from_deck(deck_id):
    """Remove one copy of a card from a deck (AJAX)."""
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied.'}), 403

    card_id  = request.json.get('card_id')
    existing = DeckCard.query.filter_by(deck_id=deck_id, card_id=card_id).first()

    if not existing:
        return jsonify({'success': False, 'message': 'Card not in deck.'})

    if existing.quantity > 1:
        existing.quantity -= 1
    else:
        db.session.delete(existing)

    db.session.commit()
    return jsonify({'success': True, 'total_cards': deck.total_cards, 'total_value': deck.total_value})


@collection_bp.route('/decks/<int:deck_id>/delete', methods=['POST'])
@login_required
def delete_deck(deck_id):
    """Delete an entire deck."""
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('collection.decks'))

    db.session.delete(deck)
    db.session.commit()
    flash(f'"{deck.name}" deleted.', 'info')
    return redirect(url_for('collection.decks'))


# ── Wishlist ───────────

@collection_bp.route('/wishlist')
@login_required
def wishlist():
    """Show user's wishlist."""
    items = WishlistItem.query.filter_by(user_id=current_user.id)\
                              .order_by(WishlistItem.added_at.desc()).all()
    # All cards not yet in their wishlist and not already scanned
    scanned_ids  = {s.card_id for s in current_user.scans}
    wishlist_ids = {w.card_id for w in items}
    available    = Card.query.filter(
        ~Card.id.in_(wishlist_ids | scanned_ids)
    ).all()

    return render_template('collection/wishlist.html',
                           items=items,
                           available_cards=available)


@collection_bp.route('/wishlist/add', methods=['POST'])
@login_required
def add_to_wishlist():
    """Add a card to the wishlist."""
    card_id = request.form.get('card_id', type=int)
    card    = Card.query.get_or_404(card_id)

    existing = WishlistItem.query.filter_by(
        user_id=current_user.id, card_id=card_id
    ).first()

    if existing:
        flash(f'{card.name} is already on your wishlist.', 'warning')
    else:
        db.session.add(WishlistItem(user_id=current_user.id, card_id=card_id))
        db.session.commit()
        flash(f'{card.name} added to wishlist!', 'success')

    return redirect(url_for('collection.wishlist'))


@collection_bp.route('/wishlist/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_wishlist(item_id):
    """Remove from wishlist."""
    item = WishlistItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('collection.wishlist'))

    db.session.delete(item)
    db.session.commit()
    flash('Removed from wishlist.', 'info')
    return redirect(url_for('collection.wishlist'))


@collection_bp.route('/history')
@login_required
def scan_history():
    """Full scan history with timestamps for the current user."""
    from datetime import timedelta
    scans = Scan.query.filter_by(user_id=current_user.id)\
                      .order_by(Scan.scanned_at.desc()).all()
    return render_template('collection/scan_history.html',
                           scans=scans,
                           timedelta=timedelta)

@collection_bp.route('/search')
@login_required
def search_users():
    """Search for other users by username."""
    query = request.args.get('q', '').strip()
    results = []
 
    # All non-admin users for the default view
    all_users = User.query.filter_by(role='user').order_by(User.username).all()
 
    if query:
        results = User.query.filter(
            User.username.ilike(f'%{query}%'),
            User.role == 'user'
        ).all()
 
    return render_template('collection/search_users.html',
                           query=query,
                           results=results,
                           all_users=all_users)


@collection_bp.route('/decks/public')
@login_required
def public_decks():
    """Browse all public decks from all users."""
    public_decks = Deck.query.filter_by(is_public=True)\
                             .order_by(Deck.created_at.desc()).all()
    return render_template('collection/public_decks.html', public_decks=public_decks)
 
 
@collection_bp.route('/decks/public/<int:deck_id>')
@login_required
def view_public_deck(deck_id):
    """View a single public deck with ratings."""
    deck = Deck.query.get_or_404(deck_id)
    if not deck.is_public and deck.user_id != current_user.id:
        flash('This deck is private.', 'warning')
        return redirect(url_for('collection.public_decks'))
 
    # Get current user's existing rating if any
    user_rating = DeckRating.query.filter_by(
        deck_id=deck_id,
        user_id=current_user.id
    ).first()
 
    return render_template('collection/view_public_deck.html',
                           deck=deck,
                           user_rating=user_rating)
 
 
@collection_bp.route('/decks/<int:deck_id>/toggle_public', methods=['POST'])
@login_required
def toggle_deck_public(deck_id):
    """Toggle a deck between public and private."""
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('collection.decks'))
 
    deck.is_public = not deck.is_public
    db.session.commit()
    status = 'public' if deck.is_public else 'private'
    flash(f'"{deck.name}" is now {status}!', 'success')
    return redirect(url_for('collection.deck_detail', deck_id=deck_id))
 


@collection_bp.route('/decks/<int:deck_id>/rate', methods=['POST'])
@login_required
@csrf.exempt
def rate_deck(deck_id):
    """Rate a public deck 1-5 stars."""
    deck = Deck.query.get_or_404(deck_id)
 
    if not deck.is_public:
        return jsonify({'success': False, 'message': 'Deck is not public.'})
 
    if deck.user_id == current_user.id:
        return jsonify({'success': False, 'message': "You can't rate your own deck."})
 
    rating_val = request.json.get('rating', type=int)
    if not rating_val or rating_val < 1 or rating_val > 5:
        return jsonify({'success': False, 'message': 'Rating must be between 1 and 5.'})
 
    # Update existing rating or create new one
    existing = DeckRating.query.filter_by(
        deck_id=deck_id, user_id=current_user.id
    ).first()
 
    if existing:
        existing.rating = rating_val
    else:
        db.session.add(DeckRating(
            deck_id=deck_id,
            user_id=current_user.id,
            rating=rating_val
        ))
 
    db.session.commit()
    return jsonify({
        'success':        True,
        'message':        f'Rated {rating_val} stars!',
        'average_rating': deck.average_rating,
        'rating_count':   deck.rating_count
    })
 
 
@collection_bp.route('/decks/<int:deck_id>/copy', methods=['POST'])
@login_required
def copy_deck(deck_id):
    """Copy a public deck into the current user's collection."""
    original = Deck.query.get_or_404(deck_id)
 
    if not original.is_public:
        flash('This deck is not public.', 'warning')
        return redirect(url_for('collection.public_decks'))
 
    # Create new deck for current user
    new_deck = Deck(
        user_id=current_user.id,
        name=f'{original.name} (copy)',
        description=f'Copied from {original.user.username}\'s deck.'
    )
    db.session.add(new_deck)
    db.session.flush()
 
    # Copy all cards
    for dc in original.deck_cards:
        db.session.add(DeckCard(
            deck_id=new_deck.id,
            card_id=dc.card_id,
            quantity=dc.quantity
        ))
 
    db.session.commit()
    flash(f'"{original.name}" copied to your decks!', 'success')
    return redirect(url_for('collection.deck_detail', deck_id=new_deck.id))