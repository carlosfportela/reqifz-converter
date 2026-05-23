document.addEventListener('DOMContentLoaded', () => {
    // ── Seções ──────────────────────────────────────────────────────────
    const stepUpload   = document.getElementById('step-upload');
    const stepLoading  = document.getElementById('step-loading');
    const stepResult   = document.getElementById('step-result');

    // ── Elementos de Upload ──────────────────────────────────────────────
    const dropZone          = document.getElementById('drop-zone');
    const fileInput         = document.getElementById('file-input');
    const browseBtn         = document.getElementById('browse-btn');
    const dropZoneContent   = document.querySelector('.drop-zone-content'); // null neste layout
    const fileListContainer = document.getElementById('file-list-container');
    const selectedFilesList = document.getElementById('selected-files-list');
    const fileCount         = document.getElementById('file-count');
    const clearAllBtn       = document.getElementById('clear-all-btn');
    const convertBtn        = document.getElementById('convert-btn');

    // ── Elementos de Resultado ───────────────────────────────────────────
    const newBatchBtn       = document.getElementById('new-batch-btn');
    const terminalLogs      = document.getElementById('terminal-logs');
    const downloadFilesList = document.getElementById('download-files-list');
    const downloadAllBtn    = document.getElementById('download-all-btn');

    // ── Alertas ──────────────────────────────────────────────────────────
    const alertContainer = document.getElementById('alert-container');
    const alertBox       = document.getElementById('alert-box');
    const alertIcon      = document.getElementById('alert-icon');
    const alertMessage   = document.getElementById('alert-message');

    let currentFiles = [];

    // ── Drag & Drop ──────────────────────────────────────────────────────
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt =>
        dropZone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }, false)
    );

    ['dragenter', 'dragover'].forEach(evt =>
        dropZone.addEventListener(evt, () => dropZone.classList.add('dragover'), false)
    );

    ['dragleave', 'drop'].forEach(evt =>
        dropZone.addEventListener(evt, () => dropZone.classList.remove('dragover'), false)
    );

    dropZone.addEventListener('drop', e => addFiles(Array.from(e.dataTransfer.files)), false);

    // ── Browse ───────────────────────────────────────────────────────────
    browseBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', function () {
        addFiles(Array.from(this.files));
        this.value = '';
    });

    // ── Gerenciamento de Arquivos ─────────────────────────────────────────
    function addFiles(files) {
        hideAlert();
        let added = 0;
        files.forEach(file => {
            if (file.name.toLowerCase().endsWith('.reqifz')) {
                if (!currentFiles.find(f => f.name === file.name)) {
                    currentFiles.push(file);
                    added++;
                }
            } else {
                showAlert(`Arquivo ignorado: ${file.name} (não é .reqifz)`, 'error');
            }
        });
        if (added > 0) updateFileListUI();
    }

    function removeFile(index) {
        currentFiles.splice(index, 1);
        updateFileListUI();
    }

    clearAllBtn.addEventListener('click', () => {
        currentFiles = [];
        updateFileListUI();
    });

    function updateFileListUI() {
        if (currentFiles.length === 0) {
            fileListContainer.classList.add('hidden');
            if (dropZoneContent) dropZoneContent.style.display = 'flex';
            dropZone.classList.remove('has-files');
            return;
        }

        if (dropZoneContent) dropZoneContent.style.display = 'none';
        dropZone.classList.add('has-files');
        fileListContainer.classList.remove('hidden');
        fileCount.textContent = currentFiles.length;

        selectedFilesList.innerHTML = '';
        currentFiles.forEach((file, index) => {
            const li = document.createElement('li');
            li.className = 'file-item';
            li.innerHTML = `
                <div class="file-info">
                    <i class="fa-solid fa-file-zipper"></i>
                    <div style="flex:1;overflow:hidden;">
                        <div class="file-name">${file.name}</div>
                        <div class="file-size">${formatBytes(file.size)}</div>
                    </div>
                </div>
                <button class="btn-icon" data-index="${index}" title="Remover">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            `;
            selectedFilesList.appendChild(li);
        });

        selectedFilesList.querySelectorAll('.btn-icon').forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                removeFile(parseInt(btn.getAttribute('data-index')));
            });
        });
    }

    // ── Conversão ─────────────────────────────────────────────────────────
    convertBtn.addEventListener('click', async () => {
        if (currentFiles.length === 0) return;

        stepUpload.classList.add('hidden');
        stepLoading.classList.remove('hidden');
        hideAlert();

        const formData = new FormData();
        currentFiles.forEach(file => formData.append('files', file));

        try {
            const response = await fetch('/api/convert_batch', { method: 'POST', body: formData });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Erro na requisição.');
            }

            const data = await response.json();
            renderResults(data);

        } catch (error) {
            console.error('Erro na conversão em lote:', error);
            showAlert(`Falha na conversão: ${error.message}`, 'error');
            stepLoading.classList.add('hidden');
            stepUpload.classList.remove('hidden');
        }
    });

    // ── Renderização de Resultados ────────────────────────────────────────
    function renderResults(data) {
        stepLoading.classList.add('hidden');
        stepResult.classList.remove('hidden');

        terminalLogs.innerHTML = '';
        downloadFilesList.innerHTML = '';
        let successCount = 0;

        data.results.forEach(result => {
            const logHeader = document.createElement('div');
            logHeader.className = 'log-file-header';
            logHeader.textContent = `--- Processando: ${result.original_name} ---`;
            terminalLogs.appendChild(logHeader);

            const logContent = document.createElement('div');
            logContent.textContent = result.logs ||
                (result.status === 'success' ? 'Sucesso, nenhum log gerado.' : 'Falha sem logs.');
            if (result.status !== 'success') logContent.style.color = '#ff5f56';
            terminalLogs.appendChild(logContent);

            const li = document.createElement('li');
            li.className = 'file-item';

            if (result.status === 'success') {
                successCount++;
                li.innerHTML = `
                    <div class="file-info">
                        <i class="fa-solid fa-file-zipper" style="color:var(--success-color)"></i>
                        <div class="file-name">${result.output_filename}</div>
                    </div>
                    <a href="/api/download/${data.batch_id}/${result.id}" class="btn-icon btn-download" title="Baixar" download>
                        <i class="fa-solid fa-download"></i>
                    </a>
                `;
            } else {
                li.innerHTML = `
                    <div class="file-info">
                        <i class="fa-solid fa-triangle-exclamation" style="color:var(--danger-color)"></i>
                        <div class="file-name" style="text-decoration:line-through;">${result.original_name}</div>
                    </div>
                `;
            }
            downloadFilesList.appendChild(li);
        });

        terminalLogs.scrollTop = terminalLogs.scrollHeight;

        if (successCount > 0) {
            downloadAllBtn.disabled = false;
            downloadAllBtn.onclick = () => { window.location.href = `/api/download_all/${data.batch_id}`; };
        } else {
            downloadAllBtn.disabled = true;
        }
    }

    newBatchBtn.addEventListener('click', () => {
        currentFiles = [];
        updateFileListUI();
        stepResult.classList.add('hidden');
        stepUpload.classList.remove('hidden');
    });

    // ── Utilitários ───────────────────────────────────────────────────────
    function formatBytes(bytes, decimals = 2) {
        if (!+bytes) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
    }

    function showAlert(message, type) {
        alertMessage.textContent = message;
        alertBox.className = `alert ${type}`;
        alertIcon.className = type === 'success'
            ? 'fa-solid fa-circle-check'
            : 'fa-solid fa-triangle-exclamation';
        alertContainer.classList.remove('hidden');
        setTimeout(hideAlert, 5000);
    }

    function hideAlert() {
        alertContainer.classList.add('hidden');
    }
});
