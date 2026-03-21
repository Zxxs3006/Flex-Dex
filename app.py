"""
FlexDex - Pokémon Card Scanner & Collection Tracker
Web Deployment Version with Ranking System & Regional Pokédex
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from database import db, init_db, User, Card, Binder, UserCard, Achievement, RANKS, REGIONAL_DEXES, ShopPurchase
from database.models import Party, PartyCard, Battle, BattleTurn, BattleStats, TYPE_CHART
from scanner import CardLookup
from datetime import datetime
import json
import os

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Initialize database
init_db(app)

# Initialize card lookup
card_lookup = CardLookup(app.config.get('POKEMON_TCG_API_KEY', ''))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Context processor to make RANKS and REGIONAL_DEXES available in all templates
@app.context_processor
def inject_globals():
    return {
        'RANKS': RANKS,
        'REGIONAL_DEXES': REGIONAL_DEXES,
        'app_name': 'FlexDex'
    }


# ============== Page Routes ==============

@app.route('/')
def index():
    """Home page."""
    # Get top trainers for leaderboard
    top_trainers = User.query.order_by(User.total_cards.desc()).limit(5).all()
    return render_template('index.html', top_trainers=top_trainers)


@app.route('/scanner')
def scanner():
    """Card scanner page with PokéLens."""
    return render_template('scanner.html')


@app.route('/search')
def search():
    """Search results page with advanced filtering."""
    query = request.args.get('q', '').strip()
    card_number = request.args.get('number', '').strip()
    set_name = request.args.get('set', '').strip()
    use_pokemontcg = request.args.get('use_pokemontcg', '') == '1'
    show_all = request.args.get('show_all', '') == '1'

    # If no query, show empty search page with tips
    if not query:
        return render_template('search.html',
                               query='',
                               number='',
                               set_name='',
                               cards=[],
                               searched=False,
                               exact_match=False,
                               use_pokemontcg=False,
                               show_all=False)

    # Fetch more results for "See More" pagination (show 30 at a time in UI)
    limit = 150

    # Search for cards - use pokemontcg.io directly if requested (with TCGdex fallback)
    if use_pokemontcg:
        raw_cards = card_lookup.search_pokemontcg(query, limit=limit)
        # Mark as pokemontcg source for proper formatting
        for card in raw_cards:
            card['_source'] = 'pokemontcg'
        # If pokemontcg.io fails or returns nothing, fallback to TCGdex
        if not raw_cards:
            raw_cards = card_lookup.search_fuzzy(query, limit=limit)
    else:
        raw_cards = card_lookup.search_fuzzy(query, limit=limit)

    cards = [card_lookup.format_card_data(c) for c in raw_cards]

    exact_match = False

    # Filter by card number if provided
    if card_number:
        # Clean the card number (handle formats like "25/165" or just "25")
        # Also strip leading zeros (041 -> 41)
        clean_number = card_number.split('/')[0].strip().lstrip('0') or '0'

        # Filter cards that match the number (also strip leading zeros from card data)
        filtered_cards = [c for c in cards if str(c.get('number', '')).strip().lstrip('0') == clean_number]

        if filtered_cards:
            cards = filtered_cards
            exact_match = True

    # Filter by set name if provided
    if set_name:
        set_name_lower = set_name.lower()
        filtered_cards = [c for c in cards if set_name_lower in c.get('set', {}).get('name', '').lower()]

        if filtered_cards:
            cards = filtered_cards
            if card_number:
                exact_match = True

    # Sort by price (cards with prices first)
    cards.sort(key=lambda x: (x.get('prices', {}).get('market') is None, -(x.get('prices', {}).get('market') or 0)))

    return render_template('search.html',
                           query=query,
                           number=card_number,
                           set_name=set_name,
                           cards=cards,
                           searched=True,
                           exact_match=exact_match,
                           use_pokemontcg=use_pokemontcg,
                           show_all=show_all)


@app.route('/card/<card_id>')
def card_details(card_id):
    """Card details page."""
    raw_card = card_lookup.get_card_by_id(card_id)

    if not raw_card:
        flash('Card not found', 'error')
        return redirect(url_for('index'))

    card = card_lookup.format_card_data(raw_card)
    return render_template('card_details.html', card=card)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Welcome back, {}!'.format(user.username), 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page - simple username & password only."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        errors = []

        if len(username) < 3:
            errors.append('Username must be at least 3 characters')

        if len(username) > 20:
            errors.append('Username must be 20 characters or less')

        if User.query.filter_by(username=username).first():
            errors.append('Username already taken')

        if len(password) < 4:
            errors.append('Password must be at least 4 characters')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')

        # Generate a placeholder email from username
        placeholder_email = f"{username.lower()}@flexdex.local"

        user = User(username=username, email=placeholder_email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Create default binder
        default_binder = Binder(name='My Collection', user_id=user.id, description='Default binder')
        db.session.add(default_binder)

        # First achievement
        achievement = Achievement(
            user_id=user.id,
            achievement_type='milestone',
            achievement_name='Welcome to FlexDex!',
            details=json.dumps({'message': 'Started your trainer journey'})
        )
        db.session.add(achievement)
        db.session.commit()

        flash('Registration successful! Welcome to FlexDex, Trainer!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    """Log out user."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/profile')
@app.route('/profile/<username>')
def profile(username=None):
    """User profile page."""
    if username:
        user = User.query.filter_by(username=username).first_or_404()
    elif current_user.is_authenticated:
        user = current_user
    else:
        flash('Please log in to view your profile', 'info')
        return redirect(url_for('login'))

    # Get user stats
    rank = user.get_rank()
    next_rank = user.get_next_rank()
    rank_progress = user.get_rank_progress()
    regional_progress = user.get_regional_progress()
    achievements = Achievement.query.filter_by(user_id=user.id).order_by(Achievement.achieved_at.desc()).limit(10).all()

    # Recent cards
    recent_cards = UserCard.query.filter_by(user_id=user.id).order_by(UserCard.added_at.desc()).limit(6).all()

    return render_template('profile.html',
                         profile_user=user,
                         rank=rank,
                         next_rank=next_rank,
                         rank_progress=rank_progress,
                         regional_progress=regional_progress,
                         achievements=achievements,
                         recent_cards=recent_cards)


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit profile page."""
    if request.method == 'POST':
        current_user.bio = request.form.get('bio', '')[:500]
        current_user.favorite_pokemon = request.form.get('favorite_pokemon', '')[:100]
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html')


@app.route('/pokedex')
@login_required
def pokedex():
    """Regional Pokédex progress page."""
    regional_progress = current_user.get_regional_progress()
    return render_template('pokedex.html', regional_progress=regional_progress)


@app.route('/pokedex/<region>')
@login_required
def regional_dex(region):
    """View specific regional Pokédex."""
    if region not in REGIONAL_DEXES:
        flash('Invalid region', 'error')
        return redirect(url_for('pokedex'))

    region_info = REGIONAL_DEXES[region]
    start, end = region_info['range']

    # Get user's cards in this region
    user_cards = UserCard.query.filter_by(user_id=current_user.id).all()
    owned_pokemon = {}
    for uc in user_cards:
        if uc.card.national_dex and start <= uc.card.national_dex <= end:
            dex_num = uc.card.national_dex
            if dex_num not in owned_pokemon:
                owned_pokemon[dex_num] = uc.card

    progress = current_user.get_regional_progress()[region]

    return render_template('regional_dex.html',
                         region=region,
                         region_info=region_info,
                         progress=progress,
                         owned_pokemon=owned_pokemon,
                         dex_range=range(start, end + 1))


@app.route('/leaderboard')
def leaderboard():
    """Global leaderboard."""
    # Top collectors by total cards
    top_collectors = User.query.order_by(User.total_cards.desc()).limit(50).all()

    # Top by collection value
    top_value = User.query.order_by(User.collection_value.desc()).limit(10).all()

    return render_template('leaderboard.html',
                         top_collectors=top_collectors,
                         top_value=top_value)


@app.route('/binder')
@login_required
def binder():
    """User's card collection."""
    binder_id = request.args.get('binder_id', type=int)

    binders = Binder.query.filter_by(user_id=current_user.id).all()
    current_binder = None

    if binder_id:
        current_binder = Binder.query.filter_by(id=binder_id, user_id=current_user.id).first()
        cards = UserCard.query.filter_by(user_id=current_user.id, binder_id=binder_id).all()
    else:
        cards = UserCard.query.filter_by(user_id=current_user.id).all()

    return render_template('binder.html', cards=cards, binders=binders, current_binder=current_binder)


