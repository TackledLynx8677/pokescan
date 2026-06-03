from datetime import datetime
from flask_login import UserMixin
from . import db, bcrypt


# ── Users ────

class User(UserMixin, db.Model):
    """Registered users. Role is either 'user' or 'admin'."""
    __tablename__ = 'users'

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80), unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(256), nullable=False)
    role       = db.Column(db.String(20), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    scans       = db.relationship('Scan',         backref='user', lazy=True, cascade='all, delete-orphan')
    decks       = db.relationship('Deck',         backref='user', lazy=True, cascade='all, delete-orphan')
    wishlist    = db.relationship('WishlistItem', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def collection_value(self):
        """Total market value of all unique scanned cards."""
        scanned_card_ids = {s.card_id for s in self.scans}
        cards = Card.query.filter(Card.id.in_(scanned_card_ids)).all()
        return round(sum(c.market_value or 0 for c in cards), 2)

    @property
    def unique_card_count(self):
        return len({s.card_id for s in self.scans})


# ── Cards ────

class Card(db.Model):
    """Pokemon cards stored in the catalogue. Admin manages these."""
    __tablename__ = 'cards'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    set_name        = db.Column(db.String(100), nullable=False)
    set_number      = db.Column(db.String(20))
    rarity          = db.Column(db.String(50))          # e.g. "Rare Holo", "Common"
    card_type       = db.Column(db.String(50))          # e.g. "Pokemon", "Trainer", "Energy"
    hp              = db.Column(db.Integer)
    pokemon_type    = db.Column(db.String(50))          # e.g. "Fire", "Water"
    description     = db.Column(db.Text)
    image_url       = db.Column(db.String(500))         # URL to card image
    market_value    = db.Column(db.Float, default=0.0)  # AUD value
    roboflow_class  = db.Column(db.String(100), unique=True, nullable=False)  # Matches Roboflow label exactly
    added_at        = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    scans      = db.relationship('Scan',         backref='card', lazy=True)
    deck_cards = db.relationship('DeckCard',     backref='card', lazy=True, cascade='all, delete-orphan')
    wishlist   = db.relationship('WishlistItem', backref='card', lazy=True, cascade='all, delete-orphan')

    @property
    def scan_count(self):
        return len(self.scans)

    @property
    def rarity_colour(self):
        """Returns a CSS colour class based on rarity."""
        colours = {
            'Common':        'rarity-common',
            'Uncommon':      'rarity-uncommon',
            'Rare':          'rarity-rare',
            'Rare Holo':     'rarity-holo',
            'Rare Ultra':    'rarity-ultra',
            'Secret Rare':   'rarity-secret',
        }
        return colours.get(self.rarity, 'rarity-common')


# ── Scans ──────

class Scan(db.Model):
    """Every time a user successfully scans a card."""
    __tablename__ = 'scans'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    card_id     = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=False)
    confidence  = db.Column(db.Float, nullable=False)
    scanned_at  = db.Column(db.DateTime, default=datetime.utcnow)


# ── Decks ─────────────────────────────────────────────────────────────────────

class Deck(db.Model):
    """A named deck belonging to a user."""
    __tablename__ = 'decks'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    deck_cards  = db.relationship('DeckCard', backref='deck', lazy=True, cascade='all, delete-orphan')

    @property
    def total_cards(self):
        return sum(dc.quantity for dc in self.deck_cards)

    @property
    def total_value(self):
        return round(sum((dc.card.market_value or 0) * dc.quantity for dc in self.deck_cards), 2)


class DeckCard(db.Model):
    """Junction table: which cards are in which deck, and how many."""
    __tablename__ = 'deck_cards'

    id       = db.Column(db.Integer, primary_key=True)
    deck_id  = db.Column(db.Integer, db.ForeignKey('decks.id'),  nullable=False)
    card_id  = db.Column(db.Integer, db.ForeignKey('cards.id'),  nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    __table_args__ = (db.UniqueConstraint('deck_id', 'card_id'),)


# ── Wishlist ───────

class WishlistItem(db.Model):
    """Cards a user wants but hasn't scanned yet."""
    __tablename__ = 'wishlist'

    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    card_id  = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'card_id'),)


# ── Trades ───────

class Trade(db.Model):
    """
    A trade offer between two users.
    Status: 'pending', 'accepted', 'declined', 'cancelled'
    """
    __tablename__ = 'trades'
 
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status      = db.Column(db.String(20), nullable=False, default='pending')
    message     = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
 
    sender   = db.relationship('User', foreign_keys=[sender_id],   backref='sent_trades')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_trades')
    items    = db.relationship('TradeItem', backref='trade', lazy=True, cascade='all, delete-orphan')
 
    @property
    def offered_cards(self):
        """Cards the sender is offering."""
        return [i.card for i in self.items if i.direction == 'offer']
 
    @property
    def requested_cards(self):
        """Cards the sender wants in return."""
        return [i.card for i in self.items if i.direction == 'request']
 
 
class TradeItem(db.Model):
    """A single card in a trade — either being offered or requested."""
    __tablename__ = 'trade_items'
 
    id        = db.Column(db.Integer, primary_key=True)
    trade_id  = db.Column(db.Integer, db.ForeignKey('trades.id'),  nullable=False)
    card_id   = db.Column(db.Integer, db.ForeignKey('cards.id'),   nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # 'offer' or 'request'
 
    card = db.relationship('Card', backref='trade_items')