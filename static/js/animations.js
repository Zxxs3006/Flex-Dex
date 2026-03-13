// FlexDex - Animations Module

// Screen flicker on page load
document.addEventListener('DOMContentLoaded', () => {
    const screen = document.querySelector('.screen-inner');
    if (screen) {
        screen.classList.add('flicker');
        setTimeout(() => {
            screen.classList.remove('flicker');
        }, 500);
    }
});

// Button press feedback
document.querySelectorAll('.pokedex-btn').forEach(btn => {
    btn.addEventListener('mousedown', () => {
        btn.style.transform = 'scale(0.95)';
    });

    btn.addEventListener('mouseup', () => {
        btn.style.transform = '';
    });

    btn.addEventListener('mouseleave', () => {
        btn.style.transform = '';
    });
});

// Card hover effects with 3D tilt
function addCardHoverEffects() {
    document.querySelectorAll('.pokemon-card, .binder-card').forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const centerX = rect.width / 2;
            const centerY = rect.height / 2;

            const rotateX = (y - centerY) / 20;
            const rotateY = (centerX - x) / 20;

            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.02)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    });
}

// Initialize card effects
document.addEventListener('DOMContentLoaded', addCardHoverEffects);

// LED animation control
function setLEDState(ledClass, state) {
    const led = document.querySelector(`.led.${ledClass}`);
    if (!led) return;

    switch (state) {
        case 'on':
            led.style.opacity = '1';
            led.style.animation = 'none';
            break;
        case 'off':
            led.style.opacity = '0.3';
            led.style.animation = 'none';
            break;
        case 'blink':
            led.style.animation = 'led-blink 0.5s ease-in-out infinite';
            break;
        case 'pulse':
            led.style.animation = 'led-pulse 1s ease-in-out infinite';
            break;
    }
}

// Flash message auto-hide
document.addEventListener('DOMContentLoaded', () => {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(msg => {
        setTimeout(() => {
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                msg.remove();
            }, 300);
        }, 5000);
    });
});

// Card reveal animation
function revealCard(cardElement) {
    cardElement.classList.remove('card-reveal');
    void cardElement.offsetWidth; // Trigger reflow
    cardElement.classList.add('card-reveal');
}

// Type color mapping
const typeColors = {
    fire: '#F08030',
    water: '#6890F0',
    grass: '#78C850',
    electric: '#F8D030',
    psychic: '#F85888',
    ice: '#98D8D8',
    dragon: '#7038F8',
    dark: '#705848',
    fairy: '#EE99AC',
    fighting: '#C03028',
    flying: '#A890F0',
    poison: '#A040A0',
    ground: '#E0C068',
    rock: '#B8A038',
    bug: '#A8B820',
    ghost: '#705898',
    steel: '#B8B8D0',
    normal: '#A8A878'
};

function getTypeColor(type) {
    return typeColors[type.toLowerCase()] || '#A8A878';
}

// ==========================================
// RANK UP CELEBRATION
// ==========================================

function showRankUpCelebration(rankName, rankIcon, rankColor) {
    // Create modal overlay
    const modal = document.createElement('div');
    modal.className = 'rank-up-modal';
    modal.innerHTML = `
        <div class="rank-up-content" style="border-color: ${rankColor};">
            <div class="rank-up-icon">${rankIcon}</div>
            <div class="rank-up-title">RANK UP!</div>
            <div class="rank-up-name" style="color: ${rankColor};">${rankName}</div>
            <button class="pokedex-btn btn-primary rank-up-close">Continue</button>
        </div>
    `;

    document.body.appendChild(modal);

    // Play celebration sound if available
    playSound('rankup');

    // Create confetti effect
    createConfetti(rankColor);

    // Close on button click
    modal.querySelector('.rank-up-close').addEventListener('click', () => {
        modal.style.animation = 'modal-fade-out 0.3s ease forwards';
        setTimeout(() => modal.remove(), 300);
    });

    // Close on backdrop click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.animation = 'modal-fade-out 0.3s ease forwards';
            setTimeout(() => modal.remove(), 300);
        }
    });
}