@app.route('/binder/create', methods=['POST'])
@login_required
def create_binder():
    """Create a new binder."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Binder name is required', 'error')
        return redirect(url_for('binder'))

    binder = Binder(name=name, description=description, user_id=current_user.id)
    db.session.add(binder)
    db.session.commit()

    flash('Binder created successfully!', 'success')
    return redirect(url_for('binder', binder_id=binder.id))


@app.route('/analytics')
@login_required
def analytics():
    """Collection analytics page."""
    user_cards = UserCard.query.filter_by(user_id=current_user.id).all()
    binders = Binder.query.filter_by(user_id=current_user.id).all()

    stats = {
        'total_cards': current_user.total_cards,
        'unique_cards': len(user_cards),
        'total_binders': len(binders),
        'total_value': current_user.collection_value,
        'most_valuable': None,
        'strongest': None,
        'rarest': None,
        'type_distribution': {},
        'recent_cards': []
    }

    if user_cards:
        for uc in user_cards:
            card = uc.card
            if card.price_market and (not stats['most_valuable'] or
                    card.price_market > stats['most_valuable'].price_market):
                stats['most_valuable'] = card

            if card.hp and (not stats['strongest'] or card.hp > stats['strongest'].hp):
                stats['strongest'] = card

            if card.types:
                try:
                    types = json.loads(card.types) if isinstance(card.types, str) else card.types
                    for t in types:
                        stats['type_distribution'][t] = stats['type_distribution'].get(t, 0) + uc.quantity
                except:
                    pass

        rarity_order = ['Common', 'Uncommon', 'Rare', 'Rare Holo', 'Rare Holo EX',
                       'Rare Holo GX', 'Rare Holo V', 'Rare VMAX', 'Rare VSTAR',
                       'Rare Ultra', 'Rare Secret', 'Rare Rainbow', 'Rare Shiny']
        for uc in user_cards:
            if uc.card.rarity:
                if not stats['rarest']:
                    stats['rarest'] = uc.card
                elif uc.card.rarity in rarity_order and stats['rarest'].rarity in rarity_order:
                    if rarity_order.index(uc.card.rarity) > rarity_order.index(stats['rarest'].rarity):
                        stats['rarest'] = uc.card

        recent = sorted(user_cards, key=lambda x: x.added_at, reverse=True)[:6]
        stats['recent_cards'] = [uc.card for uc in recent]

    return render_template('analytics.html', stats=stats)


@app.route('/add_to_binder', methods=['POST'])
@login_required
def add_to_binder():
    """Redirect to verification page before adding card."""
    card_id = request.form.get('card_id')

    if not card_id:
        flash('No card specified', 'error')
        return redirect(url_for('scanner'))

    # Redirect to verification page
    return redirect(url_for('verify_card', card_id=card_id))


@app.route('/verify/<card_id>')
@login_required
def verify_card(card_id):
    """Card verification page."""
    raw_card = card_lookup.get_card_by_id(card_id)

    # Try pokemontcg.io if not found
    if not raw_card:
        raw_card = card_lookup.get_card_pokemontcg(card_id)
        if raw_card:
            raw_card['_source'] = 'pokemontcg'

    if not raw_card:
        flash('Card not found', 'error')
        return redirect(url_for('scanner'))

    card = card_lookup.format_card_data(raw_card)
    return render_template('verify_card.html', card=card)


@app.route('/api/verify_card', methods=['POST'])
@login_required
def api_verify_card():
    """API endpoint to add verified card to binder (verification done client-side)."""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'No data provided'})

    card_id = data.get('card_id')
    verified = data.get('verified', False)
    score = data.get('score', 0)

    if not card_id:
        return jsonify({'success': False, 'error': 'No card ID provided'})

    if not verified or score < 55:
        return jsonify({'success': False, 'error': 'Card not verified'})

    # Add verified card to binder
    card = get_or_create_card(card_id)

    if not card:
        return jsonify({'success': False, 'error': 'Card not found'})

    old_total = current_user.total_cards

    user_card = UserCard.query.filter_by(user_id=current_user.id, card_id=card.id).first()

    if user_card:
        user_card.quantity += 1
        user_card.verified = True
    else:
        user_card = UserCard(user_id=current_user.id, card_id=card.id, verified=True)
        db.session.add(user_card)

    db.session.commit()

    # Update user stats and check for rank up
    current_user.update_stats()
    check_achievements(current_user, old_total)

    return jsonify({'success': True, 'message': f'{card.name} added to your binder!'})


# ============== API Routes ==============

@app.route('/api/search')
def api_search():
    """Search cards API."""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'success': False, 'error': 'Query too short'})

    raw_cards = card_lookup.search_fuzzy(query, limit=10)
    cards = [card_lookup.format_card_data(c) for c in raw_cards]

    return jsonify({'success': True, 'cards': cards})


@app.route('/api/ocr', methods=['POST'])
def api_ocr():
    """OCR endpoint using OCR.space API (free, 25k/month)."""
    import base64

    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'success': False, 'error': 'No image provided'})

    # Get base64 image data
    image_data = data['image']

    # Remove data URL prefix if present
    if ',' in image_data:
        image_data = image_data.split(',')[1]

    try:
        # OCR.space free API endpoint
        ocr_url = 'https://api.ocr.space/parse/image'

        # OCR.space free demo API key
        api_key = 'K85682737488957'

        payload = {
            'apikey': api_key,
            'base64Image': f'data:image/png;base64,{image_data}',
            'language': 'eng',
            'isOverlayRequired': False,
            'detectOrientation': True,
            'scale': True,
            'OCREngine': 2  # Engine 2 is better for stylized text
        }

        response = requests.post(ocr_url, data=payload, timeout=30)
        result = response.json()

        if result.get('IsErroredOnProcessing'):
            error_msg = result.get('ErrorMessage', ['Unknown error'])
            return jsonify({'success': False, 'error': error_msg[0] if isinstance(error_msg, list) else error_msg})

        # Extract text from response
        parsed_results = result.get('ParsedResults', [])
        if not parsed_results:
            return jsonify({'success': False, 'error': 'No text detected'})

        text = parsed_results[0].get('ParsedText', '')

        # Clean and extract card name and number
        card_name = extract_card_name(text)
        card_number = extract_card_number(text)

        return jsonify({
            'success': True,
            'raw_text': text,
            'card_name': card_name,
            'card_number': card_number
        })

    except requests.Timeout:
        return jsonify({'success': False, 'error': 'OCR request timed out'})
    except Exception as e:
        print(f'OCR error: {e}')
        return jsonify({'success': False, 'error': str(e)})


def extract_card_name(text):
    """Extract Pokemon card name from OCR text."""
    if not text:
        return ''

    lines = text.strip().split('\n')

    # First line usually contains the Pokemon name
    for line in lines[:3]:  # Check first 3 lines
        line = line.strip()

        # Skip lines that are just numbers or HP
        if not line or line.isdigit():
            continue
        if 'HP' in line.upper() and any(c.isdigit() for c in line):
            # This line has HP, try to extract name before HP
            hp_index = line.upper().find('HP')
            if hp_index > 0:
                name = line[:hp_index].strip()
                # Clean up
                name = ''.join(c for c in name if c.isalpha() or c.isspace() or c == '-' or c == "'").strip()
                if len(name) >= 2:
                    return name
            continue

        # Clean the name
        name = line

        # Remove common Pokemon card text
        remove_words = ['BASIC', 'STAGE', 'GX', 'EX', 'VMAX', 'VSTAR', 'V', 'POKEMON', 'TRAINER', 'ENERGY']
        for word in remove_words:
            name = name.replace(word, '').replace(word.lower(), '')

        # Keep only letters, spaces, hyphens, and apostrophes
        name = ''.join(c for c in name if c.isalpha() or c.isspace() or c == '-' or c == "'").strip()

        # Take first 2 words max (Pokemon names are usually 1-2 words)
        words = name.split()
        if words:
            name = ' '.join(words[:2])
            if len(name) >= 2:
                return name

    return ''


def extract_card_number(text):
    """Extract card number from OCR text."""
    if not text:
        return ''

    import re

    # Look for patterns like "123/456" or "123 / 456"
    match = re.search(r'(\d{1,3})\s*[/\\]\s*(\d{1,3})', text)
    if match:
        return match.group(1)

    # Look for number at end of text (often card number)
    lines = text.strip().split('\n')
    for line in reversed(lines):
        match = re.search(r'(\d{1,3})\s*[/\\]\s*(\d{1,3})', line)
        if match:
            return match.group(1)

    return ''


# Popular Pokemon list with National Dex numbers for browsing
POPULAR_POKEMON = [
    # Gen 1 Starters & Evolutions
    (1, "Bulbasaur"), (2, "Ivysaur"), (3, "Venusaur"),
    (4, "Charmander"), (5, "Charmeleon"), (6, "Charizard"),
    (7, "Squirtle"), (8, "Wartortle"), (9, "Blastoise"),
    # Gen 1 Popular
    (25, "Pikachu"), (26, "Raichu"), (39, "Jigglypuff"),
    (52, "Meowth"), (54, "Psyduck"), (55, "Golduck"),
    (63, "Abra"), (64, "Kadabra"), (65, "Alakazam"),
    (66, "Machop"), (67, "Machoke"), (68, "Machamp"),
    (74, "Geodude"), (75, "Graveler"), (76, "Golem"),
    (92, "Gastly"), (93, "Haunter"), (94, "Gengar"),
    (129, "Magikarp"), (130, "Gyarados"),
    (131, "Lapras"), (133, "Eevee"), (134, "Vaporeon"),
    (135, "Jolteon"), (136, "Flareon"), (143, "Snorlax"),
    (144, "Articuno"), (145, "Zapdos"), (146, "Moltres"),
    (147, "Dratini"), (148, "Dragonair"), (149, "Dragonite"),
    (150, "Mewtwo"), (151, "Mew"),
    # Gen 2 Starters & Popular
    (152, "Chikorita"), (155, "Cyndaquil"), (158, "Totodile"),
    (172, "Pichu"), (175, "Togepi"), (176, "Togetic"),
    (196, "Espeon"), (197, "Umbreon"), (212, "Scizor"),
    (243, "Raikou"), (244, "Entei"), (245, "Suicune"),
    (248, "Tyranitar"), (249, "Lugia"), (250, "Ho-Oh"), (251, "Celebi"),
    # Gen 3 Starters & Popular
    (252, "Treecko"), (255, "Torchic"), (258, "Mudkip"),
    (282, "Gardevoir"), (306, "Aggron"), (330, "Flygon"),
    (359, "Absol"), (373, "Salamence"), (376, "Metagross"),
    (380, "Latias"), (381, "Latios"), (382, "Kyogre"),
    (383, "Groudon"), (384, "Rayquaza"), (385, "Jirachi"),
    # Gen 4 Popular
    (387, "Turtwig"), (390, "Chimchar"), (393, "Piplup"),
    (403, "Shinx"), (405, "Luxray"), (445, "Garchomp"),
    (448, "Lucario"), (470, "Leafeon"), (471, "Glaceon"),
    (483, "Dialga"), (484, "Palkia"), (487, "Giratina"),
    (491, "Darkrai"), (492, "Shaymin"), (493, "Arceus"),
    # Gen 5-9 Popular
    (495, "Snivy"), (498, "Tepig"), (501, "Oshawott"),
    (571, "Zoroark"), (609, "Chandelure"), (635, "Hydreigon"),
    (643, "Reshiram"), (644, "Zekrom"), (646, "Kyurem"),
    (700, "Sylveon"), (716, "Xerneas"), (717, "Yveltal"),
    (724, "Decidueye"), (727, "Incineroar"), (730, "Primarina"),
    (778, "Mimikyu"), (800, "Necrozma"),
    (810, "Grookey"), (813, "Scorbunny"), (816, "Sobble"),
    (888, "Zacian"), (889, "Zamazenta"), (890, "Eternatus"),
    (906, "Sprigatito"), (909, "Fuecoco"), (912, "Quaxly"),
]


@app.route('/api/pokemon/browse')
def api_pokemon_browse():
    """Get list of popular Pokemon with sprites for browsing."""
    pokemon_list = []
    for dex_num, name in POPULAR_POKEMON:
        pokemon_list.append({
            'dex': dex_num,
            'name': name,
            'sprite': f'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{dex_num}.png'
        })
    return jsonify({'success': True, 'pokemon': pokemon_list})


@app.route('/api/pokemon/search/<name>')
def api_pokemon_search(name):
    """Search for all cards of a specific Pokemon."""
    raw_cards = card_lookup.search_fuzzy(name, limit=20)
    cards = [card_lookup.format_card_data(c) for c in raw_cards]
    return jsonify({'success': True, 'cards': cards})


@app.route('/api/card/<card_id>')
def api_card(card_id):
    """Get card details API."""
    raw_card = card_lookup.get_card_by_id(card_id)

    if not raw_card:
        return jsonify({'success': False, 'error': 'Card not found'})

    card = card_lookup.format_card_data(raw_card)
    return jsonify({'success': True, 'card': card})


@app.route('/api/binder/add', methods=['POST'])
@login_required
def api_add_to_binder():
    """Add card to binder API - requires verification first."""
    data = request.get_json()

    if not data or 'card_id' not in data:
        return jsonify({'success': False, 'error': 'No card specified'})

    card_id = data['card_id']

    # Redirect to verification - cards must be verified before adding
    return jsonify({
        'success': False,
        'requires_verification': True,
        'redirect': url_for('verify_card', card_id=card_id),
        'message': 'Please verify your card first'
    })


@app.route('/api/binder/remove/<int:user_card_id>', methods=['DELETE'])
@login_required
def api_remove_from_binder(user_card_id):
    """Remove card from binder API."""
    user_card = UserCard.query.filter_by(id=user_card_id, user_id=current_user.id).first()

    if not user_card:
        return jsonify({'success': False, 'error': 'Card not found'})

    db.session.delete(user_card)
    db.session.commit()
    current_user.update_stats()

    return jsonify({'success': True, 'message': 'Card removed'})


@app.route('/api/binder/quantity/<int:user_card_id>', methods=['PATCH'])
@login_required
def api_update_quantity(user_card_id):
    """Update card quantity API."""
    data = request.get_json()
    delta = data.get('delta', 0)

    user_card = UserCard.query.filter_by(id=user_card_id, user_id=current_user.id).first()

    if not user_card:
        return jsonify({'success': False, 'error': 'Card not found'})

    user_card.quantity += delta

    if user_card.quantity <= 0:
        db.session.delete(user_card)

    db.session.commit()
    current_user.update_stats()

    return jsonify({'success': True, 'quantity': max(0, user_card.quantity if user_card.quantity > 0 else 0)})


@app.route('/api/binder/move/<int:user_card_id>', methods=['PATCH'])
@login_required
def api_move_card(user_card_id):
    """Move card to different binder API."""
    data = request.get_json()
    new_binder_id = data.get('binder_id')

    user_card = UserCard.query.filter_by(id=user_card_id, user_id=current_user.id).first()

    if not user_card:
        return jsonify({'success': False, 'error': 'Card not found'})

    if new_binder_id:
        binder = Binder.query.filter_by(id=new_binder_id, user_id=current_user.id).first()
        if not binder:
            return jsonify({'success': False, 'error': 'Binder not found'})

    user_card.binder_id = new_binder_id
    db.session.commit()

    return jsonify({'success': True, 'message': 'Card moved'})


@app.route('/api/binder/<int:binder_id>', methods=['DELETE'])
@login_required
def api_delete_binder(binder_id):
    """Delete binder API."""
    binder = Binder.query.filter_by(id=binder_id, user_id=current_user.id).first()

    if not binder:
        return jsonify({'success': False, 'error': 'Binder not found'})

    UserCard.query.filter_by(binder_id=binder_id).update({'binder_id': None})

    db.session.delete(binder)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Binder deleted'})


@app.route('/api/binder/export')
@login_required
def api_export_collection():
    """Export collection data API."""
    user_cards = UserCard.query.filter_by(user_id=current_user.id).all()

    cards_data = []
    for uc in user_cards:
        card = uc.card
        cards_data.append({
            'name': card.name,
            'set_name': card.set_name,
            'number': card.number,
            'rarity': card.rarity,
            'hp': card.hp,
            'types': card.types,
            'price_market': card.price_market,
            'quantity': uc.quantity
        })

    return jsonify({'success': True, 'cards': cards_data})


@app.route('/api/profile/stats')
@login_required
def api_profile_stats():
    """Get current user stats API."""
    rank = current_user.get_rank()
    next_rank = current_user.get_next_rank()

    return jsonify({
        'success': True,
        'total_cards': current_user.total_cards,
        'unique_pokemon': current_user.unique_pokemon,
        'collection_value': current_user.collection_value,
        'rank': rank,
        'next_rank': next_rank,
        'rank_progress': current_user.get_rank_progress()
    })


# ============== Daily Rewards System ==============

# Starter Pokemon pool for guests (common, basic Pokemon)
STARTER_POKEMON_IDS = [
    'base1-44',   # Bulbasaur
    'base1-46',   # Charmander
    'base1-63',   # Squirtle
    'base1-55',   # Pikachu
    'base1-43',   # Abra
    'base1-52',   # Machop
    'base1-49',   # Drowzee
    'base1-58',   # Ponyta
    'base1-67',   # Voltorb
    'base1-39',   # Geodude (was Porygon)
    'base1-66',   # Staryu
    'base1-56',   # Pidgey
]

# Popular Pokemon that guests CAN'T use
RESTRICTED_POKEMON = [
    'Charizard', 'Blastoise', 'Venusaur', 'Pikachu VMAX', 'Mewtwo',
    'Mew', 'Rayquaza', 'Umbreon', 'Gengar', 'Dragonite', 'Gyarados',
    'Lugia', 'Ho-Oh', 'Arceus', 'Giratina', 'Dialga', 'Palkia'
]

SPIN_REWARDS = [
    {'type': 'coins', 'amount': 50, 'label': '50 Coins', 'color': '#FFD700', 'weight': 25},
    {'type': 'coins', 'amount': 100, 'label': '100 Coins', 'color': '#FFA500', 'weight': 20},
    {'type': 'coins', 'amount': 250, 'label': '250 Coins', 'color': '#FF6347', 'weight': 10},
    {'type': 'card', 'rarity': 'Common', 'label': 'Random Card', 'color': '#90EE90', 'weight': 20},
    {'type': 'card', 'rarity': 'Rare', 'label': 'Rare Card', 'color': '#87CEEB', 'weight': 8},
    {'type': 'booster', 'amount': 3, 'label': 'Mini Booster (3)', 'color': '#DDA0DD', 'weight': 10},
    {'type': 'boost_damage', 'amount': 10, 'label': '+10% Damage', 'color': '#FF4444', 'weight': 5},
    {'type': 'boost_hp', 'amount': 10, 'label': '+10% HP', 'color': '#44FF44', 'weight': 2},
]

import random
from datetime import date, timedelta

@app.route('/rewards')
@login_required
def daily_rewards():
    """Daily rewards page with spin the wheel."""
    # Check if user can spin today
    today = date.today()
    can_spin = current_user.last_spin_date != today

    # Check active boosts
    active_boost = None
    if current_user.battle_boost_type and current_user.battle_boost_expires:
        if current_user.battle_boost_expires > datetime.utcnow():
            active_boost = {
                'type': current_user.battle_boost_type,
                'expires': current_user.battle_boost_expires
            }

    return render_template('daily_rewards.html',
                          can_spin=can_spin,
                          coins=current_user.coins,
                          active_boost=active_boost,
                          spin_rewards=SPIN_REWARDS)


@app.route('/api/spin', methods=['POST'])
@login_required
def api_spin_wheel():
    """API endpoint to spin the daily wheel."""
    today = date.today()

    if current_user.last_spin_date == today:
        return jsonify({'success': False, 'error': 'You already spun today!'})

    # Weighted random selection
    total_weight = sum(r['weight'] for r in SPIN_REWARDS)
    rand = random.uniform(0, total_weight)
    cumulative = 0

    reward = SPIN_REWARDS[0]
    reward_index = 0
    for i, r in enumerate(SPIN_REWARDS):
        cumulative += r['weight']
        if rand <= cumulative:
            reward = r
            reward_index = i
            break

    # Apply reward
    reward_message = ""
    if reward['type'] == 'coins':
        current_user.coins += reward['amount']
        reward_message = f"You won {reward['amount']} coins!"
    elif reward['type'] == 'card':
        # Give a random card
        rarity = reward.get('rarity', 'Common')
        cards = Card.query.filter(Card.rarity.ilike(f'%{rarity}%')).limit(100).all()
        if cards:
            random_card = random.choice(cards)
            # Check if user already has this card
            existing = UserCard.query.filter_by(user_id=current_user.id, card_id=random_card.id).first()
            if existing:
                existing.quantity += 1
            else:
                new_card = UserCard(user_id=current_user.id, card_id=random_card.id, quantity=1, verified=True)
                db.session.add(new_card)
            reward_message = f"You won a {rarity} card: {random_card.name}!"
        else:
            current_user.coins += 100
            reward_message = "No cards available, you got 100 coins instead!"
    elif reward['type'] == 'booster':
        # Give multiple random cards
        count = reward.get('amount', 3)
        cards = Card.query.limit(500).all()
        if cards:
            won_cards = random.sample(cards, min(count, len(cards)))
            for card in won_cards:
                existing = UserCard.query.filter_by(user_id=current_user.id, card_id=card.id).first()
                if existing:
                    existing.quantity += 1
                else:
                    new_card = UserCard(user_id=current_user.id, card_id=card.id, quantity=1, verified=True)
                    db.session.add(new_card)
            reward_message = f"You won a mini booster with {count} cards!"
        else:
            current_user.coins += 150
            reward_message = "No cards available, you got 150 coins instead!"
    elif reward['type'] == 'boost_damage':
        current_user.battle_boost_type = 'damage'
        current_user.battle_boost_expires = datetime.utcnow() + timedelta(hours=24)
        reward_message = f"+{reward['amount']}% damage boost for 24 hours!"
    elif reward['type'] == 'boost_hp':
        current_user.battle_boost_type = 'hp'
        current_user.battle_boost_expires = datetime.utcnow() + timedelta(hours=24)
        reward_message = f"+{reward['amount']}% HP boost for 24 hours!"

    current_user.last_spin_date = today
    current_user.update_stats()
    db.session.commit()

    return jsonify({
        'success': True,
        'reward_index': reward_index,
        'reward': reward,
        'message': reward_message,
        'new_coins': current_user.coins
    })


# ============== Battle System Routes ==============

@app.route('/battle')
def battle_lobby():
    """Battle lobby - find opponents and manage parties."""
    # Check if user is a guest
    is_guest = not current_user.is_authenticated

    if is_guest:
        # Guest battle lobby
        guest_battles_today = int(request.cookies.get('guest_battles', 0))
        can_battle = guest_battles_today < 3

        # Get available battles
        available_battles = Battle.query.filter(
            Battle.status == 'waiting'
        ).order_by(Battle.created_at.desc()).limit(20).all()

        return render_template('battle_lobby_guest.html',
                              available_battles=available_battles,
                              battles_remaining=3 - guest_battles_today,
                              can_battle=can_battle)

    # Logged in user battle lobby
    # Get user's active party
    active_party = Party.query.filter_by(user_id=current_user.id, is_active=True).first()

    # Get all user's parties
    parties = Party.query.filter_by(user_id=current_user.id).all()

    # Get available battles (waiting for opponent)
    available_battles = Battle.query.filter(
        Battle.status == 'waiting',
        Battle.player1_id != current_user.id
    ).order_by(Battle.created_at.desc()).limit(20).all()

    # Get user's active battles
    my_battles = Battle.query.filter(
        Battle.status.in_(['waiting', 'active']),
        db.or_(Battle.player1_id == current_user.id, Battle.player2_id == current_user.id)
    ).order_by(Battle.created_at.desc()).all()

    # Get battle stats
    battle_stats = BattleStats.query.filter_by(user_id=current_user.id).first()

    # Get recent battle history
    recent_battles = Battle.query.filter(
        Battle.status == 'completed',
        db.or_(Battle.player1_id == current_user.id, Battle.player2_id == current_user.id)
    ).order_by(Battle.ended_at.desc()).limit(10).all()

    # Check if user can spin today
    can_spin = current_user.last_spin_date != date.today()

    return render_template('battle_lobby.html',
                          active_party=active_party,
                          parties=parties,
                          available_battles=available_battles,
                          my_battles=my_battles,
                          battle_stats=battle_stats,
                          recent_battles=recent_battles,
                          can_spin=can_spin)


@app.route('/battle/party')
@login_required
def manage_party():
    """Manage battle party."""
    # Get active party or create one
    party = Party.query.filter_by(user_id=current_user.id, is_active=True).first()

    if not party:
        party = Party(user_id=current_user.id, name='My Battle Team', is_active=True)
        db.session.add(party)
        db.session.commit()

    # Get user's cards for selection
    user_cards = UserCard.query.filter_by(user_id=current_user.id).all()

    # Get current party cards
    party_cards = party.get_cards()

    return render_template('manage_party.html',
                          party=party,
                          party_cards=party_cards,
                          user_cards=user_cards)


@app.route('/api/party/add', methods=['POST'])
@login_required
def api_add_to_party():
    """Add card to party."""
    data = request.get_json()
    card_db_id = data.get('card_id')

    if not card_db_id:
        return jsonify({'success': False, 'error': 'No card specified'})

    # Get or create active party
    party = Party.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not party:
        party = Party(user_id=current_user.id, name='My Battle Team', is_active=True)
        db.session.add(party)
        db.session.commit()

    # Check if party is full
    if party.is_full():
        return jsonify({'success': False, 'error': 'Party is full (6 cards max)'})

    # Check if card already in party
    existing = PartyCard.query.filter_by(party_id=party.id, card_id=card_db_id).first()
    if existing:
        return jsonify({'success': False, 'error': 'Card already in party'})

    # Verify user owns this card
    card = Card.query.get(card_db_id)
    if not card:
        return jsonify({'success': False, 'error': 'Card not found'})

    user_card = UserCard.query.filter_by(user_id=current_user.id, card_id=card_db_id).first()
    if not user_card:
        return jsonify({'success': False, 'error': 'You do not own this card'})

    # Find next available position
    next_position = party.card_count() + 1

    party_card = PartyCard(party_id=party.id, card_id=card_db_id, position=next_position)
    db.session.add(party_card)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{card.name} added to party',
        'party_count': party.card_count()
    })


@app.route('/api/party/remove', methods=['POST'])
@login_required
def api_remove_from_party():
    """Remove card from party."""
    data = request.get_json()
    card_db_id = data.get('card_id')

    party = Party.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not party:
        return jsonify({'success': False, 'error': 'No active party'})

    party_card = PartyCard.query.filter_by(party_id=party.id, card_id=card_db_id).first()
    if not party_card:
        return jsonify({'success': False, 'error': 'Card not in party'})

    removed_position = party_card.position
    db.session.delete(party_card)

    # Reorder remaining cards
    remaining = PartyCard.query.filter(
        PartyCard.party_id == party.id,
        PartyCard.position > removed_position
    ).all()

    for pc in remaining:
        pc.position -= 1

    db.session.commit()

    return jsonify({'success': True, 'party_count': party.card_count()})


@app.route('/api/party/reorder', methods=['POST'])
@login_required
def api_reorder_party():
    """Reorder party cards."""
    data = request.get_json()
    new_order = data.get('order', [])  # List of card_ids in new order

    party = Party.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not party:
        return jsonify({'success': False, 'error': 'No active party'})

    for i, card_id in enumerate(new_order, 1):
        party_card = PartyCard.query.filter_by(party_id=party.id, card_id=card_id).first()
        if party_card:
            party_card.position = i

    db.session.commit()
    return jsonify({'success': True})


def get_or_create_guest_party(guest_user, party_name='Starter Team'):
    """Get or create a guest party with random Pokemon from the database."""
    # Clear any existing party cards and recreate with fresh random Pokemon
    guest_party = Party.query.filter_by(user_id=guest_user.id, name=party_name).first()

    if guest_party:
        # Clear old party cards
        PartyCard.query.filter_by(party_id=guest_party.id).delete()
    else:
        guest_party = Party(user_id=guest_user.id, name=party_name, is_active=True)
        db.session.add(guest_party)
        db.session.commit()

    # Get random cards from database (prefer common/basic Pokemon)
    # First try to get cards with lower HP (typically basic Pokemon)
    available_cards = Card.query.filter(
        Card.hp.isnot(None),
        Card.hp > 0,
        Card.hp <= 100,  # Basic Pokemon typically have lower HP
        Card.image_small.isnot(None)
    ).limit(100).all()

    # If not enough, get any cards
    if len(available_cards) < 6:
        available_cards = Card.query.filter(
            Card.hp.isnot(None),
            Card.hp > 0,
            Card.image_small.isnot(None)
        ).limit(100).all()

    if available_cards:
        # Pick up to 6 random cards
        selected_cards = random.sample(available_cards, min(6, len(available_cards)))
        for i, card in enumerate(selected_cards):
            pc = PartyCard(party_id=guest_party.id, card_id=card.id, position=i+1)
            db.session.add(pc)
        db.session.commit()

    return guest_party


@app.route('/battle/guest/create', methods=['POST'])
def guest_create_battle():
    """Create a guest battle with starter Pokemon."""
    # Check guest battle limit
    guest_battles = int(request.cookies.get('guest_battles', 0))
    guest_date = request.cookies.get('guest_date', '')

    today = date.today().isoformat()
    if guest_date != today:
        guest_battles = 0

    if guest_battles >= 3:
        flash('You have used all 3 guest battles today. Register for unlimited battles!', 'error')
        return redirect(url_for('battle_lobby'))

    # Check if there are any cards in the database
    card_count = Card.query.filter(Card.hp.isnot(None), Card.hp > 0).count()
    if card_count < 1:
        flash('No Pokemon cards available yet! Ask a registered user to scan some cards first.', 'error')
        return redirect(url_for('battle_lobby'))

    # Get or create guest user
    guest_user = User.query.filter_by(username='_GuestPlayer_').first()
    if not guest_user:
        guest_user = User(
            username='_GuestPlayer_',
            email='guest@flexdex.local',
            password_hash='guest_no_login'
        )
        db.session.add(guest_user)
        db.session.commit()

    # Get or create guest party with random Pokemon
    guest_party = get_or_create_guest_party(guest_user, 'Starter Team')

    # Create battle
    battle = Battle(
        player1_id=guest_user.id,
        player1_party_id=guest_party.id,
        status='waiting'
    )
    db.session.add(battle)
    db.session.commit()

    # Set cookie to track battles
    response = redirect(url_for('battle_room', battle_id=battle.id))
    response.set_cookie('guest_battles', str(guest_battles + 1), max_age=86400)
    response.set_cookie('guest_date', today, max_age=86400)
    response.set_cookie('guest_battle_id', str(battle.id), max_age=3600)

    flash('Guest battle created! Waiting for opponent...', 'success')
    return response


@app.route('/battle/guest/join/<int:battle_id>', methods=['POST'])
def guest_join_battle(battle_id):
    """Join a battle as guest."""
    # Check guest battle limit
    guest_battles = int(request.cookies.get('guest_battles', 0))
    guest_date = request.cookies.get('guest_date', '')

    today = date.today().isoformat()
    if guest_date != today:
        guest_battles = 0

    if guest_battles >= 3:
        flash('You have used all 3 guest battles today. Register for unlimited battles!', 'error')
        return redirect(url_for('battle_lobby'))

    battle = Battle.query.get_or_404(battle_id)

    if battle.status != 'waiting':
        flash('This battle is no longer available', 'error')
        return redirect(url_for('battle_lobby'))

    # Check if there are any cards in the database
    card_count = Card.query.filter(Card.hp.isnot(None), Card.hp > 0).count()
    if card_count < 1:
        flash('No Pokemon cards available yet! Ask a registered user to scan some cards first.', 'error')
        return redirect(url_for('battle_lobby'))

    # Get or create second guest user
    guest_user2 = User.query.filter_by(username='_GuestPlayer2_').first()
    if not guest_user2:
        guest_user2 = User(
            username='_GuestPlayer2_',
            email='guest2@flexdex.local',
            password_hash='guest_no_login'
        )
        db.session.add(guest_user2)
        db.session.commit()

    # Get or create guest party with random Pokemon from database
    guest_party2 = get_or_create_guest_party(guest_user2, 'Starter Team 2')

    # Join battle
    battle.player2_id = guest_user2.id
    battle.player2_party_id = guest_party2.id
    battle.status = 'active'
    battle.started_at = datetime.utcnow()

    # Initialize HP
    p1_hp = {}
    p2_hp = {}
    for pc in battle.player1_party.get_cards():
        p1_hp[str(pc.card.id)] = pc.card.hp or 100
    for pc in battle.player2_party.get_cards():
        p2_hp[str(pc.card.id)] = pc.card.hp or 100

    battle.set_player1_hp(p1_hp)
    battle.set_player2_hp(p2_hp)
    db.session.commit()

    # Set cookie
    response = redirect(url_for('battle_room', battle_id=battle.id))
    response.set_cookie('guest_battles', str(guest_battles + 1), max_age=86400)
    response.set_cookie('guest_date', today, max_age=86400)
    response.set_cookie('guest_battle_id', str(battle.id), max_age=3600)

    flash('Joined battle! Good luck!', 'success')
    return response


@app.route('/battle/create', methods=['POST'])
@login_required
def create_battle():
    """Create a new battle and wait for opponent."""
    party = Party.query.filter_by(user_id=current_user.id, is_active=True).first()

    if not party or party.card_count() < 1:
        flash('You need at least 1 card in your party to battle!', 'error')
        return redirect(url_for('manage_party'))

    # Create battle
    battle = Battle(
        player1_id=current_user.id,
        player1_party_id=party.id,
        status='waiting'
    )
    db.session.add(battle)
    db.session.commit()

    flash('Battle created! Waiting for opponent...', 'success')
    return redirect(url_for('battle_room', battle_id=battle.id))


@app.route('/battle/join/<int:battle_id>', methods=['POST'])
@login_required
def join_battle(battle_id):
    """Join an existing battle."""
    battle = Battle.query.get_or_404(battle_id)

    if battle.status != 'waiting':
        flash('This battle is no longer available', 'error')
        return redirect(url_for('battle_lobby'))

    if battle.player1_id == current_user.id:
        flash('You cannot join your own battle', 'error')
        return redirect(url_for('battle_lobby'))

    party = Party.query.filter_by(user_id=current_user.id, is_active=True).first()

    if not party or party.card_count() < 1:
        flash('You need at least 1 card in your party to battle!', 'error')
        return redirect(url_for('manage_party'))

    # Join battle
    battle.player2_id = current_user.id
    battle.player2_party_id = party.id
    battle.status = 'active'
    battle.started_at = datetime.utcnow()

    # Initialize HP for both players' Pokemon
    p1_hp = {}
    p2_hp = {}

    for pc in battle.player1_party.get_cards():
        p1_hp[str(pc.card_id)] = pc.card.hp or 100

    for pc in party.get_cards():
        p2_hp[str(pc.card_id)] = pc.card.hp or 100

    battle.set_player1_hp(p1_hp)
    battle.set_player2_hp(p2_hp)

    db.session.commit()

    flash('Battle started!', 'success')
    return redirect(url_for('battle_room', battle_id=battle.id))


@app.route('/battle/room/<int:battle_id>')
def battle_room(battle_id):
    """Battle room - the actual battle UI."""
    battle = Battle.query.get_or_404(battle_id)

    # Determine user_id (handle both logged in users and guests)
    user_id = None
    if current_user.is_authenticated:
        user_id = current_user.id
    else:
        # Check if this is a guest battle
        guest_battle_id = request.cookies.get('guest_battle_id')
        if guest_battle_id == str(battle_id):
            guest_user = User.query.filter_by(username='_GuestPlayer_').first()
            guest_user2 = User.query.filter_by(username='_GuestPlayer2_').first()
            if guest_user and battle.player1_id == guest_user.id:
                user_id = guest_user.id
            elif guest_user2 and battle.player2_id == guest_user2.id:
                user_id = guest_user2.id

    # Verify user is in this battle
    if not user_id or user_id not in [battle.player1_id, battle.player2_id]:
        flash('You are not in this battle', 'error')
        return redirect(url_for('battle_lobby'))

    # Determine if current user is player 1 or 2
    is_player1 = user_id == battle.player1_id

    # Get party cards
    my_party = battle.player1_party if is_player1 else battle.player2_party
    opponent_party = battle.player2_party if is_player1 else battle.player1_party

    my_party_cards = my_party.get_cards() if my_party else []
    opponent_party_cards = opponent_party.get_cards() if opponent_party else []

    # Get HP states
    my_hp = battle.get_player1_hp() if is_player1 else battle.get_player2_hp()
    opponent_hp = battle.get_player2_hp() if is_player1 else battle.get_player1_hp()

    # Get active Pokemon
    my_active = battle.player1_active if is_player1 else battle.player2_active
    opponent_active = battle.player2_active if is_player1 else battle.player1_active

    # Get recent turns
    recent_turns = BattleTurn.query.filter_by(battle_id=battle_id).order_by(
        BattleTurn.turn_number.desc()
    ).limit(10).all()

    # Get attack data for active Pokemon
    my_attacks = []
    opponent_attacks = []

    # Find my active card and get its attacks
    for pc in my_party_cards:
        if pc.position == my_active:
            raw_card = card_lookup.get_card_by_id(pc.card.card_id)
            if raw_card:
                my_attacks = raw_card.get('attacks', [])
            break

    # Find opponent active card and get its attacks
    for pc in opponent_party_cards:
        if pc.position == opponent_active:
            raw_card = card_lookup.get_card_by_id(pc.card.card_id)
            if raw_card:
                opponent_attacks = raw_card.get('attacks', [])
            break

    return render_template('battle_room.html',
                          battle=battle,
                          is_player1=is_player1,
                          my_party_cards=my_party_cards,
                          opponent_party_cards=opponent_party_cards,
                          my_hp=my_hp,
                          opponent_hp=opponent_hp,
                          my_active=my_active,
                          opponent_active=opponent_active,
                          recent_turns=recent_turns,
                          type_chart=TYPE_CHART,
                          my_attacks=my_attacks,
                          opponent_attacks=opponent_attacks)


@app.route('/api/battle/<int:battle_id>/state')
def api_battle_state(battle_id):
    """Get current battle state - no login required for polling."""
    battle = Battle.query.get_or_404(battle_id)

    # Determine who is checking (for is_my_turn)
    user_id = None
    if current_user.is_authenticated:
        user_id = current_user.id
    else:
        # Check guest cookie
        guest_battle_id = request.cookies.get('guest_battle_id')
        if guest_battle_id == str(battle_id):
            # Guest is player 1 or 2 depending on which guest user
            guest_user = User.query.filter_by(username='_GuestPlayer_').first()
            guest_user2 = User.query.filter_by(username='_GuestPlayer2_').first()
            if guest_user and battle.player1_id == guest_user.id:
                user_id = guest_user.id
            elif guest_user2 and battle.player2_id == guest_user2.id:
                user_id = guest_user2.id

    is_my_turn = False
    if user_id:
        is_my_turn = battle.is_player_turn(user_id)

    return jsonify({
        'success': True,
        'status': battle.status,
        'current_turn': battle.current_turn,
        'is_my_turn': is_my_turn,
        'whose_turn': battle.whose_turn,
        'player1_active': battle.player1_active,
        'player2_active': battle.player2_active,
        'player1_hp': battle.get_player1_hp(),
        'player2_hp': battle.get_player2_hp(),
        'player1_knocked_out': battle.get_player1_knocked_out(),
        'player2_knocked_out': battle.get_player2_knocked_out(),
        'winner_id': battle.winner_id,
        'has_player2': battle.player2_id is not None
    })


def get_battle_user(battle):
    """Get the user for a battle - handles both logged in users and guests."""
    if current_user.is_authenticated:
        if current_user.id in [battle.player1_id, battle.player2_id]:
            return current_user
    else:
        # Check guest cookie
        guest_battle_id = request.cookies.get('guest_battle_id')
        if guest_battle_id == str(battle.id):
            guest_user = User.query.filter_by(username='_GuestPlayer_').first()
            guest_user2 = User.query.filter_by(username='_GuestPlayer2_').first()
            if guest_user and battle.player1_id == guest_user.id:
                return guest_user
            elif guest_user2 and battle.player2_id == guest_user2.id:
                return guest_user2
    return None


@app.route('/api/battle/<int:battle_id>/attack', methods=['POST'])
def api_battle_attack(battle_id):
    """Execute an attack."""
    battle = Battle.query.get_or_404(battle_id)

    # Get the user (logged in or guest)
    user = get_battle_user(battle)
    if not user:
        return jsonify({'success': False, 'error': 'Not authorized for this battle'})

    if battle.status != 'active':
        return jsonify({'success': False, 'error': 'Battle is not active'})

    if not battle.is_player_turn(user.id):
        return jsonify({'success': False, 'error': 'Not your turn'})

    data = request.get_json()
    attack_index = data.get('attack_index', 0)

    is_player1 = user.id == battle.player1_id

    # Get active Pokemon
    my_party = battle.player1_party if is_player1 else battle.player2_party
    opponent_party = battle.player2_party if is_player1 else battle.player1_party

    my_active_pos = battle.player1_active if is_player1 else battle.player2_active
    opponent_active_pos = battle.player2_active if is_player1 else battle.player1_active

    my_cards = my_party.get_cards()
    opponent_cards = opponent_party.get_cards()

    # Find active Pokemon
    attacker = None
    defender = None

    for pc in my_cards:
        if pc.position == my_active_pos:
            attacker = pc.card
            break

    for pc in opponent_cards:
        if pc.position == opponent_active_pos:
            defender = pc.card
            break

    if not attacker or not defender:
        return jsonify({'success': False, 'error': 'Active Pokemon not found'})

    # Get attack from card data (using API)
    raw_card = card_lookup.get_card_by_id(attacker.card_id)
    attacks = raw_card.get('attacks', []) if raw_card else []

    if not attacks:
        # Default attack if card has no attacks
        attack_name = "Tackle"
        base_damage = 30
    else:
        attack_index = min(attack_index, len(attacks) - 1)
        attack = attacks[attack_index]
        attack_name = attack.get('name', 'Attack')
        damage_str = attack.get('damage', '30')
        # Parse damage (handle "30+", "20x", etc.)
        base_damage = int(''.join(filter(str.isdigit, str(damage_str))) or '30')

    # Calculate type effectiveness
    attacker_types = []
    try:
        if attacker.types:
            attacker_types = json.loads(attacker.types) if isinstance(attacker.types, str) else attacker.types
    except:
        pass

    defender_types = []
    try:
        if defender.types:
            defender_types = json.loads(defender.types) if isinstance(defender.types, str) else defender.types
    except:
        pass

    effectiveness = 1.0
    for a_type in attacker_types:
        for d_type in defender_types:
            if a_type in TYPE_CHART and d_type in TYPE_CHART.get(a_type, {}):
                effectiveness *= TYPE_CHART[a_type][d_type]

    # Calculate final damage
    damage = int(base_damage * effectiveness)

    # Apply damage
    opponent_hp_dict = battle.get_player2_hp() if is_player1 else battle.get_player1_hp()
    current_hp = opponent_hp_dict.get(str(defender.id), defender.hp or 100)
    new_hp = max(0, current_hp - damage)
    opponent_hp_dict[str(defender.id)] = new_hp

    if is_player1:
        battle.set_player2_hp(opponent_hp_dict)
    else:
        battle.set_player1_hp(opponent_hp_dict)

    # Build message
    effectiveness_msg = ""
    if effectiveness > 1:
        effectiveness_msg = " It's super effective!"
    elif effectiveness < 1 and effectiveness > 0:
        effectiveness_msg = " It's not very effective..."
    elif effectiveness == 0:
        effectiveness_msg = " It had no effect!"

    message = f"{attacker.name} used {attack_name}! Dealt {damage} damage.{effectiveness_msg}"

    was_knockout = new_hp <= 0

    if was_knockout:
        message += f" {defender.name} was knocked out!"

        # Add to knocked out list
        knocked_out_list = battle.get_player2_knocked_out() if is_player1 else battle.get_player1_knocked_out()
        knocked_out_list.append(defender.id)

        if is_player1:
            battle.player2_knocked_out = json.dumps(knocked_out_list)
        else:
            battle.player1_knocked_out = json.dumps(knocked_out_list)

        # Check if opponent has any Pokemon left
        opponent_alive = False
        for pc in opponent_cards:
            if pc.card.id not in knocked_out_list:
                # Auto-switch to next available Pokemon
                if is_player1:
                    battle.player2_active = pc.position
                else:
                    battle.player1_active = pc.position
                opponent_alive = True
                break

        if not opponent_alive:
            # Battle won!
            battle.status = 'completed'
            battle.winner_id = user.id
            battle.ended_at = datetime.utcnow()
            message += f" {user.username} wins the battle!"

            # Update battle stats
            update_battle_stats(user.id, won=True, knockouts=1, damage=damage)
            opponent_id = battle.player2_id if is_player1 else battle.player1_id
            update_battle_stats(opponent_id, won=False, knockouts=0, damage=0)

    # Record turn
    turn = BattleTurn(
        battle_id=battle.id,
        turn_number=battle.current_turn,
        player_id=user.id,
        action_type='attack',
        attack_name=attack_name,
        attacker_card_id=attacker.id,
        defender_card_id=defender.id,
        damage_dealt=damage,
        type_effectiveness=effectiveness,
        was_knockout=was_knockout,
        message=message
    )
    db.session.add(turn)

    # Switch turn
    if battle.status == 'active':
        battle.whose_turn = 2 if battle.whose_turn == 1 else 1
        battle.current_turn += 1

    db.session.commit()

    return jsonify({
        'success': True,
        'message': message,
        'damage': damage,
        'damage_dealt': damage,
        'effectiveness': effectiveness,
        'was_knockout': was_knockout,
        'battle_won': battle.status == 'completed'
    })


@app.route('/api/battle/<int:battle_id>/switch', methods=['POST'])
def api_battle_switch(battle_id):
    """Switch active Pokemon."""
    battle = Battle.query.get_or_404(battle_id)

    # Get the user (logged in or guest)
    user = get_battle_user(battle)
    if not user:
        return jsonify({'success': False, 'error': 'Not authorized for this battle'})

    if battle.status != 'active':
        return jsonify({'success': False, 'error': 'Battle is not active'})

    if not battle.is_player_turn(user.id):
        return jsonify({'success': False, 'error': 'Not your turn'})

    data = request.get_json()
    new_position = data.get('position')

    is_player1 = user.id == battle.player1_id

    # Verify Pokemon is not knocked out
    my_party = battle.player1_party if is_player1 else battle.player2_party
    knocked_out = battle.get_player1_knocked_out() if is_player1 else battle.get_player2_knocked_out()

    target_card = None
    for pc in my_party.get_cards():
        if pc.position == new_position and pc.card.id not in knocked_out:
            target_card = pc.card
            break

    if not target_card:
        return jsonify({'success': False, 'error': 'Cannot switch to that Pokemon'})

    # Switch
    if is_player1:
        battle.player1_active = new_position
    else:
        battle.player2_active = new_position

    message = f"{user.username} sent out {target_card.name}!"

    # Record turn
    turn = BattleTurn(
        battle_id=battle.id,
        turn_number=battle.current_turn,
        player_id=user.id,
        action_type='switch',
        switched_to_card_id=target_card.id,
        message=message
    )
    db.session.add(turn)

    # Switch turn
    battle.whose_turn = 2 if battle.whose_turn == 1 else 1
    battle.current_turn += 1

    db.session.commit()

    return jsonify({'success': True, 'message': message})


@app.route('/api/battle/<int:battle_id>/forfeit', methods=['POST'])
def api_battle_forfeit(battle_id):
    """Forfeit the battle."""
    battle = Battle.query.get_or_404(battle_id)

    # Get the user (logged in or guest)
    user = get_battle_user(battle)
    if not user:
        return jsonify({'success': False, 'error': 'Not in this battle'})

    if battle.status not in ['waiting', 'active']:
        return jsonify({'success': False, 'error': 'Cannot forfeit this battle'})

    is_player1 = user.id == battle.player1_id

    if battle.status == 'waiting':
        # Just cancel if waiting
        battle.status = 'cancelled'
    else:
        # Player loses
        battle.status = 'completed'
        battle.winner_id = battle.player2_id if is_player1 else battle.player1_id
        battle.ended_at = datetime.utcnow()

        # Update stats
        update_battle_stats(user.id, won=False, knockouts=0, damage=0)
        update_battle_stats(battle.winner_id, won=True, knockouts=0, damage=0)

        # Record turn
        turn = BattleTurn(
            battle_id=battle.id,
            turn_number=battle.current_turn,
            player_id=user.id,
            action_type='forfeit',
            message=f"{user.username} forfeited the battle!"
        )
        db.session.add(turn)

    db.session.commit()

    return jsonify({'success': True, 'message': 'Battle forfeited'})


@app.route('/api/battle/<int:battle_id>/turns')
def api_battle_turns(battle_id):
    """Get battle turn log."""
    battle = Battle.query.get_or_404(battle_id)

    # Get the user (logged in or guest)
    user = get_battle_user(battle)
    if not user:
        return jsonify({'success': False, 'error': 'Not in this battle'})

    turns = BattleTurn.query.filter_by(battle_id=battle_id).order_by(
        BattleTurn.turn_number.desc()
    ).limit(20).all()

    turn_data = []
    for turn in turns:
        turn_data.append({
            'turn_number': turn.turn_number,
            'player': turn.player.username if turn.player else 'Unknown',
            'action_type': turn.action_type,
            'message': turn.message,
            'damage': turn.damage_dealt,
            'was_knockout': turn.was_knockout
        })

    return jsonify({'success': True, 'turns': turn_data})


def update_battle_stats(user_id, won, knockouts, damage):
    """Update user's battle statistics."""
    stats = BattleStats.query.filter_by(user_id=user_id).first()

    if not stats:
        stats = BattleStats(user_id=user_id)
        db.session.add(stats)

    stats.total_battles += 1
    stats.total_knockouts += knockouts
    stats.total_damage_dealt += damage

    if won:
        stats.wins += 1
        stats.win_streak += 1
        if stats.win_streak > stats.best_win_streak:
            stats.best_win_streak = stats.win_streak
        # Increase rating
        stats.battle_rating += 25
    else:
        stats.losses += 1
        stats.win_streak = 0
        # Decrease rating (minimum 100)
        stats.battle_rating = max(100, stats.battle_rating - 20)

    db.session.commit()


