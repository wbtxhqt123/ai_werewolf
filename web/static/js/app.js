/**
 * @file This file contains the core client-side logic for the Werewolf game web interface.
 * It manages the game state, renders the UI, handles user interactions, and communicates
 * with the backend server via HTTP requests.
 */

// --- STATE MANAGEMENT ---

/**
 * @type {object} gameState - The central object holding the client-side state of the game.
 * @property {boolean} active - Whether a game is currently in progress.
 * @property {boolean} isAlive - The life status of the human player.
 * @property {Array<object>} players - A list of all players in the game.
 * @property {Array<object>} logs - A list of log entries received from the server.
 * @property {number} lastLogIndex - The index of the last log received, used for polling.
 * @property {string} myRole - The role of the human player.
 * @property {string} myAvatar - The avatar of the human player.
 * @property {string} phase - The current game phase (e.g., 'Day 1', 'Night 1').
 * @property {object|null} pendingAction - An object describing the action required from the user.
 * @property {string} lang - The current language ('zh' or 'en').
 * @property {string|null} gameId - The unique identifier for the current game session.
 * @property {boolean} isSending - A flag to prevent duplicate action submissions.
 * @property {boolean} isPolling - A flag to prevent overlapping poll requests.
 */
let gameState = {
    active: false,
    isAlive: true,
    players: [],
    logs: [],
    lastLogIndex: 0,
    myRole: '',
    myAvatar: '👤',
    phase: 'Day 1',
    pendingAction: null,
    lang: 'zh',
    gameId: null,
    isSending: false,
    isPolling: false
};

/** @type {number|null} - The interval ID for the game state polling timer. */
let pollingInterval = null;

// --- CONSTANTS & CONFIGURATION ---

/** @const {object} I18N - Contains all internationalization strings for Chinese and English. */
const I18N = {
    zh: {
        title: "狼人杀",
        selectAvatar: "选择头像",
        selectRole: "选择身份",
        playerCount: "玩家人数",
        advancedSettings: "高级设置",
        provider: "提供商",
        apiKey: "API 密钥 (可选)",
        baseUrl: "接口地址 (可选)",
        modelName: "模型名称 (可选)",
        saveSettings: "保存并关闭",
        startGame: "开始游戏",
        waitingStart: "等待游戏开始...",
        gameOver: "游戏结束",
        reconnected: "已重连到游戏",
        networkError: "网络错误",
        confirmQuit: "确定要退出吗？",
        typeMessage: "输入消息...",
        send: "发送",
        waiting: "等待中...",
        day: "第 {n} 天",
        night: "第 {n} 夜",
        alive: "存活",
        dead: "死亡",
        roles: {
            Villager: "村民",
            Werewolf: "狼人",
            Witch: "女巫",
            Seer: "预言家",
            Guard: "守卫",
            Hunter: "猎人",
            "Black Werewolf King": "黑狼王",
            Random: "随机"
        },
        roleDescs: {
            Villager: "在白天找出狼人并投票将其放逐。",
            Werewolf: "每晚杀死一名村民，白天伪装成村民。",
            Witch: "拥有两瓶药：一瓶救人，一瓶毒人。",
            Seer: "每晚可以查验一名玩家的身份。",
            Guard: "每晚可以守护一名玩家不被杀死。",
            Hunter: "被淘汰时可以开枪带走另一名玩家。",
            "Black Werewolf King": "狼人首领，可以杀人，也有特殊能力。",
            Random: "随机分配身份。"
        },
        eval: {
            title: "游戏评价",
            intro: "选择AI评价者的性格：",
            modes: {
                mild: "😊 温和",
                neutral: "😐 中立",
                mean: "😈 嘲讽"
            },
            apiKeyWarning: "评价需要API Key",
            startBtn: "开始评价",
            evaluating: "评价中...",
            inputPlaceholder: "与AI争论...",
            send: "发送"
        },

        newMessages: "⬇️ 新消息",
        operationsHistory: "操作历史",
        opHistory: {
            title: "操作历史",
            role: "你的角色",
            teammates: "狼人队友",
            king: "狼王",
            saved: "你救的人",
            poisoned: "你毒的人",
            checked: "你查验的人",
            camp: "阵营",
            protected: "你守护的人",
            shot: "你射击的人",
            noData: "没有可显示的操作历史。"
        }
    },
    en: {
        title: "Werewolf",
        selectAvatar: "Select Avatar",
        selectRole: "Select Role",
        playerCount: "Number of Players",
        advancedSettings: "Advanced Settings",
        apiKey: "API Key (Optional)",
        baseUrl: "Base URL (Optional)",
        modelName: "Model Name (Optional)",
        saveSettings: "Save & Close",
        startGame: "Start Game",
        waitingStart: "Waiting for game to start...",
        gameOver: "Game Over",
        reconnected: "Reconnected to existing game.",
        networkError: "Network error",
        confirmQuit: "Are you sure you want to quit?",
        typeMessage: "Type a message...",
        send: "Send",
        waiting: "Waiting...",
        day: "Day {n}",
        night: "Night {n}",
        alive: "Alive",
        dead: "Dead",
        roles: {
            Villager: "Villager",
            Werewolf: "Werewolf",
            Witch: "Witch",
            Seer: "Seer",
            Guard: "Guard",
            Hunter: "Hunter",
            "Black Werewolf King": "Black Werewolf King",
            Random: "Random"
        },
        roleDescs: {
            Villager: "Find the werewolves and vote them out during the day.",
            Werewolf: "Kill a villager each night and pretend to be a villager during the day.",
            Witch: "Has two potions: one to save a player, one to eliminate a player.",
            Seer: "Can check the identity of one player each night.",
            Guard: "Can protect one player from being killed each night.",
            Hunter: "Can shoot another player when eliminated.",
            "Black Werewolf King": "Leader of the werewolves. Can kill, but also has special abilities.",
            Random: "Randomly assigned role."
        },
        eval: {
            title: "Game Evaluation",
            intro: "Choose a personality for the AI evaluator:",
            modes: {
                mild: "😊 Mild",
                neutral: "😐 Neutral",
                mean: "😈 Sneer"
            },
            apiKeyWarning: "API Key required for evaluation",
            startBtn: "Start Evaluation",
            evaluating: "Evaluating...",
            inputPlaceholder: "Argue with the AI...",
            send: "Send"
        },

        newMessages: "⬇️ New Messages",
        operationsHistory: "Operations History",
        opHistory: {
            title: "Operations History",
            role: "Your Role",
            teammates: "Werewolf Teammates",
            king: "Werewolf King",
            saved: "Saved",
            poisoned: "Poisoned",
            checked: "Checked",
            camp: "Camp",
            protected: "Protected",
            shot: "Shot",
            noData: "No operations history to display."
        }
    }
};

