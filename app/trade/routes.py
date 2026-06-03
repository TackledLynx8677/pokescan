from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from . import trade_bp
from ..models import User, Card, Trade, TradeItem, Scan
from .. import db, csrf


@trade_bp.route('/')
@login_required
def inbox():
    """Trade inbox — shows received and sent trades."""
    received = Trade.query.filter_by(
        receiver_id=current_user.id
    ).order_by(Trade.created_at.desc()).all()

    sent = Trade.query.filter_by(
        sender_id=current_user.id
    ).order_by(Trade.created_at.desc()).all()

    pending_count = Trade.query.filter_by(
        receiver_id=current_user.id,
        status='pending'
    ).count()

    return render_template('trade/inbox.html',
                           received=received,
                           sent=sent,
                           pending_count=pending_count)


@trade_bp.route('/offer/<username>', methods=['GET', 'POST'])
@login_required
def offer(username):
    """Create a trade offer to another user."""
    receiver = User.query.filter_by(username=username).first_or_404()

    # Can't trade with yourself
    if receiver.id == current_user.id:
        flash("You can't trade with yourself!", 'warning')
        return redirect(url_for('trade.inbox'))

    # Cards the sender owns
    my_card_ids   = {s.card_id for s in current_user.scans}
    my_cards      = Card.query.filter(Card.id.in_(my_card_ids)).all()

    # Cards the receiver owns (to request)
    their_card_ids = {s.card_id for s in receiver.scans}
    their_cards    = Card.query.filter(Card.id.in_(their_card_ids)).all()

    if request.method == 'POST':
        offered_ids  = request.form.getlist('offered_cards', type=int)
        requested_ids = request.form.getlist('requested_cards', type=int)
        message       = request.form.get('message', '').strip()

        if not offered_ids and not requested_ids:
            flash('You must select at least one card to offer or request.', 'danger')
            return redirect(url_for('trade.offer', username=username))

        # Create the trade
        trade = Trade(
            sender_id=current_user.id,
            receiver_id=receiver.id,
            message=message,
            status='pending'
        )
        db.session.add(trade)
        db.session.flush()  # Get the trade ID before committing

        # Add offered cards
        for card_id in offered_ids:
            db.session.add(TradeItem(trade_id=trade.id, card_id=card_id, direction='offer'))

        # Add requested cards
        for card_id in requested_ids:
            db.session.add(TradeItem(trade_id=trade.id, card_id=card_id, direction='request'))

        db.session.commit()
        flash(f'Trade offer sent to {receiver.username}!', 'success')
        return redirect(url_for('trade.inbox'))

    return render_template('trade/offer.html',
                           receiver=receiver,
                           my_cards=my_cards,
                           their_cards=their_cards)


@trade_bp.route('/accept/<int:trade_id>', methods=['POST'])
@login_required
def accept(trade_id):
    """Accept a trade offer and transfer cards between users."""
    trade = Trade.query.get_or_404(trade_id)

    if trade.receiver_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('trade.inbox'))

    if trade.status != 'pending':
        flash('This trade is no longer pending.', 'warning')
        return redirect(url_for('trade.inbox'))

    # Add offered cards to receiver's library
    for card in trade.offered_cards:
        scan = Scan(
            user_id=current_user.id,
            card_id=card.id,
            confidence=1.0
        )
        db.session.add(scan)

    # Add requested cards to sender's library
    for card in trade.requested_cards:
        scan = Scan(
            user_id=trade.sender_id,
            card_id=card.id,
            confidence=1.0
        )
        db.session.add(scan)

    trade.status = 'accepted'
    db.session.commit()
    flash(f'Trade accepted! Cards have been added to your library.', 'success')
    return redirect(url_for('trade.inbox'))


@trade_bp.route('/decline/<int:trade_id>', methods=['POST'])
@login_required
def decline(trade_id):
    """Decline a trade offer."""
    trade = Trade.query.get_or_404(trade_id)

    if trade.receiver_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('trade.inbox'))

    if trade.status != 'pending':
        flash('This trade is no longer pending.', 'warning')
        return redirect(url_for('trade.inbox'))

    trade.status = 'declined'
    db.session.commit()
    flash('Trade declined.', 'info')
    return redirect(url_for('trade.inbox'))


@trade_bp.route('/cancel/<int:trade_id>', methods=['POST'])
@login_required
def cancel(trade_id):
    """Cancel your own sent trade."""
    trade = Trade.query.get_or_404(trade_id)

    if trade.sender_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('trade.inbox'))

    if trade.status != 'pending':
        flash('Can only cancel pending trades.', 'warning')
        return redirect(url_for('trade.inbox'))

    trade.status = 'cancelled'
    db.session.commit()
    flash('Trade cancelled.', 'info')
    return redirect(url_for('trade.inbox'))


@trade_bp.route('/view/<int:trade_id>')
@login_required
def view_trade(trade_id):
    """View a specific trade's details."""
    trade = Trade.query.get_or_404(trade_id)

    # Only sender or receiver can view
    if trade.sender_id != current_user.id and trade.receiver_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('trade.inbox'))

    return render_template('trade/view_trade.html', trade=trade)