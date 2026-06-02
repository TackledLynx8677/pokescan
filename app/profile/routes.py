from flask import render_template, abort
from flask_login import login_required, current_user
from . import profile_bp
from ..models import User, Card, Scan
from .. import db


def get_profile_stats(user):
    """
    Build a full stats dictionary for a user's profile page.
    Returns a dict with all computed stats so the template stays clean.
    """
    scanned_ids = {s.card_id for s in user.scans}
    scanned_cards = Card.query.filter(Card.id.in_(scanned_ids)).all() if scanned_ids else []
    total_catalogue = Card.query.count()

    # ── Rarest card ───
    rarity_order = {
        'Secret Rare': 6,
        'Rare Ultra':  5,
        'Rare Holo':   4,
        'Rare':        3,
        'Uncommon':    2,
        'Common':      1,
    }
    rarest_card = None
    if scanned_cards:
        rarest_card = max(
            scanned_cards,
            key=lambda c: rarity_order.get(c.rarity or '', 0)
        )

    # ── Most scanned card (favourite) ────
    favourite_card = None
    if user.scans:
        from collections import Counter
        counts = Counter(s.card_id for s in user.scans)
        most_common_id = counts.most_common(1)[0][0]
        favourite_card = Card.query.get(most_common_id)

    # ── Most valuable card ─────
    most_valuable = None
    if scanned_cards:
        most_valuable = max(scanned_cards, key=lambda c: c.market_value or 0)

    # ── Completion % ─────
    completion = round((len(scanned_ids) / total_catalogue * 100), 1) if total_catalogue > 0 else 0

    # ── Type breakdown ────
    type_counts = {}
    for card in scanned_cards:
        t = card.pokemon_type or card.card_type or 'Unknown'
        type_counts[t] = type_counts.get(t, 0) + 1
    # Sort by count descending
    type_breakdown = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)

    # ── Rarity breakdown ────
    rarity_counts = {}
    for card in scanned_cards:
        r = card.rarity or 'Unknown'
        rarity_counts[r] = rarity_counts.get(r, 0) + 1

    return {
        'total_scans':      len(user.scans),
        'unique_cards':     len(scanned_ids),
        'total_catalogue':  total_catalogue,
        'completion':       completion,
        'collection_value': user.collection_value,
        'rarest_card':      rarest_card,
        'favourite_card':   favourite_card,
        'most_valuable':    most_valuable,
        'type_breakdown':   type_breakdown[:5],  # Top 5 types
        'rarity_counts':    rarity_counts,
        'scanned_cards':    scanned_cards,
    }


@profile_bp.route('/me')
@login_required
def my_profile():
    """The current user's own profile."""
    stats = get_profile_stats(current_user)
    return render_template('profile/profile.html',
                           profile_user=current_user,
                           stats=stats,
                           is_own_profile=True)


@profile_bp.route('/<username>')
@login_required
def public_profile(username):
    """Public profile for any user — accessible by other logged-in users."""
    user = User.query.filter_by(username=username).first_or_404()
    stats = get_profile_stats(user)
    return render_template('profile/profile.html',
                           profile_user=user,
                           stats=stats,
                           is_own_profile=(user.id == current_user.id))