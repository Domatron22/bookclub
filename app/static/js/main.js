// BookClub JavaScript

// Utility function to show temporary notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 ${
        type === 'success' ? 'bg-green-500' : 
        type === 'error' ? 'bg-red-500' : 
        'bg-blue-500'
    } text-white`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transition = 'opacity 0.3s';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Auto-uppercase club code input
document.addEventListener('DOMContentLoaded', () => {
    const codeInput = document.querySelector('input[name="code"]');
    if (codeInput) {
        codeInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.toUpperCase();
        });
    }
    
    // Confirm before vetoing a book
    const vetoForms = document.querySelectorAll('form[action*="/veto"]');
    vetoForms.forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!confirm('Are you sure you want to veto this book?')) {
                e.preventDefault();
            }
        });
    });
    
    // Confirm before marking book as complete
    const completeForms = document.querySelectorAll('form[action*="/complete"]');
    completeForms.forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!confirm('Mark this book as completed?')) {
                e.preventDefault();
            }
        });
    });
});

// Copy club code to clipboard
function copyClubCode(code) {
    navigator.clipboard.writeText(code).then(() => {
        showNotification('Club code copied to clipboard!', 'success');
    }).catch(() => {
        showNotification('Failed to copy code', 'error');
    });
}
