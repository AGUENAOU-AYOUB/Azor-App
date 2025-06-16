document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('togglePass');
    const icon = toggle ? toggle.querySelector('i') : null;

    if (toggle) {
        toggle.addEventListener('click', () => {
            const pass = document.getElementById('password');
            if (!pass) return;

            const isHidden = pass.type === 'password';
            pass.type = isHidden ? 'text' : 'password';

            if (icon) {
                icon.classList.toggle('fa-eye', !isHidden);
                icon.classList.toggle('fa-eye-slash', isHidden);
            }
        });
    }
});
