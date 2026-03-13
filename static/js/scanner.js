// FlexDex Card Scanner - Using OCR.space API

// Switch between camera and search modes
function switchMode(mode) {
    document.querySelectorAll('.mode-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.mode-content').forEach(content => content.classList.remove('active'));

    document.querySelector(`.mode-tab[onclick="switchMode('${mode}')"]`).classList.add('active');
    document.getElementById(`${mode}-mode`).classList.add('active');
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

        this.stream = null;
        this.isScanning = false;
        this.selectedCardData = null;

        this.initButtons();
        this.initSearch();

        // Show ready message
        if (this.ocrStatus) {
            this.ocrStatus.textContent = 'Scanner ready! Position your card in the frame.';
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

            this.statusText.textContent = 'Position the Pokemon card so it fills most of the frame';

            document.getElementById('btn-start-camera').disabled = true;
            document.getElementById('btn-capture').disabled = false;
            document.getElementById('btn-stop-camera').disabled = false;

            // Setup canvas
            this.video.onloadedmetadata = () => {
                this.canvas.width = this.video.videoWidth;
                this.canvas.height = this.video.videoHeight;
            };

        } catch (error) {
            console.error('Camera error:', error);
            this.statusText.textContent = 'Camera access denied. Please allow camera permissions.';
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
        this.statusText.textContent = 'Scanning card... (this may take a few seconds)';
        document.getElementById('btn-capture').disabled = true;

        // Capture full frame
        const ctx = this.canvas.getContext('2d');
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        ctx.drawImage(this.video, 0, 0);

        try {
            // Convert to base64
            const imageData = this.canvas.toDataURL('image/png');

            this.statusText.textContent = 'Analyzing card with OCR...';

            // Send to backend OCR API
            const response = await fetch('/api/ocr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageData })
            });

            const result = await response.json();

            if (result.success) {
                const cardName = result.card_name;
                const cardNumber = result.card_number;

                console.log('OCR Result:', result.raw_text);
                console.log('Detected Name:', cardName);
                console.log('Detected Number:', cardNumber);

                if (cardName && cardName.length >= 2) {
                    let statusMsg = `Found: "${cardName}"`;
                    if (cardNumber) {
                        statusMsg += ` #${cardNumber}`;
                    }
                    this.statusText.textContent = statusMsg + ' - Searching...';

                    // Search with both name and number
                    await this.searchCardsWithNumber(cardName, cardNumber);
                } else {
                    this.statusText.textContent = 'Could not read card. Try better lighting or use manual search.';
                    this.showRawOCR(result.raw_text);
                }
            } else {
                this.statusText.textContent = `Scan failed: ${result.error}. Try manual search.`;
            }

        } catch (error) {
            console.error('Scan error:', error);
            this.statusText.textContent = 'Error scanning. Please try again.';
        }

        this.container.classList.remove('scanning');
        this.isScanning = false;
        document.getElementById('btn-capture').disabled = false;
    }

    showRawOCR(text) {
        // Show raw OCR text so user can manually search
        if (text) {
            this.searchResults.innerHTML = `
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <p style="color: #666; margin-bottom: 10px;">Raw text detected:</p>
                    <pre style="white-space: pre-wrap; font-size: 12px; color: #333;">${text}</pre>
                    <p style="color: #666; margin-top: 10px;">Try typing the Pokemon name in the Search tab.</p>
                </div>
            `;
            this.scanResult.style.display = 'block';
        }
    }

    async searchCardsWithNumber(name, number) {
        try {
            let url = `/api/search?q=${encodeURIComponent(name)}`;

            const response = await fetch(url);
            const data = await response.json();

            if (data.success && data.cards && data.cards.length > 0) {
                let cards = data.cards;

                // If we have a number, try to find exact match
                if (number) {
                    const exactMatch = cards.find(c => {
                        const cardNum = String(c.number).replace(/^0+/, '');
                        const searchNum = number.replace(/^0+/, '');
                        return cardNum === searchNum;
                    });

                    if (exactMatch) {
                        // Put exact match first
                        cards = [exactMatch, ...cards.filter(c => c.id !== exactMatch.id)];
                        this.statusText.textContent = `Exact match found: ${exactMatch.name} #${exactMatch.number}`;
                    }
                }

                this.displaySearchResults(cards);
            } else {
                this.statusText.textContent = `No cards found for "${name}"`;
                this.searchResults.innerHTML = '<p style="text-align:center;">No results. Try manual search.</p>';
                this.scanResult.style.display = 'block';
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
    // Initialize scanner
    if (document.getElementById('video-feed')) {
        window.cardScanner = new CardScanner();
    }
});
