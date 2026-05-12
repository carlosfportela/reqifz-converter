document.addEventListener('DOMContentLoaded', () => {
    // Seções
    const stepUpload = document.getElementById('step-upload');
    const stepLoading = document.getElementById('step-loading');
    const stepResult = document.getElementById('step-result');

    // Elementos Upload
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const browseBtn = document.getElementById('browse-btn');
    const dropZoneContent = document.querySelector('.drop-zone-content'); // may be null in index2.html
    const fileListContainer = document.getElementById('file-list-container');
    const selectedFilesList = document.getElementById('selected-files-list');
    const fileCount = document.getElementById('file-count');
    const clearAllBtn = document.getElementById('clear-all-btn');
    const convertBtn = document.getElementById('convert-btn');

    // Elementos Resultado
    const newBatchBtn = document.getElementById('new-batch-btn');
    const terminalLogs = document.getElementById('terminal-logs');
    const downloadFilesList = document.getElementById('download-files-list');
    const downloadAllBtn = document.getElementById('download-all-btn');

    // Alertas
    const alertContainer = document.getElementById('alert-container');
    const alertBox = document.getElementById('alert-box');
    const alertIcon = document.getElementById('alert-icon');
    const alertMessage = document.getElementById('alert-message');

    const translations = {
        'pt-BR': {
            'header_desc': 'Converta pacotes ReqIFZ do IBM RDNG de versões anteriores para a versão ELM 7.2. Arraste múltiplos arquivos para convertê-los em lote.',
            'algo_label': 'Algoritmo de Conversão:',
            'algo_v2': 'v2 (Regras Atuais)',
            'algo_v1': 'v1 (Regras Originais)',
            'drop_title': 'Arraste seus arquivos .reqifz aqui',
            'drop_desc': 'Você pode soltar múltiplos arquivos',
            'browse_btn': 'Procurar Arquivos',
            'selected_files': 'Arquivos Selecionados',
            'clear_all': 'Limpar tudo',
            'start_conversion': 'Iniciar Conversão em Lote',
            'processing': 'Processando arquivos, por favor aguarde...',
            'conversion_done': 'Conversão Concluída',
            'new_batch': 'Novo Lote',
            'logs_title': 'Logs de Conversão',
            'files_ready': 'Arquivos Prontos',
            'download_all': 'Baixar Todos (.zip)',
            'ignored_file': 'Arquivo ignorado',
            'not_reqifz': 'não é .reqifz',
            'req_error': 'Erro na requisição.',
            'conv_failed': 'Falha na conversão',
            'processing_log': 'Processando',
            'success_no_log': 'Sucesso, nenhum log gerado.',
            'fail_no_log': 'Falha sem logs.',
            'remove': 'Remover',
            'download': 'Baixar'
        },
        'en': {
            'header_desc': 'Convert ReqIFZ packages from earlier IBM RDNG versions to ELM 7.2. Drag and drop multiple files for batch conversion.',
            'algo_label': 'Conversion Algorithm:',
            'algo_v2': 'v2 (Current Rules)',
            'algo_v1': 'v1 (Original Rules)',
            'drop_title': 'Drop your .reqifz files here',
            'drop_desc': 'You can drop multiple files',
            'browse_btn': 'Browse Files',
            'selected_files': 'Selected Files',
            'clear_all': 'Clear all',
            'start_conversion': 'Start Batch Conversion',
            'processing': 'Processing files, please wait...',
            'conversion_done': 'Conversion Completed',
            'new_batch': 'New Batch',
            'logs_title': 'Conversion Logs',
            'files_ready': 'Ready Files',
            'download_all': 'Download All (.zip)',
            'ignored_file': 'Ignored file',
            'not_reqifz': 'is not .reqifz',
            'req_error': 'Request error.',
            'conv_failed': 'Conversion failed',
            'processing_log': 'Processing',
            'success_no_log': 'Success, no logs generated.',
            'fail_no_log': 'Failed without logs.',
            'remove': 'Remove',
            'download': 'Download'
        }
    };

    function getDefaultLanguage() {
        if (localStorage.getItem('appLang')) {
            return localStorage.getItem('appLang');
        }
        const browserLang = navigator.language || navigator.userLanguage;
        return browserLang.toLowerCase().startsWith('pt') ? 'pt-BR' : 'en';
    }

    let currentLang = getDefaultLanguage();

    function setLanguage(lang) {
        currentLang = lang;
        localStorage.setItem('appLang', lang);
        document.documentElement.lang = lang;
        
        document.querySelectorAll('.lang-btn').forEach(btn => {
            if (btn.dataset.lang === lang) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (translations[lang] && translations[lang][key]) {
                el.textContent = translations[lang][key];
            }
        });

        if (currentFiles.length > 0) {
            updateFileListUI();
        }
    }

    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            setLanguage(btn.dataset.lang);
        });
    });

    let currentFiles = [];
    setLanguage(currentLang);

    // --- Eventos Drag and Drop ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', (e) => {
        const files = Array.from(e.dataTransfer.files);
        addFiles(files);
    }, false);

    // --- Eventos Clique e Seleção ---
    browseBtn.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', function() {
        addFiles(Array.from(this.files));
        this.value = ''; // reseta input
    });

    // --- Lógica de Fila ---
    function addFiles(files) {
        hideAlert();
        let added = 0;
        
        files.forEach(file => {
            if (file.name.toLowerCase().endsWith('.reqifz')) {
                // Evitar duplicados por nome
                if (!currentFiles.find(f => f.name === file.name)) {
                    currentFiles.push(file);
                    added++;
                }
            } else {
                showAlert(`${translations[currentLang]['ignored_file']}: ${file.name} (${translations[currentLang]['not_reqifz']})`, 'error');
            }
        });

        if (added > 0) {
            updateFileListUI();
        }
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
                    <i class="fa-solid fa-file-zipper" style="color:var(--accent-color)"></i>
                    <div class="file-details" style="flex:1; overflow:hidden">
                        <div class="file-name">${file.name}</div>
                        <div class="file-size">${formatBytes(file.size)}</div>
                    </div>
                </div>
                <button class="btn-icon" data-index="${index}" title="${translations[currentLang]['remove']}"><i class="fa-solid fa-xmark"></i></button>
            `;
            selectedFilesList.appendChild(li);
        });

        // Eventos de remover
        selectedFilesList.querySelectorAll('.btn-icon').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                removeFile(parseInt(btn.getAttribute('data-index')));
            });
        });
    }

    // --- API & Conversão ---
    convertBtn.addEventListener('click', async () => {
        if (currentFiles.length === 0) return;

        // Transição de tela
        stepUpload.classList.add('hidden');
        stepLoading.classList.remove('hidden');
        hideAlert();

        const formData = new FormData();
        currentFiles.forEach(file => formData.append('files', file));
        
        const algorithmSelect = document.getElementById('algorithm-select');
        if (algorithmSelect) {
            formData.append('algorithm', algorithmSelect.value);
        }

        try {
            const response = await fetch('/api/convert_batch', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || translations[currentLang]['req_error']);
            }

            const data = await response.json();
            renderResults(data);

        } catch (error) {
            console.error('Batch conversion error:', error);
            showAlert(`${translations[currentLang]['conv_failed']}: ${error.message}`, 'error');
            // Volta pra tela 1
            stepLoading.classList.add('hidden');
            stepUpload.classList.remove('hidden');
        }
    });

    function renderResults(data) {
        stepLoading.classList.add('hidden');
        stepResult.classList.remove('hidden');

        terminalLogs.innerHTML = '';
        downloadFilesList.innerHTML = '';

        let successCount = 0;

        data.results.forEach(result => {
            // Render Logs
            const logHeader = document.createElement('div');
            logHeader.className = 'log-file-header';
            logHeader.textContent = `--- ${translations[currentLang]['processing_log']}: ${result.original_name} ---`;
            terminalLogs.appendChild(logHeader);

            const logContent = document.createElement('div');
            logContent.textContent = result.logs || (result.status === 'success' ? translations[currentLang]['success_no_log'] : translations[currentLang]['fail_no_log']);
            if (result.status !== 'success') logContent.style.color = '#ff5f56';
            terminalLogs.appendChild(logContent);

            // Render Links
            const li = document.createElement('li');
            li.className = 'file-item';
            
            if (result.status === 'success') {
                successCount++;
                li.innerHTML = `
                    <div class="file-info">
                        <i class="fa-solid fa-file-zipper" style="color:var(--success-color)"></i>
                        <div class="file-name">${result.output_filename}</div>
                    </div>
                    <a href="/api/download/${data.batch_id}/${result.id}" class="btn-icon btn-download" title="${translations[currentLang]['download']}" download>
                        <i class="fa-solid fa-download"></i>
                    </a>
                `;
            } else {
                li.innerHTML = `
                    <div class="file-info">
                        <i class="fa-solid fa-triangle-exclamation" style="color:var(--danger-color)"></i>
                        <div class="file-name" style="text-decoration: line-through">${result.original_name}</div>
                        <div class="file-size" style="color:var(--danger-color)">${translations[currentLang]['conv_failed']}</div>
                    </div>
                `;
            }
            downloadFilesList.appendChild(li);
        });

        // Scroll terminal to bottom
        terminalLogs.scrollTop = terminalLogs.scrollHeight;

        // Configurar botão de baixar todos
        if (successCount > 0) {
            downloadAllBtn.disabled = false;
            downloadAllBtn.onclick = () => {
                window.location.href = `/api/download_all/${data.batch_id}`;
            };
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

    // --- Utils ---
    function formatBytes(bytes, decimals = 2) {
        if (!+bytes) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
    }

    function showAlert(message, type) {
        alertMessage.textContent = message;
        alertBox.className = `alert ${type}`;
        alertIcon.className = type === 'success' ? 'fa-solid fa-circle-check' : 'fa-solid fa-triangle-exclamation';
        alertContainer.classList.remove('hidden');
        
        // Auto-hide alert after 5s
        setTimeout(hideAlert, 5000);
    }

    function hideAlert() {
        alertContainer.classList.add('hidden');
    }
});
