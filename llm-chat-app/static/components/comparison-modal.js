/**
 * Comparison Modal Component
 * Compare two DSMC iterations side-by-side
 */

class ComparisonModal {
    constructor() {
        this.modal = null;
        this.overlay = null;
        this.selectA = null;
        this.selectB = null;
        this.content = null;

        this.iterations = [];
        this.comparisonData = null;
    }

    init() {
        this.modal = document.getElementById('iterationComparisonModal');
        this.overlay = document.getElementById('customModalOverlay');
        this.selectA = document.getElementById('comparisonIterA');
        this.selectB = document.getElementById('comparisonIterB');
        this.content = document.getElementById('comparisonContent');

        if (!this.modal || !this.overlay) {
            console.warn('Comparison modal elements not found');
            return false;
        }

        return true;
    }

    show(iterations, defaultIterA = null, defaultIterB = null) {
        if (!this.modal && !this.init()) {
            return;
        }

        this.iterations = iterations;
        this.populateSelectors(defaultIterA, defaultIterB);
        this.overlay.classList.remove('hidden');
        this.modal.classList.remove('hidden');
    }

    hide() {
        if (this.modal) this.modal.classList.add('hidden');
        if (this.overlay) this.overlay.classList.add('hidden');
        if (this.content) this.content.classList.add('hidden');
    }

    populateSelectors(defaultIterA, defaultIterB) {
        if (!this.selectA || !this.selectB) return;

        // Clear existing options
        this.selectA.innerHTML = '';
        this.selectB.innerHTML = '';

        // Add options for each iteration
        this.iterations.forEach(iter => {
            const optionA = document.createElement('option');
            optionA.value = iter.iteration_id;
            optionA.textContent = `v${iter.iteration_number} - ${iter.modification_description || 'N/A'}`;
            this.selectA.appendChild(optionA);

            const optionB = optionA.cloneNode(true);
            this.selectB.appendChild(optionB);
        });

        // Set default selections
        if (defaultIterA) this.selectA.value = defaultIterA;
        if (defaultIterB) this.selectB.value = defaultIterB;

        // Default: select last two iterations
        if (!defaultIterA && this.iterations.length >= 2) {
            this.selectA.value = this.iterations[0].iteration_id; // Newest
            this.selectB.value = this.iterations[1].iteration_id; // Second newest
        }
    }

    async loadComparison() {
        const iterIdA = this.selectA.value;
        const iterIdB = this.selectB.value;

        if (!iterIdA || !iterIdB) {
            alert('请选择两个版本进行对比');
            return;
        }

        if (iterIdA === iterIdB) {
            alert('请选择不同的版本进行对比');
            return;
        }

        try {
            // Fetch iteration details
            const [iterA, iterB] = await Promise.all([
                fetch(`/api/dsmc/sessions/${currentSessionId}/iterations/${iterIdA}`).then(r => r.json()),
                fetch(`/api/dsmc/sessions/${currentSessionId}/iterations/${iterIdB}`).then(r => r.json())
            ]);

            this.comparisonData = { iterA, iterB };
            this.renderComparison();
            this.content.classList.remove('hidden');

        } catch (error) {
            console.error('Error loading comparison:', error);
            alert('加载对比数据失败');
        }
    }

    renderComparison() {
        const { iterA, iterB } = this.comparisonData;

        // Update headers
        const headerA = document.getElementById('headerIterA');
        const headerB = document.getElementById('headerIterB');
        if (headerA) headerA.textContent = `v${iterA.iteration_number}`;
        if (headerB) headerB.textContent = `v${iterB.iteration_number}`;

        // Render metadata comparison
        this.renderMetadataComparison(iterA, iterB);

        // Render input file diff
        this.renderInputDiff(iterA.input_file_content || iterA.input_file, iterB.input_file_content || iterB.input_file);

        // Render results comparison if available
        if (iterA.run_result && iterB.run_result) {
            this.renderResultsComparison(iterA.run_result, iterB.run_result);
            const resultsSection = document.getElementById('resultsComparisonSection');
            if (resultsSection) resultsSection.classList.remove('hidden');
        } else {
            const resultsSection = document.getElementById('resultsComparisonSection');
            if (resultsSection) resultsSection.classList.add('hidden');
        }
    }

    renderMetadataComparison(iterA, iterB) {
        const tbody = document.getElementById('metadataComparisonBody');
        if (!tbody) return;

        tbody.innerHTML = '';

        const fields = [
            { label: '迭代编号', keyA: 'iteration_number', keyB: 'iteration_number' },
            { label: '修改描述', keyA: 'modification_description', keyB: 'modification_description' },
            { label: '状态', keyA: 'status', keyB: 'status' },
            { label: '总时间', keyA: 'timing.total_time', keyB: 'timing.total_time', format: v => v ? `${v.toFixed(2)}s` : 'N/A' },
            { label: '创建时间', keyA: 'created_at', keyB: 'created_at', format: v => v ? new Date(v).toLocaleString() : 'N/A' }
        ];

        fields.forEach(field => {
            const tr = document.createElement('tr');

            const valueA = this.getNestedValue(iterA, field.keyA);
            const valueB = this.getNestedValue(iterB, field.keyB);

            const displayA = field.format ? field.format(valueA) : (valueA || 'N/A');
            const displayB = field.format ? field.format(valueB) : (valueB || 'N/A');

            const isDifferent = displayA !== displayB;

            tr.innerHTML = `
                <td>${field.label}</td>
                <td style="${isDifferent ? 'background: rgba(251, 191, 36, 0.1);' : ''}">${displayA}</td>
                <td style="${isDifferent ? 'background: rgba(251, 191, 36, 0.1);' : ''}">${displayB}</td>
            `;

            tbody.appendChild(tr);
        });
    }

    getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => current?.[key], obj);
    }

    renderInputDiff(contentA, contentB) {
        const container = document.getElementById('inputFileDiff');
        if (!container) return;

        if (!contentA || !contentB) {
            container.innerHTML = '<p style="color: var(--text-muted);">输入文件内容不可用</p>';
            return;
        }

        // Simple line-by-line diff
        const linesA = contentA.split('\n');
        const linesB = contentB.split('\n');

        const maxLines = Math.max(linesA.length, linesB.length);
        let diffHtml = '';

        for (let i = 0; i < maxLines; i++) {
            const lineA = linesA[i] || '';
            const lineB = linesB[i] || '';

            if (lineA === lineB) {
                diffHtml += `<div class="diff-line unchanged">  ${this.escapeHtml(lineA)}</div>`;
            } else {
                if (lineA) {
                    diffHtml += `<div class="diff-line removed">- ${this.escapeHtml(lineA)}</div>`;
                }
                if (lineB) {
                    diffHtml += `<div class="diff-line added">+ ${this.escapeHtml(lineB)}</div>`;
                }
            }
        }

        container.innerHTML = diffHtml || '<p style="color: var(--text-muted);">文件内容相同</p>';
    }

    renderResultsComparison(resultA, resultB) {
        const container = document.getElementById('resultsComparison');
        if (!container) return;

        const cardA = this.createResultCard('版本 A', resultA);
        const cardB = this.createResultCard('版本 B', resultB);

        container.innerHTML = '';
        container.appendChild(cardA);
        container.appendChild(cardB);
    }

    createResultCard(title, result) {
        const card = document.createElement('div');
        card.className = 'result-card';

        const stats = [
            { label: '完成步数', value: result.current_step || result.total_steps || 'N/A' },
            { label: '总步数', value: result.total_steps || 'N/A' },
            { label: '粒子数', value: result.particles_count ? result.particles_count.toLocaleString() : 'N/A' },
            { label: '碰撞次数', value: result.collisions ? result.collisions.toLocaleString() : 'N/A' },
            { label: '墙面碰撞', value: result.wall_collisions ? result.wall_collisions.toLocaleString() : 'N/A' }
        ];

        const statsHtml = stats.map(stat => `
            <div class="stat-row">
                <span class="stat-label">${stat.label}:</span>
                <span class="stat-value">${stat.value}</span>
            </div>
        `).join('');

        card.innerHTML = `
            <h5>${title}</h5>
            <div class="result-stats">
                ${statsHtml}
            </div>
        `;

        return card;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    exportComparison() {
        if (!this.comparisonData) {
            alert('请先加载对比数据');
            return;
        }

        const { iterA, iterB } = this.comparisonData;

        const report = `
# SPARTA DSMC 迭代对比报告

## 基本信息

### 版本 A (v${iterA.iteration_number})
- 修改描述: ${iterA.modification_description || 'N/A'}
- 状态: ${iterA.status}
- 总时间: ${iterA.timing?.total_time?.toFixed(2) || 'N/A'}s
- 创建时间: ${iterA.created_at ? new Date(iterA.created_at).toLocaleString() : 'N/A'}

### 版本 B (v${iterB.iteration_number})
- 修改描述: ${iterB.modification_description || 'N/A'}
- 状态: ${iterB.status}
- 总时间: ${iterB.timing?.total_time?.toFixed(2) || 'N/A'}s
- 创建时间: ${iterB.created_at ? new Date(iterB.created_at).toLocaleString() : 'N/A'}

## 输入文件差异

### 版本 A:
\`\`\`
${iterA.input_file_content || iterA.input_file || 'N/A'}
\`\`\`

### 版本 B:
\`\`\`
${iterB.input_file_content || iterB.input_file || 'N/A'}
\`\`\`

## 运行结果对比

### 版本 A:
${JSON.stringify(iterA.run_result, null, 2)}

### 版本 B:
${JSON.stringify(iterB.run_result, null, 2)}

---
生成时间: ${new Date().toLocaleString()}
        `.trim();

        // Download as markdown file
        const blob = new Blob([report], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `comparison_v${iterA.iteration_number}_vs_v${iterB.iteration_number}.md`;
        a.click();
        URL.revokeObjectURL(url);
    }
}

// Global instance
let comparisonModal = null;

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    comparisonModal = new ComparisonModal();
});

// Global functions for onclick handlers
function closeComparisonModal() {
    if (comparisonModal) comparisonModal.hide();
}

function loadComparison() {
    if (comparisonModal) comparisonModal.loadComparison();
}

function exportComparison() {
    if (comparisonModal) comparisonModal.exportComparison();
}

// Make comparisonModal available globally
if (typeof window !== 'undefined') {
    window.comparisonModal = comparisonModal;
    window.closeComparisonModal = closeComparisonModal;
    window.loadComparison = loadComparison;
    window.exportComparison = exportComparison;
}
