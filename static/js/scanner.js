// FlexDex Card Scanner - Browse & Match Mode

// Switch between camera, search, and browse modes
function switchMode(mode) {
    document.querySelectorAll('.mode-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.mode-content').forEach(content => content.classList.remove('active'));

    document.querySelector(`.mode-tab[onclick="switchMode('${mode}')"]`).classList.add('active');
    document.getElementById(`${mode}-mode`).classList.add('active');

    // Load Pokemon grid when switching to browse mode
    if (mode === 'browse' && window.cardScanner) {
        window.cardScanner.loadPokemonGrid();
    }
}

class CardScanner {
    constructor() {
        this.video = document.getElementById('video-feed');
        this.canvas = document.getElementById('canvas-overlay');
        this.container = document.getElementById('scanner-container');
        this.placeholder = document.getElementById('camera-placeholder');
        this.statusText = document.getElementById('scanner-status');
        this.searchResults = document.getElementById('search-results');
        this.scanResult = document.getElementById('scan-result');
        this.selectedCard = document.getElementById('selected-card');
        this.cardDisplay = document.getElementById('card-display');
        this.ocrStatus = document.getElementById('ocr-status');
        this.pokemonGrid = document.getElementById('pokemon-grid');
        this.browseFilter = document.getElementById('browse-filter');

        this.stream = null;
        this.isScanning = false;
        this.selectedCardData = null;
        this.allPokemon = [];

        this.initButtons();
        this.initSearch();
        this.initBrowseFilter();

        // Show ready message
        if (this.ocrStatus) {
            this.ocrStatus.textContent = 'Ready! Use Browse mode to find your card visually.';
            this.ocrStatus.style.background = '#d4edda';
            setTimeout(() => {
                this.ocrStatus.style.display = 'none';
            }, 3000);
        }
    }

    initButtons() {
        const startBtn = document.getElementById('btn-start-camera');
        const captureBtn = document.getElementById('btn-capture');
        const stopBtn = document.getElementById('btn-stop-camera');

        if (startBtn) startBtn.addEventListener('click', () => this.startCamera());
        if (captureBtn) captureBtn.addEventListener('click', () => this.captureAndScan());
        if (stopBtn) stopBtn.addEventListener('click', () => this.stopCamera());

        const addToBinderBtn = document.getElementById('btn-add-to-binder');
        if (addToBinderBtn) {
            addToBinderBtn.addEventListener('click', () => this.addToBinder());
        }
    }

