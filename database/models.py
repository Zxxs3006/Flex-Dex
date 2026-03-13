from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()

# Ranking System Thresholds
RANKS = [
    {'name': 'Rookie Trainer', 'min_cards': 0, 'icon': '🎒', 'color': '#9CA3AF'},
    {'name': 'Pokémon Trainer', 'min_cards': 11, 'icon': '⚡', 'color': '#60A5FA'},
    {'name': 'Ace Trainer', 'min_cards': 51, 'icon': '⭐', 'color': '#34D399'},
    {'name': 'Gym Leader', 'min_cards': 101, 'icon': '🏆', 'color': '#FBBF24'},
    {'name': 'Elite Four', 'min_cards': 251, 'icon': '👑', 'color': '#F472B6'},
    {'name': 'Champion', 'min_cards': 501, 'icon': '🏅', 'color': '#A78BFA'},
    {'name': 'Pokémon Master', 'min_cards': 1001, 'icon': '🌟', 'color': '#F59E0B'},
    {'name': 'Legend', 'min_cards': 2501, 'icon': '💎', 'color': '#EC4899'},
]

# Regional Pokédex Definitions (National Dex Numbers)
REGIONAL_DEXES = {
    'kanto': {'name': 'Kanto', 'range': (1, 151), 'icon': '🔴', 'game': 'Red/Blue'},
    'johto': {'name': 'Johto', 'range': (152, 251), 'icon': '🥈', 'game': 'Gold/Silver'},
    'hoenn': {'name': 'Hoenn', 'range': (252, 386), 'icon': '🔷', 'game': 'Ruby/Sapphire'},
    'sinnoh': {'name': 'Sinnoh', 'range': (387, 493), 'icon': '💎', 'game': 'Diamond/Pearl'},
    'unova': {'name': 'Unova', 'range': (494, 649), 'icon': '⚫', 'game': 'Black/White'},
    'kalos': {'name': 'Kalos', 'range': (650, 721), 'icon': '🔵', 'game': 'X/Y'},
    'alola': {'name': 'Alola', 'range': (722, 809), 'icon': '🌺', 'game': 'Sun/Moon'},
    'galar': {'name': 'Galar', 'range': (810, 898), 'icon': '⚔️', 'game': 'Sword/Shield'},
    'paldea': {'name': 'Paldea', 'range': (899, 1025), 'icon': '📕', 'game': 'Scarlet/Violet'},
}


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Profile fields
    bio = db.Column(db.String(500), default='')
    favorite_pokemon = db.Column(db.String(100), default='')
    avatar_url = db.Column(db.String(255), default='')
    profile_badge = db.Column(db.String(50), default='kanto')  # Current badge display

    # Stats (cached for performance)
    total_cards = db.Column(db.Integer, default=0)
    unique_pokemon = db.Column(db.Integer, default=0)
    collection_value = db.Column(db.Float, default=0.0)

    binders = db.relationship('Binder', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    cards = db.relationship('UserCard', backref='owner', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_rank(self):
        """Get user's current rank based on total cards."""
        current_rank = RANKS[0]
        for rank in RANKS:
            if self.total_cards >= rank['min_cards']:
                current_rank = rank
        return current_rank

    def get_next_rank(self):
        """Get the next rank and cards needed."""
        current_rank = self.get_rank()
        current_index = RANKS.index(current_rank)
        if current_index < len(RANKS) - 1:
            next_rank = RANKS[current_index + 1]
            cards_needed = next_rank['min_cards'] - self.total_cards
            return {'rank': next_rank, 'cards_needed': cards_needed}
        return None

    def get_rank_progress(self):
        """Get progress percentage to next rank."""
        current_rank = self.get_rank()
        next_rank_info = self.get_next_rank()
        if not next_rank_info:
            return 100

        current_min = current_rank['min_cards']
        next_min = next_rank_info['rank']['min_cards']
        progress = ((self.total_cards - current_min) / (next_min - current_min)) * 100
        return min(progress, 100)

    def update_stats(self):
        """Recalculate user stats from their collection (only verified cards count for rankings)."""
        user_cards = UserCard.query.filter_by(user_id=self.id).all()

        # Only verified cards count toward rankings and stats
        verified_cards = [uc for uc in user_cards if uc.verified]

        self.total_cards = sum(uc.quantity for uc in verified_cards)
        self.unique_pokemon = len(set(uc.card.national_dex for uc in verified_cards if uc.card.national_dex))
        self.collection_value = sum(
            (uc.card.price_market or 0) * uc.quantity for uc in verified_cards
        )
        db.session.commit()

    def get_regional_progress(self):
        """Get completion progress for each regional Pokédex (only verified cards count)."""
        user_cards = UserCard.query.filter_by(user_id=self.id).all()
        # Only count verified cards
        owned_dex_numbers = set(uc.card.national_dex for uc in user_cards if uc.card.national_dex and uc.verified)

        progress = {}
        for region_id, region in REGIONAL_DEXES.items():
            start, end = region['range']
            total_pokemon = end - start + 1
            owned = len([n for n in owned_dex_numbers if start <= n <= end])
            progress[region_id] = {
                'name': region['name'],
                'icon': region['icon'],
                'game': region['game'],
                'owned': owned,
                'total': total_pokemon,
                'percentage': round((owned / total_pokemon) * 100, 1),
                'completed': owned >= total_pokemon
            }
        return progress

    def get_completed_dexes(self):
        """Get list of completed regional dexes."""
        progress = self.get_regional_progress()
        return [r for r in progress.values() if r['completed']]

    def __repr__(self):
        return f'<User {self.username}>'


class Card(db.Model):
    __tablename__ = 'cards'

    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    set_name = db.Column(db.String(100))
    set_id = db.Column(db.String(50))
    number = db.Column(db.String(20))
    rarity = db.Column(db.String(50))
    hp = db.Column(db.Integer)
    types = db.Column(db.String(100))
    artist = db.Column(db.String(100))
    image_small = db.Column(db.String(255))
    image_large = db.Column(db.String(255))
    price_market = db.Column(db.Float)
    price_low = db.Column(db.Float)
    price_mid = db.Column(db.Float)
    price_high = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    # National Pokédex number for regional dex tracking
    national_dex = db.Column(db.Integer, nullable=True)

    user_cards = db.relationship('UserCard', backref='card', lazy='dynamic')

    def __repr__(self):
        return f'<Card {self.name} ({self.card_id})>'


class Binder(db.Model):
    __tablename__ = 'binders'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    cover_image = db.Column(db.String(255), default='')

    cards = db.relationship('UserCard', backref='binder', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Binder {self.name}>'


class UserCard(db.Model):
    __tablename__ = 'user_cards'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=False)
    binder_id = db.Column(db.Integer, db.ForeignKey('binders.id'), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    condition = db.Column(db.String(20), default='Near Mint')
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    verified = db.Column(db.Boolean, default=False)  # Card ownership verified via photo

    __table_args__ = (
        db.UniqueConstraint('user_id', 'card_id', 'binder_id', name='unique_user_card_binder'),
    )

    def __repr__(self):
        return f'<UserCard {self.card_id} owned by User {self.user_id}>'


class Achievement(db.Model):
    """Track user achievements and milestones."""
    __tablename__ = 'achievements'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    achievement_type = db.Column(db.String(50), nullable=False)  # 'rank_up', 'dex_complete', 'milestone'
    achievement_name = db.Column(db.String(100), nullable=False)
    achieved_at = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)  # JSON string for extra data

    user = db.relationship('User', backref='achievements')

    def __repr__(self):
        return f'<Achievement {self.achievement_name} for User {self.user_id}>'


# =============================================================================
# BATTLE SYSTEM MODELS
# =============================================================================

# Type effectiveness chart (attacker -> defender -> multiplier)
TYPE_CHART = {
    'Fire': {'Grass': 2.0, 'Water': 0.5, 'Fire': 0.5, 'Ice': 2.0, 'Bug': 2.0, 'Steel': 2.0},
    'Water': {'Fire': 2.0, 'Water': 0.5, 'Grass': 0.5, 'Ground': 2.0, 'Rock': 2.0},
    'Grass': {'Water': 2.0, 'Fire': 0.5, 'Grass': 0.5, 'Ground': 2.0, 'Rock': 2.0, 'Flying': 0.5},
    'Electric': {'Water': 2.0, 'Flying': 2.0, 'Electric': 0.5, 'Ground': 0.0, 'Grass': 0.5},
    'Psychic': {'Fighting': 2.0, 'Poison': 2.0, 'Psychic': 0.5, 'Dark': 0.0, 'Steel': 0.5},
    'Fighting': {'Normal': 2.0, 'Ice': 2.0, 'Rock': 2.0, 'Dark': 2.0, 'Steel': 2.0, 'Flying': 0.5, 'Psychic': 0.5, 'Fairy': 0.5},
    'Dark': {'Psychic': 2.0, 'Ghost': 2.0, 'Fighting': 0.5, 'Dark': 0.5, 'Fairy': 0.5},
    'Dragon': {'Dragon': 2.0, 'Steel': 0.5, 'Fairy': 0.0},
    'Fairy': {'Fighting': 2.0, 'Dragon': 2.0, 'Dark': 2.0, 'Fire': 0.5, 'Poison': 0.5, 'Steel': 0.5},
    'Steel': {'Ice': 2.0, 'Rock': 2.0, 'Fairy': 2.0, 'Fire': 0.5, 'Water': 0.5, 'Electric': 0.5, 'Steel': 0.5},
    'Ghost': {'Psychic': 2.0, 'Ghost': 2.0, 'Normal': 0.0, 'Dark': 0.5},
    'Ice': {'Grass': 2.0, 'Ground': 2.0, 'Flying': 2.0, 'Dragon': 2.0, 'Fire': 0.5, 'Water': 0.5, 'Ice': 0.5, 'Steel': 0.5},
    'Flying': {'Grass': 2.0, 'Fighting': 2.0, 'Bug': 2.0, 'Electric': 0.5, 'Rock': 0.5, 'Steel': 0.5},
    'Bug': {'Grass': 2.0, 'Psychic': 2.0, 'Dark': 2.0, 'Fire': 0.5, 'Fighting': 0.5, 'Flying': 0.5, 'Ghost': 0.5, 'Steel': 0.5, 'Fairy': 0.5},
    'Rock': {'Fire': 2.0, 'Ice': 2.0, 'Flying': 2.0, 'Bug': 2.0, 'Fighting': 0.5, 'Ground': 0.5, 'Steel': 0.5},
    'Ground': {'Fire': 2.0, 'Electric': 2.0, 'Poison': 2.0, 'Rock': 2.0, 'Steel': 2.0, 'Grass': 0.5, 'Bug': 0.5, 'Flying': 0.0},
    'Poison': {'Grass': 2.0, 'Fairy': 2.0, 'Poison': 0.5, 'Ground': 0.5, 'Rock': 0.5, 'Ghost': 0.5, 'Steel': 0.0},
    'Normal': {'Ghost': 0.0, 'Rock': 0.5, 'Steel': 0.5},
    'Colorless': {},  # Neutral to all
}


class Party(db.Model):
    """User's battle party - a team of up to 6 Pokemon cards."""
    __tablename__ = 'parties'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), default='My Battle Team')
    is_active = db.Column(db.Boolean, default=True)  # Current active party
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Stats
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)

    user = db.relationship('User', backref='parties')
    party_cards = db.relationship('PartyCard', backref='party', lazy='dynamic', cascade='all, delete-orphan')

    def get_cards(self):
        """Get all cards in party ordered by position."""
        return PartyCard.query.filter_by(party_id=self.id).order_by(PartyCard.position).all()

    def card_count(self):
        """Get number of cards in party."""
        return PartyCard.query.filter_by(party_id=self.id).count()

    def is_full(self):
        """Check if party has 6 cards."""
        return self.card_count() >= 6

    def total_hp(self):
        """Calculate total HP of all cards in party."""
        cards = self.get_cards()
        return sum(pc.card.hp or 0 for pc in cards)

    def __repr__(self):
        return f'<Party {self.name} ({self.card_count()}/6)>'


