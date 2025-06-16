document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('togglePass');
    const openIcon = toggle ? toggle.querySelector('.eye-open') : null;
    const closedIcon = toggle ? toggle.querySelector('.eye-closed') : null;


    if (toggle) {
        toggle.addEventListener('click', () => {
            const pass = document.getElementById('password');
            if (!pass) return;

            const isHidden = pass.type === 'password';
            pass.type = isHidden ? 'text' : 'password';
            if (openIcon && closedIcon) {
                openIcon.classList.toggle('d-none', !isHidden);
                closedIcon.classList.toggle('d-none', isHidden);
            }
        });
    }
});