    initSearch() {
        const searchForm = document.getElementById('search-form');
        if (searchForm) {
            searchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.performSearch();
            });
        }
    }

    initBrowseFilter() {
        if (this.browseFilter) {
            this.browseFilter.addEventListener('input', (e) => {
                this.filterPokemonGrid(e.target.value);
            });
        }
    }

    async loadPokemonGrid() {
        if (!this.pokemonGrid) return;
        if (this.allPokemon.length > 0) {
            // Already loaded, just display
            this.displayPokemonGrid(this.allPokemon);
            return;
        }

        this.pokemonGrid.innerHTML = '<p style="text-align: center; padding: 20px;">Loading Pokemon...</p>';

        try {
            const response = await fetch('/api/pokemon/browse');
            const data = await response.json();

            if (data.success) {
                this.allPokemon = data.pokemon;
                this.displayPokemonGrid(this.allPokemon);
            }
        } catch (error) {
            console.error('Error loading Pokemon:', error);
            this.pokemonGrid.innerHTML = '<p style="text-align: center; color: red;">Failed to load Pokemon</p>';
        }
    }

    displayPokemonGrid(pokemon) {
        if (!this.pokemonGrid) return;

        this.pokemonGrid.innerHTML = '';

        pokemon.forEach(p => {
            const item = document.createElement('div');
            item.className = 'pokemon-grid-item';
            item.onclick = () => this.selectPokemon(p.name);

            item.innerHTML = `
                <img src="${p.sprite}" alt="${p.name}" loading="lazy">
                <span>${p.name}</span>
            `;

            this.pokemonGrid.appendChild(item);
        });
    }

    filterPokemonGrid(query) {
        const filtered = this.allPokemon.filter(p =>
            p.name.toLowerCase().includes(query.toLowerCase())
        );
        this.displayPokemonGrid(filtered);
    }

    async selectPokemon(name) {
        this.statusText.textContent = `Searching for ${name} cards...`;

        // Switch to show results
        this.scanResult.style.display = 'block';
        this.searchResults.innerHTML = '<p style="text-align: center;">Loading cards...</p>';

        try {
            const response = await fetch(`/api/pokemon/search/${encodeURIComponent(name)}`);
            const data = await response.json();

            if (data.success && data.cards && data.cards.length > 0) {
                this.statusText.textContent = `Found ${data.cards.length} ${name} cards`;
                this.displaySearchResults(data.cards);
            } else {
                this.statusText.textContent = `No cards found for ${name}`;
                this.searchResults.innerHTML = '<p style="text-align: center;">No cards found. Try a different Pokemon.</p>';
            }
        } catch (error) {
            console.error('Search error:', error);
            this.statusText.textContent = 'Search failed';
        }
    }

    async startCamera() {
        try {
            const useBackCamera = document.getElementById('use-back-camera')?.checked ?? true;

            const constraints = {
                video: {
                    facingMode: useBackCamera ? 'environment' : 'user',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            };

            this.stream = await navigator.mediaDevices.getUserMedia(constraints);

            this.video.srcObject = this.stream;
            this.video.style.display = 'block';
            this.placeholder.style.display = 'none';
            this.video.play();

            this.statusText.textContent = 'Position card and capture, or use Browse mode to find visually';

            document.getElementById('btn-start-camera').disabled = true;
            document.getElementById('btn-capture').disabled = false;
            document.getElementById('btn-stop-camera').disabled = false;

            this.video.onloadedmetadata = () => {
                this.canvas.width = this.video.videoWidth;
                this.canvas.height = this.video.videoHeight;
            };

        } catch (error) {
            console.error('Camera error:', error);
            this.statusText.textContent = 'Camera access denied. Use Browse or Search mode instead.';
        }
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        this.video.srcObject = null;
        this.video.style.display = 'none';
        this.placeholder.style.display = 'flex';
        this.statusText.textContent = 'Camera stopped';

        document.getElementById('btn-start-camera').disabled = false;
        document.getElementById('btn-capture').disabled = true;
        document.getElementById('btn-stop-camera').disabled = true;
    }

    async captureAndScan() {
        if (this.isScanning) return;

        this.isScanning = true;
        this.container.classList.add('scanning');
        this.statusText.textContent = 'Scanning... (if this fails, try Browse mode)';
        document.getElementById('btn-capture').disabled = true;

        const ctx = this.canvas.getContext('2d');
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        ctx.drawImage(this.video, 0, 0);

        try {
            const imageData = this.canvas.toDataURL('image/png');

            const response = await fetch('/api/ocr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageData })
            });

            const result = await response.json();

            if (result.success && result.card_name && result.card_name.length >= 2) {
                const cardName = result.card_name;
                const cardNumber = result.card_number;

                let statusMsg = `Found: "${cardName}"`;
                if (cardNumber) statusMsg += ` #${cardNumber}`;
                this.statusText.textContent = statusMsg + ' - Searching...';

                await this.searchCardsWithNumber(cardName, cardNumber);
            } else {
                // OCR failed - suggest browse mode
                this.statusText.textContent = 'Could not read card. Try the Browse tab to find it visually!';
                this.showBrowseSuggestion();
            }

        } catch (error) {
            console.error('Scan error:', error);
            this.statusText.textContent = 'Scan failed. Try the Browse tab instead!';
            this.showBrowseSuggestion();
        }

        this.container.classList.remove('scanning');
        this.isScanning = false;
        document.getElementById('btn-capture').disabled = false;
    }

    showBrowseSuggestion() {
        this.searchResults.innerHTML = `
            <div style="background: #e3f2fd; padding: 20px; border-radius: 10px; text-align: center;">
                <p style="font-size: 2em; margin-bottom: 10px;">🔍</p>
                <p style="font-weight: bold; margin-bottom: 10px;">Can't read the card?</p>
                <p style="margin-bottom: 15px;">Use the <strong>Browse</strong> tab to find your Pokemon visually!</p>
                <button onclick="switchMode('browse')" class="pokedex-btn btn-primary">
                    Browse Pokemon
                </button>
            </div>
        `;
        this.scanResult.style.display = 'block';
    }

    async searchCardsWithNumber(name, number) {
        try {
            let url = `/api/search?q=${encodeURIComponent(name)}`;

            const response = await fetch(url);
            const data = await response.json();

            if (data.success && data.cards && data.cards.length > 0) {
                let cards = data.cards;

                if (number) {
                    const exactMatch = cards.find(c => {
                        const cardNum = String(c.number).replace(/^0+/, '');
                        const searchNum = number.replace(/^0+/, '');
                        return cardNum === searchNum;
                    });

                    if (exactMatch) {
                        cards = [exactMatch, ...cards.filter(c => c.id !== exactMatch.id)];
                        this.statusText.textContent = `Exact match found: ${exactMatch.name} #${exactMatch.number}`;
                    }
                }

                this.displaySearchResults(cards);
            } else {
                this.statusText.textContent = `No cards found for "${name}". Try Browse mode!`;
                this.showBrowseSuggestion();
            }

        } catch (error) {
            console.error('Search error:', error);
            this.statusText.textContent = 'Search failed. Please try again.';
        }
    }

    async performSearch() {
        const query = document.getElementById('search-input').value.trim();
        if (query.length < 2) {
            this.statusText.textContent = 'Enter at least 2 characters';
            return;
        }
        this.statusText.textContent = `Searching for "${query}"...`;
        await this.searchCardsWithNumber(query, '');
    }

    displaySearchResults(cards) {
        this.searchResults.innerHTML = '';

        cards.forEach((card, index) => {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            if (index === 0) item.classList.add('best-match');
            item.onclick = () => this.selectCard(card);

            const priceHtml = card.prices && card.prices.market
                ? `<div class="card-price">$${card.prices.market.toFixed(2)}</div>`
                : '';

            item.innerHTML = `
                <img src="${card.images.small}" alt="${card.name}">
                <div class="search-result-info">
                    <div class="search-result-name">${card.name}</div>
                    <div class="search-result-set">${card.set.name} - #${card.number}</div>
                    ${card.rarity ? `<span class="card-tag rarity">${card.rarity}</span>` : ''}
                </div>
                <div style="text-align: right;">
                    ${priceHtml}
                </div>
            `;

            this.searchResults.appendChild(item);
        });

        this.scanResult.style.display = 'block';
    }

    selectCard(card) {
        this.selectedCardData = card;

        const typeTags = (card.types || [])
            .map(t => `<span class="card-tag type-${t.toLowerCase()}">${t}</span>`)
            .join('');

        const priceHtml = card.prices && card.prices.market
            ? `<div class="card-price">Market: $${card.prices.market.toFixed(2)}</div>`
            : '';

        const attacksHtml = (card.attacks || []).map(attack => `
            <div style="background: #f5f5f5; padding: 8px; border-radius: 5px; margin: 5px 0;">
                <strong>${attack.name}</strong>
                ${attack.damage ? `<span style="float: right;">${attack.damage}</span>` : ''}
            </div>
        `).join('');

        this.cardDisplay.innerHTML = `
            <img src="${card.images.large || card.images.small}" alt="${card.name}">
            <div class="card-info">
                <div class="card-name">${card.name}</div>
                <div class="card-meta">
                    ${card.hp ? `<span class="card-tag">HP ${card.hp}</span>` : ''}
                    ${typeTags}
                    ${card.rarity ? `<span class="card-tag rarity">${card.rarity}</span>` : ''}
                </div>
                <p><strong>Set:</strong> ${card.set.name}</p>
                <p><strong>Number:</strong> ${card.number}</p>
                ${card.artist ? `<p><strong>Artist:</strong> ${card.artist}</p>` : ''}
                ${attacksHtml ? `<div style="margin-top: 10px;"><strong>Attacks:</strong>${attacksHtml}</div>` : ''}
                ${priceHtml}
            </div>
        `;

        this.selectedCard.style.display = 'block';
        this.cardDisplay.classList.remove('card-reveal');
        void this.cardDisplay.offsetWidth;
        this.cardDisplay.classList.add('card-reveal');

        const addBtn = document.getElementById('btn-add-to-binder');
        if (addBtn && typeof isAuthenticated !== 'undefined' && isAuthenticated) {
            addBtn.disabled = false;
        }

        this.selectedCard.scrollIntoView({ behavior: 'smooth' });
    }

    async addToBinder() {
        if (!this.selectedCardData) {
            alert('Please select a card first');
            return;
        }

        try {
            const response = await fetch('/api/binder/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ card_id: this.selectedCardData.id })
            });

            const data = await response.json();

            if (data.success) {
                alert('Card added to your binder!');
            } else {
                alert(data.error || 'Failed to add card');
            }

        } catch (error) {
            console.error('Error adding to binder:', error);
            alert('Error adding card to binder');
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('video-feed')) {
        window.cardScanner = new CardScanner();
    }
});