/** @const {Array<object>} ROLES - Defines the available roles in the game. */
const ROLES = [
    { id: 'Villager', icon: '👱‍♀️' },
    { id: 'Werewolf', icon: '🐺' },
    { id: 'Witch', icon: '🧙‍♀️' },
    { id: 'Seer', icon: '🔮' },
    { id: 'Guard', icon: '🛡️' },
    { id: 'Hunter', icon: '🔫' },
    { id: 'Black Werewolf King', icon: '👹' },
    { id: 'Random', icon: '🎲' }
];

/** @const {Array<string>} AVATARS - A list of available avatars for players. */
const AVATARS = ['🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯', '🦁', '🐮', '🐷', '🐵'];

/** @const {object} ROLE_DISTRIBUTION - Defines the role composition for different player counts. */
const ROLE_DISTRIBUTION = {
    6: {
        "Werewolf": 2,
        "Villager": 2,
        "Seer": 1,
        "Guard": 1
    },
    9: {
        "Black Werewolf King": 1,
        "Werewolf": 2,
        "Villager": 3,
        "Seer": 1,
        "Witch": 1,
        "Guard": 1
    },
    12: {
        "Black Werewolf King": 1,
        "Werewolf": 3,
        "Villager": 4,
        "Seer": 1,
        "Witch": 1,
        "Hunter": 1,
        "Guard": 1
    }
};

// --- DOM ELEMENT CACHING ---

/** @const {object} screens - References to the main screen containers. */
const screens = {
    setup: document.getElementById('setup-screen'),
    game: document.getElementById('game-screen')
};

/** @const {object} setupUI - References to DOM elements on the setup screen. */
const setupUI = {
    roleSelection: document.getElementById('role-selection'),
    avatarSelection: document.getElementById('avatar-selection'),
    playerCountGroup: document.getElementById('player-count-group'),
    startBtn: document.getElementById('start-game-btn'),
    openSettingsBtn: document.getElementById('open-settings-btn'),
    apiKeyInput: document.getElementById('api-key'),
    title: document.querySelector('.setup-container h1'),
    labels: document.querySelectorAll('.form-group label'),
};

/** @const {object} gameUI - References to DOM elements on the game screen. */
const gameUI = {
    phaseIndicator: document.getElementById('phase-indicator'),
    playersLeft: document.getElementById('players-left'),
    playersRight: document.getElementById('players-right'),
    chatBox: document.getElementById('chat-box'),
    myRole: document.getElementById('my-role'),
    myStatus: document.querySelector('.my-status'),
    actionPrompt: document.getElementById('action-prompt'),
    input: document.getElementById('game-input'),
    sendBtn: document.getElementById('send-action-btn'),
    choiceButtons: document.getElementById('choice-buttons'),
    quitBtn: document.getElementById('quit-btn'),
    debugBtn: document.getElementById('toggle-debug-btn'),
    gameLangBtn: document.getElementById('game-lang-btn'),
    lobbyLangBtn: document.getElementById('lobby-lang-btn'),
    newMessagesIndicator: document.getElementById('new-messages-indicator'),
    togglePlayersBtn: document.getElementById('toggle-players-btn'),
    showPlayersBtn: document.getElementById('show-players-btn'),
    playersSidebar: document.getElementById('players-sidebar'),
    voiceInputBtn: document.getElementById('voice-input-btn')
};

/** @const {object} evalUI - References to DOM elements in the evaluation modal. */
const evalUI = {
    modal: document.getElementById('evaluation-modal'),
    closeBtn: document.querySelector('#evaluation-modal .close-modal'),
    setupSection: document.getElementById('eval-setup'),
    chatSection: document.getElementById('eval-chat-section'),
    modeBtns: document.querySelectorAll('.eval-mode-btn'),
    apiKeySection: document.getElementById('eval-api-key-section'),
    apiKeyInput: document.getElementById('eval-api-key'),
    startBtn: document.getElementById('start-eval-btn'),
    chatBox: document.getElementById('eval-chat-box'),
    input: document.getElementById('eval-input'),
    sendBtn: document.getElementById('send-eval-btn')
};

/** @const {object} settingsUI - References to DOM elements in the settings modal. */
const settingsUI = {
    modal: document.getElementById('settings-modal'),
    closeBtn: document.getElementById('close-settings-btn'),
    saveBtn: document.getElementById('save-settings-btn')
};

// --- INITIALIZATION ---

/**
 * Initializes the application on page load.
 * Sets up default UI elements, event listeners, and language settings.
 */
function init() {
    const defaultCount = 9;
    renderRoleSelection(defaultCount);
    renderAvatarSelection();
    setupEventListeners();
    updateLanguage();
    
    let debugVisible = false;
    if (gameUI.debugBtn) {
        gameUI.debugBtn.addEventListener('click', () => {
            debugVisible = !debugVisible;
            document.querySelectorAll('.message.debug').forEach(el => {
                el.classList.toggle('visible', debugVisible);
            });
            gameUI.debugBtn.style.opacity = debugVisible ? '1' : '0.5';
        });
    }

    if (gameUI.gameLangBtn) {
        gameUI.gameLangBtn.addEventListener('click', toggleLanguage);
    }
    
    if (gameUI.lobbyLangBtn) {
        gameUI.lobbyLangBtn.addEventListener('click', toggleLanguage);
    }

    if (gameUI.newMessagesIndicator) {
        gameUI.newMessagesIndicator.addEventListener('click', () => {
            scrollToBottom(true);
        });
    }

    if (gameUI.chatBox) {
        gameUI.chatBox.addEventListener('scroll', checkScrollPosition);
    }

    if (gameUI.togglePlayersBtn) {
        gameUI.togglePlayersBtn.addEventListener('click', () => {
            gameUI.playersSidebar.classList.add('collapsed');
            gameUI.showPlayersBtn.classList.remove('hidden');
        });
    }

    if (gameUI.showPlayersBtn) {
        gameUI.showPlayersBtn.addEventListener('click', () => {
            gameUI.playersSidebar.classList.remove('collapsed');
            gameUI.showPlayersBtn.classList.add('hidden');
        });
    }

    setupEvaluationListeners();
    setupSettingsListeners();
    setupVoiceInput();
}