# ============== Helper Functions ==============

def get_or_create_card(api_card_id):
    """Get card from database or create if not exists."""
    card = Card.query.filter_by(card_id=api_card_id).first()

    if not card:
        # Try TCGdex first
        raw_card = card_lookup.get_card_by_id(api_card_id)
        source = 'tcgdex'

        # If not found in TCGdex, try pokemontcg.io
        if not raw_card:
            raw_card = card_lookup.get_card_pokemontcg(api_card_id)
            if raw_card:
                raw_card['_source'] = 'pokemontcg'
                source = 'pokemontcg'

        if not raw_card:
            return None

        formatted = card_lookup.format_card_data(raw_card)

        # If card is from TCGdex (no prices), try to get prices from pokemontcg.io
        price_market = formatted['prices'].get('market')
        price_low = formatted['prices'].get('low')
        price_mid = formatted['prices'].get('mid')
        price_high = formatted['prices'].get('high')

        if source == 'tcgdex' and not price_market:
            # Try to find prices from pokemontcg.io by searching
            try:
                ptcg_results = card_lookup.search_pokemontcg(formatted['name'], limit=5)
                for ptcg_card in ptcg_results:
                    # Match by name and set number if possible
                    if ptcg_card.get('number') == formatted['number']:
                        ptcg_formatted = card_lookup.format_card_data(ptcg_card)
                        price_market = ptcg_formatted['prices'].get('market') or price_market
                        price_low = ptcg_formatted['prices'].get('low') or price_low
                        price_mid = ptcg_formatted['prices'].get('mid') or price_mid
                        price_high = ptcg_formatted['prices'].get('high') or price_high
                        break
            except Exception as e:
                print(f"Failed to get prices from pokemontcg.io: {e}")

        # Get national dex number if available
        national_dex = None
        if raw_card.get('nationalPokedexNumbers'):
            national_dex = raw_card['nationalPokedexNumbers'][0]
        elif raw_card.get('dexId'):
            national_dex = raw_card['dexId'][0] if raw_card['dexId'] else None

        # Handle HP that might be a string or int
        hp_value = formatted.get('hp', '')
        if isinstance(hp_value, str) and hp_value.isdigit():
            hp_value = int(hp_value)
        elif isinstance(hp_value, int):
            hp_value = hp_value
        else:
            hp_value = None

        card = Card(
            card_id=formatted['id'],
            name=formatted['name'],
            set_name=formatted['set']['name'],
            set_id=formatted['set']['id'],
            number=formatted['number'],
            rarity=formatted.get('rarity'),
            hp=hp_value,
            types=json.dumps(formatted.get('types', [])),
            artist=formatted.get('artist'),
            image_small=formatted['images']['small'],
            image_large=formatted['images']['large'],
            price_market=price_market,
            price_low=price_low,
            price_mid=price_mid,
            price_high=price_high,
            national_dex=national_dex
        )

        db.session.add(card)
        db.session.commit()

    return card


