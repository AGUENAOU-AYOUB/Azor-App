document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('togglePass');
    if (toggle) {
        toggle.addEventListener('click', () => {
            const pass = document.getElementById('password');
            if (pass) pass.type = pass.type === 'password' ? 'text' : 'password';
        });
    }
});