/**
 * Sets up the voice input functionality.
 * Checks for browser support and handles microphone access and recording.
 */
function setupVoiceInput() {
    if (!gameUI.voiceInputBtn) return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.warn("MediaDevices API not supported in this browser.");
        gameUI.voiceInputBtn.style.display = 'none';
        return;
    }

    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;

    gameUI.voiceInputBtn.addEventListener('click', async () => {
        if (isRecording) {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                gameUI.voiceInputBtn.classList.remove('recording');
                isRecording = false;
            }
        } else {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    await sendAudioForTranscription(audioBlob);
                    stream.getTracks().forEach(track => track.stop());
                };

                mediaRecorder.start();
                isRecording = true;
                gameUI.voiceInputBtn.classList.add('recording');
            } catch (err) {
                console.error("Error accessing microphone:", err);
                alert(gameState.lang === 'zh' ? "无法访问麦克风。" : "Cannot access microphone.");
            }
        }
    });
}

/**
 * Sends the recorded audio blob to the backend for transcription.
 * @param {Blob} audioBlob - The recorded audio data.
 */
async function sendAudioForTranscription(audioBlob) {
    const originalPlaceholder = gameUI.input.placeholder;
    gameUI.input.placeholder = gameState.lang === 'zh' ? "正在转录..." : "Transcribing...";
    gameUI.input.disabled = true;

    const formData = new FormData();
    formData.append("file", audioBlob, "recording.webm");
    formData.append("language", gameState.lang === 'zh' ? 'zh' : 'en');

    try {
        const response = await fetch('/api/transcribe', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            if (data.text) {
                const currentText = gameUI.input.value;
                gameUI.input.value = currentText + (currentText ? " " : "") + data.text;
            }
        } else {
            console.error("Transcription failed:", await response.text());
            alert(gameState.lang === 'zh' ? "转录失败。" : "Transcription failed.");
        }
    } catch (error) {
        console.error("Error sending audio:", error);
        alert(gameState.lang === 'zh' ? "网络错误。" : "Network error.");
    } finally {
        gameUI.input.disabled = false;
        gameUI.input.placeholder = originalPlaceholder;
        gameUI.input.focus();
    }
}

/**
 * Sets up event listeners for the advanced settings modal.
 */
function setupSettingsListeners() {
    const PROVIDERS = {
        "doubao": {
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "model": "doubao-seed-1-6-flash-250828"
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o"
        },
        "gemini": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "model": "gemini-1.5-flash"
        },
        "qwen": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus"
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat"
        },
        "custom": {
            "base_url": "",
            "model": ""
        }
    };

    if (setupUI.openSettingsBtn) {
        setupUI.openSettingsBtn.addEventListener('click', () => {
            settingsUI.modal.classList.add('active');
            trapFocus(settingsUI.modal);
            settingsUI.modal.querySelector('select').focus();
        });
    }

    const providerSelect = document.getElementById('provider-select');
    const baseUrlInput = document.getElementById('base-url');

    if (providerSelect) {
        providerSelect.addEventListener('change', (e) => {
            const provider = e.target.value;
            const config = PROVIDERS[provider];
            if (config) {
                if (baseUrlInput) baseUrlInput.value = config.base_url;
            }
        });
        
        if (baseUrlInput && !baseUrlInput.value) {
             providerSelect.dispatchEvent(new Event('change'));
        }
    }

    if (settingsUI.closeBtn) {
        settingsUI.closeBtn.addEventListener('click', () => {
            settingsUI.modal.classList.remove('active');
        });
    }

    if (settingsUI.saveBtn) {
        settingsUI.saveBtn.addEventListener('click', () => {
            settingsUI.modal.classList.remove('active');
        });
    }
}

/**
 * Sets up event listeners for the post-game evaluation modal.
 */
function setupEvaluationListeners() {
    evalUI.closeBtn.onclick = () => {
        evalUI.modal.classList.remove('active');
    };

    evalUI.modeBtns.forEach(btn => {
        btn.onclick = () => {
            evalUI.modeBtns.forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            evalUI.startBtn.disabled = false;
        };
    });

    evalUI.startBtn.onclick = startEvaluation;

    evalUI.sendBtn.onclick = sendEvaluationMessage;
    evalUI.input.onkeydown = (e) => {
        if (e.key === 'Enter') sendEvaluationMessage();
    };

    const newGameBtn = document.getElementById('new-game-btn');
    if (newGameBtn) {
        newGameBtn.onclick = () => {
            location.reload();
        };
    }
}

/**
 * Toggles the display language between English and Chinese.
 */
function toggleLanguage() {
    gameState.lang = gameState.lang === 'zh' ? 'en' : 'zh';
    updateLanguage();
    renderLogs();
}

/**
 * Re-renders all logs currently stored in the game state.
 * This is used after a language change to update the display.
 */
function renderLogs() {
    gameUI.chatBox.innerHTML = '';
    gameState.logs.forEach(processLog);
    scrollToBottom();
}

/**
 * Initializes tooltips for the player count selection buttons.
 * The tooltips show the role distribution for each player count.
 */
function initPlayerCountTooltips() {
    const buttons = setupUI.playerCountGroup.querySelectorAll('.toggle-btn');
    buttons.forEach(btn => {
        const count = parseInt(btn.dataset.value);
        const distribution = ROLE_DISTRIBUTION[count];
        if (distribution) {
            const tooltip = document.createElement('div');
            tooltip.className = 'count-tooltip';
            
            const t = I18N[gameState.lang];
            const distText = Object.entries(distribution).map(([role, num]) => {
                const roleObj = ROLES.find(r => r.id === role);
                return `${roleObj ? roleObj.icon : ''} ${num}`;
            }).join(' ');
            
            tooltip.innerText = distText;
            btn.appendChild(tooltip);
        }
    });
}

/**
 * Updates all text in the UI to the currently selected language.
 */