// Confetti effect for celebrations
function createConfetti(color) {
    const colors = [color, '#fbbf24', '#22c55e', '#8b5cf6', '#ec4899'];
    const confettiCount = 50;

    for (let i = 0; i < confettiCount; i++) {
        const confetti = document.createElement('div');
        confetti.style.cssText = `
            position: fixed;
            width: ${Math.random() * 10 + 5}px;
            height: ${Math.random() * 10 + 5}px;
            background: ${colors[Math.floor(Math.random() * colors.length)]};
            left: ${Math.random() * 100}vw;
            top: -20px;
            border-radius: ${Math.random() > 0.5 ? '50%' : '0'};
            z-index: 1001;
            pointer-events: none;
        `;

        document.body.appendChild(confetti);

        // Animate falling
        const duration = Math.random() * 2000 + 1500;
        const rotation = Math.random() * 720 - 360;
        const drift = Math.random() * 200 - 100;

        confetti.animate([
            { transform: 'translateY(0) rotate(0deg)', opacity: 1 },
            { transform: `translateY(100vh) translateX(${drift}px) rotate(${rotation}deg)`, opacity: 0 }
        ], {
            duration: duration,
            easing: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)'
        }).onfinish = () => confetti.remove();
    }
}

// ==========================================
// ACHIEVEMENT NOTIFICATION
// ==========================================

