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
        statusLabels: {
            me: "我",
            sheriff: "警长",
            candidate: "竞选",
            tie: "平票PK",
            dead: "出局"
        },
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
        statusLabels: {
            me: "ME",
            sheriff: "SHERIFF",
            candidate: "CANDIDATE",
            tie: "TIE PK",
            dead: "DEAD"
        },
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
    voiceInputBtn: document.getElementById('voice-input-btn'),
    turnTimer: document.getElementById('turn-timer')
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
    sendBtn: document.getElementById('send-eval-btn'),
    newGameBtn: document.getElementById('new-game-btn')
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
        if (!isRecording && (!gameState.pendingAction || gameState.pendingAction.type !== 'speech')) {
            return;
        }

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
        const isSpeechAction = gameState.pendingAction && gameState.pendingAction.type === 'speech';
        gameUI.input.disabled = !isSpeechAction;
        gameUI.input.placeholder = originalPlaceholder;
        if (isSpeechAction) {
            gameUI.input.focus();
        }
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

    const tabEvalBtn = document.getElementById('tab-eval-btn');
    const tabHistoryBtn = document.getElementById('tab-history-btn');
    const evalTabView = document.getElementById('eval-tab-view');
    const historyTabView = document.getElementById('history-tab-view');

    if (tabEvalBtn && tabHistoryBtn) {
        tabEvalBtn.onclick = () => {
            tabEvalBtn.classList.add('active');
            tabHistoryBtn.classList.remove('active');
            if (evalTabView) evalTabView.style.display = 'block';
            if (historyTabView) historyTabView.style.display = 'none';
        };

        tabHistoryBtn.onclick = () => {
            tabHistoryBtn.classList.add('active');
            tabEvalBtn.classList.remove('active');
            if (historyTabView) historyTabView.style.display = 'block';
            if (evalTabView) evalTabView.style.display = 'none';
            loadOperationsHistory();
        };
    }

    evalUI.modeBtns = document.querySelectorAll('.eval-mode-btn');
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

    if (gameUI.phaseIndicator && gameState.phase) {
        const nightMatch = gameState.phase.match(/(?:Night|夜)\s*(\d+)|(\d+)\s*夜/i);
        const dayMatch = gameState.phase.match(/(?:Day|天)\s*(\d+)|(\d+)\s*天/i);
        if (nightMatch) {
            const num = nightMatch[1] || nightMatch[2];
            gameUI.phaseIndicator.innerText = t.night.replace('{n}', num);
        } else if (dayMatch) {
            const num = dayMatch[1] || dayMatch[2];
            gameUI.phaseIndicator.innerText = t.day.replace('{n}', num);
        }
    }
    
    if (gameState.myRole) {
        if (t.roles[gameState.myRole]) {
            gameUI.myRole.innerText = t.roles[gameState.myRole];
        } else {
            gameUI.myRole.innerText = gameState.myRole;
        }
    }

    if (gameState.pendingAction && gameUI.actionPrompt) {
        let promptText = gameState.pendingAction.prompt;
        if (typeof promptText === 'object') {
            promptText = promptText[gameState.lang] || promptText['zh'] || promptText['en'] || JSON.stringify(promptText);
        }
        gameUI.actionPrompt.innerText = promptText;
    }

    // Evaluation & Game Over Modal
    if (evalUI.modal) {
        const t_eval = I18N[gameState.lang].eval;
        const tabEvalBtn = document.getElementById('tab-eval-btn');
        const tabHistoryBtn = document.getElementById('tab-history-btn');
        if (tabEvalBtn) tabEvalBtn.innerText = `🤖 ${t_eval.title}`;
        if (tabHistoryBtn) tabHistoryBtn.innerText = `📜 ${I18N[gameState.lang].operationsHistory}`;

        const evalIntro = document.getElementById('eval-intro');
        if (evalIntro) evalIntro.innerText = t_eval.intro;

        const modeBtns = document.querySelectorAll('.eval-mode-btn');
        const modeKeys = ['mild', 'neutral', 'mean'];
        modeBtns.forEach((btn, idx) => {
            const key = btn.dataset.mode || modeKeys[idx];
            const titleEl = btn.querySelector('.mode-title');
            if (titleEl && t_eval.modes[key]) {
                titleEl.innerText = t_eval.modes[key].replace(/^[^\s]+\s*/, '');
            }
        });

        const warningText = document.querySelector('.warning-text');
        if (warningText) warningText.innerText = t_eval.apiKeyWarning;
        if (evalUI.startBtn.disabled) {
             evalUI.startBtn.innerText = t_eval.evaluating;
        } else {
             evalUI.startBtn.innerText = t_eval.startBtn;
        }
        evalUI.input.placeholder = t_eval.inputPlaceholder;
        evalUI.sendBtn.innerText = t_eval.send;
        if (evalUI.newGameBtn) evalUI.newGameBtn.innerText = gameState.lang === 'zh' ? '再来一局' : 'New Game';
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
            stopTurnTimer();
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
    const tabEvalBtn = document.getElementById('tab-eval-btn');
    const tabHistoryBtn = document.getElementById('tab-history-btn');
    const evalTabView = document.getElementById('eval-tab-view');
    const historyTabView = document.getElementById('history-tab-view');

    if (tabEvalBtn) tabEvalBtn.classList.add('active');
    if (tabHistoryBtn) tabHistoryBtn.classList.remove('active');
    if (evalTabView) evalTabView.style.display = 'block';
    if (historyTabView) historyTabView.style.display = 'none';

    evalUI.modal.classList.add('active');
    trapFocus(evalUI.modal);
    const firstModeBtn = evalUI.modal.querySelector('.eval-mode-btn');
    if (firstModeBtn) firstModeBtn.focus();
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
        setPhase('Night', log.message);
    } else if (log.type === 'DAY_BREAKS') {
        setPhase('Day', log.message);
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

        const statusTexts = I18N[gameState.lang]?.statusLabels || {
            me: "ME",
            sheriff: "SHERIFF",
            candidate: "CANDIDATE",
            tie: "TIE PK",
            dead: "DEAD"
        };

        if (p.name === 'Player 1') {
            card.classList.add('me');
            card.querySelector('.player-name').innerText = "1";
            const meLabel = card.querySelector('.player-me-label');
            if (meLabel) {
                meLabel.style.display = 'block';
                if (p.is_sheriff) {
                    meLabel.innerText = `${statusTexts.me} · 👮`;
                } else if (p.is_sheriff_candidate) {
                    meLabel.innerText = `${statusTexts.me} · 🎙️`;
                } else if (p.is_tie) {
                    meLabel.innerText = `${statusTexts.me} · ⚔️`;
                } else {
                    meLabel.innerText = `⭐ ${statusTexts.me}`;
                }
            }

            if (p.is_sheriff) card.classList.add('sheriff');
            if (p.is_sheriff_candidate) card.classList.add('sheriff-candidate');
            if (p.is_tie) card.classList.add('tie');
        } else {
            const num = p.name.replace('Player ', '');
            card.querySelector('.player-name').innerText = num;

            if (p.is_tie) {
                card.classList.add('tie');
                const tieLabel = card.querySelector('.player-tie-label');
                if (tieLabel) {
                    tieLabel.innerText = `⚔️ ${statusTexts.tie}`;
                    tieLabel.style.display = 'block';
                }
            } else if (p.is_sheriff) {
                card.classList.add('sheriff');
                const sheriffLabel = card.querySelector('.player-sheriff-label');
                if (sheriffLabel) {
                    sheriffLabel.innerText = `👮 ${statusTexts.sheriff}`;
                    sheriffLabel.style.display = 'block';
                }
            } else if (p.is_sheriff_candidate) {
                card.classList.add('sheriff-candidate');
                const candidateLabel = card.querySelector('.player-candidate-label');
                if (candidateLabel) {
                    candidateLabel.innerText = `🎙️ ${statusTexts.candidate}`;
                    candidateLabel.style.display = 'block';
                }
            }
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

    if (gameState.pendingAction && (gameState.pendingAction.type === 'vote' || gameState.pendingAction.type === 'choice')) {
        const validTargets = (gameState.pendingAction.options || []).filter(opt => typeof opt === 'string' && opt.startsWith('Player '));
        updatePlayerSelectableState(validTargets);
    }
}

/**
 * Updates player card visuals to indicate which players can be targeted.
 * @param {Array<string>} targetPlayerNames - Array of selectable player names e.g. ['Player 2', 'Player 3']
 */
function updatePlayerSelectableState(targetPlayerNames = []) {
    const cards = document.querySelectorAll('.player-card');
    cards.forEach(card => {
        const name = card.dataset.name;
        if (targetPlayerNames.length === 0) {
            card.classList.remove('selectable-target', 'non-target');
        } else if (targetPlayerNames.includes(name)) {
            card.classList.add('selectable-target');
            card.classList.remove('non-target');
        } else {
            card.classList.remove('selectable-target');
            card.classList.add('non-target');
        }
    });
}

/** @type {number|null} - The timer ID for the turn countdown. */
let turnTimerInterval = null;
const TURN_TIMEOUT_SECONDS = 120; // 2 minutes default
let turnSecondsRemaining = TURN_TIMEOUT_SECONDS;
let currentTurnRequestId = null;

/**
 * Starts a countdown timer for the player's pending turn.
 * @param {Function} onTimeout - Callback invoked when the countdown expires.
 * @param {number} totalSeconds - Total seconds for the countdown.
 */
function startTurnTimer(onTimeout, totalSeconds = TURN_TIMEOUT_SECONDS) {
    stopTurnTimer();
    const timerEl = gameUI.turnTimer || document.getElementById('turn-timer');
    if (!timerEl) return;

    turnSecondsRemaining = totalSeconds;
    timerEl.classList.remove('hidden', 'warning', 'urgent');
    updateTimerDisplay(timerEl, turnSecondsRemaining);

    turnTimerInterval = setInterval(() => {
        turnSecondsRemaining--;
        updateTimerDisplay(timerEl, turnSecondsRemaining);

        if (turnSecondsRemaining <= 10) {
            timerEl.classList.add('urgent');
            timerEl.classList.remove('warning');
        } else if (turnSecondsRemaining <= 30) {
            timerEl.classList.add('warning');
            timerEl.classList.remove('urgent');
        }

        if (turnSecondsRemaining <= 0) {
            stopTurnTimer();
            if (typeof onTimeout === 'function') {
                onTimeout();
            }
        }
    }, 1000);
}

/**
 * Stops and hides the active turn countdown timer.
 */
function stopTurnTimer() {
    if (turnTimerInterval) {
        clearInterval(turnTimerInterval);
        turnTimerInterval = null;
    }
    const timerEl = gameUI.turnTimer || document.getElementById('turn-timer');
    if (timerEl) {
        timerEl.classList.add('hidden');
        timerEl.classList.remove('warning', 'urgent');
    }
}

/**
 * Formats seconds as MM:SS and updates the timer element text.
 * @param {HTMLElement} el - The timer DOM element.
 * @param {number} seconds - Number of seconds remaining.
 */
function updateTimerDisplay(el, seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    const formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    el.innerText = `⏳ ${formatted}`;
}

/**
 * Handles a request for player input from the server.
 * @param {object|null} req - The input request object, or null to clear the prompt.
 */
function handleInputRequest(req) {
    if (!req) {
        currentTurnRequestId = null;
        gameState.pendingAction = null;
        stopTurnTimer();
        gameUI.input.disabled = true;
        gameUI.sendBtn.disabled = true;
        if (gameUI.voiceInputBtn) gameUI.voiceInputBtn.disabled = true;
        gameUI.choiceButtons.innerHTML = '';
        gameUI.actionPrompt.innerText = I18N[gameState.lang].waiting;
        updatePlayerSelectableState([]);
        return;
    }

    // Generate stable request ID to avoid resetting countdown on every polling tick
    const reqId = req.id || `${req.type}_${typeof req.prompt === 'object' ? JSON.stringify(req.prompt) : req.prompt}_${JSON.stringify(req.options)}`;
    
    // Keep pendingAction updated
    gameState.pendingAction = req;

    let promptText = req.prompt;
    if (typeof promptText === 'object') {
        promptText = promptText[gameState.lang] || promptText['zh'] || promptText['en'] || JSON.stringify(promptText);
    }
    gameUI.actionPrompt.innerText = promptText;

    // If this exact request is already active, don't restart the countdown
    if (reqId === currentTurnRequestId) {
        return;
    }
    currentTurnRequestId = reqId;

    const timeoutSeconds = (req.timeout && Number.isFinite(req.timeout)) ? Math.round(req.timeout) : TURN_TIMEOUT_SECONDS;

    if (req.type === 'speech') {
        gameUI.input.disabled = false;
        gameUI.sendBtn.disabled = false;
        if (gameUI.voiceInputBtn) gameUI.voiceInputBtn.disabled = false;
        gameUI.input.focus();
        gameUI.choiceButtons.innerHTML = '';
        updatePlayerSelectableState([]);
        startTurnTimer(() => {
            const text = gameUI.input.value.trim();
            const fallback = gameState.lang === 'zh' ? "过" : "Pass";
            sendAction(text || fallback);
            gameUI.input.value = '';
        }, timeoutSeconds);
    } else if (req.type === 'vote' || req.type === 'choice') {
        gameUI.input.disabled = true;
        gameUI.sendBtn.disabled = true;
        if (gameUI.voiceInputBtn) gameUI.voiceInputBtn.disabled = true;
        
        const options = [...req.options];
        const validTargets = options.filter(opt => typeof opt === 'string' && opt.startsWith('Player '));
        updatePlayerSelectableState(validTargets);
        
        const noActionText = gameState.lang === 'zh' ? "不行动 / 弃票" : "No Action / Abstain";
        
        if (!options.includes(noActionText) && !options.includes("Abstain") && !options.includes("弃票")) {
             renderChoiceButtons(options, true);
        } else {
             renderChoiceButtons(options, false);
        }

        startTurnTimer(() => {
            sendAction("Abstain");
        }, timeoutSeconds);
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
        const options = gameState.pendingAction.options || [];
        if (options.includes(playerName)) {
            sendAction(playerName);
        }
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

    stopTurnTimer();
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
 * @param {object|string|null} rawMessage - Optional localized message from server log.
 */
function setPhase(phase, rawMessage = null) {
    if (rawMessage) {
        let text = typeof rawMessage === 'object' ? (rawMessage[gameState.lang] || rawMessage['zh'] || rawMessage['en'] || '') : rawMessage;
        const clean = text.replace(/[-—]/g, '').trim();
        if (clean) {
            gameState.phase = clean;
        }
    } else if (!gameState.phase) {
        gameState.phase = phase;
    }

    gameUI.phaseIndicator.innerText = gameState.phase || phase;
    
    if (phase.toLowerCase().includes('night') || (gameState.phase && (gameState.phase.toLowerCase().includes('night') || gameState.phase.includes('夜')))) {
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
    loadOperationsHistory();
}

async function loadOperationsHistory() {
    const content = document.getElementById('op-history-content');
    if (!content) return;

    const t = I18N[gameState.lang].opHistory;
    content.innerHTML = `<p class="op-history-loading">${gameState.lang === 'zh' ? '正在加载操作记录...' : 'Loading operations history...'}</p>`;

    try {
        const response = await fetch(`/api/game/${gameState.gameId}/player/Player 1/operations`);
        const data = await response.json();

        if (response.ok) {
            content.innerHTML = renderOperationsHistory(data, t);
        } else {
            content.innerHTML = `<div class="op-empty-card"><p>${data.detail || (gameState.lang === 'zh' ? '获取历史记录失败' : 'Failed to load history.')}</p></div>`;
        }
    } catch (error) {
        console.error('Error fetching operations history:', error);
        content.innerHTML = `<div class="op-empty-card"><p>${gameState.lang === 'zh' ? '网络错误，请稍后重试' : 'Network error. Please try again.'}</p></div>`;
    }
}

function renderOperationsHistory(data, t) {
    if (!data || Object.keys(data).length === 0) {
        return `<div class="op-empty-card"><p>${t.noData}</p></div>`;
    }

    const roleName = data.role || 'Villager';
    const roleConfig = ROLES.find(r => r.id === roleName) || { icon: '👱‍♀️' };
    const localizedRole = I18N[gameState.lang].roles[roleName] || roleName;

    let html = `
        <div class="op-history-role">
            <span><strong>${t.role}:</strong></span>
            <span class="op-role-pill">${roleConfig.icon} ${localizedRole}</span>
        </div>
    `;

    let hasOperations = false;

    if (data.teammates && (data.teammates.length > 0 || data.king)) {
        hasOperations = true;
        html += `<div class="op-card">
            <div class="op-card-title">🐺 ${t.teammates}</div>
            <div class="op-badges-list">`;
        if (data.teammates.length > 0) {
            data.teammates.forEach(tm => {
                html += `<span class="op-badge teammate">${getAvatar(tm)} ${tm}</span>`;
            });
        }
        if (data.king) {
            html += `<span class="op-badge teammate" style="background:#ffd200;">👑 ${t.king}: ${data.king}</span>`;
        }
        html += `</div></div>`;
    }

    if (data.saved !== undefined || data.poisoned !== undefined) {
        hasOperations = true;
        html += `<div class="op-card">
            <div class="op-card-title">🧙‍♀️ ${gameState.lang === 'zh' ? '女巫用药' : 'Witch Potions'}</div>
            <div style="display:flex; flex-direction:column; gap:8px;">
                <div class="op-badges-list" style="align-items:center;">
                    <span style="font-size:0.9rem; font-weight:700;">💚 ${t.saved}:</span>
                    ${(data.saved && data.saved.length > 0) 
                        ? data.saved.map(p => `<span class="op-badge saved">${p}</span>`).join('') 
                        : `<span style="color:var(--text-muted); font-size:0.85rem;">${gameState.lang === 'zh' ? '未使用' : 'None'}</span>`}
                </div>
                <div class="op-badges-list" style="align-items:center;">
                    <span style="font-size:0.9rem; font-weight:700;">💜 ${t.poisoned}:</span>
                    ${(data.poisoned && data.poisoned.length > 0) 
                        ? data.poisoned.map(p => `<span class="op-badge poisoned">${p}</span>`).join('') 
                        : `<span style="color:var(--text-muted); font-size:0.85rem;">${gameState.lang === 'zh' ? '未使用' : 'None'}</span>`}
                </div>
            </div>
        </div>`;
    }

    if (data.checked && data.checked.length > 0) {
        hasOperations = true;
        html += `<div class="op-card">
            <div class="op-card-title">🔮 ${t.checked}</div>
            <div style="display:flex; flex-direction:column; gap:6px;">`;
        data.checked.forEach(item => {
            const isWerewolf = item.camp === 'Werewolves';
            const campLabel = isWerewolf ? (gameState.lang === 'zh' ? '狼人阵营 🐺' : 'Werewolf 🐺') : (gameState.lang === 'zh' ? '好人阵营 👱' : 'Good 👱');
            html += `
                <div class="op-check-item">
                    <span style="font-weight:700;">${getAvatar(item.player)} ${item.player}</span>
                    <span class="op-camp-tag ${isWerewolf ? 'werewolf' : 'good'}">${campLabel}</span>
                </div>
            `;
        });
        html += `</div></div>`;
    }

    if (data.protected && data.protected.length > 0) {
        hasOperations = true;
        html += `<div class="op-card">
            <div class="op-card-title">🛡️ ${t.protected}</div>
            <div class="op-badges-list">
                ${data.protected.map(p => `<span class="op-badge protected">${getAvatar(p)} ${p}</span>`).join('')}
            </div>
        </div>`;
    }

    if (data.shot && data.shot.length > 0) {
        hasOperations = true;
        html += `<div class="op-card">
            <div class="op-card-title">🏹 ${t.shot}</div>
            <div class="op-badges-list">
                ${data.shot.map(p => `<span class="op-badge shot">${getAvatar(p)} ${p}</span>`).join('')}
            </div>
        </div>`;
    }

    if (!hasOperations) {
        const villagerDesc = gameState.lang === 'zh'
            ? '作为普通村民，夜间无需操作。请在白天的发言和投票中发挥你的智慧！'
            : 'As a Villager, you had no special night actions. Your strength lies in daytime discussion and voting!';
        html += `<div class="op-empty-card"><p>${villagerDesc}</p></div>`;
    }

    return html;
}

// Start
init();