function updateLanguage() {
    const t = I18N[gameState.lang];
    
    // Setup Screen
    if (setupUI.title) setupUI.title.innerText = t.title;
    if (setupUI.labels[0]) setupUI.labels[0].innerText = t.selectAvatar;
    if (setupUI.labels[1]) setupUI.labels[1].innerText = t.playerCount;
    if (setupUI.labels[2]) setupUI.labels[2].innerText = t.selectRole;
    
    // Settings Modal
    const settingsModal = document.getElementById('settings-modal');
    if (settingsModal) {
        const title = settingsModal.querySelector('h2');
        if (title) title.innerText = t.advancedSettings;
    }
    const settingsLabels = document.querySelectorAll('#settings-modal label');
    if (settingsLabels[0]) settingsLabels[0].innerText = t.provider;
    if (settingsLabels[1]) settingsLabels[1].innerText = t.apiKey;
    if (settingsLabels[2]) settingsLabels[2].innerText = t.baseUrl;
    if (settingsLabels[3]) settingsLabels[3].innerText = t.modelName;
    if (settingsUI.saveBtn) settingsUI.saveBtn.innerText = t.saveSettings;
    if (setupUI.openSettingsBtn) setupUI.openSettingsBtn.innerText = "⚙️ " + t.advancedSettings;
    if (setupUI.startBtn) setupUI.startBtn.innerText = t.startGame;
    
    const selectedCountEl = document.querySelector('.toggle-btn.active');
    const count = selectedCountEl ? parseInt(selectedCountEl.dataset.value) : 9;
    renderRoleSelection(count);
    
    document.querySelectorAll('.count-tooltip').forEach(el => el.remove());
    initPlayerCountTooltips();

    // Game Screen
    if (gameUI.input) gameUI.input.placeholder = t.typeMessage;
    if (gameUI.sendBtn) gameUI.sendBtn.innerText = t.send;
    if (gameUI.myStatus) gameUI.myStatus.innerText = gameState.isAlive ? t.alive : t.dead;
    if (gameUI.newMessagesIndicator) gameUI.newMessagesIndicator.innerText = t.newMessages;
    
    if (gameState.myRole) {
        if (t.roles[gameState.myRole]) {
            gameUI.myRole.innerText = t.roles[gameState.myRole];
        } else {
            gameUI.myRole.innerText = gameState.myRole;
        }
    }

    // Evaluation Modal
    if (evalUI.modal) {
        const t_eval = I18N[gameState.lang].eval;
        document.getElementById('eval-title').innerText = t_eval.title;
        document.getElementById('eval-intro').innerText = t_eval.intro;
        const modeBtns = document.querySelectorAll('.eval-mode-btn');
        if (modeBtns.length >= 3) {
            modeBtns[0].innerText = t_eval.modes.mild;
            modeBtns[1].innerText = t_eval.modes.neutral;
            modeBtns[2].innerText = t_eval.modes.mean;
        }
        const warningText = document.querySelector('.warning-text');
        if (warningText) warningText.innerText = t_eval.apiKeyWarning;
        if (evalUI.startBtn.disabled) {
             evalUI.startBtn.innerText = t_eval.evaluating;
        } else {
             evalUI.startBtn.innerText = t_eval.startBtn;
        }
        evalUI.input.placeholder = t_eval.inputPlaceholder;
        evalUI.sendBtn.innerText = t_eval.send;
    }

    // Records Modal
    const recordsModal = document.getElementById('records-modal');
    if (recordsModal) {
        const t_records = I18N[gameState.lang].records;
        const title = recordsModal.querySelector('h2');
        if (title) title.innerText = t_records.title;
        const tabs = recordsModal.querySelectorAll('.tab-btn');
        if (tabs.length >= 2) {
            tabs[0].innerText = t_records.votingHistory;
            tabs[1].innerText = t_records.casualties;
        }
        const footerCloseBtn = document.getElementById('close-records-footer-btn');
        if (footerCloseBtn) {
            footerCloseBtn.innerText = t_records.close;
        }
        if (recordsModal.classList.contains('active')) {
             fetchAndRenderRecords();
        }
    }
}

/**
 * Renders the role selection UI based on the number of players.
 * @param {number} playerCount - The number of players in the game.
 */
function renderRoleSelection(playerCount) {
    const t = I18N[gameState.lang];
    let currentSelection = gameState.myRole || 'Villager';
    
    let availableRoles = ROLES;
    if (playerCount && ROLE_DISTRIBUTION[playerCount]) {
        const allowedRoles = Object.keys(ROLE_DISTRIBUTION[playerCount]);
        allowedRoles.push('Random');
        availableRoles = ROLES.filter(r => allowedRoles.includes(r.id));
        
        if (!gameState.active && !allowedRoles.includes(currentSelection)) {
            currentSelection = 'Random';
            gameState.myRole = 'Random';
        }
    }

    setupUI.roleSelection.innerHTML = availableRoles.map(role => `
        <div class="role-option ${role.id === currentSelection ? 'selected' : ''}" data-role="${role.id}" data-description="${t.roleDescs[role.id]}" tabindex="0">
            <div class="role-icon">${role.icon}</div>
            <div class="role-name">${t.roles[role.id]}</div>
        </div>
    `).join('');
}


/**
 * Renders the avatar selection UI.
 */
function renderAvatarSelection() {
    const container = setupUI.avatarSelection;
    if (!container) {
        console.error("Avatar selection container not found!");
        return;
    }
    container.innerHTML = AVATARS.map((avatar, index) => `
        <div class="avatar-option ${index === 0 ? 'selected' : ''}" data-avatar="${avatar}" tabindex="0">
            <div class="avatar-icon">${avatar}</div>
        </div>
    `).join('');
}

/**
 * Sets up all the primary event listeners for the application.
 */
function setupEventListeners() {
    // Setup Screen
    setupUI.roleSelection.addEventListener('click', (e) => {
        const option = e.target.closest('.role-option');
        if (option) {
            document.querySelectorAll('.role-option').forEach(el => el.classList.remove('selected'));
            option.classList.add('selected');
            gameState.myRole = option.dataset.role;
        }
    });

    setupUI.roleSelection.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault(); // prevent space from scrolling
            const option = e.target.closest('.role-option');
            if (option) {
                document.querySelectorAll('.role-option').forEach(el => el.classList.remove('selected'));
                option.classList.add('selected');
                gameState.myRole = option.dataset.role;
            }
        }
    });

    setupUI.avatarSelection.addEventListener('click', (e) => {
        const option = e.target.closest('.avatar-option');
        if (option) {
            document.querySelectorAll('.avatar-option').forEach(el => el.classList.remove('selected'));
            option.classList.add('selected');
        }
    });

    setupUI.avatarSelection.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault(); // prevent space from scrolling
            const option = e.target.closest('.avatar-option');
            if (option) {
                document.querySelectorAll('.avatar-option').forEach(el => el.classList.remove('selected'));
                option.classList.add('selected');
            }
        }
    });

    setupUI.playerCountGroup.addEventListener('click', (e) => {
        const btn = e.target.closest('.toggle-btn');
        if (btn) {
            document.querySelectorAll('.toggle-btn').forEach(el => el.classList.remove('active'));
            btn.classList.add('active');
            const count = parseInt(btn.dataset.value);
            renderRoleSelection(count);
        }
    });

    initPlayerCountTooltips();
    setupUI.startBtn.addEventListener('click', startGame);

    // Game Screen
    gameUI.sendBtn.addEventListener('click', () => sendTextAction());
    gameUI.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendTextAction();
    });

    gameUI.quitBtn.addEventListener('click', () => {
        if (confirm(I18N[gameState.lang].confirmQuit)) {
            location.reload();
        }
    });


}