function showAchievementNotification(achievementName, achievementIcon) {
    const notification = document.createElement('div');
    notification.className = 'achievement-notification';
    notification.innerHTML = `
        <div class="achievement-notification-icon">${achievementIcon}</div>
        <div class="achievement-notification-text">
            <div class="achievement-notification-title">Achievement Unlocked!</div>
            <div class="achievement-notification-name">${achievementName}</div>
        </div>
    `;

    // Add styles dynamically
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: -350px;
        background: linear-gradient(145deg, #1a1a1a, #2d2d2d);
        border-left: 4px solid #f59e0b;
        border-radius: 10px;
        padding: 15px 20px;
        display: flex;
        align-items: center;
        gap: 15px;
        z-index: 1000;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        transition: right 0.5s ease;
        color: white;
    `;

    document.body.appendChild(notification);

    // Play achievement sound
    playSound('achievement');

    // Slide in
    setTimeout(() => {
        notification.style.right = '20px';
    }, 100);

    // Slide out and remove
    setTimeout(() => {
        notification.style.right = '-350px';
        setTimeout(() => notification.remove(), 500);
    }, 4000);
}

// ==========================================
// PROGRESS BAR ANIMATIONS
// ==========================================

function animateProgressBar(element, targetPercent, duration = 1000) {
    const start = parseFloat(element.style.width) || 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Easing function (ease-out cubic)
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = start + (targetPercent - start) * eased;

        element.style.width = `${current}%`;

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

// ==========================================
// NUMBER COUNTER ANIMATION
// ==========================================

function animateNumber(element, targetValue, duration = 1000, prefix = '', suffix = '') {
    const start = parseInt(element.textContent.replace(/[^0-9]/g, '')) || 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Easing function
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + (targetValue - start) * eased);

        element.textContent = prefix + current.toLocaleString() + suffix;

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

// ==========================================
// SOUND EFFECTS
// ==========================================

const sounds = {
    scan: null,
    success: null,
    error: null,
    rankup: null,
    achievement: null
};

function loadSounds() {
    // Sound URLs would be loaded from static folder
    // For now, we'll create empty audio objects
    Object.keys(sounds).forEach(key => {
        sounds[key] = new Audio();
        sounds[key].volume = 0.5;
    });
}

function playSound(soundName) {
    if (sounds[soundName] && sounds[soundName].src) {
        sounds[soundName].currentTime = 0;
        sounds[soundName].play().catch(() => {});
    }
}

// ==========================================
// CARD SCAN ANIMATION
// ==========================================

function showScanAnimation(container) {
    const scanOverlay = document.createElement('div');
    scanOverlay.className = 'scan-overlay';
    scanOverlay.innerHTML = `
        <div class="scan-line"></div>
        <div class="scan-corners">
            <div class="corner top-left"></div>
            <div class="corner top-right"></div>
            <div class="corner bottom-left"></div>
            <div class="corner bottom-right"></div>
        </div>
    `;

    scanOverlay.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        pointer-events: none;
        z-index: 5;
    `;

    container.style.position = 'relative';
    container.appendChild(scanOverlay);

    return scanOverlay;
}

function hideScanAnimation(overlay) {
    if (overlay && overlay.parentNode) {
        overlay.remove();
    }
}

// ==========================================
// CARD ADDED TO BINDER ANIMATION
// ==========================================

function showCardAddedAnimation(cardImage) {
    const overlay = document.createElement('div');
    overlay.innerHTML = `
        <div class="card-added-animation">
            <img src="${cardImage}" alt="Card">
            <div class="added-text">Added to Binder!</div>
        </div>
    `;

    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        animation: fade-in 0.3s ease;
    `;

    const inner = overlay.querySelector('.card-added-animation');
    inner.style.cssText = `
        text-align: center;
        animation: pop-in 0.5s ease;
    `;

    const img = overlay.querySelector('img');
    img.style.cssText = `
        max-width: 250px;
        border-radius: 15px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        margin-bottom: 20px;
    `;

    const text = overlay.querySelector('.added-text');
    text.style.cssText = `
        color: #22c55e;
        font-size: 1.5em;
        font-weight: bold;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
    `;

    document.body.appendChild(overlay);

    playSound('success');

    setTimeout(() => {
        overlay.style.opacity = '0';
        overlay.style.transition = 'opacity 0.3s ease';
        setTimeout(() => overlay.remove(), 300);
    }, 1500);
}

// ==========================================
// SHIMMER EFFECT FOR LOADING
// ==========================================

function addShimmerEffect(element) {
    element.classList.add('shimmer');
    element.style.cssText += `
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
    `;
}

function removeShimmerEffect(element) {
    element.classList.remove('shimmer');
    element.style.background = '';
    element.style.animation = '';
}

// ==========================================
// PAGE TRANSITION EFFECTS
// ==========================================

function initPageTransitions() {
    document.querySelectorAll('a:not([target="_blank"])').forEach(link => {
        link.addEventListener('click', (e) => {
            if (link.hostname === window.location.hostname) {
                e.preventDefault();
                const href = link.href;

                document.body.style.opacity = '0';
                document.body.style.transition = 'opacity 0.2s ease';

                setTimeout(() => {
                    window.location.href = href;
                }, 200);
            }
        });
    });
}

// Fade in on page load
document.addEventListener('DOMContentLoaded', () => {
    document.body.style.opacity = '0';
    requestAnimationFrame(() => {
        document.body.style.transition = 'opacity 0.3s ease';
        document.body.style.opacity = '1';
    });
});

// ==========================================
// REGIONAL DEX SLOT HOVER
// ==========================================

function addDexSlotEffects() {
    document.querySelectorAll('.dex-slot.owned').forEach(slot => {
        slot.addEventListener('mouseenter', () => {
            slot.style.transform = 'scale(1.1)';
            slot.style.zIndex = '10';
            slot.style.boxShadow = '0 5px 20px rgba(34, 197, 94, 0.4)';
        });

        slot.addEventListener('mouseleave', () => {
            slot.style.transform = '';
            slot.style.zIndex = '';
            slot.style.boxShadow = '';
        });
    });
}

document.addEventListener('DOMContentLoaded', addDexSlotEffects);

// ==========================================
// LEADERBOARD ROW HOVER EFFECTS
// ==========================================

function addLeaderboardEffects() {
    document.querySelectorAll('.leaderboard-row').forEach(row => {
        row.addEventListener('mouseenter', () => {
            row.style.transform = 'translateX(10px) scale(1.02)';
        });

        row.addEventListener('mouseleave', () => {
            row.style.transform = '';
        });
    });
}

document.addEventListener('DOMContentLoaded', addLeaderboardEffects);

// ==========================================
// INITIALIZE
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    loadSounds();
    // initPageTransitions(); // Uncomment to enable page transitions
});

// Export functions for use in other modules
window.flexDexAnimations = {
    setLEDState,
    revealCard,
    getTypeColor,
    showRankUpCelebration,
    showAchievementNotification,
    animateProgressBar,
    animateNumber,
    playSound,
    showScanAnimation,
    hideScanAnimation,
    showCardAddedAnimation,
    addShimmerEffect,
    removeShimmerEffect,
    createConfetti
};

// Backwards compatibility
window.pokedexAnimations = window.flexDexAnimations;
