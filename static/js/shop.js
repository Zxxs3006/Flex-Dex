/**
 * FlexDex Shop - Pack Opening Experience
 */

// Store pack data globally
let currentPackCards = [];
let revealedCount = 0;

/**
 * Buy a booster pack
 */
async function buyPack(setId, setName, price) {
    const currentCoins = parseInt(document.getElementById('coin-amount').textContent);

    // Check if user has enough coins
    if (currentCoins < price) {
        showInsufficientCoinsModal(price, currentCoins);
        return;
    }

    // Show the pack opening modal
    showPackOpeningModal();

    try {
        // Call API to buy pack
        const response = await fetch('/api/shop/buy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ set_id: setId })
        });

        const data = await response.json();

        if (!data.success) {
            closePackOpening();
            if (data.error === 'Not enough coins') {
                showInsufficientCoinsModal(data.required, data.current);
            } else {
                alert('Error: ' + data.error);
            }
            return;
        }

        // Store pack data
        currentPackCards = data.cards;
        revealedCount = 0;

        // Update coin display
        document.getElementById('coin-amount').textContent = data.coins_remaining;

        // Setup pack opening
        setupPackOpening(data);

    } catch (error) {
        console.error('Error buying pack:', error);
        closePackOpening();
        alert('Failed to purchase pack. Please try again.');
    }
}

/**
 * Show pack opening modal
 */
function showPackOpeningModal() {
    const modal = document.getElementById('pack-opening-modal');
    modal.style.display = 'flex';

    // Reset to pack phase
    document.getElementById('pack-phase').style.display = 'block';
    document.getElementById('cards-phase').style.display = 'none';
    document.getElementById('summary-phase').style.display = 'none';

    // Reset pack animation
    const pack = document.getElementById('booster-pack');
    pack.classList.remove('tearing');
}

/**
 * Setup pack opening interaction
 */
function setupPackOpening(packData) {
    const pack = document.getElementById('booster-pack');

    // Add click handler to pack
    pack.onclick = () => tearOpenPack(packData);
}

/**
 * Play pack tear animation and transition to cards phase
 */
function tearOpenPack(packData) {
    const pack = document.getElementById('booster-pack');

    // Add tearing animation
    pack.classList.add('tearing');

    // Play sound effect (if available)
    playTearSound();

    // After animation, show cards
    setTimeout(() => {
        showCardsPhase(packData);
    }, 800);
}

/**
 * Show the cards reveal phase
 */
function showCardsPhase(packData) {
    document.getElementById('pack-phase').style.display = 'none';
    document.getElementById('cards-phase').style.display = 'block';

    const container = document.getElementById('cards-container');
    container.innerHTML = '';

    // Create card elements
    packData.cards.forEach((card, index) => {
        const cardEl = createCardElement(card, index);
        container.appendChild(cardEl);

        // Stagger animation
        setTimeout(() => {
            cardEl.style.opacity = '1';
            cardEl.style.transform = 'translateY(0)';
        }, index * 100);
    });

    // Show reveal all button after a delay
    setTimeout(() => {
        document.getElementById('reveal-actions').style.display = 'block';
    }, packData.cards.length * 100 + 500);
}

/**
 * Create a card element for reveal
 */
function createCardElement(card, index) {
    const rarityClass = getRarityClass(card.rarity);

    const cardEl = document.createElement('div');
    cardEl.className = `reveal-card ${rarityClass}`;
    cardEl.id = `card-${index}`;
    cardEl.style.opacity = '0';
    cardEl.style.transform = 'translateY(20px)';
    cardEl.style.transition = 'all 0.3s ease';

    cardEl.innerHTML = `
        <div class="reveal-card-inner">
            <div class="card-face card-back"></div>
            <div class="card-face card-front">
                <img src="${card.images.small}" alt="${card.name}" loading="lazy">
            </div>
        </div>
    `;

    // Add click handler
    cardEl.onclick = () => revealCard(index, card);

    return cardEl;
}

/**
 * Get CSS class based on rarity
 */
function getRarityClass(rarity) {
    if (!rarity) return 'common';

    const rarityLower = rarity.toLowerCase();

    if (rarityLower.includes('secret') ||
        rarityLower.includes('rainbow') ||
        rarityLower.includes('ultra') ||
        rarityLower.includes('hyper') ||
        rarityLower.includes('special art')) {
        return 'ultra-rare';
    }

    if (rarityLower.includes('holo') ||
        rarityLower.includes('vmax') ||
        rarityLower.includes('vstar') ||
        rarityLower.includes('illustration')) {
        return 'holo';
    }

    if (rarityLower.includes('rare') || rarityLower.includes('double')) {
        return 'rare';
    }

    if (rarityLower.includes('uncommon')) {
        return 'uncommon';
    }

    return 'common';
}

/**
 * Reveal a single card
 */