/**
 * Starts a new game.
 * Collects settings from the setup screen and sends a request to the backend.
 */
async function startGame() {
    const selectedRoleEl = document.querySelector('.role-option.selected');
    const selectedAvatarEl = document.querySelector('.avatar-option.selected');
    const selectedCountEl = document.querySelector('.toggle-btn.active');
    
    const role = gameState.myRole || (selectedRoleEl ? selectedRoleEl.dataset.role : 'Villager');
    const avatar = selectedAvatarEl ? selectedAvatarEl.dataset.avatar : '👤';
    const count = selectedCountEl ? parseInt(selectedCountEl.dataset.value) : 9;
    const apiKey = setupUI.apiKeyInput.value;
    const baseUrl = document.getElementById('base-url').value;
    const modelName = document.getElementById('model-name').value;
    const provider = document.getElementById('provider-select').value;

    try {
        const response = await fetch('/api/game/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                num_players: count,
                user_role: role,
                user_avatar: avatar,
                api_key: apiKey,
                base_url: baseUrl,
                model_name: modelName,
                provider: provider,
                language: gameState.lang
            })
        });

        if (response.ok) {
            const data = await response.json();
            gameState.gameId = data.game_id;
            gameState.myRole = role;
            gameState.myAvatar = avatar;
            gameState.isAlive = true;
            switchScreen('game');
            gameState.active = true;
            startPolling();
            addSystemMessage(I18N[gameState.lang].waitingStart);
            document.querySelector('.my-avatar').innerText = avatar;
        } else {
            const data = await response.json();
            alert('Failed to start game: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error starting game:', error);
        alert(I18N[gameState.lang].networkError);
    }
}

/**
 * Switches the visible screen between 'setup' and 'game'.
 * @param {string} screenName - The name of the screen to show.
 */
function switchScreen(screenName) {
    Object.values(screens).forEach(s => s.classList.remove('active'));
    screens[screenName].classList.add('active');
}

/**
 * Starts the long-polling process to get game state updates from the server.
 */
function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(pollGameState, 1000);
}

/**
 * Polls the server for the latest game state.
 * This function is the heart of the client-server communication during the game.
 */
async function pollGameState() {
    if (!gameState.active || !gameState.gameId) return;
    if (gameState.isPolling) return;

    gameState.isPolling = true;

    try {
        const response = await fetch(`/api/game/${gameState.gameId}/state?last_log_index=${gameState.lastLogIndex}`);
        const data = await response.json();

        const justDied = new Set();
        if (data.logs && data.logs.length > 0) {
            const shouldScroll = isUserNearBottom();
            gameState.logs = gameState.logs.concat(data.logs);
            
            data.logs.forEach(log => {
                processLog(log);
                if (log.type === 'PLAYER_ELIMINATED' && log.target) {
                    justDied.add(log.target.name);
                }
            });
            gameState.lastLogIndex += data.logs.length;
            scrollToBottom(shouldScroll);
        }

        if (data.players) {
            updatePlayers(data.players, justDied);
            
            const myPlayer = data.players.find(p => p.name === 'Player 1');
            if (myPlayer) {
                gameState.isAlive = myPlayer.is_alive;
                if (gameUI.myStatus) {
                    gameUI.myStatus.innerText = gameState.isAlive ? I18N[gameState.lang].alive : I18N[gameState.lang].dead;
                }

                const myStatusIcons = document.querySelector('.my-status-icons');
                if (myStatusIcons) {
                    myStatusIcons.innerText = myPlayer.is_sheriff ? '⭐' : '';
                }

                if (myPlayer.role && myPlayer.role !== 'Unknown' && myPlayer.role !== gameState.myRole) {
                    gameState.myRole = myPlayer.role;
                    updateLanguage();
                } else if (gameState.myRole && I18N[gameState.lang].roles[gameState.myRole] && gameUI.myRole.innerText !== I18N[gameState.lang].roles[gameState.myRole]) {
                    gameUI.myRole.innerText = I18N[gameState.lang].roles[gameState.myRole];
                } else if (gameState.myRole && !I18N[gameState.lang].roles[gameState.myRole]) {
                    console.warn("Role translation missing for:", gameState.myRole);
                    gameUI.myRole.innerText = gameState.myRole;
                }
            }
        }

        handleInputRequest(data.input_required);

        if (!data.game_active && !data.input_required) {
            gameState.active = false;
            clearInterval(pollingInterval);
            addSystemMessage(I18N[gameState.lang].gameOver);
            
            setTimeout(() => {
                showEvaluationModal();
            }, 2000);
        }

    } catch (error) {
        console.error('Polling error:', error);
    } finally {
        gameState.isPolling = false;
    }
}

/**
 * Displays the post-game evaluation modal.
 */
function showEvaluationModal() {
    const gameOverHTML = `
        <div class="game-over-tabs">
            <button id="operations-history-btn" class="tab-button">${I18N[gameState.lang].operationsHistory}</button>
            <button id="evaluate-game-btn" class="tab-button">${I18N[gameState.lang].eval.title}</button>
        </div>
    `;
    evalUI.modal.querySelector('.modal-content').insertAdjacentHTML('afterbegin', gameOverHTML);

    document.getElementById('evaluate-game-btn').addEventListener('click', () => {
        evalUI.setupSection.style.display = 'block';
        document.getElementById('operations-history-btn').classList.remove('active');
        document.getElementById('evaluate-game-btn').classList.add('active');
    });

    document.getElementById('operations-history-btn').addEventListener('click', () => {
        evalUI.setupSection.style.display = 'none';
        document.getElementById('evaluate-game-btn').classList.remove('active');
        document.getElementById('operations-history-btn').classList.add('active');
        showOperationsHistory();
    });


    evalUI.modal.classList.add('active');
    trapFocus(evalUI.modal);
    evalUI.modal.querySelector('.eval-mode-btn').focus();
    evalUI.setupSection.style.display = 'block';
    evalUI.chatSection.style.display = 'none';
    
    const cachedKey = setupUI.apiKeyInput.value;
    if (cachedKey) {
        evalUI.apiKeySection.style.display = 'none';
        evalUI.apiKeyInput.value = cachedKey;
    } else {
        evalUI.apiKeySection.style.display = 'block';
    }
}