def check_achievements(user, old_total):
    """Check and award achievements after card additions."""
    rank_up = False
    new_total = user.total_cards

    # Check for rank up
    old_rank = None
    new_rank = user.get_rank()

    for rank in RANKS:
        if old_total >= rank['min_cards']:
            old_rank = rank

    if old_rank and new_rank['name'] != old_rank['name']:
        rank_up = True
        achievement = Achievement(
            user_id=user.id,
            achievement_type='rank_up',
            achievement_name=f"Ranked up to {new_rank['name']}!",
            details=json.dumps({'rank': new_rank['name'], 'icon': new_rank['icon']})
        )
        db.session.add(achievement)

    # Check for milestones
    milestones = [10, 50, 100, 250, 500, 1000, 2500, 5000]
    for milestone in milestones:
        if old_total < milestone <= new_total:
            achievement = Achievement(
                user_id=user.id,
                achievement_type='milestone',
                achievement_name=f"Collected {milestone} cards!",
                details=json.dumps({'milestone': milestone})
            )
            db.session.add(achievement)

    # Check for regional dex completion
    regional_progress = user.get_regional_progress()
    for region_id, progress in regional_progress.items():
        if progress['completed']:
            # Check if already has this achievement
            existing = Achievement.query.filter_by(
                user_id=user.id,
                achievement_type='dex_complete',
                achievement_name=f"Completed {progress['name']} Pokédex!"
            ).first()

            if not existing:
                achievement = Achievement(
                    user_id=user.id,
                    achievement_type='dex_complete',
                    achievement_name=f"Completed {progress['name']} Pokédex!",
                    details=json.dumps({'region': region_id})
                )
                db.session.add(achievement)

    db.session.commit()
    return rank_up