class PartyCard(db.Model):
    """A card slot in a party."""
    __tablename__ = 'party_cards'

    id = db.Column(db.Integer, primary_key=True)
    party_id = db.Column(db.Integer, db.ForeignKey('parties.id'), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)  # 1-6 position in party

    card = db.relationship('Card')

    __table_args__ = (
        db.UniqueConstraint('party_id', 'position', name='unique_party_position'),
        db.UniqueConstraint('party_id', 'card_id', name='unique_party_card'),
    )

    def __repr__(self):
        return f'<PartyCard {self.card.name if self.card else "?"} at position {self.position}>'


class Battle(db.Model):
    """An online battle between two users."""
    __tablename__ = 'battles'

    id = db.Column(db.Integer, primary_key=True)

    # Players
    player1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Null while waiting
    player1_party_id = db.Column(db.Integer, db.ForeignKey('parties.id'), nullable=False)
    player2_party_id = db.Column(db.Integer, db.ForeignKey('parties.id'), nullable=True)

    # Battle state
    status = db.Column(db.String(20), default='waiting')  # waiting, active, completed, cancelled
    current_turn = db.Column(db.Integer, default=1)
    whose_turn = db.Column(db.Integer, default=1)  # 1 or 2

    # Active Pokemon (position in party)
    player1_active = db.Column(db.Integer, default=1)
    player2_active = db.Column(db.Integer, default=1)

    # HP tracking (JSON: {card_id: current_hp})
    player1_hp = db.Column(db.Text, default='{}')
    player2_hp = db.Column(db.Text, default='{}')

    # Knocked out cards (JSON list of card_ids)
    player1_knocked_out = db.Column(db.Text, default='[]')
    player2_knocked_out = db.Column(db.Text, default='[]')

    # Result
    winner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    player1 = db.relationship('User', foreign_keys=[player1_id], backref='battles_as_p1')
    player2 = db.relationship('User', foreign_keys=[player2_id], backref='battles_as_p2')
    winner = db.relationship('User', foreign_keys=[winner_id])
    player1_party = db.relationship('Party', foreign_keys=[player1_party_id])
    player2_party = db.relationship('Party', foreign_keys=[player2_party_id])

    turns = db.relationship('BattleTurn', backref='battle', lazy='dynamic', cascade='all, delete-orphan')

    def get_player1_hp(self):
        return json.loads(self.player1_hp or '{}')

    def set_player1_hp(self, hp_dict):
        self.player1_hp = json.dumps(hp_dict)

    def get_player2_hp(self):
        return json.loads(self.player2_hp or '{}')

    def set_player2_hp(self, hp_dict):
        self.player2_hp = json.dumps(hp_dict)

    def get_player1_knocked_out(self):
        return json.loads(self.player1_knocked_out or '[]')

    def get_player2_knocked_out(self):
        return json.loads(self.player2_knocked_out or '[]')

    def is_player_turn(self, user_id):
        """Check if it's this player's turn."""
        if self.whose_turn == 1:
            return user_id == self.player1_id
        return user_id == self.player2_id

    def get_opponent(self, user_id):
        """Get the opponent user."""
        if user_id == self.player1_id:
            return self.player2
        return self.player1

    def __repr__(self):
        return f'<Battle {self.id} - {self.status}>'