/**
 * Starts the game evaluation process.
 */
async function startEvaluation() {
    const selectedModeBtn = document.querySelector('.eval-mode-btn.selected');
    if (!selectedModeBtn) return;
    
    const mode = selectedModeBtn.dataset.mode;
    const apiKey = evalUI.apiKeyInput.value;
    
    if (!apiKey) {
        alert(I18N[gameState.lang].eval.apiKeyWarning);
        evalUI.startBtn.disabled = false;
        evalUI.startBtn.innerText = I18N[gameState.lang].eval.startBtn;
        return;
    }

    evalUI.startBtn.disabled = true;
    evalUI.startBtn.innerText = I18N[gameState.lang].eval.evaluating;

    try {
        const response = await fetch('/api/game/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_id: gameState.gameId,
                mode: mode,
                api_key: apiKey,
                language: gameState.lang
            })
        });

        const data = await response.json();
        
        if (response.ok) {
            evalUI.setupSection.style.display = 'none';
            evalUI.chatSection.style.display = 'flex';
            evalUI.chatBox.innerHTML = '';
            
            renderEvaluationChat(data.evaluation, false);
        } else {
            alert('Evaluation failed: ' + (data.detail || 'Unknown error'));
            evalUI.startBtn.disabled = false;
            evalUI.startBtn.innerText = I18N[gameState.lang].eval.startBtn;
        }
    } catch (error) {
        console.error('Evaluation error:', error);
        alert('Network error during evaluation.');
        evalUI.startBtn.disabled = false;
        evalUI.startBtn.innerText = I18N[gameState.lang].eval.startBtn;
    }
}

/**
 * Sends a follow-up message in the evaluation chat.
 */
async function sendEvaluationMessage() {
    const text = evalUI.input.value.trim();
    if (!text) return;

    renderEvaluationChat(text, true);
    evalUI.input.value = '';
    
    evalUI.input.disabled = true;
    evalUI.sendBtn.disabled = true;

    try {
        const response = await fetch('/api/game/evaluation/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_id: gameState.gameId,
                message: text
            })
        });

        const data = await response.json();
        
        if (response.ok) {
            renderEvaluationChat(data.reply, false);
        } else {
            renderEvaluationChat("Error: " + (data.detail || "Failed to get reply"), false);
        }
    } catch (error) {
        console.error('Chat error:', error);
        renderEvaluationChat("Network error.", false);
    } finally {
        evalUI.input.disabled = false;
        evalUI.sendBtn.disabled = false;
        evalUI.input.focus();
    }
}

/**
 * Renders a message in the evaluation chat box.
 * @param {string} message - The message content.
 * @param {boolean} isUser - Whether the message is from the user or the AI.
 */
function renderEvaluationChat(message, isUser) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `eval-message ${isUser ? 'user' : 'ai'}`;
    
    if (!isUser) {
        let formatted = message.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
        formatted = formatted.replace(/\n/g, '<br>');
        msgDiv.innerHTML = formatted;
    } else {
        msgDiv.innerText = message;
    }
    
    evalUI.chatBox.appendChild(msgDiv);
    evalUI.chatBox.scrollTop = evalUI.chatBox.scrollHeight;
}

/**
 * Processes a single log entry and renders it to the chat box.
 * @param {object} log - The log entry object from the server.
 */
function processLog(log) {
    if (log.type === 'PLAYER_THINKING') {
        const card = Array.from(document.querySelectorAll('.player-card')).find(c => c.dataset.name === log.source);
        if (card) {
            card.classList.add('thinking');
        }
        return; // Don't display a message for this log type
    }

    if (log.type === 'PLAYER_DONE_THINKING') {
        const card = Array.from(document.querySelectorAll('.player-card')).find(c => c.dataset.name === log.source);
        if (card) {
            card.classList.remove('thinking');
        }
        return; // Don't display a message for this log type
    }
    if (log.type === 'NIGHT_FALLS') {
        setPhase('Night');
    } else if (log.type === 'DAY_BREAKS') {
        setPhase('Day');
    }

    const msgContainer = document.createElement('div');
    msgContainer.className = `message-container ${getLogClass(log)}`;
    
    let text = log.message;
    if (typeof text === 'object') {
        text = text[gameState.lang] || text['zh'] || text['en'] || JSON.stringify(text);
    }

    if (log.source && log.source.startsWith('Player')) {
        const avatar = getAvatar(log.source);
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'chat-avatar';
        avatarDiv.innerText = avatar;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'chat-content';

        const senderDiv = document.createElement('div');
        senderDiv.className = 'chat-sender';
        
        const playerNum = log.source.replace('Player ', '');
        const isMe = log.source === 'Player 1';
        if (gameState.lang === 'zh') {
            senderDiv.innerText = isMe ? `${playerNum}号玩家 (我)` : `${playerNum}号玩家`;
        } else {
            senderDiv.innerText = isMe ? `Player ${playerNum} (Me)` : `Player ${playerNum}`;
        }

        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'chat-bubble';
        bubbleDiv.innerText = text;
        
        contentDiv.appendChild(senderDiv);
        contentDiv.appendChild(bubbleDiv);

        msgContainer.appendChild(avatarDiv);
        msgContainer.appendChild(contentDiv);
    } else {
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'chat-bubble system';
        bubbleDiv.innerText = text;
        msgContainer.appendChild(bubbleDiv);
    }
    
    gameUI.chatBox.appendChild(msgContainer);

    if (log.source && log.type !== 'SYSTEM') {
        showSpeechBubble(log.source, text);
    }

    if (typeof text === 'string' && (text.startsWith("You are a") || text.startsWith("你的身份是"))) {
        let role = "";
        if (text.startsWith("You are a ")) {
             role = text.split("You are a ")[1].replace('.', '');
        } else if (text.startsWith("你的身份是 ")) {
             role = text.split("你的身份是 ")[1].replace('。', '');
        }
        if (role) gameUI.myRole.innerText = role;
    }
}

/**
 * Determines the CSS class for a log message based on its type and source.
 * @param {object} log - The log entry object.
 * @returns {string} The CSS class name.
 */