# ============== Shop Routes ==============

@app.route('/shop')
@login_required
def shop():
    """Shop page - browse and buy booster packs."""
    # Fetch available sets from Pokemon TCG API (most recent 20)
    raw_sets = card_lookup.get_shop_sets(limit=20)

    sets = []
    for s in raw_sets:
        set_data = {
            'id': s.get('id', ''),
            'name': s.get('name', ''),
            'series': s.get('series', ''),
            'total': s.get('total', 0),
            'releaseDate': s.get('releaseDate', ''),
            'images': {
                'logo': s.get('images', {}).get('logo', ''),
                'symbol': s.get('images', {}).get('symbol', '')
            },
            'price': card_lookup.calculate_pack_price(s.get('id', ''))
        }
        sets.append(set_data)

    return render_template('shop.html', sets=sets, coins=current_user.coins)


@app.route('/api/shop/buy', methods=['POST'])
@login_required
def api_buy_pack():
    """Purchase a booster pack."""
    data = request.get_json()

    if not data or 'set_id' not in data:
        return jsonify({'success': False, 'error': 'No set specified'})

    set_id = data['set_id']

    # Get set info
    set_info = card_lookup.get_set_by_id(set_id)
    if not set_info:
        return jsonify({'success': False, 'error': 'Set not found'})

    # Calculate price
    pack_price = card_lookup.calculate_pack_price(set_id)

    # Check if user has enough coins
    if current_user.coins < pack_price:
        return jsonify({
            'success': False,
            'error': 'Not enough coins',
            'required': pack_price,
            'current': current_user.coins
        })

    # Generate 10 random cards from the set
    cards = card_lookup.generate_pack_cards(set_id, count=10)

    if not cards:
        return jsonify({'success': False, 'error': 'Failed to generate pack cards'})

    # Deduct coins
    current_user.coins -= pack_price

    # Add cards to user's collection
    card_ids = []
    for card_data in cards:
        # Get or create card in database
        card = get_or_create_card(card_data['id'])
        if card:
            card_ids.append(card_data['id'])

            # Check if user already has this card
            user_card = UserCard.query.filter_by(
                user_id=current_user.id,
                card_id=card.id,
                binder_id=None
            ).first()

            if user_card:
                user_card.quantity += 1
            else:
                user_card = UserCard(
                    user_id=current_user.id,
                    card_id=card.id
                )
                db.session.add(user_card)

    # Record purchase
    purchase = ShopPurchase(
        user_id=current_user.id,
        set_id=set_id,
        set_name=set_info.get('name', ''),
        coins_spent=pack_price,
        cards_received=json.dumps(card_ids)
    )
    db.session.add(purchase)

    db.session.commit()

    # Update user stats
    current_user.update_stats()

    return jsonify({
        'success': True,
        'cards': cards,
        'coins_spent': pack_price,
        'coins_remaining': current_user.coins,
        'set_name': set_info.get('name', '')
    })


@app.route('/api/shop/sets')
@login_required
def api_shop_sets():
    """Get available sets for the shop."""
    raw_sets = card_lookup.get_shop_sets(limit=20)

    sets = []
    for s in raw_sets:
        set_data = {
            'id': s.get('id', ''),
            'name': s.get('name', ''),
            'series': s.get('series', ''),
            'total': s.get('total', 0),
            'releaseDate': s.get('releaseDate', ''),
            'images': {
                'logo': s.get('images', {}).get('logo', ''),
                'symbol': s.get('images', {}).get('symbol', '')
            },
            'price': card_lookup.calculate_pack_price(s.get('id', ''))
        }
        sets.append(set_data)

    return jsonify({
        'success': True,
        'sets': sets,
        'coins': current_user.coins
    })


# ============== Run Application ==============

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