class BattleTurn(db.Model):
    """A single turn/action in a battle."""
    __tablename__ = 'battle_turns'

    id = db.Column(db.Integer, primary_key=True)
    battle_id = db.Column(db.Integer, db.ForeignKey('battles.id'), nullable=False)
    turn_number = db.Column(db.Integer, nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Action details
    action_type = db.Column(db.String(20), nullable=False)  # 'attack', 'switch', 'forfeit'
    attack_name = db.Column(db.String(100), nullable=True)
    attacker_card_id = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=True)
    defender_card_id = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=True)
    switched_to_card_id = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=True)

    # Results
    damage_dealt = db.Column(db.Integer, default=0)
    type_effectiveness = db.Column(db.Float, default=1.0)
    was_knockout = db.Column(db.Boolean, default=False)
    message = db.Column(db.Text)  # Battle log message

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    player = db.relationship('User')
    attacker_card = db.relationship('Card', foreign_keys=[attacker_card_id])
    defender_card = db.relationship('Card', foreign_keys=[defender_card_id])

    def __repr__(self):
        return f'<BattleTurn {self.turn_number} - {self.action_type}>'


class BattleStats(db.Model):
    """Track overall battle statistics for users."""
    __tablename__ = 'battle_stats'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    total_battles = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    win_streak = db.Column(db.Integer, default=0)
    best_win_streak = db.Column(db.Integer, default=0)
    total_knockouts = db.Column(db.Integer, default=0)
    total_damage_dealt = db.Column(db.Integer, default=0)

    # ELO-style rating
    battle_rating = db.Column(db.Integer, default=1000)

    user = db.relationship('User', backref='battle_stats_entry')

    def win_rate(self):
        if self.total_battles == 0:
            return 0
        return round((self.wins / self.total_battles) * 100, 1)

    def __repr__(self):
        return f'<BattleStats {self.user_id} - {self.wins}W/{self.losses}L>'
