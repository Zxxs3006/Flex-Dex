import requests
from typing import Optional, Dict, List, Any


class CardLookup:
    """Handles Pokemon card lookup using TCGdex API with pokemontcg.io fallback."""

    TCGDEX_URL = 'https://api.tcgdex.net/v2/en'
    POKEMONTCG_URL = 'https://api.pokemontcg.io/v2'

    def __init__(self, api_key: str = ''):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'FlexDex/1.0'

    # ============== TCGdex Methods (Primary) ==============

    def search_by_name(self, name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search TCGdex by name."""
        name = name.strip()
        if not name:
            return []

        try:
            response = self.session.get(
                f'{self.TCGDEX_URL}/cards',
                params={'name': name},
                timeout=15
            )
            response.raise_for_status()
            cards = response.json()

            detailed_cards = []
            for card in cards[:limit]:
                card_id = card.get('id')
                if card_id:
                    full_card = self.get_card_by_id(card_id)
                    if full_card:
                        detailed_cards.append(full_card)

            return detailed_cards
        except requests.RequestException as e:
            print(f"TCGdex API request failed: {e}")
            return []

    def get_card_by_id(self, card_id: str) -> Optional[Dict[str, Any]]:
        """Get card from TCGdex by ID."""
        try:
            response = self.session.get(
                f'{self.TCGDEX_URL}/cards/{card_id}',
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"TCGdex API request failed: {e}")
            return None

    # ============== PokemonTCG.io Methods (Fallback) ==============

    def search_pokemontcg(self, name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search pokemontcg.io by name (fallback)."""
        name = name.strip()
        if not name:
            return []

        try:
            headers = {'X-Api-Key': self.api_key} if self.api_key else {}
            # Use wildcard search for better matching
            response = self.session.get(
                f'{self.POKEMONTCG_URL}/cards',
                params={'q': f'name:{name}*', 'pageSize': limit},
                headers=headers,
                timeout=20
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except requests.RequestException as e:
            print(f"PokemonTCG API request failed: {e}")
            return []

    def get_card_pokemontcg(self, card_id: str) -> Optional[Dict[str, Any]]:
        """Get card from pokemontcg.io by ID."""
        try:
            headers = {'X-Api-Key': self.api_key} if self.api_key else {}
            response = self.session.get(
                f'{self.POKEMONTCG_URL}/cards/{card_id}',
                headers=headers,
                timeout=20
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data')
        except requests.RequestException as e:
            print(f"PokemonTCG API request failed: {e}")
            return None

    # ============== Combined Search with Fallback ==============

    def search_fuzzy(self, name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search with TCGdex first, fallback to pokemontcg.io if no results."""
        # Try TCGdex first
        results = self.search_by_name(name, limit)

        # Clean name and retry TCGdex if needed
        if not results:
            clean_name = ''.join(c for c in name if c.isalnum() or c.isspace())
            if clean_name != name:
                results = self.search_by_name(clean_name, limit)

        # Fallback to pokemontcg.io if still no results
        if not results:
            print(f"TCGdex returned no results for '{name}', trying pokemontcg.io...")
            pokemontcg_results = self.search_pokemontcg(name, limit)
            if pokemontcg_results:
                # Mark these as from pokemontcg.io for formatting
                for card in pokemontcg_results:
                    card['_source'] = 'pokemontcg'
                return pokemontcg_results

        return results

    # ============== Format Card Data ==============

    def format_card_data(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """Format card data from either API to a standard format."""
        # Check if card is from pokemontcg.io
        if card.get('_source') == 'pokemontcg' or 'images' in card:
            return self._format_pokemontcg_card(card)
        else:
            return self._format_tcgdex_card(card)

    def _format_tcgdex_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """Format TCGdex card data."""
        prices = self._extract_prices(card)
        image_base = card.get('image', '')

        return {
            'id': card.get('id', ''),
            'name': card.get('name', ''),
            'supertype': card.get('category', ''),
            'subtypes': [card.get('stage', '')] if card.get('stage') else [],
            'hp': card.get('hp', ''),
            'types': card.get('types', []),
            'set': {
                'id': card.get('set', {}).get('id', ''),
                'name': card.get('set', {}).get('name', ''),
                'series': '',
                'releaseDate': '',
                'logo': card.get('set', {}).get('logo', ''),
                'symbol': card.get('set', {}).get('symbol', '')
            },
            'number': card.get('localId', ''),
            'rarity': card.get('rarity', ''),
            'artist': card.get('illustrator', ''),
            'images': {
                'small': f"{image_base}/low.webp" if image_base else '',
                'large': f"{image_base}/high.webp" if image_base else ''
            },
            'attacks': card.get('attacks', []),
            'weaknesses': card.get('weaknesses', []),
            'resistances': card.get('resistances', []),
            'retreatCost': ['*'] * card.get('retreat', 0) if card.get('retreat') else [],
            'abilities': card.get('abilities', []),
            'prices': prices,
            'tcgplayer_url': self._get_tcgplayer_url(card),
            'cardmarket_url': self._get_cardmarket_url(card),
            'psa_ebay_urls': self._get_psa_ebay_urls(card),
            'dex_id': card.get('dexId', [None])[0] if card.get('dexId') else None,
            'regulation_mark': card.get('regulationMark', ''),
            'legal': card.get('legal', {}),
            '_source': 'tcgdex'
        }

    def _format_pokemontcg_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """Format pokemontcg.io card data."""
        # Extract prices from tcgplayer data
        prices = {
            'market': None,
            'low': None,
            'mid': None,
            'high': None,
            'source': 'tcgplayer',
            'currency': 'USD',
            'psa_prices': {}
        }

        tcgplayer = card.get('tcgplayer', {})
        if tcgplayer and tcgplayer.get('prices'):
            # Get first available price type (normal, holofoil, etc.)
            for price_type, price_data in tcgplayer.get('prices', {}).items():
                if price_data:
                    prices['market'] = price_data.get('market')
                    prices['low'] = price_data.get('low')
                    prices['mid'] = price_data.get('mid')
                    prices['high'] = price_data.get('high')
                    break

        images = card.get('images', {})
        set_data = card.get('set', {})

        return {
            'id': card.get('id', ''),
            'name': card.get('name', ''),
            'supertype': card.get('supertype', ''),
            'subtypes': card.get('subtypes', []),
            'hp': card.get('hp', ''),
            'types': card.get('types', []),
            'set': {
                'id': set_data.get('id', ''),
                'name': set_data.get('name', ''),
                'series': set_data.get('series', ''),
                'releaseDate': set_data.get('releaseDate', ''),
                'logo': set_data.get('images', {}).get('logo', ''),
                'symbol': set_data.get('images', {}).get('symbol', '')
            },
            'number': card.get('number', ''),
            'rarity': card.get('rarity', ''),
            'artist': card.get('artist', ''),
            'images': {
                'small': images.get('small', ''),
                'large': images.get('large', '')
            },
            'attacks': card.get('attacks', []),
            'weaknesses': card.get('weaknesses', []),
            'resistances': card.get('resistances', []),
            'retreatCost': card.get('retreatCost', []),
            'abilities': card.get('abilities', []),
            'prices': prices,
            'tcgplayer_url': tcgplayer.get('url', self._get_tcgplayer_url(card)),
            'cardmarket_url': card.get('cardmarket', {}).get('url', self._get_cardmarket_url(card)),
            'psa_ebay_urls': self._get_psa_ebay_urls(card),
            'dex_id': card.get('nationalPokedexNumbers', [None])[0] if card.get('nationalPokedexNumbers') else None,
            'regulation_mark': card.get('regulationMark', ''),
            'legal': card.get('legalities', {}),
            '_source': 'pokemontcg'
        }

    def _extract_prices(self, card: Dict[str, Any]) -> Dict[str, Any]:
        prices = {
            'market': None,
            'low': None,
            'mid': None,
            'high': None,
            'source': None,
            'currency': 'USD',
            'psa_prices': {}
        }
        return prices

    def _get_tcgplayer_url(self, card: Dict[str, Any]) -> str:
        name = card.get('name', '')
        set_name = card.get('set', {}).get('name', '')
        if name:
            search_query = f"{name} {set_name}".strip()
            return f"https://www.tcgplayer.com/search/pokemon/product?q={search_query.replace(' ', '+')}"
        return ''

    def _get_cardmarket_url(self, card: Dict[str, Any]) -> str:
        name = card.get('name', '')
        if name:
            return f"https://www.cardmarket.com/en/Pokemon/Products/Search?searchString={name.replace(' ', '+')}"
        return ''

    def _get_psa_ebay_urls(self, card: Dict[str, Any]) -> Dict[str, str]:
        name = card.get('name', '')
        set_name = card.get('set', {}).get('name', '')
        card_number = card.get('localId', '') or card.get('number', '')

        urls = {}
        if name:
            base_query = f"PSA {name} {set_name} {card_number} pokemon".strip().replace(' ', '+')
            urls['sold'] = f"https://www.ebay.com/sch/i.html?_nkw={base_query}&LH_Complete=1&LH_Sold=1&_sop=13"
            psa10_query = f"PSA+10+{name}+{set_name}+{card_number}+pokemon".replace(' ', '+')
            urls['psa_10'] = f"https://www.ebay.com/sch/i.html?_nkw={psa10_query}&LH_Complete=1&LH_Sold=1&_sop=13"
            psa9_query = f"PSA+9+{name}+{set_name}+{card_number}+pokemon".replace(' ', '+')
            urls['psa_9'] = f"https://www.ebay.com/sch/i.html?_nkw={psa9_query}&LH_Complete=1&LH_Sold=1&_sop=13"
            cgc_query = f"CGC+{name}+{set_name}+{card_number}+pokemon".replace(' ', '+')
            urls['cgc'] = f"https://www.ebay.com/sch/i.html?_nkw={cgc_query}&LH_Complete=1&LH_Sold=1&_sop=13"
        return urls

    def get_sets(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            response = self.session.get(f'{self.TCGDEX_URL}/sets', timeout=15)
            response.raise_for_status()
            sets = response.json()
            return sets[:limit]
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return []

    def get_all_sets_list(self) -> List[Dict[str, Any]]:
        try:
            response = self.session.get(f'{self.TCGDEX_URL}/sets', timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return []
