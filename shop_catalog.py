"""
shop_catalog.py
Static catalog of purchasable cosmetics. Nothing here is withdrawable —
coins only ever move from balance into cosmetic ownership.
"""

CATALOG = {
    "dice_skin": [
        {"id": "classic", "name": "Classic Dice", "price": 0},
        {"id": "gold", "name": "Gold Dice", "price": 300},
        {"id": "neon", "name": "Neon Dice", "price": 500},
        {"id": "wood", "name": "Carved Wood Dice", "price": 400},
    ],
    "board_theme": [
        {"id": "classic", "name": "Classic Board", "price": 0},
        {"id": "midnight", "name": "Midnight Arcade", "price": 600},
        {"id": "festival", "name": "Festival Lights", "price": 600},
        {"id": "marble", "name": "Marble Hall", "price": 800},
    ],
    "token_skin": [
        {"id": "classic", "name": "Classic Pawns", "price": 0},
        {"id": "gems", "name": "Gem Tokens", "price": 450},
        {"id": "animals", "name": "Animal Tokens", "price": 450},
        {"id": "robots", "name": "Robo Tokens", "price": 550},
    ],
}


def find_item(slot: str, cosmetic_id: str):
    for item in CATALOG.get(slot, []):
        if item["id"] == cosmetic_id:
            return item
    return None


def all_items_flat():
    flat = []
    for slot, items in CATALOG.items():
        for item in items:
            flat.append({**item, "slot": slot})
    return flat
