// Экспорт функций для Python
eel.expose(setProgress, 'setProgress');
eel.expose(addLog, 'addLog');
eel.expose(setSource, 'setSource');
eel.expose(updateBatchList, 'updateBatchList');
eel.expose(refreshPresets, 'refreshPresets');

let videoPlayer, playerControls, noVideoMsg;

function setProgress(percent) {
    const bar = document.getElementById('progress-bar');
    if (bar) bar.style.width = Math.min(100, Math.max(0, percent)) + '%';
}

function addLog(message) {
    const log = document.getElementById('log');
    if (log) {
        log.textContent += message + '\n';
        log.scrollTop = log.scrollHeight;
    }
}

function setSource(path) {
    document.getElementById('source').value = path;
    loadVideoToPlayer(path);
}

async function loadVideoToPlayer(source) {
    if (!source) return;
    videoPlayer = document.getElementById('video-player');
    playerControls = document.getElementById('player-controls');
    noVideoMsg = document.getElementById('no-video-msg');
    try {
        const url = await eel.get_video_url(source)();
        if (url) {
            videoPlayer.src = url;
            videoPlayer.style.display = 'block';
            playerControls.style.display = 'flex';
            if (noVideoMsg) noVideoMsg.style.display = 'none';
            return;
        }
    } catch (e) {}
    videoPlayer.style.display = 'none';
    playerControls.style.display = 'none';
    if (noVideoMsg) noVideoMsg.style.display = 'flex';
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function setupPlayerControls() {
    videoPlayer = document.getElementById('video-player');
    playerControls = document.getElementById('player-controls');
    const timeDisplay = document.getElementById('current-time-display');
    const btnStart = document.getElementById('btn-set-start');
    const btnEnd = document.getElementById('btn-set-end');

    if (!videoPlayer) return;

    videoPlayer.addEventListener('timeupdate', () => {
        if (timeDisplay) timeDisplay.textContent = formatTime(videoPlayer.currentTime);
    });

    btnStart.addEventListener('click', () => {
        document.getElementById('start').value = formatTime(videoPlayer.currentTime);
    });
    btnEnd.addEventListener('click', () => {
        document.getElementById('end').value = formatTime(videoPlayer.currentTime);
    });

    videoPlayer.addEventListener('loadstart', () => {
        if (videoPlayer.src) {
            videoPlayer.style.display = 'block';
            playerControls.style.display = 'flex';
            noVideoMsg.style.display = 'none';
        }
    });
    videoPlayer.addEventListener('error', () => {
        videoPlayer.style.display = 'none';
        playerControls.style.display = 'none';
        noVideoMsg.style.display = 'flex';
    });
}

// Вкладки
function initTabs() {
    document.querySelectorAll('.tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
        });
    });
}

// Очередь
function updateBatchList(tasksJson) {
    const tasks = JSON.parse(tasksJson);
    const container = document.getElementById('batch-list');
    container.innerHTML = tasks.map((t, i) => `
        <div class="batch-item">
            <span>${t.source}</span>
            <span>${t.start || '0'} - ${t.end || 'конец'}</span>
            <button onclick="removeBatchItem(${i})">×</button>
        </div>
    `).join('');
    document.getElementById('queue-count').textContent = tasks.length;
}

function getCurrentSettings() {
    return {
        source: document.getElementById('source').value,
        start: document.getElementById('start').value,
        end: document.getElementById('end').value,
        mode: document.getElementById('mode').value,
        accurate: document.getElementById('accurate').checked,
        audio_filter: document.getElementById('audio-filter').value
    };
}

async function addToBatch() {
    const settings = getCurrentSettings();
    await eel.add_to_batch(JSON.stringify(settings));
}

async function runBatch() { await eel.run_batch(); }
async function clearBatch() { await eel.clear_batch(); }

async function removeBatchItem(index) {
    await eel.remove_from_batch(index);
    // updateBatchList будет вызван из Python
}

// Пресеты
function refreshPresets(json) {
    const presets = JSON.parse(json);
    const container = document.getElementById('presets-list');
    container.innerHTML = presets.map(p => `
        <div class="preset-item">
            <span>${p.name}</span>
            <button onclick="applyPreset('${p.name}')">Применить</button>
            <button onclick="deletePreset('${p.name}')">Удалить</button>
        </div>
    `).join('');
    // Сохраним пресеты в dataset, чтобы applyPreset мог получить доступ
    document.getElementById('presets-list').dataset.presets = json;
}