function getLogClass(log) {
    if (['SYSTEM', 'GAME_START', 'NIGHT_FALLS', 'DAY_BREAKS'].includes(log.type)) return 'system';
    if (log.message && typeof log.message === 'string' && (log.message.includes('---') || log.message.includes('State'))) return 'debug';
    if (log.source === 'Player 1') return 'user';
    return 'ai';
}

/**
 * Updates the player display based on the latest data from the server.
 * @param {Array<object>} playersData - A list of player objects.
 * @param {Set<string>} justDied - A set of player names who were eliminated in the last update.
 */
function updatePlayers(playersData, justDied = new Set()) {
    playersData.sort((a, b) => {
        const numA = parseInt(a.name.replace('Player ', ''));
        const numB = parseInt(b.name.replace('Player ', ''));
        return numA - numB;
    });

    if (gameUI.playersLeft) gameUI.playersLeft.innerHTML = '';
    if (gameUI.playersRight) gameUI.playersRight.innerHTML = '';
    
    const totalPlayers = playersData.length;
    const midPoint = Math.ceil(totalPlayers / 2);

    playersData.forEach((p, index) => {
        const template = document.getElementById('player-card-template');
        const clone = template.content.cloneNode(true);
        const card = clone.querySelector('.player-card');
        
        card.dataset.name = p.name;
        
        if (p.name === 'Player 1') {
            card.querySelector('.player-avatar').innerText = gameState.myAvatar;
        } else {
            card.querySelector('.player-avatar').innerText = getAvatar(p.name);
        }
        
        if (!p.is_alive) {
            if (!justDied.has(p.name)) {
                card.classList.add('dead');
            }
        } else {
            card.classList.remove('dead');
        }

        if (p.is_tie) {
            card.classList.add('tie');
            card.querySelector('.player-tie-label').style.display = 'block';
        } else if (p.is_sheriff) {
            card.classList.add('sheriff');
            card.querySelector('.player-sheriff-label').style.display = 'block';
        } else if (p.is_sheriff_candidate) {
            card.classList.add('sheriff-candidate');
            card.querySelector('.player-candidate-label').style.display = 'block';
        }

        if (p.name === 'Player 1') {
            card.classList.add('me');
            card.querySelector('.player-name').innerText = "1";
            if (!p.is_tie && !p.is_sheriff && !p.is_sheriff_candidate) {
                card.querySelector('.player-me-label').style.display = 'block';
            }
        } else {
            const num = p.name.replace('Player ', '');
            card.querySelector('.player-name').innerText = num;
        }

        card.onclick = () => handlePlayerClick(p.name);

        if (gameUI.playersLeft && gameUI.playersRight) {
            if (index < midPoint) {
                gameUI.playersLeft.appendChild(card);
            } else {
                gameUI.playersRight.appendChild(card);
            }
        }
    });
}

/**
 * Handles a request for player input from the server.
 * @param {object|null} req - The input request object, or null to clear the prompt.
 */
function handleInputRequest(req) {
    gameState.pendingAction = req;

    if (!req) {
        gameUI.input.disabled = true;
        gameUI.sendBtn.disabled = true;
        gameUI.choiceButtons.innerHTML = '';
        gameUI.actionPrompt.innerText = I18N[gameState.lang].waiting;
        return;
    }

    let promptText = req.prompt;
    if (typeof promptText === 'object') {
        promptText = promptText[gameState.lang] || promptText['zh'] || promptText['en'] || JSON.stringify(promptText);
    }
    gameUI.actionPrompt.innerText = promptText;

    if (req.type === 'speech') {
        gameUI.input.disabled = false;
        gameUI.sendBtn.disabled = false;
        gameUI.input.focus();
        gameUI.choiceButtons.innerHTML = '';
    } else if (req.type === 'vote' || req.type === 'choice') {
        gameUI.input.disabled = true;
        gameUI.sendBtn.disabled = true;
        
        const options = [...req.options];
        
        const noActionText = gameState.lang === 'zh' ? "不行动 / 弃票" : "No Action / Abstain";
        
        if (!options.includes(noActionText) && !options.includes("Abstain") && !options.includes("弃票")) {
             renderChoiceButtons(options, true);
        } else {
             renderChoiceButtons(options, false);
        }
    }
}

/**
 * Renders the choice buttons for a vote or selection action.
 * @param {Array<string>} options - The list of choices.
 * @param {boolean} addNoAction - Whether to add a "No Action" button.
 */
function renderChoiceButtons(options, addNoAction) {
    gameUI.choiceButtons.innerHTML = '';
    if (!options) return;

    options.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'choice-btn';
        
        if (opt.startsWith('Player ')) {
            const avatar = getAvatar(opt);
            const playerNum = opt.replace('Player ', '');
            btn.innerHTML = `<span class="btn-avatar">${avatar}</span> ${playerNum}`;
        } else {
            btn.innerText = opt;
        }
        
        btn.onclick = () => sendAction(opt);
        gameUI.choiceButtons.appendChild(btn);
    });
    
    if (addNoAction) {
        const btn = document.createElement('button');
        btn.className = 'choice-btn no-action';
        btn.innerText = gameState.lang === 'zh' ? "不行动 / 弃票" : "No Action / Abstain";
        btn.onclick = () => sendAction("Abstain");
        gameUI.choiceButtons.appendChild(btn);
    }
}

/**
 * Handles clicks on player cards, submitting them as actions if a choice is pending.
 * @param {string} playerName - The name of the clicked player.
 */
function handlePlayerClick(playerName) {
    if (gameState.pendingAction && (gameState.pendingAction.type === 'vote' || gameState.pendingAction.type === 'choice')) {
        sendAction(playerName);
    }
}

/**
 * Sends the content of the text input as a speech action.
 */
async function sendTextAction() {
    const text = gameUI.input.value.trim();
    if (text) {
        await sendAction(text);
        gameUI.input.value = '';
    }
}

/**
 * Sends the player's action to the server.
 * @param {*} value - The action value to send.
 */
async function sendAction(value) {
    if (!gameState.gameId || gameState.isSending) return;

    gameState.isSending = true;
    gameUI.sendBtn.disabled = true;
    gameUI.input.disabled = true;
    
    document.querySelectorAll('.choice-btn').forEach(btn => btn.disabled = true);

    try {
        await fetch('/api/game/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_id: gameState.gameId,
                action: value
            })
        });
        
        handleInputRequest(null);
    } catch (error) {
        console.error('Error sending action:', error);
        gameUI.sendBtn.disabled = false;
        gameUI.input.disabled = false;
        document.querySelectorAll('.choice-btn').forEach(btn => btn.disabled = false);
    } finally {
        gameState.isSending = false;
    }
}

