// FlexDex Card Scanner - Smart OCR with Auto-Crop

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
        statusEl.textContent = 'OCR ready! Position your card in the frame.';
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

// Image preprocessing for better OCR
function preprocessImage(canvas) {
    const ctx = canvas.getContext('2d');
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;

    // Convert to grayscale and increase contrast
    for (let i = 0; i < data.length; i += 4) {
        // Grayscale
        const avg = (data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114);

        // Increase contrast
        let contrast = 1.5;
        let newVal = ((avg - 128) * contrast) + 128;
        newVal = Math.max(0, Math.min(255, newVal));

        // Threshold for cleaner text
        newVal = newVal > 140 ? 255 : 0;

        data[i] = newVal;
        data[i + 1] = newVal;
        data[i + 2] = newVal;
    }

    ctx.putImageData(imageData, 0, 0);
    return canvas;
}

// Crop specific region from canvas
function cropRegion(sourceCanvas, x, y, width, height) {
    const croppedCanvas = document.createElement('canvas');
    croppedCanvas.width = width;
    croppedCanvas.height = height;
    const ctx = croppedCanvas.getContext('2d');
    ctx.drawImage(sourceCanvas, x, y, width, height, 0, 0, width, height);
    return croppedCanvas;
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

        if (!ocrReady) {
            this.statusText.textContent = 'OCR not ready yet. Please wait...';
            return;
        }

        this.isScanning = true;
        this.container.classList.add('scanning');
        this.statusText.textContent = 'Analyzing card...';
        document.getElementById('btn-capture').disabled = true;

        // Capture full frame
        const ctx = this.canvas.getContext('2d');
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        ctx.drawImage(this.video, 0, 0);

        try {
            // Pokemon card layout:
            // - Name is at TOP (roughly top 12% of card)
            // - Card number is at BOTTOM LEFT (bottom 8%, left 30%)

            const w = this.canvas.width;
            const h = this.canvas.height;

            // Crop NAME region (top portion, centered)
            const nameRegion = cropRegion(this.canvas,
                Math.floor(w * 0.1),  // 10% from left
                Math.floor(h * 0.02), // 2% from top
                Math.floor(w * 0.8),  // 80% width
                Math.floor(h * 0.12)  // 12% height
            );
            const processedName = preprocessImage(nameRegion);

            // Crop NUMBER region (bottom left)
            const numberRegion = cropRegion(this.canvas,
                Math.floor(w * 0.02), // 2% from left
                Math.floor(h * 0.88), // 88% from top
                Math.floor(w * 0.35), // 35% width
                Math.floor(h * 0.10)  // 10% height
            );
            const processedNumber = preprocessImage(numberRegion);

            this.statusText.textContent = 'Reading card name...';

            // OCR on name region
            const nameResult = await tesseractWorker.recognize(processedName);
            let cardName = this.cleanCardName(nameResult.data.text);

            this.statusText.textContent = 'Reading card number...';

            // OCR on number region
            const numberResult = await tesseractWorker.recognize(processedNumber);
            let cardNumber = this.cleanCardNumber(numberResult.data.text);

            console.log('Detected Name:', cardName);
            console.log('Detected Number:', cardNumber);

            if (cardName.length >= 2) {
                let statusMsg = `Found: "${cardName}"`;
                if (cardNumber) {
                    statusMsg += ` #${cardNumber}`;
                }
                this.statusText.textContent = statusMsg + ' - Searching...';

                // Search with both name and number for better accuracy
                await this.searchCardsWithNumber(cardName, cardNumber);
            } else {
                this.statusText.textContent = 'Could not read card. Try better lighting or use manual search.';
            }

        } catch (error) {
            console.error('Scan error:', error);
            this.statusText.textContent = 'Error scanning. Please try again.';
        }

        this.container.classList.remove('scanning');
        this.isScanning = false;
        document.getElementById('btn-capture').disabled = false;
    }

    cleanCardName(text) {
        if (!text) return '';

        // Get first line, clean it up
        let name = text.split('\n')[0].trim();

        // Remove common OCR artifacts and Pokemon card text
        name = name.replace(/[^a-zA-Z\s\-\'éÉ]/g, '').trim();

        // Remove Pokemon card keywords
        const removeWords = ['BASIC', 'STAGE', 'HP', 'GX', 'EX', 'VMAX', 'VSTAR', 'VSS', 'VV', 'POKEMON'];
        removeWords.forEach(word => {
            name = name.replace(new RegExp('\\b' + word + '\\b', 'gi'), '').trim();
        });

        // Take only first 1-2 words (Pokemon names are usually 1-2 words)
        const words = name.split(/\s+/).filter(w => w.length > 1);
        name = words.slice(0, 2).join(' ');

        return name;
    }

    cleanCardNumber(text) {
        if (!text) return '';

        // Look for pattern like "123/456" or just numbers
        const match = text.match(/(\d+)\s*[\/\\]\s*(\d+)/);
        if (match) {
            return match[1]; // Return just the first number
        }

        // Try to find any number
        const numMatch = text.match(/\d+/);
        return numMatch ? numMatch[0] : '';
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