async function loadPresets() {
    const json = await eel.get_presets()();
    refreshPresets(json);
}

async function savePreset() {
    const name = document.getElementById('preset-name').value.trim();
    if (!name) return;
    const settings = getCurrentSettings();
    await eel.save_preset(name, JSON.stringify(settings));
}

async function deletePreset(name) {
    await eel.delete_preset(name);
}

function applyPreset(name) {
    const json = document.getElementById('presets-list').dataset.presets;
    if (!json) return;
    const presets = JSON.parse(json);
    const preset = presets.find(p => p.name === name);
    if (preset) {
        const s = preset.settings;
        document.getElementById('start').value = s.start || '';
        document.getElementById('end').value = s.end || '';
        document.getElementById('mode').value = s.mode || 'video+audio';
        document.getElementById('accurate').checked = s.accurate || false;
        if (s.audio_filter) document.getElementById('audio-filter').value = s.audio_filter;
    }
}

// Инициализация
window.addEventListener('DOMContentLoaded', async () => {
    setupPlayerControls();
    initTabs();

    const settings = await eel.get_settings()();
    applySettings(settings);

    document.getElementById('btn-browse').addEventListener('click', async () => {
        const path = await eel.select_file()();
        if (path) {
            document.getElementById('source').value = path;
            loadVideoToPlayer(path);
        }
    });

    document.getElementById('btn-process').addEventListener('click', () => {
        const data = getCurrentSettings();
        eel.process(JSON.stringify(data));
    });

    // Очередь
    document.getElementById('btn-add-to-batch').addEventListener('click', addToBatch);
    document.getElementById('btn-run-batch').addEventListener('click', runBatch);
    document.getElementById('btn-clear-batch').addEventListener('click', clearBatch);

    // Пресеты
    document.getElementById('btn-save-preset').addEventListener('click', savePreset);
    await loadPresets();

    // Настройки
    document.getElementById('btn-settings').addEventListener('click', openSettings);
    document.getElementById('btn-close-settings').addEventListener('click', closeSettings);
    document.getElementById('btn-save-settings').addEventListener('click', saveSettings);
    document.getElementById('btn-browse-output').addEventListener('click', async () => {
        const path = await eel.select_dir()();
        if (path) document.getElementById('setting-output').value = path;
    });

    const initialSource = document.getElementById('source').value;
    if (initialSource) loadVideoToPlayer(initialSource);
});

function openSettings() {
    const modal = document.getElementById('settings-modal');
    const settings = JSON.parse(localStorage.getItem('settings') || '{}');
    document.getElementById('setting-output').value = settings.output_dir || '';
    document.getElementById('setting-quality').value = settings.youtube_quality || 'best';
    document.getElementById('setting-theme').value = settings.appearance_mode || 'dark';
    modal.classList.add('open');
}

function closeSettings() { document.getElementById('settings-modal').classList.remove('open'); }

async function saveSettings() {
    const btnSave = document.getElementById('btn-save-settings');
    const btnClose = document.getElementById('btn-close-settings');

    // Блокируем кнопку, чтобы избежать повторных нажатий
    btnSave.disabled = true;
    btnSave.textContent = 'Сохранение...';

    const newSettings = {
        output_dir: document.getElementById('setting-output').value,
        youtube_quality: document.getElementById('setting-quality').value,
        appearance_mode: document.getElementById('setting-theme').value
    };

    try {
        await eel.save_settings(newSettings);
        applyTheme(newSettings.appearance_mode);
        localStorage.setItem('settings', JSON.stringify(newSettings));
        closeSettings();
    } catch (error) {
        addLog('Ошибка при сохранении настроек');
        console.error(error);
    } finally {
        // Разблокируем кнопку (на случай, если окно не закрылось)
        btnSave.disabled = false;
        btnSave.textContent = 'Сохранить';
    }
}

function applySettings(settings) {
    localStorage.setItem('settings', JSON.stringify(settings));
    applyTheme(settings.appearance_mode);
}

function applyTheme(theme) {
    if (theme === 'light') document.body.classList.add('light');
    else document.body.classList.remove('light');
}