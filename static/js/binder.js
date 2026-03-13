// Pokédex Card Scanner - Binder Module

// Show card details modal
function showCardDetails(cardId) {
    window.location.href = `/card/${cardId}`;
}

// Change binder view
function changeBinder(binderId) {
    if (binderId) {
        window.location.href = `/binder?binder_id=${binderId}`;
    } else {
        window.location.href = '/binder';
    }
}

// Create binder modal functions
function showCreateBinderModal() {
    const modal = document.getElementById('create-binder-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function hideCreateBinderModal() {
    const modal = document.getElementById('create-binder-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Close modal on outside click
document.addEventListener('click', (e) => {
    const modal = document.getElementById('create-binder-modal');
    if (modal && e.target === modal) {
        hideCreateBinderModal();
    }
});

// Remove card from binder
async function removeFromBinder(userCardId) {
    if (!confirm('Remove this card from your binder?')) {
        return;
    }

    try {
        const response = await fetch(`/api/binder/remove/${userCardId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            window.location.reload();
        } else {
            alert(data.error || 'Failed to remove card');
        }

    } catch (error) {
        console.error('Error removing card:', error);
        alert('Error removing card from binder');
    }
}

// Update card quantity
async function updateQuantity(userCardId, delta) {
    try {
        const response = await fetch(`/api/binder/quantity/${userCardId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ delta: delta })
        });

        const data = await response.json();

        if (data.success) {
            window.location.reload();
        } else {
            alert(data.error || 'Failed to update quantity');
        }

    } catch (error) {
        console.error('Error updating quantity:', error);
        alert('Error updating card quantity');
    }
}

// Move card to different binder
async function moveCard(userCardId, newBinderId) {
    try {
        const response = await fetch(`/api/binder/move/${userCardId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ binder_id: newBinderId })
        });

        const data = await response.json();

        if (data.success) {
            window.location.reload();
        } else {
            alert(data.error || 'Failed to move card');
        }

    } catch (error) {
        console.error('Error moving card:', error);
        alert('Error moving card');
    }
}

// Delete binder
async function deleteBinder(binderId) {
    if (!confirm('Delete this binder? Cards will be moved to your main collection.')) {
        return;
    }

    try {
        const response = await fetch(`/api/binder/${binderId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            window.location.href = '/binder';
        } else {
            alert(data.error || 'Failed to delete binder');
        }

    } catch (error) {
        console.error('Error deleting binder:', error);
        alert('Error deleting binder');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Any initialization code here
});
