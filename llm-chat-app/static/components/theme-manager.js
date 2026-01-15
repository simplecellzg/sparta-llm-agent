/**
 * Theme Manager - Handles dark/light theme switching
 */

const ThemeManager = {
    current: 'dark',

    /**
     * Initialize theme system
     * Load saved preference or default to dark
     */
    init() {
        // Prevent transitions on page load
        document.body.classList.add('preload');

        // Load saved theme or default to dark
        const saved = localStorage.getItem('sparta-theme') || 'dark';
        this.setTheme(saved, false);

        // Remove preload class after a frame
        setTimeout(() => {
            document.body.classList.remove('preload');
        }, 100);

        // Listen for toggle button
        const toggleBtn = document.getElementById('themeToggleBtn');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggle());
        }

        console.log(`Theme initialized: ${this.current}`);
    },

    /**
     * Set theme
     * @param {string} theme - 'dark' or 'light'
     * @param {boolean} animate - Enable transition animation (default true)
     */
    setTheme(theme, animate = true) {
        if (!['dark', 'light'].includes(theme)) {
            console.error(`Invalid theme: ${theme}`);
            return;
        }

        // Add preload class to prevent transitions if animate is false
        if (!animate) {
            document.body.classList.add('preload');
        }

        // Set data-theme attribute on root
        document.documentElement.setAttribute('data-theme', theme);

        // Save to localStorage
        localStorage.setItem('sparta-theme', theme);

        // Update internal state
        this.current = theme;

        // Update toggle button icon
        this.updateToggleButton();

        // Remove preload class
        if (!animate) {
            setTimeout(() => {
                document.body.classList.remove('preload');
            }, 100);
        }

        console.log(`Theme changed to: ${theme}`);
    },

    /**
     * Toggle between dark and light themes
     */
    toggle() {
        const newTheme = this.current === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    },

    /**
     * Update toggle button icon to match current theme
     */
    updateToggleButton() {
        const btn = document.getElementById('themeToggleBtn');
        if (!btn) return;

        if (this.current === 'dark') {
            btn.innerHTML = '☀️'; // Sun icon for switching to light
            btn.title = 'Switch to Light Mode';
        } else {
            btn.innerHTML = '🌙'; // Moon icon for switching to dark
            btn.title = 'Switch to Dark Mode';
        }
    }
};

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => ThemeManager.init());
} else {
    ThemeManager.init();
}
