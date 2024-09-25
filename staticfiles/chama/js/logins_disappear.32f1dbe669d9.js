const form = document.querySelector('form');
const loadingAnimation = document.getElementById('loadingAnimation');

form.addEventListener('submit', (e) => {
    // hide submit button
    form.querySelector('button[type="submit"]').style.display = 'none';

    // show the loading animation
    loadingAnimation.style.display = 'grid';
});