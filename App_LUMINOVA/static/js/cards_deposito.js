document.addEventListener('DOMContentLoaded', function() {
    const cardBodies = document.querySelectorAll('.card-body');
    let maxHeight = 0;

    // Encuentra la altura máxima de todos los .card-body
    cardBodies.forEach(body => {
        maxHeight = Math.max(maxHeight, body.offsetHeight);
    });

    // Aplica la altura máxima a todos los .card-body
    cardBodies.forEach(body => {
        body.style.height = maxHeight + 'px';
    });
});