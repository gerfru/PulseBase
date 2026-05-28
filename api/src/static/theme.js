document.addEventListener('DOMContentLoaded', () => {
    var toggle = document.getElementById('theme-toggle');
    if (!toggle) return;

    toggle.checked = document.documentElement.classList.contains('dark');

    toggle.addEventListener('change', function () {
        if (this.checked) {
            document.documentElement.classList.add('dark');
            localStorage.setItem('pb-theme', 'dark');
        } else {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('pb-theme', 'light');
        }
    });
});