function revealCard(index, cardData) {
    const cardEl = document.getElementById(`card-${index}`);

    // Skip if already revealed
    if (cardEl.classList.contains('revealed')) return;

    // Add revealed class to flip card
    cardEl.classList.add('revealed');
    revealedCount++;

    // Play reveal effects based on rarity
    const rarityClass = getRarityClass(cardData.rarity);

    if (rarityClass === 'ultra-rare') {
        playUltraRareEffect(cardEl);
        screenFlash();
    } else if (rarityClass === 'holo') {
        playHoloEffect();
    }

    // Check if all cards revealed
    if (revealedCount === currentPackCards.length) {
        setTimeout(() => {
            showSummaryPhase();
        }, 1500);
    }

    // Update title
    updateRevealTitle();
}

/**
 * Reveal all cards at once
 */
function revealAllCards() {
    currentPackCards.forEach((card, index) => {
        setTimeout(() => {
            revealCard(index, card);
        }, index * 150);
    });

    // Hide reveal all button
    document.getElementById('reveal-actions').style.display = 'none';
}

/**
 * Update the reveal title with count
 */
function updateRevealTitle() {
    const remaining = currentPackCards.length - revealedCount;
    const title = document.getElementById('reveal-title');

    if (remaining > 0) {
        title.textContent = `${remaining} cards remaining - Tap to reveal!`;
    } else {
        title.textContent = 'All cards revealed!';
    }
}

/**
 * Play ultra rare sparkle effect
 */
function playUltraRareEffect(cardEl) {
    // Create sparkle container
    const sparkleContainer = document.createElement('div');
    sparkleContainer.className = 'sparkle-container';
    document.body.appendChild(sparkleContainer);

    // Get card position
    const rect = cardEl.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    // Create sparkles
    for (let i = 0; i < 20; i++) {
        setTimeout(() => {
            const sparkle = document.createElement('div');
            sparkle.className = 'sparkle';

            // Random position around card
            const angle = (Math.random() * 360) * (Math.PI / 180);
            const distance = Math.random() * 100;
            sparkle.style.left = (centerX + Math.cos(angle) * distance) + 'px';
            sparkle.style.top = (centerY + Math.sin(angle) * distance) + 'px';

            sparkleContainer.appendChild(sparkle);

            // Remove sparkle after animation
            setTimeout(() => sparkle.remove(), 1500);
        }, i * 50);
    }

    // Remove container after all sparkles done
    setTimeout(() => sparkleContainer.remove(), 2500);
}

/**
 * Screen flash effect
 */
function screenFlash() {
    const flash = document.createElement('div');
    flash.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: white;
        pointer-events: none;
        z-index: 1002;
        animation: flash 0.3s ease-out forwards;
    `;

    // Add animation keyframes
    const style = document.createElement('style');
    style.textContent = `
        @keyframes flash {
            0% { opacity: 0.8; }
            100% { opacity: 0; }
        }
    `;
    document.head.appendChild(style);
    document.body.appendChild(flash);

    setTimeout(() => {
        flash.remove();
        style.remove();
    }, 300);
}

/**
 * Play holo shimmer sound/effect
 */
function playHoloEffect() {
    // Could add sound or additional visual effects here
}

/**
 * Play pack tear sound
 */
function playTearSound() {
    // Could add sound effect here
}

/**
 * Show summary phase
 */
function showSummaryPhase() {
    document.getElementById('cards-phase').style.display = 'none';
    document.getElementById('summary-phase').style.display = 'block';

    // Populate summary cards
    const summaryContainer = document.getElementById('summary-cards');
    summaryContainer.innerHTML = '';

    currentPackCards.forEach(card => {
        const cardEl = document.createElement('div');
        cardEl.className = 'summary-card';
        cardEl.innerHTML = `<img src="${card.images.small}" alt="${card.name}">`;
        cardEl.onclick = () => window.open(`/card/${card.id}`, '_blank');
        summaryContainer.appendChild(cardEl);
    });

    // Calculate stats
    const coinsSpent = document.querySelector('.pack-card[data-set-id]')?.dataset.price || 449;
    const coinsRemaining = document.getElementById('coin-amount').textContent;

    document.getElementById('coins-spent').textContent = `Coins spent: ${coinsSpent}`;
    document.getElementById('coins-remaining').textContent = `Coins remaining: ${coinsRemaining}`;
}

/**
 * Close pack opening modal
 */
function closePackOpening() {
    const modal = document.getElementById('pack-opening-modal');
    modal.style.display = 'none';

    // Reset state
    currentPackCards = [];
    revealedCount = 0;
}

/**
 * Show insufficient coins modal
 */
function showInsufficientCoinsModal(required, current) {
    document.getElementById('required-coins').textContent = required;
    document.getElementById('current-coins').textContent = current;
    document.getElementById('insufficient-coins-modal').style.display = 'flex';
}

/**
 * Close insufficient coins modal
 */
function closeInsufficientModal() {
    document.getElementById('insufficient-coins-modal').style.display = 'none';
}

// Close modals when clicking outside
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        if (e.target.id === 'insufficient-coins-modal') {
            closeInsufficientModal();
        }
        // Don't close pack opening modal by clicking outside during opening
    }
});

// Keyboard support
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (document.getElementById('insufficient-coins-modal').style.display === 'flex') {
            closeInsufficientModal();
        }
    }

    // Space bar to reveal all cards
    if (e.key === ' ' && document.getElementById('cards-phase').style.display === 'block') {
        e.preventDefault();
        revealAllCards();
    }
});
