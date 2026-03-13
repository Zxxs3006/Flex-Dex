import requests
from typing import Optional, Dict, List, Any


class CardLookup:
    """Handles Pokemon card lookup using the Pokemon TCG API."""

    BASE_URL = 'https://api.pokemontcg.io/v2'

    def __init__(self, api_key: str = ''):
        """
        Initialize the card lookup service.

        Args:
            api_key: Optional API key for higher rate limits
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'FlexDex/1.0'
        if api_key:
            self.session.headers['X-Api-Key'] = api_key

    def search_by_name(self, name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for cards by name.

        Args:
            name: Card name to search for
            limit: Maximum number of results

        Returns:
            List of matching card data dictionaries
        """
        name = name.strip()
        if not name:
            return []

        try:
            response = self.session.get(
                f'{self.BASE_URL}/cards',
                params={
                    'q': f'name:"{name}"',
                    'pageSize': limit,
                    'orderBy': '-set.releaseDate'
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return []

    def get_card_by_id(self, card_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific card by its ID.

        Args:
            card_id: The Pokemon TCG card ID

        Returns:
            Card data dictionary or None
        """
        try:
            response = self.session.get(
                f'{self.BASE_URL}/cards/{card_id}',
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data')
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return None

    def search_fuzzy(self, name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Perform a fuzzy search for cards.

        Args:
            name: Partial or approximate card name
            limit: Maximum number of results

        Returns:
            List of matching card data dictionaries
        """
        name = name.strip()
        if not name:
            return []

        try:
            # Use wildcard search for fuzzy matching
            response = self.session.get(
                f'{self.BASE_URL}/cards',
                params={
                    'q': f'name:"{name}*"',
                    'pageSize': limit,
                    'orderBy': '-set.releaseDate'
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return []

    def format_card_data(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format raw API card data into a cleaner structure.

        Args:
            card: Raw card data from API

        Returns:
            Formatted card dictionary
        """
        prices = self._extract_prices(card)

        return {
            'id': card.get('id', ''),
            'name': card.get('name', ''),
            'supertype': card.get('supertype', ''),
            'subtypes': card.get('subtypes', []),
            'hp': card.get('hp', ''),
            'types': card.get('types', []),
            'set': {
                'id': card.get('set', {}).get('id', ''),
                'name': card.get('set', {}).get('name', ''),
                'series': card.get('set', {}).get('series', ''),
                'releaseDate': card.get('set', {}).get('releaseDate', ''),
                'logo': card.get('set', {}).get('images', {}).get('logo', ''),
                'symbol': card.get('set', {}).get('images', {}).get('symbol', '')
            },
            'number': card.get('number', ''),
            'rarity': card.get('rarity', ''),
            'artist': card.get('artist', ''),
            'images': {
                'small': card.get('images', {}).get('small', ''),
                'large': card.get('images', {}).get('large', '')
            },
            'attacks': card.get('attacks', []),
            'weaknesses': card.get('weaknesses', []),
            'resistances': card.get('resistances', []),
            'retreatCost': card.get('retreatCost', []),
            'abilities': card.get('abilities', []),
            'prices': prices,
            'tcgplayer_url': self._get_tcgplayer_url(card),
            'cardmarket_url': self._get_cardmarket_url(card),
            'psa_ebay_urls': self._get_psa_ebay_urls(card),
            'dex_id': card.get('nationalPokedexNumbers', [None])[0] if card.get('nationalPokedexNumbers') else None,
            'regulation_mark': card.get('regulationMark', ''),
            'legal': card.get('legalities', {})
        }

    def _extract_prices(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract price information from card data.

        Args:
            card: Raw card data

        Returns:
            Dictionary with price information
        """
        prices = {
            'market': None,
            'low': None,
            'mid': None,
            'high': None,
            'source': None,
            'currency': 'USD',
            'psa_prices': {}
        }

        # Try TCGPlayer prices first
        tcgplayer = card.get('tcgplayer', {})
        if tcgplayer:
            tcg_prices = tcgplayer.get('prices', {})
            # Check different variants
            for variant in ['holofoil', 'reverseHolofoil', 'normal', '1stEditionHolofoil', 'unlimited']:
                if variant in tcg_prices:
                    variant_prices = tcg_prices[variant]
                    prices['market'] = variant_prices.get('market')
                    prices['low'] = variant_prices.get('low')
                    prices['mid'] = variant_prices.get('mid')
                    prices['high'] = variant_prices.get('high')
                    prices['source'] = 'TCGPlayer'
                    prices['currency'] = 'USD'
                    break

        # Fall back to Cardmarket if no TCGPlayer prices
        if prices['market'] is None:
            cardmarket = card.get('cardmarket', {})
            if cardmarket:
                cm_prices = cardmarket.get('prices', {})
                prices['market'] = cm_prices.get('averageSellPrice')
                prices['low'] = cm_prices.get('lowPrice')
                prices['mid'] = cm_prices.get('trendPrice')
                prices['high'] = cm_prices.get('avg30')
                prices['source'] = 'Cardmarket'
                prices['currency'] = 'EUR'

        return prices

    def _get_tcgplayer_url(self, card: Dict[str, Any]) -> str:
        """Generate TCGPlayer URL for a card."""
        tcgplayer = card.get('tcgplayer', {})
        if tcgplayer:
            return tcgplayer.get('url', '')
        # Fallback to search
        name = card.get('name', '')
        set_name = card.get('set', {}).get('name', '')
        if name:
            search_query = f"{name} {set_name}".strip()
            return f"https://www.tcgplayer.com/search/pokemon/product?q={search_query.replace(' ', '+')}"
        return ''

    def _get_cardmarket_url(self, card: Dict[str, Any]) -> str:
        """Generate Cardmarket URL for a card."""
        cardmarket = card.get('cardmarket', {})
        if cardmarket:
            return cardmarket.get('url', '')
        # Fallback to search
        name = card.get('name', '')
        if name:
            return f"https://www.cardmarket.com/en/Pokemon/Products/Search?searchString={name.replace(' ', '+')}"
        return ''

    def _get_psa_ebay_urls(self, card: Dict[str, Any]) -> Dict[str, str]:
        """Generate eBay search URLs for PSA graded versions of the card."""
        name = card.get('name', '')
        set_name = card.get('set', {}).get('name', '')
        card_number = card.get('number', '')

        urls = {}
        if name:
            # Build search query
            base_query = f"PSA {name} {set_name} {card_number} pokemon".strip()
            base_query = base_query.replace(' ', '+')

            # Sold listings (actual prices)
            urls['sold'] = f"https://www.ebay.com/sch/i.html?_nkw={base_query}&LH_Complete=1&LH_Sold=1&_sop=13"

            # PSA 10 specifically
            psa10_query = f"PSA+10+{name}+{set_name}+{card_number}+pokemon".replace(' ', '+')
            urls['psa_10'] = f"https://www.ebay.com/sch/i.html?_nkw={psa10_query}&LH_Complete=1&LH_Sold=1&_sop=13"

            # PSA 9
            psa9_query = f"PSA+9+{name}+{set_name}+{card_number}+pokemon".replace(' ', '+')
            urls['psa_9'] = f"https://www.ebay.com/sch/i.html?_nkw={psa9_query}&LH_Complete=1&LH_Sold=1&_sop=13"

            # CGC graded
            cgc_query = f"CGC+{name}+{set_name}+{card_number}+pokemon".replace(' ', '+')
            urls['cgc'] = f"https://www.ebay.com/sch/i.html?_nkw={cgc_query}&LH_Complete=1&LH_Sold=1&_sop=13"

        return urls

    def get_sets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get a list of all Pokemon TCG sets.

        Args:
            limit: Maximum number of sets to return

        Returns:
            List of set data dictionaries
        """
        try:
            response = self.session.get(
                f'{self.BASE_URL}/sets',
                params={'pageSize': limit, 'orderBy': '-releaseDate'},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return []

    def search_by_set(self, set_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all cards from a specific set.

        Args:
            set_id: The set ID to search
            limit: Maximum number of results

        Returns:
            List of card data dictionaries
        """
        try:
            response = self.session.get(
                f'{self.BASE_URL}/cards',
                params={
                    'q': f'set.id:{set_id}',
                    'pageSize': limit
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return []

    def get_all_sets_list(self) -> List[Dict[str, Any]]:
        """
        Get a simple list of all sets with basic info.

        Returns:
            List of set dictionaries
        """
        return self.get_sets(limit=250)