// --- UI HELPER FUNCTIONS ---

/**
 * Traps focus within a given element.
 * @param {HTMLElement} element - The element to trap focus within.
 */
function trapFocus(element) {
    const focusableEls = element.querySelectorAll('a[href]:not([disabled]), button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])');
    const firstFocusableEl = focusableEls[0];
    const lastFocusableEl = focusableEls[focusableEls.length - 1];
    const KEYCODE_TAB = 9;

    element.addEventListener('keydown', function(e) {
        const isTabPressed = (e.key === 'Tab' || e.keyCode === KEYCODE_TAB);

        if (!isTabPressed) {
            return;
        }

        if (e.shiftKey) /* shift + tab */ {
            if (document.activeElement === firstFocusableEl) {
                lastFocusableEl.focus();
                e.preventDefault();
            }
        } else /* tab */ {
            if (document.activeElement === lastFocusableEl) {
                firstFocusableEl.focus();
                e.preventDefault();
            }
        }
    });
}

/**
 * Adds a system message to the chat box.
 * @param {string} text - The message to display.
 */
function addSystemMessage(text) {
    const msgContainer = document.createElement('div');
    msgContainer.className = 'message-container system';
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'chat-bubble system';
    bubbleDiv.innerText = text;
    
    msgContainer.appendChild(bubbleDiv);
    gameUI.chatBox.appendChild(msgContainer);
    scrollToBottom();
}

/**
 * Checks if the user has scrolled near the bottom of the chat box.
 * @returns {boolean} True if the user is near the bottom.
 */
function isUserNearBottom() {
    const threshold = 100;
    return (gameUI.chatBox.scrollHeight - gameUI.chatBox.scrollTop - gameUI.chatBox.clientHeight) <= threshold;
}

/**
 * Scrolls the chat box to the bottom, or shows a "new messages" indicator.
 * @param {boolean} force - If true, forces scrolling regardless of user position.
 */
function scrollToBottom(force = false) {
    if (force || isUserNearBottom()) {
        gameUI.chatBox.scrollTop = gameUI.chatBox.scrollHeight;
        hideNewMessagesIndicator();
    } else {
        showNewMessagesIndicator();
    }
}

/**
 * Hides the "new messages" indicator if the user scrolls to the bottom.
 */
function checkScrollPosition() {
    if (isUserNearBottom()) {
        hideNewMessagesIndicator();
    }
}

/**
 * Shows the "new messages" indicator.
 */
function showNewMessagesIndicator() {
    if (gameUI.newMessagesIndicator) {
        gameUI.newMessagesIndicator.classList.remove('hidden');
    }
}

/**
 * Hides the "new messages" indicator.
 */
function hideNewMessagesIndicator() {
    if (gameUI.newMessagesIndicator) {
        gameUI.newMessagesIndicator.classList.add('hidden');
    }
}

/**
 * Sets the game phase indicator and updates the UI theme (day/night).
 * @param {string} phase - The name of the phase (e.g., 'Day', 'Night').
 */
function setPhase(phase) {
    gameUI.phaseIndicator.innerText = phase;
    
    if (phase.toLowerCase().includes('night')) {
        document.body.classList.add('night-mode');
    } else {
        document.body.classList.remove('night-mode');
    }
}

/**
 * Gets a deterministic avatar for a player based on their name.
 * @param {string} name - The player's name.
 * @returns {string} An emoji avatar.
 */
function getAvatar(name) {
    if (name === 'Player 1') {
        return gameState.myAvatar;
    }
    const hash = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return AVATARS[hash % AVATARS.length];
}

/**
 * Displays a temporary speech bubble above a player's card.
 * @param {string} playerName - The name of the speaking player.
 * @param {string} text - The speech content.
 */
function showSpeechBubble(playerName, text) {
    const card = Array.from(document.querySelectorAll('.player-card')).find(c => c.dataset.name === playerName);
    if (card) {
        const bubble = card.querySelector('.player-speech-bubble');
        bubble.innerText = text.length > 20 ? text.substring(0, 17) + '...' : text;
        bubble.classList.add('visible');
        card.classList.add('speaking');
        
        setTimeout(() => {
            bubble.classList.remove('visible');
            card.classList.remove('speaking');
        }, 4000);
    }
}

async function showOperationsHistory() {
    const modal = document.getElementById('op-history-modal');
    const content = document.getElementById('op-history-content');
    const title = document.getElementById('op-history-title');

    const t = I18N[gameState.lang].opHistory;
    title.innerText = t.title;

    try {
        const response = await fetch(`/api/game/${gameState.gameId}/player/Player 1/operations`);
        const data = await response.json();

        if (response.ok) {
            content.innerHTML = renderOperationsHistory(data, t);
        } else {
            content.innerText = data.detail || 'Error fetching history.';
        }
    } catch (error) {
        console.error('Error fetching operations history:', error);
        content.innerText = 'Network error.';
    }

    modal.classList.add('active');
    modal.querySelector('.close-modal').onclick = () => modal.classList.remove('active');
}

function renderOperationsHistory(data, t) {
    if (Object.keys(data).length === 0) {
        return `<p>${t.noData}</p>`;
    }

    let html = `<div class="op-history-role"><strong>${t.role}:</strong> ${I18N[gameState.lang].roles[data.role] || data.role}</div>`;

    if (data.teammates) {
        html += `<p><strong>${t.teammates}:</strong> ${data.teammates.join(', ') || 'None'}</p>`;
    }
    if (data.king) {
        html += `<p><strong>${t.king}:</strong> ${data.king}</p>`;
    }
    if (data.saved) {
        html += `<p><strong>${t.saved}:</strong> ${data.saved.join(', ') || 'None'}</p>`;
    }
    if (data.poisoned) {
        html += `<p><strong>${t.poisoned}:</strong> ${data.poisoned.join(', ') || 'None'}</p>`;
    }
    if (data.checked) {
        html += `<h3>${t.checked}</h3>`;
        html += '<ul>';
        data.checked.forEach(item => {
            html += `<li>${item.player} (${t.camp}: ${item.camp})</li>`;
        });
        html += '</ul>';
    }
    if (data.protected) {
        html += `<p><strong>${t.protected}:</strong> ${data.protected.join(', ') || 'None'}</p>`;
    }
    if (data.shot) {
        html += `<p><strong>${t.shot}:</strong> ${data.shot.join(', ') || 'None'}</p>`;
    }

    return html;
}

// Start
init();
