/**
 * Version Manager Component
 * Manages iteration history and version control for DSMC sessions
 */

class VersionManager {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.iterations = [];
        this.activeIterationId = null;
        this.container = null;
    }

    /**
     * Initialize version manager
     * @param {string} containerId - DOM element ID for version list
     */
    init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Version container not found: ${containerId}`);
            return false;
        }

        this.loadIterations();
        return true;
    }

    /**
     * Load iterations from backend
     */
    async loadIterations() {
        try {
            const response = await fetch(`/api/dsmc/sessions/${this.sessionId}/iterations`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                this.iterations = data.iterations || [];
                this.activeIterationId = data.current_iteration_id;
                this.render();

                console.log(`Loaded ${this.iterations.length} iterations for session ${this.sessionId}`);
            } else {
                console.error('Failed to load iterations:', data.error);
            }
        } catch (error) {
            console.error('Failed to load iterations:', error);
            this.renderError('Failed to load version history');
        }
    }

    /**
     * Render version history list
     */
    render() {
        if (!this.container) return;

        if (this.iterations.length === 0) {
            this.container.innerHTML = `
                <div class="version-empty">
                    <p>No iterations yet</p>
                </div>
            `;
            return;
        }

        // Sort by iteration number descending (newest first)
        const sortedIterations = [...this.iterations].sort((a, b) =>
            b.iteration_number - a.iteration_number
        );

        this.container.innerHTML = sortedIterations.map(iter =>
            this.renderIterationItem(iter)
        ).join('');

        // Attach event listeners
        this.attachEventListeners();
    }

    /**
     * Render a single iteration item
     */
    renderIterationItem(iter) {
        const isActive = iter.iteration_id === this.activeIterationId;
        const statusIcon = this.getStatusIcon(iter.status);
        const statusText = this.getStatusText(iter);

        return `
            <div class="version-item ${isActive ? 'active' : ''}" data-iteration-id="${iter.iteration_id}">
                <div class="version-header">
                    <span class="version-indicator">${isActive ? '●' : '○'}</span>
                    <span class="version-label">
                        v${iter.iteration_number} ${iter.modification_description || 'Initial'}
                    </span>
                    ${isActive ? '<span class="badge-current">Current</span>' : ''}
                </div>
                <div class="version-status">
                    <span class="status-icon">${statusIcon}</span>
                    <span class="status-text">${statusText}</span>
                </div>
                <div class="version-actions">
                    ${this.renderActions(iter, isActive)}
                </div>
            </div>
        `;
    }

    /**
     * Get status icon emoji
     */
    getStatusIcon(status) {
        const icons = {
            'completed': '✅',
            'failed': '❌',
            'running': '⏳',
            'fixing': '🔄',
            'pending': '⏸️'
        };
        return icons[status] || '❓';
    }

    /**
     * Get status text with details
     */
    getStatusText(iter) {
        if (iter.status === 'completed') {
            const time = (iter.timing?.total_time || 0).toFixed(1);
            return `Success | ${time}s`;
        } else if (iter.status === 'failed') {
            const attempts = iter.fix_history?.length || 0;
            return `Failed | ${attempts} fix attempts`;
        } else if (iter.status === 'running') {
            const current = iter.run_result?.current_step || 0;
            const total = iter.run_result?.total_steps || 1000;
            return `Running... ${current}/${total}`;
        } else if (iter.status === 'fixing') {
            return 'Auto-fixing errors...';
        } else if (iter.status === 'pending') {
            return 'Ready to run';
        }
        return iter.status;
    }

    /**
     * Render action buttons for iteration
     */
    renderActions(iter, isActive) {
        if (isActive) {
            if (iter.status === 'running' || iter.status === 'fixing') {
                return `
                    <button class="btn-version-action" data-action="view">View</button>
                    <button class="btn-version-action" data-action="compare">Compare</button>
                    <button class="btn-version-action danger" data-action="stop">Stop</button>
                `;
            } else {
                return `
                    <button class="btn-version-action" data-action="view">View</button>
                    <button class="btn-version-action" data-action="compare">Compare</button>
                    <button class="btn-version-action danger" data-action="delete">Delete</button>
                `;
            }
        } else {
            return `
                <button class="btn-version-action primary" data-action="restore">Restore</button>
                <button class="btn-version-action" data-action="view">View</button>
                <button class="btn-version-action danger" data-action="delete">Delete</button>
            `;
        }
    }

    /**
     * Attach event listeners to action buttons
     */
    attachEventListeners() {
        const buttons = this.container.querySelectorAll('.btn-version-action');

        buttons.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();

                const action = btn.dataset.action;
                const versionItem = btn.closest('.version-item');
                const iterationId = versionItem.dataset.iterationId;

                await this.handleAction(action, iterationId);
            });
        });
    }

    /**
     * Handle action button clicks
     */
    async handleAction(action, iterationId) {
        console.log(`Version action: ${action} on ${iterationId}`);

        switch (action) {
            case 'restore':
                await this.restoreVersion(iterationId);
                break;
            case 'view':
                await this.viewIteration(iterationId);
                break;
            case 'compare':
                await this.compareIterations(iterationId);
                break;
            case 'delete':
                await this.deleteIteration(iterationId);
                break;
            case 'stop':
                await this.stopIteration(iterationId);
                break;
            default:
                console.warn(`Unknown action: ${action}`);
        }
    }

    /**
     * Restore to a previous version
     */
    async restoreVersion(iterationId) {
        if (!confirm('Restore to this version? Current unsaved changes will be lost.')) {
            return;
        }

        showStatus('Restoring version...');

        try {
            const response = await fetch(
                `/api/dsmc/sessions/${this.sessionId}/iterations/${iterationId}/restore`,
                { method: 'POST' }
            );

            const result = await response.json();

            if (result.success) {
                this.activeIterationId = iterationId;
                await this.loadIterations();

                // Reload input file in main view if available
                if (typeof loadInputFileContent === 'function') {
                    await loadInputFileContent(this.sessionId);
                }

                showStatus('Version restored successfully', 'success');
            } else {
                showStatus('Restore failed: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Restore failed:', error);
            showStatus('Restore failed: ' + error.message, 'error');
        }
    }

    /**
     * View iteration details
     */
    async viewIteration(iterationId) {
        try {
            const response = await fetch(
                `/api/dsmc/sessions/${this.sessionId}/iterations/${iterationId}`
            );

            const iteration = await response.json();

            if (typeof showIterationDetailModal === 'function') {
                showIterationDetailModal(iteration);
            } else {
                console.log('Iteration details:', iteration);
                alert('Iteration detail viewer not implemented yet');
            }
        } catch (error) {
            console.error('Failed to load iteration:', error);
            showStatus('Failed to load iteration: ' + error.message, 'error');
        }
    }

    /**
     * Compare with another iteration
     */
    async compareIterations(iterationId) {
        const currentIteration = this.iterations.find(i => i.iteration_id === iterationId);
        if (!currentIteration) return;

        // Show comparison modal with current iteration pre-selected
        if (typeof comparisonModal !== 'undefined' && comparisonModal) {
            comparisonModal.show(this.iterations, iterationId, this.activeIterationId);
        } else {
            alert('Comparison modal not loaded');
        }
    }

    /**
     * Delete an iteration
     */
    async deleteIteration(iterationId) {
        const iteration = this.iterations.find(i => i.iteration_id === iterationId);
        const isActive = iterationId === this.activeIterationId;

        let message = `Delete iteration v${iteration?.iteration_number || '?'}?`;
        if (isActive) {
            message += '\n\nThis is the current active version. You cannot delete it.';
            alert(message);
            return;
        }

        if (!confirm(message + '\n\nThis action cannot be undone.')) {
            return;
        }

        showStatus('Deleting iteration...');

        try {
            const response = await fetch(
                `/api/dsmc/sessions/${this.sessionId}/iterations/${iterationId}`,
                { method: 'DELETE' }
            );

            const result = await response.json();

            if (result.success) {
                await this.loadIterations();
                showStatus('Iteration deleted', 'success');
            } else {
                showStatus('Delete failed: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Delete failed:', error);
            showStatus('Delete failed: ' + error.message, 'error');
        }
    }

    /**
     * Stop running iteration
     */
    async stopIteration(iterationId) {
        if (!confirm('Stop this simulation?')) {
            return;
        }

        try {
            await fetch(`/api/dsmc/stop/${this.sessionId}`, { method: 'POST' });
            showStatus('Simulation stopped', 'info');

            // Reload to update status
            setTimeout(() => this.loadIterations(), 1000);
        } catch (error) {
            console.error('Stop failed:', error);
            showStatus('Stop failed: ' + error.message, 'error');
        }
    }

    /**
     * Render error message
     */
    renderError(message) {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="version-error">
                <p>❌ ${message}</p>
            </div>
        `;
    }

    /**
     * Update iteration status in real-time
     * Called by SSE listeners
     */
    updateIterationStatus(iterationId, statusData) {
        const iteration = this.iterations.find(i => i.iteration_id === iterationId);
        if (iteration) {
            Object.assign(iteration, statusData);
            this.render();
        }
    }

    /**
     * Add new iteration to list
     */
    addIteration(iteration) {
        this.iterations.push(iteration);
        this.render();
    }
}

// Export for use in other scripts
if (typeof window !== 'undefined') {
    window.VersionManager = VersionManager;
}
