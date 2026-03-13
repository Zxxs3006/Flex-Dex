// Pokédex Card Scanner - Web Version with Camera & Tesseract.js OCR

let tesseractWorker = null;
let ocrReady = false;

// Initialize Tesseract.js OCR engine
async function initOCR() {
    const statusEl = document.getElementById('ocr-status');

    try {
        statusEl.textContent = 'Loading OCR engine... (this may take a moment)';
        statusEl.style.background = '#fff3cd';

        tesseractWorker = await Tesseract.createWorker('eng', 1, {
            logger: m => {
                if (m.status === 'recognizing text') {
                    statusEl.textContent = `Processing: ${Math.round(m.progress * 100)}%`;
                }
            }
        });

        ocrReady = true;
        statusEl.textContent = 'OCR ready! You can now scan cards.';
        statusEl.style.background = '#d4edda';

        setTimeout(() => {
            statusEl.style.display = 'none';
        }, 3000);

    } catch (error) {
        console.error('OCR init error:', error);
        statusEl.textContent = 'OCR failed to load. Use search mode instead.';
        statusEl.style.background = '#f8d7da';
    }
}

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

        this.stream = null;
        this.isScanning = false;
        this.selectedCardData = null;

        this.initButtons();
        this.initSearch();
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

            this.statusText.textContent = 'Camera active - Position card and click "Capture & Scan"';

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

        if (!ocrReady) {
            this.statusText.textContent = 'OCR not ready yet. Please wait...';
            return;
        }

        this.isScanning = true;
        this.container.classList.add('scanning');
        this.statusText.textContent = 'Scanning card...';
        document.getElementById('btn-capture').disabled = true;

        // Capture frame
        const ctx = this.canvas.getContext('2d');
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        ctx.drawImage(this.video, 0, 0);

        try {
            // Crop to top portion where card name appears
            const cropHeight = Math.floor(this.canvas.height * 0.2);
            const croppedCanvas = document.createElement('canvas');
            croppedCanvas.width = this.canvas.width;
            croppedCanvas.height = cropHeight;
            const croppedCtx = croppedCanvas.getContext('2d');
            croppedCtx.drawImage(this.canvas, 0, 0, this.canvas.width, cropHeight, 0, 0, this.canvas.width, cropHeight);

            // Run OCR
            this.statusText.textContent = 'Reading text...';
            const result = await tesseractWorker.recognize(croppedCanvas);
            const extractedText = result.data.text.trim();

            console.log('OCR Result:', extractedText);

            if (extractedText) {
                // Clean up the text - get first line, remove special chars
                let cardName = extractedText.split('\n')[0].trim();
                cardName = cardName.replace(/[^a-zA-Z\s\-\']/g, '').trim();

                // Remove common Pokemon card words
                const removeWords = ['BASIC', 'STAGE', 'HP', 'GX', 'EX', 'VMAX', 'VSTAR'];
                removeWords.forEach(word => {
                    cardName = cardName.replace(new RegExp(word + '$', 'i'), '').trim();
                });

                if (cardName.length >= 2) {
                    this.statusText.textContent = `Detected: "${cardName}" - Searching...`;
                    await this.searchCards(cardName);
                } else {
                    this.statusText.textContent = 'Could not read card name. Try better lighting or positioning.';
                }
            } else {
                this.statusText.textContent = 'No text detected. Make sure the card name is visible.';
            }

        } catch (error) {
            console.error('Scan error:', error);
            this.statusText.textContent = 'Error scanning. Please try again.';
        }

        this.container.classList.remove('scanning');
        this.isScanning = false;
        document.getElementById('btn-capture').disabled = false;
    }

    async performSearch() {
        const query = document.getElementById('search-input').value.trim();
        if (query.length < 2) {
            this.statusText.textContent = 'Enter at least 2 characters';
            return;
        }
        await this.searchCards(query);
    }

    async searchCards(query) {
        try {
            const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            if (data.success && data.cards && data.cards.length > 0) {
                this.displaySearchResults(data.cards);
                this.statusText.textContent = `Found ${data.cards.length} card(s) for "${query}"`;
            } else {
                this.statusText.textContent = `No cards found for "${query}"`;
                this.searchResults.innerHTML = '<p style="text-align:center;">No results. Try a different search.</p>';
                this.scanResult.style.display = 'block';
            }

        } catch (error) {
            console.error('Search error:', error);
            this.statusText.textContent = 'Search failed. Please try again.';
        }
    }

    displaySearchResults(cards) {
        this.searchResults.innerHTML = '';

        cards.forEach(card => {
            const item = document.createElement('div');
            item.className = 'search-result-item';
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
    // Initialize OCR engine
    if (typeof Tesseract !== 'undefined') {
        initOCR();
    } else {
        const statusEl = document.getElementById('ocr-status');
        if (statusEl) {
            statusEl.textContent = 'OCR library not loaded. Use search mode.';
            statusEl.style.background = '#f8d7da';
        }
    }

    // Initialize scanner
    if (document.getElementById('video-feed')) {
        window.cardScanner = new CardScanner();
    }
});
