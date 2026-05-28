"""
seed_cards.py — Run this ONCE after deploying to populate the card catalogue.

Usage:
    python seed_cards.py

IMPORTANT: The 'roboflow_class' values match exactly what was used in Roboflow.
"""

from run import app
from app import db
from app.models import Card


# ── Card data ─────────────────────────────────────────────────────────────────
CARDS = [
    {
        'name':           'Alolan Raichu',
        'set_name':       'Sun & Moon',
        'set_number':     '31/111',
        'rarity':         'Rare Holo',
        'card_type':      'Pokemon',
        'hp':             110,
        'pokemon_type':   'Electric',
        'description':    'It only evolved into this form in the Alola region. According to researchers, its diet is one of the causes of this change.',
        'image_url':      'https://otakumart.co.nz/cdn/shop/products/fa1eed17-3e5c-4241-94a6-7b5e7074833d_6a98f47c-38fa-422a-ac97-b65e0fc3024b.jpg?v=1696319474&width=720',
        'market_value':   8.50,
        'roboflow_class': 'Alolan Raichu',
    },
    {
        'name':           'Dratini',
        'set_name':       'Sun & Moon',
        'set_number':     '94/149',
        'rarity':         'Common',
        'card_type':      'Pokemon',
        'hp':             60,
        'pokemon_type':   'Dragon',
        'description':    'It is called the divine Pokemon. A Dratini continually molts and sloughs off its old skin as it grows larger.',
        'image_url':      'https://kawaiicollector.com.au/cdn/shop/products/unified-minds-148_540x.jpg?v=1586072473',
        'market_value':   2.00,
        'roboflow_class': 'Dratini',
    },
    {
        'name':           'Pidgey',
        'set_name':       'Base Set',
        'set_number':     '57/102',
        'rarity':         'Common',
        'card_type':      'Pokemon',
        'hp':             40,
        'pokemon_type':   'Colorless',
        'description':    'A common sight in forests and woods. It flaps its wings at ground level to kick up blinding sand.',
        'image_url':      'https://assets.pokemon.com/static-assets/content-assets/cms2/img/cards/web/SM9/SM9_EN_121.png',
        'market_value':   1.50,
        'roboflow_class': 'Pidgey',
    },
    {
        'name':           'Pikachu',
        'set_name':       'Base Set',
        'set_number':     '58/102',
        'rarity':         'Common',
        'card_type':      'Pokemon',
        'hp':             40,
        'pokemon_type':   'Electric',
        'description':    'When several of these Pokemon gather, their electricity can cause lightning storms.',
        'image_url':      'https://thumbs.coleka.com/media/item/201711/06/pokemon-invasion-carmin-pikachu-030-111.webp',
        'market_value':   25.00,
        'roboflow_class': 'Pikachu',
    },
    {
        'name':           'Shellos',
        'set_name':       'Diamond & Pearl',
        'set_number':     '96/130',
        'rarity':         'Common',
        'card_type':      'Pokemon',
        'hp':             70,
        'pokemon_type':   'Water',
        'description':    'Its form and color differ based on its habitat. What is unknown is which form is the original.',
        'image_url':      'https://assets.pokemon.com/static-assets/content-assets/cms2/img/cards/web/SM4/SM4_EN_29.png',
        'market_value':   1.50,
        'roboflow_class': 'Shellos',
    },
]


def seed():
    with app.app_context():
        added   = 0
        skipped = 0
        for data in CARDS:
            if Card.query.filter_by(roboflow_class=data['roboflow_class']).first():
                print(f'  SKIP  {data["name"]} (already in DB)')
                skipped += 1
                continue

            card = Card(**data)
            db.session.add(card)
            print(f'  ADD   {data["name"]} ({data["roboflow_class"]})')
            added += 1

        db.session.commit()
        print(f'\nDone — {added} added, {skipped} skipped.')
        print('Log in as admin and go to Admin -> Cards to verify.')


if __name__ == '__main__':
    seed()