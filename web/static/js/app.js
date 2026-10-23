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
    renderedLogs: [],
    logQueue: [],
    isProcessingQueue: false,
    queueTimer: null,
    focusedSpeaker: null,
    currentPhaseBodyEl: null,
    currentPhaseId: null,
    collapsedPhases: new Set(),
    toastTimer: null,
    pacingMultiplier: 1.0,
    latestServerInputRequired: null,
    latestServerGameActive: true,
    seerChecks: {},
    unreadCount: 0,
    lastLogIndex: 0,
    myRole: 'Random',
    myAvatar: '👤',
    phase: 'Day 1',
    pendingAction: null,
    lang: 'zh',
    gameId: null,
    isSending: false,
    isPolling: false,
    pendingVoteLogs: []
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
        turnTimer: "回合倒计时",
        timerOptions: {
            min1: "1 分钟 (60秒)",
            min2: "2 分钟 (120秒)",
            min3: "3 分钟 (180秒)",
            min5: "5 分钟 (300秒)",
            min10: "10 分钟 (600秒)",
            custom: "自定义..."
        },
        customMinPlaceholder: "分钟数",
        minUnit: "分钟",
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
        bgmOn: "音乐",
        bgmMuted: "静音",
        bgmTitlePlaying: "背景音乐：播放中 (点击静音)",
        bgmTitleMuted: "背景音乐：已静音 (点击开启)",
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
        },
        records: {
            btn: "📖 记录",
            title: "对局全景记录",
            filterAll: "🌟 全部时间线",
            filterActions: "🐺 我的行动",
            filterVotes: "🗳️ 投票明细",
            close: "关闭"
        },
        pacing: {
            speed1x: "1x",
            speed2x: "2x",
            speedMax: "极速",
            title1x: "消息速度：正常 (点击切换 2x)",
            title2x: "消息速度：快速 2x (点击切换极速)",
            titleMax: "消息速度：极速无延迟 (点击切换 1x)",
            skip: "快进",
            skipTitle: "立即显示所有排队中的消息"
        }
    },
    en: {
        title: "Werewolf",
        selectAvatar: "Select Avatar",
        selectRole: "Select Role",
        playerCount: "Number of Players",
        advancedSettings: "Advanced Settings",
        turnTimer: "Turn Timer",
        timerOptions: {
            min1: "1 Minute (60s)",
            min2: "2 Minutes (120s)",
            min3: "3 Minutes (180s)",
            min5: "5 Minutes (300s)",
            min10: "10 Minutes (600s)",
            custom: "Custom..."
        },
        customMinPlaceholder: "Minutes",
        minUnit: "min",
        provider: "Provider",
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
        bgmOn: "BGM",
        bgmMuted: "Muted",
        bgmTitlePlaying: "BGM: Playing (Click to mute)",
        bgmTitleMuted: "BGM: Muted (Click to play)",
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
        },
        records: {
            btn: "📖 Records",
            title: "Game Timeline Records",
            filterAll: "🌟 All Events",
            filterActions: "🐺 My Actions",
            filterVotes: "🗳️ Vote Details",
            close: "Close"
        },
        pacing: {
            speed1x: "1x",
            speed2x: "2x",
            speedMax: "MAX",
            title1x: "Message Speed: Normal 1x (Click for 2x)",
            title2x: "Message Speed: Fast 2x (Click for Instant)",
            titleMax: "Message Speed: Instant (Click for 1x)",
            skip: "Skip",
            skipTitle: "Show all queued messages immediately"
        }
    }
};

/** @const {Array<object>} ROLES - Defines the available roles in the game. */
const ROLES = [
    { id: 'Random', icon: '🎲' },
    { id: 'Villager', icon: '👱‍♀️' },
    { id: 'Werewolf', icon: '🐺' },
    { id: 'Witch', icon: '🧙‍♀️' },
    { id: 'Seer', icon: '🔮' },
    { id: 'Guard', icon: '🛡️' },
    { id: 'Hunter', icon: '🔫' },
    { id: 'Black Werewolf King', icon: '👹' }
];

/** @const {Array<string>} AVATARS - A list of available avatars for players. */
const AVATARS = ['🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯', '🦁', '🐮', '🐷', '🐵'];

/** @const {object} ROLE_DISTRIBUTION - Defines the role composition for different player counts. */
const ROLE_DISTRIBUTION = {
    6: {
        "Werewolf": 2,
        "Villager": 2,
        "Seer": 1,
        "Witch": 1
    },
    9: {
        "Black Werewolf King": 1,
        "Werewolf": 2,
        "Villager": 3,
        "Seer": 1,
        "Witch": 1,
        "Hunter": 1
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
    labels: document.querySelectorAll('.setup-container .form-group label'),
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
    recordsBtn: document.getElementById('records-btn'),
    gameSettingsBtn: document.getElementById('game-settings-btn'),
    gameLangBtn: document.getElementById('game-lang-btn'),
    lobbyLangBtn: document.getElementById('lobby-lang-btn'),
    audioToggleBtn: document.getElementById('audio-toggle-btn'),
    lobbyAudioBtn: document.getElementById('lobby-audio-btn'),
    speedToggleBtn: document.getElementById('speed-toggle-btn'),
    skipQueueBtn: document.getElementById('skip-queue-btn'),
    spotlightToastBanner: document.getElementById('spotlight-toast-banner'),
    chatInteractiveBar: document.getElementById('chat-Interactive-bar'),
    chatInteractiveStatus: document.getElementById('chat-interactive-status'),
    chatInteractiveAction: document.getElementById('chat-interactive-action'),
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
    saveBtn: document.getElementById('save-settings-btn'),
    timerSelect: document.getElementById('turn-timer-select'),
    customTimerContainer: document.getElementById('custom-timer-container'),
    customTimerInput: document.getElementById('custom-timer-input'),
    customTimerUnit: document.getElementById('custom-timer-unit'),
    timerLabel: document.getElementById('setting-timer-label'),
    providerLabel: document.getElementById('setting-provider-label'),
    apiKeyLabel: document.getElementById('setting-apikey-label'),
    baseUrlLabel: document.getElementById('setting-baseurl-label'),
    modelNameLabel: document.getElementById('setting-modelname-label'),
    title: document.getElementById('settings-modal-title')
};

// --- BACKGROUND MUSIC (BGM) MANAGER ---

/**
 * Manages looping day and night background music (BGM) with strict mutual exclusivity,
 * browser autoplay unlock, and persistent mute controls.
 */
const BGMManager = {
    tracks: {
        day: new Audio('/static/audio/day.mp3'),
        night: new Audio('/static/audio/night.mp3')
    },
    currentTrackName: null,
    isMuted: false,
    targetVolume: 0.35,
    unlocked: false,
    autoplayBlocked: false,

    init() {
        Object.entries(this.tracks).forEach(([name, audio]) => {
            audio.loop = true;
            audio.preload = 'auto';
            audio.volume = 0;
            audio.addEventListener('error', (e) => {
                console.warn(`[BGM] Failed loading track ${name}:`, e);
            });
            audio.addEventListener('play', () => {
                this.autoplayBlocked = false;
                this.unlocked = true;
                this.updateButtonsUI();
            });
        });

        const storedMute = localStorage.getItem('werewolf_bgm_muted');
        this.isMuted = storedMute === 'true';

        const unlockAudio = (e) => {
            // Do not intercept clicks on the audio toggle button itself — let toggleMute() handle it cleanly
            if (e && e.target && e.target.closest && e.target.closest('#lobby-audio-btn, #audio-toggle-btn')) {
                return;
            }
            this.unlock();
        };

        ['pointerdown', 'keydown', 'touchstart', 'click'].forEach(evt => {
            window.addEventListener(evt, unlockAudio, { passive: true });
        });

        this.updateButtonsUI();

        // Attempt initial playback if permitted by browser
        if (!this.isMuted) {
            const isNight = document.body.classList.contains('night-mode');
            this.playTrack(isNight ? 'night' : 'day');
        }
    },

    unlock() {
        if (this.unlocked && !this.autoplayBlocked) return;
        this.unlocked = true;
        if (!this.isMuted) {
            const isNight = document.body.classList.contains('night-mode');
            this.playTrack(isNight ? 'night' : 'day');
        }
    },

    stopOtherTracks(activeTrackName) {
        Object.entries(this.tracks).forEach(([name, audio]) => {
            if (name !== activeTrackName) {
                audio.pause();
                audio.currentTime = 0;
                audio.volume = 0;
            }
        });
    },

    toggleMute() {
        this.unlocked = true;
        const activeName = this.currentTrackName || (document.body.classList.contains('night-mode') ? 'night' : 'day');
        const activeAudio = this.tracks[activeName];
        const isCurrentlySilent = this.isMuted || this.autoplayBlocked || (activeAudio && activeAudio.paused);

        if (isCurrentlySilent) {
            // Single click turns music ON immediately when it was muted or blocked by browser autoplay
            this.isMuted = false;
            this.autoplayBlocked = false;
            localStorage.setItem('werewolf_bgm_muted', 'false');
            const isNight = document.body.classList.contains('night-mode');
            this.playTrack(isNight ? 'night' : 'day');
        } else {
            // Music was genuinely audible -> mute it
            this.isMuted = true;
            this.autoplayBlocked = false;
            localStorage.setItem('werewolf_bgm_muted', 'true');
            this.stopAll();
        }
        this.updateButtonsUI();
    },

    playTrack(trackName) {
        if (this.isMuted) {
            this.currentTrackName = trackName;
            this.stopAll();
            return;
        }

        // Strictly enforce mutual exclusivity: stop all other tracks immediately
        this.stopOtherTracks(trackName);

        const targetAudio = this.tracks[trackName];
        if (!targetAudio) return;

        this.currentTrackName = trackName;
        targetAudio.volume = this.targetVolume;

        if (targetAudio.paused) {
            const playPromise = targetAudio.play();
            if (playPromise !== undefined) {
                playPromise.then(() => {
                    this.autoplayBlocked = false;
                    this.unlocked = true;
                    this.updateButtonsUI();
                }).catch(() => {
                    // Autoplay prevented pending user interaction; reflect silent state on button
                    this.autoplayBlocked = true;
                    this.updateButtonsUI();
                });
            }
        }
    },

    setTrack(trackName) {
        if (this.isMuted) {
            this.currentTrackName = trackName;
            return;
        }
        this.playTrack(trackName);
    },

    stopAll() {
        Object.values(this.tracks).forEach(audio => {
            audio.pause();
            audio.currentTime = 0;
            audio.volume = 0;
        });
        this.currentTrackName = null;
    },

    updateButtonsUI() {
        const lang = (gameState && gameState.lang) || 'zh';
        const isZh = lang === 'zh';
        const isSilent = this.isMuted || this.autoplayBlocked;
        const labelText = isSilent ? (isZh ? '静音' : 'Muted') : (isZh ? '音乐' : 'BGM');
        const icon = isSilent ? '🔇' : '🎵';
        const titleText = isSilent 
            ? (I18N[lang]?.bgmTitleMuted || 'BGM: Muted (Click to play)')
            : (I18N[lang]?.bgmTitlePlaying || 'BGM: Playing (Click to mute)');

        const updateBtn = (btn) => {
            if (!btn) return;
            btn.classList.toggle('muted', isSilent);
            btn.title = titleText;
            btn.setAttribute('aria-label', titleText);
            btn.innerHTML = `${icon} <span class="audio-label">${labelText}</span>`;
        };

        updateBtn(gameUI.lobbyAudioBtn);
        updateBtn(gameUI.audioToggleBtn);
    }
};

window.BGMManager = BGMManager;

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
    loadStoredSettings();
    updateLanguage();
    BGMManager.init();
    
    let debugVisible = false;
    if (gameUI.debugBtn) {
        gameUI.debugBtn.addEventListener('click', () => {
            debugVisible = !debugVisible;
            if (gameUI.chatBox) {
                gameUI.chatBox.classList.toggle('show-debug-logs', debugVisible);
            }
            document.querySelectorAll('.message-container.debug, .message.debug').forEach(el => {
                el.classList.toggle('visible', debugVisible);
            });
            gameUI.debugBtn.classList.toggle('active', debugVisible);
        });
    }

    if (gameUI.gameLangBtn) {
        gameUI.gameLangBtn.addEventListener('click', toggleLanguage);
    }
    
    if (gameUI.lobbyLangBtn) {
        gameUI.lobbyLangBtn.addEventListener('click', toggleLanguage);
    }

    if (gameUI.lobbyAudioBtn) {
        gameUI.lobbyAudioBtn.addEventListener('click', () => BGMManager.toggleMute());
    }

    if (gameUI.audioToggleBtn) {
        gameUI.audioToggleBtn.addEventListener('click', () => BGMManager.toggleMute());
    }

    if (gameUI.speedToggleBtn) {
        gameUI.speedToggleBtn.addEventListener('click', togglePacingSpeed);
    }

    if (gameUI.skipQueueBtn) {
        gameUI.skipQueueBtn.addEventListener('click', skipLogQueue);
    }

    if (gameUI.newMessagesIndicator) {
        gameUI.newMessagesIndicator.addEventListener('click', () => {
            scrollToBottom(true);
        });
    }

    if (gameUI.chatBox) {
        gameUI.chatBox.addEventListener('scroll', checkScrollPosition);

        // Delegate hover and click on @seat mention pills inside chat bubbles
        gameUI.chatBox.addEventListener('mouseover', (e) => {
            const pill = e.target.closest('.seat-mention-pill');
            if (pill && pill.dataset.player) {
                highlightSidebarPlayerCard(pill.dataset.player, true);
            }
        });
        gameUI.chatBox.addEventListener('mouseout', (e) => {
            const pill = e.target.closest('.seat-mention-pill');
            if (pill && pill.dataset.player) {
                highlightSidebarPlayerCard(pill.dataset.player, false);
            }
        });
        gameUI.chatBox.addEventListener('click', (e) => {
            const pill = e.target.closest('.seat-mention-pill');
            if (pill && pill.dataset.player) {
                e.stopPropagation();
                toggleSpeakerFocus(pill.dataset.player);
            }
        });
    }

    // Spacebar to step/advance the next queued message when not typing in an input
    window.addEventListener('keydown', (e) => {
        if (e.code === 'Space' && gameState.active) {
            const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
            if (activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select' || activeTag === 'button') {
                return;
            }
            if (gameState.logQueue && gameState.logQueue.length > 0) {
                e.preventDefault();
                stepNextQueuedLogImmediately();
            }
        }
    });

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

/** @type {number|null} - Selected turn timeout in seconds (null = no limit). */
let selectedTurnTimeoutSeconds = null;

/**
 * Loads stored settings from localStorage and applies them to UI state.
 */
function loadStoredSettings() {
    try {
        const savedSpeed = localStorage.getItem('werewolf_pacing_speed');
        if (savedSpeed !== null) {
            const parsedSpeed = parseFloat(savedSpeed);
            if ([1.0, 0.5, 0].includes(parsedSpeed)) {
                gameState.pacingMultiplier = parsedSpeed;
            }
        }
    } catch (e) {
        console.warn('Failed to read settings from localStorage', e);
    }
    updatePacingControlsUI();
}

/**
 * Syncs the settings modal timer controls with the current state.
 */
function syncTimerUIFromState() {
    const timerSelect = settingsUI.timerSelect || document.getElementById('turn-timer-select');
    const customContainer = settingsUI.customTimerContainer || document.getElementById('custom-timer-container');
    const customInput = settingsUI.customTimerInput || document.getElementById('custom-timer-input');
    if (!timerSelect) return;

    const standardValues = ["60", "120", "180", "300", "600"];
    const strVal = String(selectedTurnTimeoutSeconds);
    if (standardValues.includes(strVal)) {
        timerSelect.value = strVal;
        if (customContainer) customContainer.style.display = 'none';
    } else {
        timerSelect.value = 'custom';
        if (customContainer) customContainer.style.display = 'flex';
        if (customInput) customInput.value = Math.max(1, Math.round(selectedTurnTimeoutSeconds / 60));
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

    const openModal = () => {
        syncTimerUIFromState();
        settingsUI.modal.classList.add('active');
        trapFocus(settingsUI.modal);
        if (settingsUI.timerSelect) {
            settingsUI.timerSelect.focus();
        } else {
            const firstSelect = settingsUI.modal.querySelector('select');
            if (firstSelect) firstSelect.focus();
        }
    };

    if (setupUI.openSettingsBtn) {
        setupUI.openSettingsBtn.addEventListener('click', openModal);
    }

    if (gameUI.gameSettingsBtn) {
        gameUI.gameSettingsBtn.addEventListener('click', openModal);
    }

    if (settingsUI.timerSelect) {
        settingsUI.timerSelect.addEventListener('change', () => {
            if (settingsUI.timerSelect.value === 'custom') {
                if (settingsUI.customTimerContainer) settingsUI.customTimerContainer.style.display = 'flex';
                if (settingsUI.customTimerInput) {
                    if (!settingsUI.customTimerInput.value) {
                        settingsUI.customTimerInput.value = Math.max(1, Math.round(selectedTurnTimeoutSeconds / 60));
                    }
                    settingsUI.customTimerInput.focus();
                }
            } else {
                if (settingsUI.customTimerContainer) settingsUI.customTimerContainer.style.display = 'none';
            }
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
        settingsUI.saveBtn.addEventListener('click', async () => {
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
    if (gameState.gameId) {
        fetch('/api/game/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_id: gameState.gameId,
                language: gameState.lang
            })
        }).catch(err => console.warn('Failed to sync language setting to server:', err));
    }
}

/**
 * Localizes player references (e.g. 'Player 3' <-> '3号玩家') and role names in system/prompt text.
 * @param {string} text - Raw message string in the selected language.
 * @param {boolean} isZh - Whether the target language is Chinese.
 * @returns {string}
 */
function localizeMessageText(text, isZh) {
    if (!text || typeof text !== 'string') return '';
    if (isZh) {
        let out = text.replace(/\bPlayer\s*(\d{1,2})\b/gi, '$1号玩家');
        const zhRoles = I18N.zh.roles;
        ['Black Werewolf King', 'Werewolf', 'Villager', 'Witch', 'Seer', 'Guard', 'Hunter'].forEach(enRole => {
            if (zhRoles[enRole]) {
                out = out.replace(new RegExp(`\\b${enRole}\\b`, 'g'), zhRoles[enRole]);
            }
        });
        return out;
    } else {
        return text.replace(/(\d{1,2})\s*号玩家/g, 'Player $1');
    }
}

/**
 * Checks if the player is currently making a blind/secret action (vote or sheriff election).
 * @returns {boolean}
 */
function isUserDecidingBlindAction() {
    if (!gameState.pendingAction) return false;
    if (gameState.pendingAction.type === 'vote') return true;
    const prompt = gameState.pendingAction.prompt;
    const promptStr = typeof prompt === 'object' ? (prompt.zh || prompt.en || '') : String(prompt || '');
    return promptStr.includes('竞选警长') || promptStr.includes('run for sheriff');
}

/**
 * Checks if a log entry represents a player voting or candidate signup action that should stay hidden until all players submit their choice.
 * @param {object} log - The log entry object.
 * @returns {boolean} True if the log is a blind decision action.
 */
function isHiddenDecisionLog(log) {
    if (!log) return false;
    if (log.type === 'EXECUTION_VOTE' || log.type === 'SHERIFF_VOTE' || log.type === 'SHERIFF_CANDIDATE') return true;
    const msg = typeof log.message === 'object' ? (log.message.zh || log.message.en || '') : String(log.message || '');
    return msg.includes('投票给') || msg.includes('voted for') || msg.includes('弃票') || msg.includes('abstained') || msg.includes('竞选警长') || msg.includes('run for sheriff');
}

/**
 * Checks if a log entry is a debug-only state boundary log (`--- XXXState Start/End ---`).
 * @param {object} log - The log entry object.
 * @returns {boolean}
 */
function isDebugStateBoundaryLog(log) {
    if (!log || log.type !== 'SYSTEM') return false;
    const msgZh = typeof log.message === 'object' ? (log.message.zh || '') : String(log.message || '');
    const msgEn = typeof log.message === 'object' ? (log.message.en || '') : String(log.message || '');
    const zTrim = msgZh.trim();
    const eTrim = msgEn.trim();
    if (/^---\s*.*(开始|结束)\s*---$/.test(zTrim) || /^---\s*.*(Start|End)\s*---$/i.test(eTrim)) {
        return true;
    }
    return false;
}

/**
 * Checks if a log entry is redundant individual vote/tally noise or repetitive filler chatter
 * that should be suppressed from the player chat box.
 * @param {object} log - The log entry object.
 * @returns {boolean}
 */
function isRedundantChatNoiseLog(log) {
    if (!log) return false;
    if (log.type === 'EXECUTION_VOTE' || log.type === 'SHERIFF_VOTE' || log.type === 'SHERIFF_CANDIDATE') {
        return true;
    }
    if (log.type === 'ACTION') {
        const msgZh = typeof log.message === 'object' ? (log.message.zh || '') : String(log.message || '');
        const msgEn = typeof log.message === 'object' ? (log.message.en || '') : String(log.message || '');
        const combined = `${msgZh} ${msgEn}`;
        // Suppress "open your eyes" / "close your eyes" filler since the prompt & spotlight card already show the action
        if (
            combined.includes('请睁眼') ||
            combined.includes('open your eyes') ||
            combined.includes('请闭眼') ||
            combined.includes('close your eyes')
        ) {
            return true;
        }
    }
    if (log.type === 'SYSTEM') {
        const msgZh = typeof log.message === 'object' ? (log.message.zh || '') : String(log.message || '');
        const msgEn = typeof log.message === 'object' ? (log.message.en || '') : String(log.message || '');
        const combined = `${msgZh} ${msgEn}`;

        // Filter out "--- Vote Results ---", "--- Sheriff Vote Results ---", "--- Tie-breaker Vote Results ---"
        if (
            combined.includes('--- 投票结果 ---') ||
            combined.includes('--- Vote Results ---') ||
            combined.includes('--- 警长投票结果 ---') ||
            combined.includes('--- Sheriff Vote Results ---') ||
            combined.includes('--- PK投票结果 ---') ||
            combined.includes('--- Tie-breaker Vote Results ---')
        ) {
            return true;
        }

        // Filter out individual vote tally lines like "Player 1: 2 票" or "Player 1: 2 vote(s)"
        if (/^Player\s+\d+:\s*[\d.]+\s*(票|vote\(s\))$/.test(msgZh.trim()) || /^Player\s+\d+:\s*[\d.]+\s*(票|vote\(s\))$/.test(msgEn.trim())) {
            return true;
        }

        // Filter out redundant summary lines right before/after VOTE_RESULT
        if (
            combined.includes('票数最多') ||
            combined.includes('has the most votes') ||
            combined.includes('无人投票') ||
            combined.includes('No votes were cast')
        ) {
            return true;
        }

        // Filter out redundant phase transition filler chatter (since the Night/Day pill divider and celestial banner already announce it)
        if (
            msgZh === '太阳落山了，一个新的夜晚开始了...' ||
            msgEn === 'The sun sets, and a new night begins...' ||
            msgZh === '长夜已过，黎明将至。' ||
            msgEn === 'The night is over, and dawn is approaching.' ||
            msgZh === '天亮了。' ||
            msgEn === 'A new day begins.' ||
            msgZh === '天黑了，黄昏降临。' ||
            msgEn === 'The day is over, and dusk is approaching.' ||
            msgZh === '玩家们正在回顾今天发生的事情...' ||
            msgEn === 'Players are reflecting on the day...' ||
            msgZh === '现在开始竞选警长。' ||
            msgEn === 'Players can now choose to run for sheriff.' ||
            msgZh === '请竞选玩家发表竞选演说。' ||
            msgEn === 'All election players will now give their speeches.' ||
            msgZh === '请警下玩家开始投票。' ||
            msgEn === 'All living players who are not candidates will now vote for the sheriff.' ||
            msgZh === '请所有玩家依次发言。' ||
            msgEn === 'All living players will now give their speeches.' ||
            msgZh === '现在开始放逐投票。' ||
            msgEn === "It's time to vote. Who do you want to execute?" ||
            msgZh === '没有在场警长。发言将按默认顺序进行。' ||
            msgEn === 'There is no active Sheriff. Speech will proceed in default order.' ||
            combined.includes('正在决定发言顺序') ||
            combined.includes('is deciding the speech order')
        ) {
            return true;
        }
    }
    return false;
}

/**
 * Cycles the message pacing speed between Normal (1x), Fast (2x), and Instant (MAX).
 */
function togglePacingSpeed() {
    if (gameState.pacingMultiplier === 1.0) {
        gameState.pacingMultiplier = 0.5;
    } else if (gameState.pacingMultiplier === 0.5) {
        gameState.pacingMultiplier = 0;
    } else {
        gameState.pacingMultiplier = 1.0;
    }
    try {
        localStorage.setItem('werewolf_pacing_speed', String(gameState.pacingMultiplier));
    } catch (e) {
        // Ignore storage errors
    }
    updatePacingControlsUI();
    if (gameState.pacingMultiplier === 0 && gameState.logQueue.length > 0) {
        skipLogQueue();
    }
}

/**
 * Updates the speed toggle and skip queue buttons in the game header.
 */
function updatePacingControlsUI() {
    const lang = (gameState && gameState.lang) || 'zh';
    const tp = I18N[lang]?.pacing || I18N.zh.pacing;

    if (gameUI.speedToggleBtn) {
        let icon = '🐢';
        let label = tp.speed1x;
        let title = tp.title1x;
        if (gameState.pacingMultiplier === 0.5) {
            icon = '🐇';
            label = tp.speed2x;
            title = tp.title2x;
        } else if (gameState.pacingMultiplier === 0) {
            icon = '⚡';
            label = tp.speedMax;
            title = tp.titleMax;
        }
        gameUI.speedToggleBtn.title = title;
        gameUI.speedToggleBtn.setAttribute('aria-label', title);
        gameUI.speedToggleBtn.innerHTML = `${icon} <span class="speed-label">${label}</span>`;
    }

    if (gameUI.skipQueueBtn) {
        const queuedCount = gameState.logQueue ? gameState.logQueue.length : 0;
        if (queuedCount > 1) {
            gameUI.skipQueueBtn.classList.remove('hidden');
            gameUI.skipQueueBtn.title = tp.skipTitle;
            gameUI.skipQueueBtn.innerHTML = `⏭️ <span class="skip-label">${tp.skip} (${queuedCount})</span>`;
        } else {
            gameUI.skipQueueBtn.classList.add('hidden');
        }
    }
}

/**
 * Computes the adaptive display delay (in ms) after rendering a log entry.
 * @param {object} log - The log entry just rendered.
 * @returns {number} Delay in milliseconds before displaying the next queued log.
 */
function getLogPacingDelay(log) {
    if (!log || gameState.pacingMultiplier === 0) return 0;
    if (log.type === 'PLAYER_THINKING' || log.type === 'PLAYER_DONE_THINKING') return 0;
    if (isRedundantChatNoiseLog(log) || isDebugStateBoundaryLog(log)) return 0;

    const mult = gameState.pacingMultiplier;
    const textObj = log.message;
    const text = typeof textObj === 'object' ? (textObj[gameState.lang] || textObj.zh || textObj.en || '') : String(textObj || '');

    // 1. High-priority secret role operation results (Seer check, Witch action, Guard protect, Werewolf target, Gunshot)
    if (['SEER_CHECK', 'WITCH_ACTION', 'GUARD_PROTECT', 'WEREWOLF_TARGET', 'HUNTER_SHOOT', 'BLACKWEREWOLFKING_SHOOT', 'PLAYER_SHOOT'].includes(log.type)) {
        return Math.round(2200 * mult);
    }

    // 2. Player speeches & werewolf whispers: scale by text length so players can comfortably read
    if (log.type === 'SPEECH' || log.type === 'WHISPER') {
        const charDelay = Math.min(1600, Math.max(0, text.length * 28));
        return Math.round((1500 + charDelay) * mult);
    }

    // 3. Consolidated vote result or sheriff election signup cards
    if (log.type === 'VOTE_RESULT' || (log.data && log.data.phase === 'Sheriff Signup')) {
        return Math.round(1800 * mult);
    }

    // 4. Dramatic phase transitions & eliminations
    if (['NIGHT_FALLS', 'DAY_BREAKS', 'PLAYER_ELIMINATED', 'SHERIFF_ELECTED', 'GAME_OVER'].includes(log.type)) {
        return Math.round(1400 * mult);
    }

    // 5. Role assignment / critical private notices
    if (text.includes('你被分配的角色是') || text.includes('You have been assigned the role') || text.includes('被狼人袭击了') || text.includes('targeted by the werewolves')) {
        return Math.round(1600 * mult);
    }

    // 6. Standard system / action notices
    return Math.round(650 * mult);
}

/**
 * Enqueues logs for paced rendering in the chat box.
 * @param {Array<object>} logs - Array of log objects to enqueue.
 */
function enqueueLogs(logs) {
    if (!logs || logs.length === 0) return;
    logs.forEach(log => {
        // Record Seer check results immediately into state so the Seer badge is preserved
        if (log.type === 'SEER_CHECK' && log.target && log.data && log.data.result) {
            gameState.seerChecks[log.target] = log.data.result;
        }
        gameState.logQueue.push(log);
    });
    updatePacingControlsUI();
    if (!gameState.isProcessingQueue) {
        processNextQueuedLog();
    }
}

/**
 * Updates the floating speaker filter pill above the chat box (zero layout shift).
 */
function updateInteractiveBarUI() {
    const bar = gameUI.chatInteractiveBar || document.getElementById('chat-Interactive-bar');
    const statusEl = gameUI.chatInteractiveStatus || document.getElementById('chat-interactive-status');
    const actionBtn = gameUI.chatInteractiveAction || document.getElementById('chat-interactive-action');
    if (!bar || !statusEl || !actionBtn) return;

    const isZh = gameState.lang === 'zh';

    if (gameState.focusedSpeaker) {
        const seatLabel = formatPlayerSeatLabel(gameState.focusedSpeaker, isZh);
        const avatar = getAvatar(gameState.focusedSpeaker);
        bar.classList.remove('hidden');
        bar.className = 'chat-interactive-bar speaker-filter-mode';
        statusEl.innerHTML = isZh
            ? `🔍 只看 <strong>${avatar} ${seatLabel}</strong> 的发言`
            : `🔍 Filtering <strong>${avatar} ${seatLabel}</strong>`;
        actionBtn.innerText = isZh ? '✕ 全部' : '✕ All';
        actionBtn.onclick = () => toggleSpeakerFocus(null);
        return;
    }

    bar.classList.add('hidden');
}

/**
 * Steps the next queued log entry immediately (triggered by Spacebar).
 */
function stepNextQueuedLogImmediately() {
    if (!gameState.logQueue || gameState.logQueue.length === 0) return;
    processNextQueuedLog();
}

/**
 * Shows a 2.2-second Center-Stage Comic Toast Banner for major reveals and events.
 * @param {string} htmlContent - HTML content inside the toast banner.
 * @param {string} themeClass - Theme class ('toast-wolf', 'toast-good', 'toast-sheriff', 'toast-guard', 'toast-danger').
 */
function showSpotlightToast(htmlContent, themeClass = 'toast-default') {
    const banner = gameUI.spotlightToastBanner || document.getElementById('spotlight-toast-banner');
    if (!banner) return;

    if (gameState.toastTimer) {
        clearTimeout(gameState.toastTimer);
        gameState.toastTimer = null;
    }

    banner.className = `spotlight-toast-banner ${themeClass}`;
    banner.innerHTML = htmlContent;

    gameState.toastTimer = setTimeout(() => {
        banner.classList.add('hidden');
        gameState.toastTimer = null;
    }, 2400);
}

/**
 * Triggers a Center-Stage Toast Banner if the log is a critical reveal or dramatic event.
 * @param {object} log - The log entry.
 */
function triggerToastIfBigMoment(log) {
    if (!log) return;
    const isZh = gameState.lang === 'zh';
    const type = log.type;
    const targetName = typeof log.target === 'object' ? log.target?.name : log.target;
    const sourceName = typeof log.source === 'object' ? log.source?.name : log.source;

    if (type === 'SEER_CHECK' && targetName) {
        const resultCamp = (log.data && log.data.result) || '';
        const isWolf = resultCamp === 'Werewolf' || resultCamp === 'Werewolves';
        const seat = formatPlayerSeatLabel(targetName, isZh);
        const avatar = getAvatar(targetName);
        const verdict = isWolf ? (isZh ? '🐺 狼人阵营！' : '🐺 WEREWOLF!') : (isZh ? '👱 好人阵营' : '👱 GOOD CAMP');
        showSpotlightToast(
            `<span>🔮 ${isZh ? '查验身份' : 'Seer Check'}:</span> <strong>${avatar} ${seat}</strong> ➔ <span class="toast-verdict-pill">${verdict}</span>`,
            isWolf ? 'toast-wolf' : 'toast-good'
        );
        return;
    }

    if (type === 'WITCH_ACTION' && targetName) {
        const isSave = log.data?.action === 'save';
        const seat = formatPlayerSeatLabel(targetName, isZh);
        const avatar = getAvatar(targetName);
        showSpotlightToast(
            isSave
                ? `<span>💖 ${isZh ? '解药生效' : 'Saved'}:</span> <strong>${avatar} ${seat}</strong> ${isZh ? '已获救' : 'Rescued'}`
                : `<span>🧪 ${isZh ? '毒药生效' : 'Poisoned'}:</span> <strong>${avatar} ${seat}</strong> ${isZh ? '已毒杀' : 'Eliminated'}`,
            isSave ? 'toast-good' : 'toast-wolf'
        );
        return;
    }

    if (type === 'GUARD_PROTECT' && targetName) {
        const seat = formatPlayerSeatLabel(targetName, isZh);
        const avatar = getAvatar(targetName);
        showSpotlightToast(
            `<span>🛡️ ${isZh ? '守卫守护' : 'Guarded'}:</span> <strong>${avatar} ${seat}</strong>`,
            'toast-guard'
        );
        return;
    }

    if ((type === 'HUNTER_SHOOT' || type === 'BLACKWEREWOLFKING_SHOOT' || type === 'PLAYER_SHOOT') && sourceName && targetName) {
        const sSeat = formatPlayerSeatLabel(sourceName, isZh);
        const tSeat = formatPlayerSeatLabel(targetName, isZh);
        showSpotlightToast(
            `<span>💥 ${getAvatar(sourceName)} ${sSeat}</span> ${isZh ? '开枪带走了' : 'shot'} <strong>💀 ${getAvatar(targetName)} ${tSeat}</strong>!`,
            'toast-wolf'
        );
        return;
    }

    if (type === 'SHERIFF_ELECTED' && targetName) {
        const seat = formatPlayerSeatLabel(targetName, isZh);
        const avatar = getAvatar(targetName);
        showSpotlightToast(
            `<span>👮 ${isZh ? '新任警长' : 'Sheriff Elected'}:</span> <strong>${avatar} ${seat} ⭐</strong>`,
            'toast-sheriff'
        );
    }
}

/**
 * Highlights or un-highlights a player's card on the left/right sidebar when hovering a @seat pill.
 * @param {string} playerName - e.g. 'Player 3'
 * @param {boolean} active - Whether to highlight
 */
function highlightSidebarPlayerCard(playerName, active) {
    const card = Array.from(document.querySelectorAll('.player-card')).find(c => c.dataset.name === playerName);
    if (card) {
        card.classList.toggle('mention-hovered', Boolean(active));
    }
}

/**
 * Toggles filtering/highlighting of a specific player's speeches in the chat box.
 * @param {string|null} playerName - e.g. 'Player 3', or null to clear filter.
 */
function toggleSpeakerFocus(playerName) {
    if (!playerName || gameState.focusedSpeaker === playerName) {
        gameState.focusedSpeaker = null;
    } else {
        gameState.focusedSpeaker = playerName;
    }

    // Update sidebar card active focus indicator
    document.querySelectorAll('.player-card').forEach(card => {
        card.classList.toggle('speaker-focused', card.dataset.name === gameState.focusedSpeaker);
    });

    // Update chat messages dim/highlight state
    if (gameUI.chatBox) {
        gameUI.chatBox.classList.toggle('has-speaker-focus', Boolean(gameState.focusedSpeaker));
        gameUI.chatBox.querySelectorAll('.message-container').forEach(msg => {
            if (!gameState.focusedSpeaker) {
                msg.classList.remove('speaker-match', 'speaker-dimmed');
            } else if (msg.dataset.speaker === gameState.focusedSpeaker) {
                msg.classList.add('speaker-match');
                msg.classList.remove('speaker-dimmed');
            } else {
                msg.classList.add('speaker-dimmed');
                msg.classList.remove('speaker-match');
            }
        });
    }

    updateInteractiveBarUI();
}

/**
 * Formats plain speech text by converting player seat mentions (e.g. "Player 3", "3号玩家", "3号")
 * into interactive cartoon avatar mini-pills.
 * @param {string} rawText - Raw speech text.
 * @returns {string} Safe HTML string with mention pills.
 */
function formatSpeechWithSeatPills(rawText) {
    const safe = escapeHtml(rawText);
    const totalPlayers = (gameState.players && gameState.players.length) || 12;
    const isZh = gameState.lang === 'zh';

    // Match "Player N", "N号玩家", or "N号" (where N is 1..12)
    return safe.replace(/\bPlayer\s*(\d{1,2})\b|(\d{1,2})\s*号(?:玩家)?/gi, (match, enNum, zhNum) => {
        const num = parseInt(enNum || zhNum, 10);
        if (!Number.isFinite(num) || num < 1 || num > totalPlayers) {
            return match;
        }
        const playerName = `Player ${num}`;
        const avatar = getAvatar(playerName);
        const label = isZh ? `${num}号` : `P${num}`;
        return `<span class="seat-mention-pill" data-player="${playerName}" title="${isZh ? '点击高亮该玩家所有发言' : 'Click to highlight this player\'s speeches'}">${avatar}${label}</span>`;
    });
}

/**
 * Processes the next item in the client-side message pacing queue.
 */
function processNextQueuedLog() {
    if (gameState.queueTimer) {
        clearTimeout(gameState.queueTimer);
        gameState.queueTimer = null;
    }

    if (!gameState.logQueue || gameState.logQueue.length === 0) {
        gameState.isProcessingQueue = false;
        updatePacingControlsUI();
        syncPostQueueState();
        return;
    }

    gameState.isProcessingQueue = true;
    const log = gameState.logQueue.shift();
    updatePacingControlsUI();

    // Skip redundant noise logs immediately without delay
    if (isRedundantChatNoiseLog(log)) {
        processNextQueuedLog();
        return;
    }

    // Render debug boundary logs silently (hidden unless debug mode is toggled) with 0ms delay
    if (isDebugStateBoundaryLog(log)) {
        gameState.renderedLogs.push(log);
        processLog(log);
        processNextQueuedLog();
        return;
    }

    const wasNearBottom = isUserNearBottom();
    gameState.renderedLogs.push(log);
    processLog(log);
    triggerToastIfBigMoment(log);

    if (log.type === 'PLAYER_ELIMINATED' && log.target) {
        const targetName = typeof log.target === 'object' ? log.target.name : log.target;
        const card = Array.from(document.querySelectorAll('.player-card')).find(c => c.dataset.name === targetName);
        if (card) card.classList.add('dead');
    }

    if (log.type !== 'PLAYER_THINKING' && log.type !== 'PLAYER_DONE_THINKING') {
        if (!wasNearBottom) {
            gameState.unreadCount = (gameState.unreadCount || 0) + 1;
        }
        scrollToBottom(wasNearBottom);
    }

    const delay = getLogPacingDelay(log);
    if (delay <= 0) {
        processNextQueuedLog();
    } else {
        gameState.queueTimer = setTimeout(() => {
            processNextQueuedLog();
        }, delay);
    }
}

/**
 * Instantly flushes all remaining logs in the pacing queue to the chat box.
 */
function skipLogQueue() {
    if (gameState.queueTimer) {
        clearTimeout(gameState.queueTimer);
        gameState.queueTimer = null;
    }
    const wasNearBottom = isUserNearBottom();
    while (gameState.logQueue && gameState.logQueue.length > 0) {
        const log = gameState.logQueue.shift();
        if (isRedundantChatNoiseLog(log)) continue;
        gameState.renderedLogs.push(log);
        processLog(log);
    }
    gameState.isProcessingQueue = false;
    updatePacingControlsUI();
    scrollToBottom(wasNearBottom || true);
    syncPostQueueState();
}

/**
 * Invoked once the message pacing queue finishes draining so any pending user input
 * prompt or game-over modal is presented right on cue.
 */
function syncPostQueueState() {
    if (gameState.players && gameState.players.length > 0) {
        updatePlayers(gameState.players);
    }

    handleInputRequest(gameState.latestServerInputRequired);

    if (!gameState.latestServerGameActive && !gameState.latestServerInputRequired && gameState.active) {
        gameState.active = false;
        stopTurnTimer();
        clearInterval(pollingInterval);
        addSystemMessage(I18N[gameState.lang].gameOver);

        setTimeout(() => {
            showEvaluationModal();
        }, 1800);
    }
}

/**
 * Flushes buffered decision logs once the player has submitted their choice.
 */
function flushPendingVoteLogs() {
    if (gameState.pendingVoteLogs && gameState.pendingVoteLogs.length > 0) {
        const logsToFlush = gameState.pendingVoteLogs;
        gameState.pendingVoteLogs = [];
        enqueueLogs(logsToFlush);
    }
}

/**
 * Appends a message element into the currently active phase section (or directly to chatBox before Night 1).
 * @param {HTMLElement} msgEl - The message container element.
 */
function appendToActiveChatSection(msgEl) {
    // Apply speaker focus dimming/highlighting if a speaker filter is currently active
    if (gameState.focusedSpeaker) {
        if (msgEl.dataset.speaker === gameState.focusedSpeaker) {
            msgEl.classList.add('speaker-match');
        } else {
            msgEl.classList.add('speaker-dimmed');
        }
    }

    if (gameState.currentPhaseBodyEl && gameUI.chatBox.contains(gameState.currentPhaseBodyEl)) {
        // If adding a real visible message to a Night section, remove the sleeping placeholder
        if (!msgEl.classList.contains('debug') && !msgEl.classList.contains('night-sleep-placeholder')) {
            const sleepPlaceholder = gameState.currentPhaseBodyEl.querySelector('.night-sleep-placeholder');
            if (sleepPlaceholder) {
                sleepPlaceholder.remove();
            }
        }
        gameState.currentPhaseBodyEl.appendChild(msgEl);
        updatePhaseSectionCount(gameState.currentPhaseBodyEl.parentElement);
    } else {
        gameUI.chatBox.appendChild(msgEl);
    }
}

/**
 * Updates the folded message count badge on a Style 1A centered pill divider.
 * @param {HTMLElement} sectionEl - The .chat-phase-section element.
 */
function updatePhaseSectionCount(sectionEl) {
    if (!sectionEl) return;
    const bodyEl = sectionEl.querySelector('.chat-phase-body');
    const countEl = sectionEl.querySelector('.phase-folded-count');
    if (!bodyEl || !countEl) return;
    const visibleChildren = Array.from(bodyEl.children).filter(
        el => !el.classList.contains('debug') && !el.classList.contains('night-sleep-placeholder')
    );
    const count = visibleChildren.length;
    const isZh = gameState.lang === 'zh';
    countEl.innerText = isZh ? `${count}条` : `${count}`;
}

/**
 * Starts a new Style 1A collapsible phase section (Centered Cartoon Pill Divider) in the chat box.
 * @param {string} phaseType - 'Night' or 'Day'
 * @param {object} log - The NIGHT_FALLS or DAY_BREAKS log object.
 */
function startNewChatPhaseSection(phaseType, log) {
    const isZh = gameState.lang === 'zh';
    const isNight = phaseType === 'Night';
    const dayNum = log.day || 1;
    const phaseId = `${phaseType}_${dayNum}`;

    gameState.currentPhaseId = phaseId;

    const sectionEl = document.createElement('div');
    const isCollapsed = gameState.collapsedPhases && gameState.collapsedPhases.has(phaseId);
    sectionEl.className = `chat-phase-section ${isNight ? 'night-section' : 'day-section'}${isCollapsed ? ' collapsed' : ''}`;
    sectionEl.dataset.phaseId = phaseId;

    let rawTitle = log.message;
    if (typeof rawTitle === 'object') {
        rawTitle = rawTitle[gameState.lang] || rawTitle.zh || rawTitle.en || '';
    }
    const cleanTitle = String(rawTitle || '').replace(/[-—]/g, '').trim() || (isNight ? (isZh ? `第 ${dayNum} 夜` : `Night ${dayNum}`) : (isZh ? `第 ${dayNum} 天` : `Day ${dayNum}`));

    const dividerRow = document.createElement('div');
    dividerRow.className = 'phase-ribbon-divider';

    const pillBtn = document.createElement('button');
    pillBtn.type = 'button';
    pillBtn.className = `phase-ribbon-pill ${isNight ? 'night' : 'day'}`;
    pillBtn.setAttribute('aria-expanded', isCollapsed ? 'false' : 'true');
    pillBtn.title = isZh ? '点击收起 / 展开本阶段记录' : 'Click to collapse / expand phase';
    pillBtn.innerHTML = `
        <span>${isNight ? '🌙' : '☀️'} ${escapeHtml(cleanTitle)}</span>
        <span class="phase-folded-count">${isZh ? '0条' : '0'}</span>
        <span class="phase-chevron">▾</span>
    `;

    dividerRow.appendChild(pillBtn);

    const bodyEl = document.createElement('div');
    bodyEl.className = 'chat-phase-body';

    // For Night phases, add a subtle peaceful sleeping note by default; if the player has a night role action, it is replaced automatically
    if (isNight) {
        const sleepEl = document.createElement('div');
        sleepEl.className = 'message-container system night-sleep-placeholder';
        sleepEl.innerHTML = `<div class="chat-bubble system sleep-bubble">${isZh ? '💤 夜深人静，闭眼沉睡中...' : '💤 Sleeping peacefully through the night...'}</div>`;
        bodyEl.appendChild(sleepEl);
    }

    pillBtn.addEventListener('click', () => {
        const nowCollapsed = sectionEl.classList.toggle('collapsed');
        pillBtn.setAttribute('aria-expanded', nowCollapsed ? 'false' : 'true');
        if (nowCollapsed) {
            gameState.collapsedPhases.add(phaseId);
        } else {
            gameState.collapsedPhases.delete(phaseId);
        }
    });

    sectionEl.appendChild(dividerRow);
    sectionEl.appendChild(bodyEl);
    gameUI.chatBox.appendChild(sectionEl);

    gameState.currentPhaseBodyEl = bodyEl;
}

/**
 * Re-renders all logs that have already been displayed in the chat box.
 * This is used after a language change to update the display without dumping unqueued items.
 */
function renderLogs() {
    gameUI.chatBox.innerHTML = '';
    gameState.currentPhaseBodyEl = null;
    gameState.currentPhaseId = null;
    const logsToRender = (gameState.renderedLogs && gameState.renderedLogs.length > 0)
        ? gameState.renderedLogs
        : gameState.logs;
    logsToRender.forEach(log => {
        if (isUserDecidingBlindAction() && isHiddenDecisionLog(log)) {
            return;
        }
        if (isRedundantChatNoiseLog(log)) {
            return;
        }
        processLog(log);
    });
    updateInteractiveBarUI();
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
    const isZh = gameState.lang === 'zh';
    
    // Setup Screen
    if (setupUI.title) setupUI.title.innerText = t.title;
    if (setupUI.labels[0]) setupUI.labels[0].innerText = t.selectAvatar;
    if (setupUI.labels[1]) setupUI.labels[1].innerText = t.playerCount;
    if (setupUI.labels[2]) setupUI.labels[2].innerText = t.selectRole;
    
    // Settings Modal
    if (settingsUI.title) settingsUI.title.innerText = t.advancedSettings;
    if (settingsUI.timerLabel) settingsUI.timerLabel.innerText = t.turnTimer;
    if (settingsUI.providerLabel) settingsUI.providerLabel.innerText = t.provider;
    if (settingsUI.apiKeyLabel) settingsUI.apiKeyLabel.innerText = t.apiKey;
    if (settingsUI.baseUrlLabel) settingsUI.baseUrlLabel.innerText = t.baseUrl;
    if (settingsUI.modelNameLabel) settingsUI.modelNameLabel.innerText = t.modelName;
    if (settingsUI.customTimerUnit) settingsUI.customTimerUnit.innerText = t.minUnit;
    if (settingsUI.customTimerInput && t.customMinPlaceholder) {
        settingsUI.customTimerInput.placeholder = t.customMinPlaceholder;
    }
    if (settingsUI.timerSelect && t.timerOptions) {
        Array.from(settingsUI.timerSelect.options).forEach(opt => {
            const key = opt.dataset.i18n;
            if (key && t.timerOptions[key]) {
                opt.text = t.timerOptions[key];
            }
        });
    }
    const providerSelect = document.getElementById('provider-select');
    if (providerSelect) {
        const providerNames = isZh ? {
            openai: 'OpenAI',
            doubao: '豆包 (火山引擎)',
            gemini: 'Gemini (Google)',
            qwen: '通义千问 (阿里云)',
            deepseek: 'DeepSeek',
            custom: '自定义'
        } : {
            openai: 'OpenAI',
            doubao: 'Doubao (Volcengine)',
            gemini: 'Gemini (Google)',
            qwen: 'Qwen (Aliyun)',
            deepseek: 'DeepSeek',
            custom: 'Custom'
        };
        Array.from(providerSelect.options).forEach(opt => {
            if (providerNames[opt.value]) {
                opt.text = providerNames[opt.value];
            }
        });
    }
    if (setupUI.apiKeyInput) {
        setupUI.apiKeyInput.placeholder = isZh ? '请输入 API Key' : 'API Key';
    }
    const baseUrlInput = document.getElementById('base-url');
    if (baseUrlInput) {
        baseUrlInput.placeholder = isZh ? '例如 https://api.openai.com/v1' : 'e.g. https://api.openai.com/v1';
    }
    const modelNameInput = document.getElementById('model-name');
    if (modelNameInput) {
        modelNameInput.placeholder = isZh ? '例如 gpt-4o' : 'e.g. gpt-4o';
    }
    if (settingsUI.saveBtn) settingsUI.saveBtn.innerText = t.saveSettings;
    if (setupUI.openSettingsBtn) setupUI.openSettingsBtn.innerText = "⚙️ " + t.advancedSettings;
    if (gameUI.gameSettingsBtn) {
        gameUI.gameSettingsBtn.title = t.advancedSettings;
        gameUI.gameSettingsBtn.setAttribute('aria-label', t.advancedSettings);
    }
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

    if (gameUI.actionPrompt) {
        if (gameState.pendingAction) {
            let promptText = gameState.pendingAction.prompt;
            if (typeof promptText === 'object') {
                promptText = promptText[gameState.lang] || promptText['zh'] || promptText['en'] || JSON.stringify(promptText);
            }
            gameUI.actionPrompt.innerText = localizeMessageText(String(promptText || ''), isZh);
            if (gameState.pendingAction.type === 'vote' || gameState.pendingAction.type === 'choice') {
                const options = [...(gameState.pendingAction.options || [])];
                const noActionText = isZh ? "不行动 / 弃票" : "No Action / Abstain";
                const hasAbstain = options.includes(noActionText) || options.includes("Abstain") || options.includes("弃票");
                renderChoiceButtons(options, !hasAbstain);
            }
        } else {
            gameUI.actionPrompt.innerText = t.waiting;
        }
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
        if (evalUI.apiKeyInput) {
            evalUI.apiKeyInput.placeholder = isZh ? '请输入 API Key' : 'Enter API Key';
        }
        if (evalUI.startBtn.disabled) {
             evalUI.startBtn.innerText = t_eval.evaluating;
        } else {
             evalUI.startBtn.innerText = t_eval.startBtn;
        }
        evalUI.input.placeholder = t_eval.inputPlaceholder;
        evalUI.sendBtn.innerText = t_eval.send;
        if (evalUI.newGameBtn) evalUI.newGameBtn.innerText = isZh ? '再来一局' : 'New Game';

        const historyTabView = document.getElementById('history-tab-view');
        if (evalUI.modal.classList.contains('active') && historyTabView && historyTabView.style.display !== 'none') {
            loadOperationsHistory();
        }
    }

    // In-game Records Modal
    const t_records = I18N[gameState.lang]?.records;
    if (t_records) {
        if (gameUI.recordsBtn) {
            gameUI.recordsBtn.innerText = t_records.btn;
        }
        const recordsModal = document.getElementById('records-modal');
        if (recordsModal) {
            const title = document.getElementById('records-modal-title');
            if (title) title.innerText = t_records.title;
            const filterAll = document.getElementById('filter-all-btn');
            if (filterAll) filterAll.innerText = t_records.filterAll;
            const filterActions = document.getElementById('filter-actions-btn');
            if (filterActions) filterActions.innerText = t_records.filterActions;
            const filterVotes = document.getElementById('filter-votes-btn');
            if (filterVotes) filterVotes.innerText = t_records.filterVotes;

            if (recordsModal.classList.contains('active')) {
                renderIdentityCard(timelineState.operations);
                renderCurrentTimeline();
            }
        }
    }

    if (typeof BGMManager !== 'undefined') {
        BGMManager.updateButtonsUI();
    }
    updatePacingControlsUI();

    if (gameState.players && gameState.players.length > 0) {
        updatePlayers(gameState.players);
    }
}

/**
 * Renders the role selection UI based on the number of players.
 * @param {number} playerCount - The number of players in the game.
 */
function renderRoleSelection(playerCount) {
    const t = I18N[gameState.lang];
    let currentSelection = gameState.myRole || 'Random';
    
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

    setupRecordsModalListeners();
}



/**
 * Starts a new game.
 * Collects settings from the setup screen and sends a request to the backend.
 */
async function startGame() {
    const selectedRoleEl = document.querySelector('.role-option.selected');
    const selectedAvatarEl = document.querySelector('.avatar-option.selected');
    const selectedCountEl = document.querySelector('.toggle-btn.active');
    
    const role = gameState.myRole || (selectedRoleEl ? selectedRoleEl.dataset.role : 'Random');
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
            gameState.logs = [];
            gameState.renderedLogs = [];
            gameState.logQueue = [];
            gameState.isProcessingQueue = false;
            gameState.isQueuePausedByHover = false;
            gameState.focusedSpeaker = null;
            gameState.currentPhaseBodyEl = null;
            gameState.currentPhaseId = null;
            gameState.collapsedPhases = new Set();
            gameState.seerChecks = {};
            gameState.unreadCount = 0;
            gameState.lastLogIndex = 0;
            gameState.latestServerInputRequired = null;
            gameState.latestServerGameActive = true;
            if (gameState.queueTimer) {
                clearTimeout(gameState.queueTimer);
                gameState.queueTimer = null;
            }
            if (gameState.toastTimer) {
                clearTimeout(gameState.toastTimer);
                gameState.toastTimer = null;
            }
            gameUI.chatBox.innerHTML = '';
            gameUI.chatBox.classList.remove('has-speaker-focus');
            updateInteractiveBarUI();
            switchScreen('game');
            gameState.active = true;
            updatePacingControlsUI();
            if (typeof BGMManager !== 'undefined') {
                BGMManager.unlock();
            }
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

        gameState.latestServerInputRequired = data.input_required || null;
        gameState.latestServerGameActive = Boolean(data.game_active);

        // Temporarily sync pendingAction check for blind decision buffering
        const decidingBlind = Boolean(
            data.input_required && (
                data.input_required.type === 'vote' ||
                (data.input_required.prompt && (
                    JSON.stringify(data.input_required.prompt).includes('竞选警长') ||
                    JSON.stringify(data.input_required.prompt).includes('run for sheriff')
                ))
            )
        );

        const justDied = new Set();
        if (data.logs && data.logs.length > 0) {
            gameState.logs = gameState.logs.concat(data.logs);
            const logsToEnqueue = [];

            data.logs.forEach(log => {
                if (decidingBlind && isHiddenDecisionLog(log)) {
                    gameState.pendingVoteLogs.push(log);
                } else {
                    logsToEnqueue.push(log);
                }
                if (log.type === 'PLAYER_ELIMINATED' && log.target) {
                    const targetName = typeof log.target === 'object' ? log.target.name : log.target;
                    justDied.add(targetName);
                }
            });
            gameState.lastLogIndex += data.logs.length;
            enqueueLogs(logsToEnqueue);
        }

        if (data.players) {
            gameState.players = data.players;
            // While logs are still draining in the queue, avoid prematurely marking newly killed players dead
            const queuedDeaths = new Set(justDied);
            if (gameState.logQueue && gameState.logQueue.length > 0) {
                gameState.logQueue.forEach(qLog => {
                    if (qLog.type === 'PLAYER_ELIMINATED' && qLog.target) {
                        const tName = typeof qLog.target === 'object' ? qLog.target.name : qLog.target;
                        queuedDeaths.add(tName);
                    }
                });
            }
            updatePlayers(data.players, queuedDeaths);
            
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

        // Only present input_required or game-over once the message pacing queue has finished draining
        if (!gameState.isProcessingQueue && (!gameState.logQueue || gameState.logQueue.length === 0)) {
            syncPostQueueState();
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
    const baseUrlEl = document.getElementById('base-url');
    const modelNameEl = document.getElementById('model-name');
    const providerEl = document.getElementById('provider-select');
    const baseUrl = baseUrlEl ? baseUrlEl.value : '';
    const modelName = modelNameEl ? modelNameEl.value : '';
    const provider = providerEl ? providerEl.value : '';
    
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
                base_url: baseUrl || null,
                model_name: modelName || null,
                provider: provider || null,
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

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
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
        let formatted = escapeHtml(message).replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
        formatted = formatted.replace(/\n/g, '<br>');
        msgDiv.innerHTML = formatted;
    } else {
        msgDiv.innerText = message;
    }
    
    evalUI.chatBox.appendChild(msgDiv);
    evalUI.chatBox.scrollTop = evalUI.chatBox.scrollHeight;
}

/**
 * Formats a player name like 'Player 3' into a localized seat label with avatar.
 * @param {string} playerName - e.g. 'Player 3'
 * @param {boolean} isZh - Whether current language is Chinese
 * @returns {string} HTML string for player badge
 */
function formatPlayerSeatLabel(playerName, isZh) {
    if (!playerName || typeof playerName !== 'string') return '';
    const num = playerName.replace('Player ', '');
    const isMe = playerName === 'Player 1';
    if (isZh) {
        return `${num}号${isMe ? '(我)' : ''}`;
    }
    return `P${num}${isMe ? '(Me)' : ''}`;
}

/**
 * Builds a Consolidated Vote Card DOM element for VOTE_RESULT logs.
 * @param {object} log - The VOTE_RESULT log object.
 * @returns {HTMLElement}
 */
function createConsolidatedVoteCard(log) {
    const isZh = gameState.lang === 'zh';
    const data = log.data || {};
    const votesObj = data.votes || {};
    const phaseRaw = data.phase || 'Execution Vote';
    const resultRaw = data.result || 'None';
    const sheriffName = data.sheriff || null;
    const isSheriffElection = phaseRaw === 'Sheriff Election' || data.context === 'sheriff';

    let phaseTitle = isZh ? '🗳️ 放逐投票结果' : '🗳️ Execution Vote Results';
    if (phaseRaw === 'Sheriff Election') {
        phaseTitle = isZh ? '🎖️ 警长竞选投票' : '🎖️ Sheriff Election Vote';
    } else if (phaseRaw === 'Tie Breaker') {
        phaseTitle = isZh ? '⚔️ 平票 PK 投票' : '⚔️ Tie-Breaker PK Vote';
    }

    let resultBadgeText = '';
    let resultBadgeClass = 'neutral';
    if (!resultRaw || resultRaw === 'None') {
        resultBadgeText = isSheriffElection
            ? (isZh ? '无人当选' : 'No Sheriff')
            : (isZh ? '无人出局' : 'No Execution');
    } else if (resultRaw === 'Tie') {
        resultBadgeText = isZh ? '⚔️ 平票' : '⚔️ Tie Vote';
        resultBadgeClass = 'warning';
    } else {
        const seatText = formatPlayerSeatLabel(resultRaw, isZh);
        const avatar = getAvatar(resultRaw);
        if (isSheriffElection) {
            resultBadgeText = isZh ? `👮 ${avatar} ${seatText} 当选警长` : `👮 ${avatar} ${seatText} Elected`;
            resultBadgeClass = 'sheriff';
        } else {
            resultBadgeText = isZh ? `💀 ${avatar} ${seatText} 放逐出局` : `💀 ${avatar} ${seatText} Executed`;
            resultBadgeClass = 'danger';
        }
    }

    const entries = Object.entries(votesObj).filter(([targetName, voters]) => {
        return Array.isArray(voters) && voters.length > 0;
    });

    // Sort targets: non-abstain targets by vote weight descending, then Abstain last
    entries.sort(([targetA, votersA], [targetB, votersB]) => {
        const isAbstainA = targetA === 'Abstained' || targetA === '弃票';
        const isAbstainB = targetB === 'Abstained' || targetB === '弃票';
        if (isAbstainA && !isAbstainB) return 1;
        if (!isAbstainA && isAbstainB) return -1;
        const calcWeight = (voters) => voters.reduce((sum, v) => {
            const w = (!isSheriffElection && sheriffName && v === sheriffName) ? 1.5 : 1;
            return sum + w;
        }, 0);
        return calcWeight(votersB) - calcWeight(votersA);
    });

    let rowsHtml = '';
    if (entries.length === 0) {
        rowsHtml = `<div class="chat-vote-empty">${isZh ? '⚪ 全员弃票 / 无人投票' : '⚪ No votes were cast'}</div>`;
    } else {
        entries.forEach(([targetName, voters]) => {
            const isAbstain = targetName === 'Abstained' || targetName === '弃票';
            const totalWeight = voters.reduce((sum, v) => {
                const w = (!isSheriffElection && sheriffName && v === sheriffName) ? 1.5 : 1;
                return sum + w;
            }, 0);

            const targetHtml = isAbstain
                ? `<span class="chat-vote-target abstain">⚪ ${isZh ? '弃票' : 'Abstain'} <small>(${voters.length}${isZh ? '人' : ''})</small></span>`
                : `<span class="chat-vote-target">🎯 ${getAvatar(targetName)} ${formatPlayerSeatLabel(targetName, isZh)} <span class="vote-count-tag">${totalWeight}${isZh ? '票' : 'v'}</span></span>`;

            const voterPillsHtml = voters.map(voter => {
                const isSheriffWeight = !isSheriffElection && sheriffName && voter === sheriffName;
                const label = formatPlayerSeatLabel(voter, isZh);
                return isSheriffWeight
                    ? `<span class="voter-pill sheriff-voter">${getAvatar(voter)} ${label} ⭐1.5</span>`
                    : `<span class="voter-pill">${getAvatar(voter)} ${label}</span>`;
            }).join('');

            rowsHtml += `
                <div class="chat-vote-row">
                    <div class="chat-vote-target-col">${targetHtml}</div>
                    <div class="chat-vote-arrow">⟵</div>
                    <div class="chat-vote-voters-col">${voterPillsHtml}</div>
                </div>
            `;
        });
    }

    const card = document.createElement('div');
    card.className = 'chat-consolidated-card vote-summary-card';
    card.innerHTML = `
        <div class="chat-card-header">
            <span class="chat-card-title">${phaseTitle}</span>
            <span class="chat-card-badge ${resultBadgeClass}">${resultBadgeText}</span>
        </div>
        <div class="chat-card-body">
            ${rowsHtml}
        </div>
    `;
    return card;
}

/**
 * Builds a Consolidated Sheriff Election Signup Card DOM element.
 * @param {object} log - The log entry containing data.phase === 'Sheriff Signup'.
 * @returns {HTMLElement}
 */
function createSheriffSignupCard(log) {
    const isZh = gameState.lang === 'zh';
    const data = log.data || {};
    const candidates = data.candidates || [];
    const nonCandidates = data.non_candidates || [];

    const title = isZh ? '🎖️ 警长竞选报名汇总' : '🎖️ Sheriff Election Signups';
    let badgeText = '';
    let badgeClass = 'neutral';
    if (candidates.length === 0) {
        badgeText = isZh ? '无人上警' : 'No Candidates';
    } else if (candidates.length === 1) {
        const only = candidates[0];
        badgeText = isZh
            ? `👮 ${getAvatar(only)} ${formatPlayerSeatLabel(only, isZh)} 自动当选`
            : `👮 ${getAvatar(only)} ${formatPlayerSeatLabel(only, isZh)} Auto-Elected`;
        badgeClass = 'sheriff';
    } else {
        badgeText = isZh ? `${candidates.length}人上警竞选` : `${candidates.length} Candidates`;
        badgeClass = 'warning';
    }

    const renderGroup = (list, emptyText, isCandidatePill) => {
        if (!list || list.length === 0) {
            return `<span class="chat-signup-empty">${emptyText}</span>`;
        }
        return list.map(pName => {
            const cls = isCandidatePill ? 'voter-pill sheriff-voter' : 'voter-pill';
            return `<span class="${cls}">${getAvatar(pName)} ${formatPlayerSeatLabel(pName, isZh)}</span>`;
        }).join('');
    };

    const card = document.createElement('div');
    card.className = 'chat-consolidated-card signup-summary-card';
    card.innerHTML = `
        <div class="chat-card-header">
            <span class="chat-card-title">${title}</span>
            <span class="chat-card-badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="chat-card-body">
            <div class="chat-vote-row">
                <div class="chat-vote-target-col"><span class="chat-vote-target">🙋 ${isZh ? '竞选警长' : 'Running'}</span></div>
                <div class="chat-vote-voters-col">${renderGroup(candidates, isZh ? '无人竞选' : 'None', true)}</div>
            </div>
            <div class="chat-vote-row">
                <div class="chat-vote-target-col"><span class="chat-vote-target abstain">🪑 ${isZh ? '警下观众' : 'Voters'}</span></div>
                <div class="chat-vote-voters-col">${renderGroup(nonCandidates, isZh ? '无' : 'None', false)}</div>
            </div>
        </div>
    `;
    return card;
}

/**
 * Checks if a log entry is a special role operation or reveal that should render as a
 * high-visibility Spotlight Card so the human player never misses their action outcome.
 * @param {object} log - The log entry.
 * @returns {HTMLElement|null}
 */
function createRoleSpotlightCardIfApplicable(log) {
    if (!log) return null;
    const isZh = gameState.lang === 'zh';
    const type = log.type;
    const targetName = typeof log.target === 'object' ? log.target?.name : log.target;
    const sourceName = typeof log.source === 'object' ? log.source?.name : log.source;

    // 1. SEER CHECK RESULT (Crystal Ball Reveal Card)
    if (type === 'SEER_CHECK' && targetName) {
        const resultCamp = (log.data && log.data.result) || '';
        const isWolf = resultCamp === 'Werewolf' || resultCamp === 'Werewolves';
        gameState.seerChecks[targetName] = isWolf ? 'Werewolf' : 'Villager';
        if (gameState.players && gameState.players.length > 0) {
            updatePlayers(gameState.players);
        }

        const seatLabel = formatPlayerSeatLabel(targetName, isZh);
        const avatar = getAvatar(targetName);
        const campStamp = isWolf
            ? (isZh ? '🐺 狼人阵营 (坏人)' : '🐺 WEREWOLF CAMP')
            : (isZh ? '👱 好人阵营 (村民/神职)' : '👱 VILLAGER CAMP');
        const campClass = isWolf ? 'wolf-reveal' : 'good-reveal';

        const card = document.createElement('div');
        card.className = `role-spotlight-card seer-spotlight ${campClass}`;
        card.innerHTML = `
            <div class="spotlight-header">
                <span class="spotlight-icon">🔮</span>
                <span class="spotlight-title">${isZh ? '预言家查验结果' : 'Seer Vision Result'}</span>
                <span class="spotlight-private-tag">${isZh ? '仅你可见' : 'Private'}</span>
            </div>
            <div class="spotlight-body">
                <div class="spotlight-target-chip">
                    <span class="spotlight-avatar">${avatar}</span>
                    <span class="spotlight-seat">${seatLabel}</span>
                </div>
                <div class="spotlight-arrow">➔</div>
                <div class="spotlight-verdict ${isWolf ? 'verdict-wolf' : 'verdict-good'}">
                    ${campStamp}
                </div>
            </div>
        `;
        return card;
    }

    // 2. WITCH SAVE / POISON ACTION
    if (type === 'WITCH_ACTION') {
        const actionType = log.data?.action;
        const isSave = actionType === 'save';
        const seatLabel = targetName ? formatPlayerSeatLabel(targetName, isZh) : '';
        const avatar = targetName ? getAvatar(targetName) : '🧪';

        const card = document.createElement('div');
        card.className = `role-spotlight-card witch-spotlight ${isSave ? 'witch-save' : 'witch-poison'}`;
        card.innerHTML = `
            <div class="spotlight-header">
                <span class="spotlight-icon">${isSave ? '💖' : '🧪'}</span>
                <span class="spotlight-title">${isSave ? (isZh ? '女巫解药已使用' : 'Antidote Used') : (isZh ? '女巫毒药已使用' : 'Poison Used')}</span>
                <span class="spotlight-private-tag">${isZh ? '仅你可见' : 'Private'}</span>
            </div>
            <div class="spotlight-body">
                <div class="spotlight-target-chip">
                    <span class="spotlight-avatar">${avatar}</span>
                    <span class="spotlight-seat">${seatLabel}</span>
                </div>
                <div class="spotlight-arrow">➔</div>
                <div class="spotlight-verdict ${isSave ? 'verdict-good' : 'verdict-wolf'}">
                    ${isSave ? (isZh ? '✨ 成功救活' : '✨ Saved') : (isZh ? '☠️ 已毒杀' : '☠️ Poisoned')}
                </div>
            </div>
        `;
        return card;
    }

    // 3. GUARD PROTECTION ACTION
    if (type === 'GUARD_PROTECT' && targetName) {
        const seatLabel = formatPlayerSeatLabel(targetName, isZh);
        const avatar = getAvatar(targetName);
        const card = document.createElement('div');
        card.className = 'role-spotlight-card guard-spotlight';
        card.innerHTML = `
            <div class="spotlight-header">
                <span class="spotlight-icon">🛡️</span>
                <span class="spotlight-title">${isZh ? '守卫守护确认' : 'Guard Protection'}</span>
                <span class="spotlight-private-tag">${isZh ? '仅你可见' : 'Private'}</span>
            </div>
            <div class="spotlight-body">
                <div class="spotlight-target-chip">
                    <span class="spotlight-avatar">${avatar}</span>
                    <span class="spotlight-seat">${seatLabel}</span>
                </div>
                <div class="spotlight-arrow">➔</div>
                <div class="spotlight-verdict verdict-guard">
                    ${isZh ? '🛡️ 今晚受你守护' : '🛡️ Protected Tonight'}
                </div>
            </div>
        `;
        return card;
    }

    // 4. WEREWOLF KILL TARGET
    if (type === 'WEREWOLF_TARGET') {
        const seatLabel = targetName ? formatPlayerSeatLabel(targetName, isZh) : (isZh ? '空刀' : 'None');
        const avatar = targetName ? getAvatar(targetName) : '🌙';
        const card = document.createElement('div');
        card.className = 'role-spotlight-card wolf-spotlight';
        card.innerHTML = `
            <div class="spotlight-header">
                <span class="spotlight-icon">🐺</span>
                <span class="spotlight-title">${isZh ? '狼队袭击目标锁定' : 'Werewolf Pack Target'}</span>
                <span class="spotlight-private-tag">${isZh ? '狼队可见' : 'Werewolves'}</span>
            </div>
            <div class="spotlight-body">
                <div class="spotlight-target-chip">
                    <span class="spotlight-avatar">${avatar}</span>
                    <span class="spotlight-seat">${seatLabel}</span>
                </div>
                <div class="spotlight-arrow">➔</div>
                <div class="spotlight-verdict verdict-wolf">
                    ${targetName ? (isZh ? '🩸 今晚袭击目标' : '🩸 Targeted for Attack') : (isZh ? '⚪ 今晚放弃袭击' : '⚪ No Attack Tonight')}
                </div>
            </div>
        `;
        return card;
    }

    // 5. PUBLIC HUNTER / BLACK WEREWOLF KING SHOT
    if ((type === 'HUNTER_SHOOT' || type === 'BLACKWEREWOLFKING_SHOOT' || type === 'PLAYER_SHOOT') && sourceName && targetName) {
        const shooterLabel = formatPlayerSeatLabel(sourceName, isZh);
        const targetLabel = formatPlayerSeatLabel(targetName, isZh);
        const isWolfViewer = gameState.myRole === 'Werewolf' || gameState.myRole === 'Black Werewolf King';
        const isSelfShooter = sourceName === 'Player 1';
        const knowsShooterRole = (isWolfViewer || isSelfShooter) && type !== 'PLAYER_SHOOT';
        const isHunter = type === 'HUNTER_SHOOT';
        const spotlightIcon = !knowsShooterRole ? '🔫' : (isHunter ? '🔫' : '👹');
        const spotlightTitle = !knowsShooterRole
            ? (isZh ? '发动技能开枪带人！' : 'Gunshot Skill Triggered!')
            : (isHunter
                ? (isZh ? '猎人发动技能开枪！' : 'Hunter Fires!')
                : (isZh ? '黑狼王发动技能带人！' : 'Black Werewolf King Strikes!'));
        const card = document.createElement('div');
        card.className = 'role-spotlight-card gunshot-spotlight';
        card.innerHTML = `
            <div class="spotlight-header">
                <span class="spotlight-icon">${spotlightIcon}</span>
                <span class="spotlight-title">${spotlightTitle}</span>
                <span class="spotlight-public-tag">${isZh ? '全员公告' : 'Public'}</span>
            </div>
            <div class="spotlight-body">
                <div class="spotlight-target-chip">
                    <span class="spotlight-avatar">${getAvatar(sourceName)}</span>
                    <span class="spotlight-seat">${shooterLabel}</span>
                </div>
                <div class="spotlight-arrow">💥➔</div>
                <div class="spotlight-verdict verdict-wolf">
                    💀 ${getAvatar(targetName)} ${targetLabel} ${isZh ? '中枪出局' : 'Eliminated'}
                </div>
            </div>
        `;
        return card;
    }

    return null;
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

    if (isRedundantChatNoiseLog(log)) {
        return;
    }

    if (log.type === 'NIGHT_FALLS') {
        setPhase('Night', log.message);
        startNewChatPhaseSection('Night', log);
        return;
    } else if (log.type === 'DAY_BREAKS') {
        setPhase('Day', log.message);
        startNewChatPhaseSection('Day', log);
        return;
    }

    // 1. Consolidated Vote Result Card
    if (log.type === 'VOTE_RESULT' && log.data && log.data.votes) {
        const msgContainer = document.createElement('div');
        msgContainer.className = 'message-container system consolidated-container';
        msgContainer.appendChild(createConsolidatedVoteCard(log));
        appendToActiveChatSection(msgContainer);
        return;
    }

    // 2. Consolidated Sheriff Election Signup Card
    if (log.data && log.data.phase === 'Sheriff Signup') {
        const msgContainer = document.createElement('div');
        msgContainer.className = 'message-container system consolidated-container';
        msgContainer.appendChild(createSheriffSignupCard(log));
        appendToActiveChatSection(msgContainer);
        return;
    }

    // 3. High-Visibility Role Operation Result Spotlight Card
    const spotlightCard = createRoleSpotlightCardIfApplicable(log);
    if (spotlightCard) {
        const msgContainer = document.createElement('div');
        msgContainer.className = 'message-container system spotlight-container';
        msgContainer.appendChild(spotlightCard);
        appendToActiveChatSection(msgContainer);
        return;
    }

    const msgContainer = document.createElement('div');
    msgContainer.className = `message-container ${getLogClass(log)}`;
    
    let text = log.message;
    if (typeof text === 'object') {
        text = text[gameState.lang] || text['zh'] || text['en'] || JSON.stringify(text);
    }

    // Highlight Witch night victim prompt or initial role assignment as an emphasized system banner
    const isRoleNotice = log.type === 'ACTION' || (log.type === 'SYSTEM' && (
        text.includes('你被分配的角色是') ||
        text.includes('You have been assigned the role') ||
        text.includes('你的队友是') ||
        text.includes('Your teammates are')
    ));

    if (log.source && log.source.startsWith('Player') && (log.type === 'SPEECH' || log.type === 'WHISPER')) {
        msgContainer.dataset.speaker = log.source;
        const avatar = getAvatar(log.source);
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'chat-avatar';
        avatarDiv.innerText = avatar;
        avatarDiv.title = gameState.lang === 'zh' ? '点击高亮该玩家所有发言' : 'Click to highlight this player\'s speeches';
        avatarDiv.style.cursor = 'pointer';
        avatarDiv.onclick = () => toggleSpeakerFocus(log.source);
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'chat-content';

        const senderDiv = document.createElement('div');
        senderDiv.className = 'chat-sender';
        
        const playerNum = log.source.replace('Player ', '');
        const isMe = log.source === 'Player 1';
        const whisperTag = log.type === 'WHISPER' ? (gameState.lang === 'zh' ? ' 🐺[狼频]' : ' 🐺[Pack]') : '';
        if (gameState.lang === 'zh') {
            senderDiv.innerText = (isMe ? `${playerNum}号玩家 (我)` : `${playerNum}号玩家`) + whisperTag;
        } else {
            senderDiv.innerText = (isMe ? `Player ${playerNum} (Me)` : `Player ${playerNum}`) + whisperTag;
        }

        // Strip redundant leading "(Player X): " prefix from speech bubble text if present, and localize last words tag
        const isZh = gameState.lang === 'zh';
        const cleanSpeechText = text
            .replace(/^\(Player\s+\d+\):\s*/i, '')
            .replace(/^\(Player\s+\d+\s*的遗言\):\s*/i, isZh ? '【遗言】' : '[Last Words] ')
            .replace(/^\(Player\s+\d+'s last words\):\s*/i, isZh ? '【遗言】' : '[Last Words] ');

        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = `chat-bubble${log.type === 'WHISPER' ? ' whisper-bubble' : ''}`;
        bubbleDiv.innerHTML = formatSpeechWithSeatPills(cleanSpeechText);
        
        contentDiv.appendChild(senderDiv);
        contentDiv.appendChild(bubbleDiv);

        msgContainer.appendChild(avatarDiv);
        msgContainer.appendChild(contentDiv);

        showSpeechBubble(log.source, cleanSpeechText);
    } else {
        const isDebug = isDebugStateBoundaryLog(log);
        const debugActive = gameUI.chatBox && gameUI.chatBox.classList.contains('show-debug-logs');
        msgContainer.className = `message-container ${isDebug ? 'debug' : 'system'}${isDebug && debugActive ? ' visible' : ''}`;
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = `chat-bubble system${isRoleNotice ? ' role-notice-bubble' : ''}`;
        bubbleDiv.innerText = localizeMessageText(String(text || ''), gameState.lang === 'zh');
        msgContainer.appendChild(bubbleDiv);
    }
    
    appendToActiveChatSection(msgContainer);

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
    if (isDebugStateBoundaryLog(log)) return 'debug';
    const msgStr = typeof log.message === 'object' ? (log.message.zh || log.message.en || '') : String(log.message || '');
    if (msgStr.includes('---') || msgStr.includes('State')) return 'debug';
    if (['SYSTEM', 'GAME_START', 'NIGHT_FALLS', 'DAY_BREAKS'].includes(log.type)) return 'system';
    if (log.source === 'Player 1') return 'user';
    return 'ai';
}

/**
 * Updates the player display based on the latest data from the server.
 * Preserves existing DOM nodes across polls so active speech bubbles, thinking indicators,
 * and hover animations do not flicker or reset every second.
 * @param {Array<object>} playersData - A list of player objects.
 * @param {Set<string>} justDied - A set of player names who were eliminated in the last update.
 */
function updatePlayers(playersData, justDied = new Set()) {
    playersData.sort((a, b) => {
        const numA = parseInt(a.name.replace('Player ', ''));
        const numB = parseInt(b.name.replace('Player ', ''));
        return numA - numB;
    });

    const totalPlayers = playersData.length;
    const alivePlayers = playersData.filter(p => p.is_alive).length;
    const aliveCounterEl = document.getElementById('alive-counter-pill');
    if (aliveCounterEl && totalPlayers > 0) {
        const label = gameState.lang === 'zh' ? '存活' : 'Alive';
        aliveCounterEl.innerText = `👥 ${label} ${alivePlayers} / ${totalPlayers}`;
    }

    const midPoint = Math.ceil(totalPlayers / 2);
    const existingCards = document.querySelectorAll('.player-card');
    const needsRebuild = existingCards.length !== totalPlayers;

    if (needsRebuild) {
        if (gameUI.playersLeft) gameUI.playersLeft.innerHTML = '';
        if (gameUI.playersRight) gameUI.playersRight.innerHTML = '';
    }

    const statusTexts = I18N[gameState.lang]?.statusLabels || {
        me: "ME",
        sheriff: "SHERIFF",
        candidate: "CANDIDATE",
        tie: "TIE PK",
        dead: "DEAD"
    };

    playersData.forEach((p, index) => {
        let card = !needsRebuild
            ? Array.from(existingCards).find(c => c.dataset.name === p.name)
            : null;

        if (!card) {
            const template = document.getElementById('player-card-template');
            const clone = template.content.cloneNode(true);
            card = clone.querySelector('.player-card');
            card.dataset.name = p.name;
            card.onclick = () => handlePlayerClick(p.name);

            if (gameUI.playersLeft && gameUI.playersRight) {
                if (index < midPoint) {
                    gameUI.playersLeft.appendChild(card);
                } else {
                    gameUI.playersRight.appendChild(card);
                }
            }
        }

        const avatarEl = card.querySelector('.player-avatar');
        const expectedAvatar = p.name === 'Player 1' ? gameState.myAvatar : getAvatar(p.name);
        if (avatarEl && avatarEl.innerText !== expectedAvatar) {
            avatarEl.innerText = expectedAvatar;
        }

        const deadLabel = card.querySelector('.player-dead-label');
        if (deadLabel) {
            deadLabel.innerText = statusTexts.dead;
        }

        if (!p.is_alive) {
            if (!justDied.has(p.name)) {
                card.classList.add('dead');
            }
        } else {
            card.classList.remove('dead');
        }

        const isSheriffAlive = Boolean(p.is_sheriff && p.is_alive);
        const hideOtherCandidates = isUserDecidingBlindAction() && p.name !== 'Player 1';
        const isCandidateActive = Boolean(p.is_sheriff_candidate && !hideOtherCandidates);

        if (p.name === 'Player 1') {
            card.classList.add('me');
            card.querySelector('.player-name').innerText = "1";
            const meLabel = card.querySelector('.player-me-label');
            if (meLabel) {
                meLabel.style.display = 'block';
                if (isSheriffAlive) {
                    meLabel.innerText = `${statusTexts.me} · 👮 ${statusTexts.sheriff}`;
                } else if (isCandidateActive) {
                    meLabel.innerText = `${statusTexts.me} · 🎙️`;
                } else if (p.is_tie) {
                    meLabel.innerText = `${statusTexts.me} · ⚔️`;
                } else {
                    meLabel.innerText = statusTexts.me;
                }
            }

            card.classList.toggle('sheriff', isSheriffAlive);
            card.classList.toggle('sheriff-candidate', isCandidateActive);
            card.classList.toggle('tie', Boolean(p.is_tie));
        } else {
            const num = p.name.replace('Player ', '');
            card.querySelector('.player-name').innerText = num;

            const tieLabel = card.querySelector('.player-tie-label');
            if (p.is_tie) {
                card.classList.add('tie');
                if (tieLabel) {
                    tieLabel.innerText = `⚔️ ${statusTexts.tie}`;
                    tieLabel.style.display = 'block';
                }
            } else {
                card.classList.remove('tie');
                if (tieLabel) {
                    tieLabel.style.display = 'none';
                }
            }

            const sheriffLabel = card.querySelector('.player-sheriff-label');
            if (isSheriffAlive) {
                card.classList.add('sheriff');
                if (sheriffLabel) {
                    sheriffLabel.innerText = `👮 ${statusTexts.sheriff}`;
                    sheriffLabel.style.display = 'block';
                }
            } else {
                card.classList.remove('sheriff');
                if (sheriffLabel) {
                    sheriffLabel.style.display = 'none';
                }
            }

            const candidateLabel = card.querySelector('.player-candidate-label');
            if (isCandidateActive) {
                card.classList.add('sheriff-candidate');
                if (candidateLabel) {
                    candidateLabel.innerText = `🎙️ ${statusTexts.candidate}`;
                    candidateLabel.style.display = 'block';
                }
            } else {
                card.classList.remove('sheriff-candidate');
                if (candidateLabel) {
                    candidateLabel.style.display = 'none';
                }
            }
        }

        const statusIcons = card.querySelector('.player-status-icons');
        if (statusIcons) {
            if (isSheriffAlive) {
                statusIcons.innerText = '⭐';
                statusIcons.title = statusTexts.sheriff;
            } else {
                statusIcons.innerText = '';
            }
        }

        // Private Seer Checked Badge on sidebar card
        const seerBadge = card.querySelector('.player-seer-badge');
        if (seerBadge) {
            const seerCheckResult = gameState.seerChecks && gameState.seerChecks[p.name];
            if (seerCheckResult) {
                const isWolf = seerCheckResult === 'Werewolf' || seerCheckResult === 'Werewolves';
                const isZh = gameState.lang === 'zh';
                seerBadge.style.display = 'inline-flex';
                seerBadge.className = `player-seer-badge ${isWolf ? 'seer-wolf' : 'seer-good'}`;
                seerBadge.innerText = isWolf ? (isZh ? '🔮狼' : '🔮W') : (isZh ? '🔮好' : '🔮G');
                seerBadge.title = isWolf
                    ? (isZh ? '预言家查验：狼人阵营' : 'Seer Checked: Werewolf')
                    : (isZh ? '预言家查验：好人阵营' : 'Seer Checked: Good');
            } else {
                seerBadge.style.display = 'none';
                seerBadge.innerText = '';
            }
        }
    });

    if (gameState.pendingAction && (gameState.pendingAction.type === 'vote' || gameState.pendingAction.type === 'choice')) {
        const validTargets = (gameState.pendingAction.options || []).filter(opt => typeof opt === 'string' && opt.startsWith('Player '));
        updatePlayerSelectableState(validTargets);
    }
}

/** List of all targeting classes to cleanly add and remove. */
const ALL_TARGET_CLASSES = [
    'selectable-target',
    'non-target',
    'target-werewolf',
    'target-witch',
    'target-witch-poison',
    'target-witch-save',
    'target-seer',
    'target-guard',
    'target-hunter',
    'target-vote',
    'target-sheriff',
    'target-default'
];

/**
 * Determines the role or action targeting class based on current pending action.
 * @returns {string} The CSS class for targeting e.g. 'target-werewolf', 'target-witch-poison', etc.
 */
function getTargetContextClass() {
    if (!gameState.pendingAction) return 'target-default';
    const req = gameState.pendingAction;
    const promptStr = typeof req.prompt === 'object'
        ? JSON.stringify(req.prompt).toLowerCase()
        : String(req.prompt || '').toLowerCase();

    // Check sheriff election or badge handoff
    if (promptStr.includes('sheriff') || promptStr.includes('警长') || promptStr.includes('badge') || promptStr.includes('警徽')) {
        return 'target-sheriff';
    }

    // Check day votes
    if (req.type === 'vote') {
        return 'target-vote';
    }

    // Role-specific night/death choices
    const role = gameState.myRole;
    if (role === 'Werewolf' || role === 'Black Werewolf King') {
        return 'target-werewolf';
    } else if (role === 'Witch') {
        if (promptStr.includes('save') || promptStr.includes('救') || promptStr.includes('解药')) {
            return 'target-witch-save';
        }
        return 'target-witch-poison';
    } else if (role === 'Seer') {
        return 'target-seer';
    } else if (role === 'Guard') {
        return 'target-guard';
    } else if (role === 'Hunter') {
        return 'target-hunter';
    }

    return 'target-default';
}

/**
 * Updates player card visuals to indicate which players can be targeted.
 * Avoids stripping/re-adding identical classes so sticker entrance animations don't replay on every poll tick.
 * @param {Array<string>} targetPlayerNames - Array of selectable player names e.g. ['Player 2', 'Player 3']
 */
function updatePlayerSelectableState(targetPlayerNames = []) {
    const cards = document.querySelectorAll('.player-card');
    const targetClass = getTargetContextClass();

    cards.forEach(card => {
        const name = card.dataset.name;

        if (targetPlayerNames.length === 0) {
            ALL_TARGET_CLASSES.forEach(cls => card.classList.remove(cls));
        } else if (targetPlayerNames.includes(name)) {
            if (!card.classList.contains('selectable-target') || !card.classList.contains(targetClass)) {
                ALL_TARGET_CLASSES.forEach(cls => card.classList.remove(cls));
                card.classList.add('selectable-target', targetClass);
            }
        } else {
            if (!card.classList.contains('non-target')) {
                ALL_TARGET_CLASSES.forEach(cls => card.classList.remove(cls));
                card.classList.add('non-target');
            }
        }
    });
}

/** @type {number|null} - The timer ID for the turn countdown. */
let turnTimerInterval = null;
const TURN_TIMEOUT_SECONDS = 120; // 2 minutes default fallback
let turnSecondsRemaining = TURN_TIMEOUT_SECONDS;
let currentTurnRequestId = null;

/**
 * Starts a countdown timer for the player's pending turn.
 * @param {Function} onTimeout - Callback invoked when the countdown expires.
 * @param {number} totalSeconds - Total seconds for the countdown.
 */
function startTurnTimer(onTimeout, totalSeconds = selectedTurnTimeoutSeconds) {
    stopTurnTimer();
    if (!totalSeconds || !Number.isFinite(totalSeconds) || totalSeconds <= 0) {
        return;
    }
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
        flushPendingVoteLogs();
        if (gameState.players && gameState.players.length > 0) {
            updatePlayers(gameState.players);
        }
        stopTurnTimer();
        gameUI.input.disabled = true;
        gameUI.sendBtn.disabled = true;
        if (gameUI.voiceInputBtn) gameUI.voiceInputBtn.disabled = true;
        gameUI.choiceButtons.innerHTML = '';
        gameUI.actionPrompt.innerText = I18N[gameState.lang].waiting;
        updatePlayerSelectableState([]);
        return;
    }

    if (req.type !== 'vote' && !isUserDecidingBlindAction()) {
        flushPendingVoteLogs();
        if (gameState.players && gameState.players.length > 0) {
            updatePlayers(gameState.players);
        }
    }

    // Generate stable request ID to avoid resetting countdown on every polling tick
    const reqId = req.id || `${req.type}_${typeof req.prompt === 'object' ? JSON.stringify(req.prompt) : req.prompt}_${JSON.stringify(req.options)}`;
    
    // Keep pendingAction updated
    gameState.pendingAction = req;

    let promptText = req.prompt;
    if (typeof promptText === 'object') {
        promptText = promptText[gameState.lang] || promptText['zh'] || promptText['en'] || JSON.stringify(promptText);
    }
    gameUI.actionPrompt.innerText = localizeMessageText(String(promptText || ''), gameState.lang === 'zh');

    // If this exact request is already active, don't restart the countdown
    if (reqId === currentTurnRequestId) {
        return;
    }
    currentTurnRequestId = reqId;

    const timeoutSeconds = (req.timeout && Number.isFinite(req.timeout) && req.timeout > 0) ? Math.round(req.timeout) : null;

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

    const isZh = gameState.lang === 'zh';
    const choiceTranslations = {
        "Yes": isZh ? "是" : "Yes",
        "No": isZh ? "否" : "No",
        "Clockwise": isZh ? "顺时针" : "Clockwise",
        "Counter-clockwise": isZh ? "逆时针" : "Counter-clockwise",
        "Abstain": isZh ? "不行动 / 弃票" : "No Action / Abstain"
    };

    options.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'choice-btn';
        
        if (typeof opt === 'string' && opt.startsWith('Player ')) {
            const avatar = getAvatar(opt);
            const playerNum = opt.replace('Player ', '');
            btn.innerHTML = `<span class="btn-avatar">${avatar}</span> ${isZh ? `${playerNum}号` : playerNum}`;
        } else if (choiceTranslations[opt]) {
            btn.innerText = choiceTranslations[opt];
        } else {
            btn.innerText = opt;
        }
        
        btn.onclick = () => sendAction(opt);
        gameUI.choiceButtons.appendChild(btn);
    });
    
    // Only add the extra "No Action / Abstain" button when options are player targets (not Yes/No or Clockwise/Counter-clockwise)
    const isBinaryChoice = options.includes('Yes') || options.includes('Clockwise');
    if (addNoAction && !isBinaryChoice) {
        const btn = document.createElement('button');
        btn.className = 'choice-btn no-action';
        btn.innerText = isZh ? "不行动 / 弃票" : "No Action / Abstain";
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
            return;
        }
    }
    // When not actively targeting a choice, clicking a player card toggles highlighting their speeches in chat
    toggleSpeakerFocus(playerName);
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

    gameState.pendingAction = null;
    flushPendingVoteLogs();
    if (gameState.players && gameState.players.length > 0) {
        updatePlayers(gameState.players);
    }
    stopTurnTimer();
    gameState.isSending = true;
    gameUI.sendBtn.disabled = true;
    gameUI.input.disabled = true;
    
    document.querySelectorAll('.choice-btn').forEach(btn => btn.disabled = true);
    updatePlayerSelectableState([]);

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
 * Traps focus within a given element without accumulating duplicate listeners.
 * @param {HTMLElement} element - The element to trap focus within.
 */
function trapFocus(element) {
    if (!element) return;
    if (element._focusTrapHandler) {
        element.removeEventListener('keydown', element._focusTrapHandler);
    }

    const KEYCODE_TAB = 9;
    element._focusTrapHandler = function(e) {
        const isTabPressed = (e.key === 'Tab' || e.keyCode === KEYCODE_TAB);
        if (!isTabPressed) {
            return;
        }

        const focusableEls = element.querySelectorAll('a[href]:not([disabled]), button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])');
        if (focusableEls.length === 0) return;
        const firstFocusableEl = focusableEls[0];
        const lastFocusableEl = focusableEls[focusableEls.length - 1];

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
    };

    element.addEventListener('keydown', element._focusTrapHandler);
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
        gameUI.chatBox.scrollTo({
            top: gameUI.chatBox.scrollHeight,
            behavior: gameState.pacingMultiplier === 0 ? 'auto' : 'smooth'
        });
        gameState.unreadCount = 0;
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
        gameState.unreadCount = 0;
        hideNewMessagesIndicator();
    }
}

/**
 * Shows the "new messages" indicator.
 */
function showNewMessagesIndicator() {
    if (gameUI.newMessagesIndicator) {
        const baseText = I18N[gameState.lang]?.newMessages || '⬇️ 新消息';
        const count = gameState.unreadCount || 0;
        gameUI.newMessagesIndicator.innerText = count > 0 ? `${baseText} (${count})` : baseText;
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
 * Triggers a celestial clockwise orbit transition between Day and Night (Zero-blocking).
 * @param {boolean} targetIsNight - Whether transitioning into night.
 * @param {Function} onSwapped - Callback invoked at mid-transition while sky shifts.
 */
let isStageTransitioning = false;

function playStageCurtainTransition(targetIsNight, onSwapped) {
    const sunEl = document.getElementById('celestial-sun');
    const moonEl = document.getElementById('celestial-moon');
    const banner = document.getElementById('celestial-banner');

    if (!sunEl || !moonEl || isStageTransitioning) {
        if (onSwapped) onSwapped();
        return;
    }

    isStageTransitioning = true;
    const isZh = gameState.lang === 'zh';

    if (targetIsNight) {
        // Day -> Night Clockwise:
        // Position sun at zenith silently, then animate sun setting & moon rising
        sunEl.className = 'celestial-orb celestial-sun pos-zenith no-transition';
        moonEl.className = 'celestial-orb celestial-moon pos-left no-transition';
        void sunEl.offsetWidth;
        sunEl.classList.remove('no-transition');
        moonEl.classList.remove('no-transition');

        requestAnimationFrame(() => {
            sunEl.className = 'celestial-orb celestial-sun pos-right';
            moonEl.className = 'celestial-orb celestial-moon pos-zenith';
        });

        if (banner) {
            banner.innerText = isZh ? '🌙 太阳西沉 · 天黑请闭眼' : '🌙 Night Falls · Close Your Eyes';
            banner.classList.add('visible');
        }

        // Halfway through the 2.2s orbit (850ms), crossfade day/night background & BGM
        setTimeout(() => {
            if (onSwapped) onSwapped();
        }, 850);

        // When transition completes (2250ms), fade out orbs and silently relocate
        setTimeout(() => {
            sunEl.classList.add('fade-out');
            moonEl.classList.add('fade-out');

            setTimeout(() => {
                sunEl.classList.add('no-transition');
                moonEl.classList.add('no-transition');
                sunEl.className = 'celestial-orb celestial-sun pos-left no-transition';
                moonEl.className = 'celestial-orb celestial-moon pos-left no-transition';
                void sunEl.offsetWidth; // force reflow
                sunEl.classList.remove('no-transition', 'fade-out');
                moonEl.classList.remove('no-transition', 'fade-out');

                if (banner) banner.classList.remove('visible');
                isStageTransitioning = false;
            }, 500);
        }, 2250);
    } else {
        // Night -> Day Clockwise:
        // Position moon at zenith silently, then animate moon setting & sun rising
        moonEl.className = 'celestial-orb celestial-moon pos-zenith no-transition';
        sunEl.className = 'celestial-orb celestial-sun pos-left no-transition';
        void moonEl.offsetWidth;
        moonEl.classList.remove('no-transition');
        sunEl.classList.remove('no-transition');

        requestAnimationFrame(() => {
            moonEl.className = 'celestial-orb celestial-moon pos-right';
            sunEl.className = 'celestial-orb celestial-sun pos-zenith';
        });

        if (banner) {
            banner.innerText = isZh ? '☀️ 晨曦破晓 · 天亮请睁眼' : '☀️ Dawn Breaks · Open Your Eyes';
            banner.classList.add('visible');
        }

        // Halfway through the 2.2s orbit (850ms), crossfade day/night background & BGM
        setTimeout(() => {
            if (onSwapped) onSwapped();
        }, 850);

        // When transition completes (2250ms), fade out orbs and silently relocate
        setTimeout(() => {
            sunEl.classList.add('fade-out');
            moonEl.classList.add('fade-out');

            setTimeout(() => {
                sunEl.classList.add('no-transition');
                moonEl.classList.add('no-transition');
                sunEl.className = 'celestial-orb celestial-sun pos-left no-transition';
                moonEl.className = 'celestial-orb celestial-moon pos-left no-transition';
                void moonEl.offsetWidth; // force reflow
                sunEl.classList.remove('no-transition', 'fade-out');
                moonEl.classList.remove('no-transition', 'fade-out');

                if (banner) banner.classList.remove('visible');
                isStageTransitioning = false;
            }, 500);
        }, 2250);
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
    
    const targetIsNight = phase.toLowerCase().includes('night') || (gameState.phase && (gameState.phase.toLowerCase().includes('night') || gameState.phase.includes('夜')));
    const wasNight = document.body.classList.contains('night-mode');
    const isGameActive = screens.game && screens.game.classList.contains('active');

    if (wasNight !== Boolean(targetIsNight) && isGameActive) {
        playStageCurtainTransition(targetIsNight, () => {
            if (targetIsNight) {
                document.body.classList.add('night-mode');
            } else {
                document.body.classList.remove('night-mode');
            }
            if (typeof BGMManager !== 'undefined') {
                BGMManager.setTrack(targetIsNight ? 'night' : 'day');
            }
        });
    } else {
        if (targetIsNight) {
            document.body.classList.add('night-mode');
        } else {
            document.body.classList.remove('night-mode');
        }
        if (!isStageTransitioning) {
            const sunEl = document.getElementById('celestial-sun');
            const moonEl = document.getElementById('celestial-moon');
            if (sunEl && moonEl) {
                sunEl.className = 'celestial-orb celestial-sun pos-left no-transition';
                moonEl.className = 'celestial-orb celestial-moon pos-left no-transition';
            }
        }
        if (typeof BGMManager !== 'undefined') {
            BGMManager.setTrack(targetIsNight ? 'night' : 'day');
        }
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
        bubble.innerText = text.length > 22 ? text.substring(0, 19) + '...' : text;
        bubble.classList.add('visible');
        card.classList.add('speaking');

        if (card._speechTimeout) {
            clearTimeout(card._speechTimeout);
        }
        card._speechTimeout = setTimeout(() => {
            bubble.classList.remove('visible');
            card.classList.remove('speaking');
            card._speechTimeout = null;
        }, 4000);
    }
}

async function showOperationsHistory() {
    loadOperationsHistory('op-history-content');
}

// State for the Unified Timeline
let timelineState = {
    operations: null,
    records: null,
    filter: 'all' // 'all', 'actions', 'votes'
};

function setupRecordsModalListeners() {
    const recordsBtn = document.getElementById('records-btn');
    const recordsModal = document.getElementById('records-modal');
    const closeRecordsBtn = document.getElementById('close-records-btn');
    const filterAllBtn = document.getElementById('filter-all-btn');
    const filterActionsBtn = document.getElementById('filter-actions-btn');
    const filterVotesBtn = document.getElementById('filter-votes-btn');

    if (recordsBtn && recordsModal) {
        recordsBtn.addEventListener('click', () => {
            recordsModal.classList.add('active');
            loadUnifiedTimeline();
        });
    }

    if (closeRecordsBtn && recordsModal) {
        closeRecordsBtn.addEventListener('click', () => {
            recordsModal.classList.remove('active');
        });
    }

    if (recordsModal) {
        recordsModal.addEventListener('click', (e) => {
            if (e.target === recordsModal) {
                recordsModal.classList.remove('active');
            }
        });
    }

    const filterBtns = [
        { btn: filterAllBtn, filter: 'all' },
        { btn: filterActionsBtn, filter: 'actions' },
        { btn: filterVotesBtn, filter: 'votes' }
    ];

    filterBtns.forEach(({ btn, filter }) => {
        if (!btn) return;
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.btn && b.btn.classList.remove('active'));
            btn.classList.add('active');
            timelineState.filter = filter;
            renderCurrentTimeline();
        });
    });
}

async function loadUnifiedTimeline() {
    const container = document.getElementById('records-timeline-content');
    const identityCard = document.getElementById('records-identity-card');
    const isZh = gameState.lang === 'zh';
    if (!container) return;

    container.innerHTML = `<p class="op-history-loading">${isZh ? '正在加载对局时间线...' : 'Loading game timeline...'}</p>`;

    if (!gameState.gameId) {
        if (identityCard) identityCard.innerHTML = `<div style="color:#888;">${isZh ? '对局尚未开始' : 'Game not started'}</div>`;
        container.innerHTML = `<div class="op-empty-card"><p>${isZh ? '暂无对局记录' : 'No game records yet.'}</p></div>`;
        return;
    }

    try {
        const [opRes, recRes] = await Promise.all([
            fetch(`/api/game/${gameState.gameId}/player/Player 1/operations`),
            fetch(`/api/game/${gameState.gameId}/records`)
        ]);

        const opData = opRes.ok ? await opRes.json() : null;
        const recData = recRes.ok ? await recRes.json() : null;

        timelineState.operations = opData;
        timelineState.records = recData;

        renderIdentityCard(opData);
        renderCurrentTimeline();
    } catch (err) {
        console.error('Error loading timeline data:', err);
        container.innerHTML = `<div class="op-empty-card"><p>${isZh ? '网络错误，请稍后重试' : 'Network error. Please try again.'}</p></div>`;
    }
}

function renderIdentityCard(opData) {
    const card = document.getElementById('records-identity-card');
    if (!card) return;
    const isZh = gameState.lang === 'zh';

    if (!opData || !opData.role) {
        card.innerHTML = `<div style="color:#888;">${isZh ? '暂无角色信息' : 'No role info'}</div>`;
        return;
    }

    const roleName = opData.role;
    const roleConfig = ROLES.find(r => r.id === roleName) || { icon: '👱‍♀️' };
    const localizedRole = I18N[gameState.lang].roles[roleName] || roleName;

    let roleHtml = `
        <div class="id-role-row">
            <span>${isZh ? '你的身份' : 'Your Role'}: <span class="op-role-pill">${roleConfig.icon} ${localizedRole}</span></span>
        </div>
    `;

    let alliesHtml = '';
    if (opData.teammates && (opData.teammates.length > 0 || opData.king)) {
        alliesHtml = `<div class="id-allies-row"><span>🐺 ${isZh ? '狼队阵容' : 'Werewolf Pack'}:</span>`;
        if (opData.teammates.length > 0) {
            opData.teammates.forEach(tm => {
                alliesHtml += `<span class="op-badge teammate">${getAvatar(tm)} ${formatPlayerSeatLabel(tm, isZh)}</span>`;
            });
        }
        if (opData.king) {
            alliesHtml += `<span class="op-badge teammate" style="background:#ffd200;">👑 ${isZh ? '狼王' : 'King'}: ${formatPlayerSeatLabel(opData.king, isZh)}</span>`;
        }
        alliesHtml += `</div>`;
    } else if (roleName === 'Seer') {
        alliesHtml = `<div class="id-allies-row" style="color:#666;">🔮 ${isZh ? '每晚可查验一名玩家真实阵营' : 'Check one player\'s camp each night'}</div>`;
    } else if (roleName === 'Witch') {
        alliesHtml = `<div class="id-allies-row" style="color:#666;">🧙‍♀️ ${isZh ? '拥有一瓶解药与一瓶毒药，同夜只能使用一种' : 'Has one save potion and one poison potion'}</div>`;
    } else if (roleName === 'Guard') {
        alliesHtml = `<div class="id-allies-row" style="color:#666;">🛡️ ${isZh ? '每晚可守护一人免受袭击，不可连守' : 'Protect one player each night (no consecutive)'}</div>`;
    } else if (roleName === 'Hunter') {
        alliesHtml = `<div class="id-allies-row" style="color:#666;">🔫 ${isZh ? '出局时可开枪带走场上一名玩家（被毒死除外）' : 'Shoot another player upon death (except by poison)'}</div>`;
    }

    card.innerHTML = roleHtml + alliesHtml;
}

function renderCurrentTimeline() {
    const container = document.getElementById('records-timeline-content');
    if (!container) return;
    const isZh = gameState.lang === 'zh';
    const filter = timelineState.filter || 'all';

    const opData = timelineState.operations || {};
    const recData = timelineState.records || {};
    const votes = recData.votes || [];
    const deaths = recData.deaths || [];

    // Calculate all rounds that exist
    const roundsSet = new Set();
    if (opData.kills) opData.kills.forEach(k => roundsSet.add(k.night));
    if (opData.checked) opData.checked.forEach(c => roundsSet.add(c.night));
    if (opData.saved_details) opData.saved_details.forEach(s => roundsSet.add(s.night));
    if (opData.poisoned_details) opData.poisoned_details.forEach(p => roundsSet.add(p.night));
    if (opData.protected_details) opData.protected_details.forEach(p => roundsSet.add(p.night));
    if (opData.shot_details) opData.shot_details.forEach(s => roundsSet.add(s.day));
    if (opData.public_shots) opData.public_shots.forEach(s => roundsSet.add(s.day));
    votes.forEach(v => roundsSet.add(v.day));
    deaths.forEach(d => roundsSet.add(d.day));

    // Fallback: at least round 1
    if (roundsSet.size === 0) roundsSet.add(1);

    const sortedRounds = Array.from(roundsSet).sort((a, b) => a - b);
    let html = '';

    sortedRounds.forEach(roundNum => {
        let roundHasContent = false;
        let roundHtml = `<div class="timeline-round-divider">${isZh ? `第 ${roundNum} 轮对局` : `Round ${roundNum}`}</div>`;

        // 1. NIGHT NODE (🌙)
        if (filter === 'all' || filter === 'actions') {
            let nightActionsHtml = '';

            // Werewolf Kills
            if (opData.kills) {
                const kill = opData.kills.find(k => k.night === roundNum);
                if (kill) {
                    const targetStr = kill.target 
                        ? `<strong>${getAvatar(kill.target)} ${formatPlayerSeatLabel(kill.target, isZh)}</strong>` 
                        : (isZh ? '空刀 (未袭击任何人)' : 'No target');
                    nightActionsHtml += `
                        <div class="timeline-card action-card">
                            <span>🩸 ${isZh ? '狼人袭击' : 'Night Attack'}: ${targetStr}</span>
                        </div>
                    `;
                }
            }

            // Seer Checks
            if (opData.checked) {
                const check = opData.checked.find(c => c.night === roundNum);
                if (check) {
                    const isWerewolf = check.camp === 'Werewolves';
                    const campLabel = isWerewolf ? (isZh ? '狼人阵营 🐺' : 'Werewolf 🐺') : (isZh ? '好人阵营 👱' : 'Good 👱');
                    nightActionsHtml += `
                        <div class="timeline-card action-card">
                            <span>🔮 ${isZh ? '查验身份' : 'Checked'}: <strong>${getAvatar(check.player)} ${formatPlayerSeatLabel(check.player, isZh)}</strong> ➔ <span class="op-camp-tag ${isWerewolf ? 'werewolf' : 'good'}">${campLabel}</span></span>
                        </div>
                    `;
                }
            }

            // Witch Saves & Poisons
            if (opData.saved_details) {
                const save = opData.saved_details.find(s => s.night === roundNum);
                if (save) {
                    const targetLabel = formatPlayerSeatLabel(save.target, isZh);
                    nightActionsHtml += `
                        <div class="timeline-card action-card">
                            <span>💚 ${isZh ? `女巫解药: 救活了 <strong>${getAvatar(save.target)} ${targetLabel}</strong>` : `Witch Save: Rescued <strong>${getAvatar(save.target)} ${targetLabel}</strong>`}</span>
                        </div>
                    `;
                }
            }
            if (opData.poisoned_details) {
                const poison = opData.poisoned_details.find(p => p.night === roundNum);
                if (poison) {
                    const targetLabel = formatPlayerSeatLabel(poison.target, isZh);
                    nightActionsHtml += `
                        <div class="timeline-card action-card">
                            <span>💜 ${isZh ? `女巫毒药: 毒杀了 <strong>${getAvatar(poison.target)} ${targetLabel}</strong>` : `Witch Poison: Eliminated <strong>${getAvatar(poison.target)} ${targetLabel}</strong>`}</span>
                        </div>
                    `;
                }
            }

            // Guard Protections
            if (opData.protected_details) {
                const protect = opData.protected_details.find(p => p.night === roundNum);
                if (protect) {
                    const targetLabel = formatPlayerSeatLabel(protect.target, isZh);
                    nightActionsHtml += `
                        <div class="timeline-card action-card">
                            <span>🛡️ ${isZh ? `守卫守护: 守护了 <strong>${getAvatar(protect.target)} ${targetLabel}</strong>` : `Protected: Guarded <strong>${getAvatar(protect.target)} ${targetLabel}</strong>`}</span>
                        </div>
                    `;
                }
            }

            // If player had no actions this night
            if (!nightActionsHtml && filter === 'actions') {
                // Don't show empty night if filtering purely by actions
            } else {
                if (!nightActionsHtml) {
                    nightActionsHtml = `<div class="timeline-card" style="background:#f8fafc; color:#888;">😴 ${isZh ? '平安闭眼，无特殊夜间操作' : 'Sleeping peacefully with no actions'}</div>`;
                }

                roundHtml += `
                    <div class="timeline-node night-node">
                        <div class="timeline-node-icon">🌙</div>
                        <div class="timeline-node-title">${isZh ? `第 ${roundNum} 夜` : `Night ${roundNum}`}</div>
                        ${nightActionsHtml}
                    </div>
                `;
                roundHasContent = true;
            }
        }

        // 2. DAY NODE (☀️)
        let dayContentHtml = '';

        // Dawn Casualties (only in 'all' view)
        if (filter === 'all') {
            const nightDeaths = deaths.filter(d => d.day === roundNum && d.phase === 'night');
            if (nightDeaths.length > 0) {
                const deathNames = nightDeaths.map(d => `<strong>${getAvatar(d.player)} ${formatPlayerSeatLabel(d.player, isZh)}</strong>`).join(', ');
                dayContentHtml += `
                    <div class="timeline-card dawn-card">
                        <span>💀 ${isZh ? '昨夜出局' : 'Night Casualties'}: ${deathNames}</span>
                    </div>
                `;
            } else {
                dayContentHtml += `
                    <div class="timeline-card dawn-card" style="background:#f0fdf4; border-color:#bbf7d0;">
                        <span>🕊️ ${isZh ? '昨夜平安夜，无人死亡' : 'Peaceful night, no casualties'}</span>
                    </div>
                `;
            }
        }

        // Votes on this day (in 'all' or 'votes' view)
        if (filter === 'all' || filter === 'votes') {
            const dayVotes = votes.filter(v => v.day === roundNum);
            dayVotes.forEach(voteEntry => {
                let phaseLabel = voteEntry.phase;
                if (voteEntry.phase === 'Sheriff Election') phaseLabel = isZh ? '警长竞选' : 'Sheriff Election';
                else if (voteEntry.phase === 'Execution Vote') phaseLabel = isZh ? '放逐投票' : 'Execution Vote';
                else if (voteEntry.phase === 'Tie Breaker') phaseLabel = isZh ? '平票PK' : 'Tie Breaker';

                let resultLabel = '';
                if (!voteEntry.result || voteEntry.result === 'None') {
                    resultLabel = isZh ? '无人当选 / 无人出局' : 'No outcome';
                } else if (voteEntry.result === 'Tie') {
                    resultLabel = isZh ? '平票进入PK' : 'Tie vote';
                } else {
                    const formattedWinner = formatPlayerSeatLabel(voteEntry.result, isZh);
                    resultLabel = isZh ? `结果: ${formattedWinner}` : `Result: ${formattedWinner}`;
                }

                // Group voters by target
                const targetMap = {};
                if (voteEntry.votes) {
                    for (const [voter, target] of Object.entries(voteEntry.votes)) {
                        const tName = target || (isZh ? '弃票' : 'Abstained');
                        if (!targetMap[tName]) targetMap[tName] = [];
                        targetMap[tName].push(voter);
                    }
                }

                let targetRowsHtml = '';
                const targets = Object.keys(targetMap);
                if (targets.length === 0) {
                    targetRowsHtml = `<div style="color:#94a3b8; font-size:0.85rem;">${isZh ? '无人投票' : 'No votes'}</div>`;
                } else {
                    targets.forEach(tName => {
                        const isAbstain = tName === 'Abstained' || tName === '弃票';
                        const voters = targetMap[tName];
                        const targetBadge = isAbstain
                            ? `<span style="color:#64748b;">⚪ ${isZh ? '弃票' : 'Abstained'} (${voters.length})</span>`
                            : `<span>🎯 ${getAvatar(tName)} ${formatPlayerSeatLabel(tName, isZh)} (${voters.length})</span>`;

                        let votersPills = voters.map(voter => {
                            const isSheriffVoter = voteEntry.sheriff && voteEntry.sheriff === voter && voteEntry.phase !== 'Sheriff Election';
                            const vLabel = formatPlayerSeatLabel(voter, isZh);
                            return isSheriffVoter
                                ? `<span class="voter-pill sheriff-voter">${getAvatar(voter)} ${vLabel} 👮(1.5)</span>`
                                : `<span class="voter-pill">${getAvatar(voter)} ${vLabel}</span>`;
                        }).join('');

                        targetRowsHtml += `
                            <div class="vote-target-row">
                                <div class="vote-target-side">${targetBadge}</div>
                                <span class="vote-arrow-indicator">⟵ ${isZh ? '投票者:' : 'Voters:'}</span>
                                <div class="vote-voters-side">${votersPills}</div>
                            </div>
                        `;
                    });
                }

                dayContentHtml += `
                    <div class="timeline-card vote-timeline-card">
                        <div class="vote-timeline-header">
                            <span class="vote-phase-badge">${phaseLabel}</span>
                            <span class="vote-result-badge">${resultLabel}</span>
                        </div>
                        ${targetRowsHtml}
                    </div>
                `;
            });
        }

        // Public Gunshots & Deaths (in 'all' or 'actions' view)
        if (filter === 'all' || filter === 'actions') {
            if (opData.public_shots) {
                const dayShots = opData.public_shots.filter(s => s.day === roundNum);
                dayShots.forEach(s => {
                    let shooterRoleLabel = '';
                    if (s.role === 'Hunter') {
                        shooterRoleLabel = isZh ? ' (猎人)' : ' (Hunter)';
                    } else if (s.role === 'Black Werewolf King') {
                        shooterRoleLabel = isZh ? ' (黑狼王)' : ' (Black Werewolf King)';
                    } else {
                        shooterRoleLabel = isZh ? ' (猎人/黑狼王)' : ' (Hunter / Wolf King)';
                    }
                    dayContentHtml += `
                        <div class="timeline-card public-card">
                            <span>🏹 <strong>${formatPlayerSeatLabel(s.shooter, isZh)}</strong>${shooterRoleLabel} ${isZh ? '死亡开枪带走了' : 'shot'} <strong>${getAvatar(s.target)} ${formatPlayerSeatLabel(s.target, isZh)}</strong></span>
                        </div>
                    `;
                });
            }
        }

        if (dayContentHtml) {
            roundHtml += `
                <div class="timeline-node day-node">
                    <div class="timeline-node-icon">☀️</div>
                    <div class="timeline-node-title">${isZh ? `第 ${roundNum} 天` : `Day ${roundNum}`}</div>
                    ${dayContentHtml}
                </div>
            `;
            roundHasContent = true;
        }

        if (roundHasContent) {
            html += roundHtml;
        }
    });

    if (!html) {
        html = `<div class="op-empty-card"><p>${isZh ? '当前筛选下暂无记录' : 'No records match the current filter.'}</p></div>`;
    }

    container.innerHTML = html;
}

// For post-game modal compatibility
async function loadOperationsHistory(containerId = 'op-history-content') {
    const content = document.getElementById(containerId);
    if (!content) return;

    const t = I18N[gameState.lang].opHistory;
    content.innerHTML = `<p class="op-history-loading">${gameState.lang === 'zh' ? '正在加载操作记录...' : 'Loading operations history...'}</p>`;

    if (!gameState.gameId) {
        content.innerHTML = `<div class="op-empty-card"><p>${t.noData}</p></div>`;
        return;
    }

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
    const isZh = gameState.lang === 'zh';

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
                html += `<span class="op-badge teammate">${getAvatar(tm)} ${formatPlayerSeatLabel(tm, isZh)}</span>`;
            });
        }
        if (data.king) {
            html += `<span class="op-badge teammate" style="background:#ffd200;">👑 ${t.king}: ${formatPlayerSeatLabel(data.king, isZh)}</span>`;
        }
        html += `</div></div>`;
    }

    if (data.kills && data.kills.length > 0) {
        hasOperations = true;
        const nightKillsTitle = isZh ? '夜间袭击目标' : 'Night Attack Targets';
        html += `<div class="op-card">
            <div class="op-card-title">🩸 ${nightKillsTitle}</div>
            <div style="display:flex; flex-direction:column; gap:6px;">`;
        data.kills.forEach(k => {
            const nightLabel = isZh ? `第 ${k.night} 夜` : `Night ${k.night}`;
            const targetText = k.target
                ? `${getAvatar(k.target)} ${formatPlayerSeatLabel(k.target, isZh)}`
                : (isZh ? '无人袭击 (空刀)' : 'No one targeted');
            html += `
                <div class="op-kill-item">
                    <span class="op-night-tag">${nightLabel}</span>
                    <span class="op-target-tag">${targetText}</span>
                </div>
            `;
        });
        html += `</div></div>`;
    }

    if (data.saved !== undefined || data.poisoned !== undefined) {
        hasOperations = true;
        html += `<div class="op-card">
            <div class="op-card-title">🧙‍♀️ ${isZh ? '女巫用药' : 'Witch Potions'}</div>
            <div style="display:flex; flex-direction:column; gap:8px;">
                <div class="op-badges-list" style="align-items:center;">
                    <span style="font-size:0.9rem; font-weight:700;">💚 ${t.saved}:</span>
                    ${(data.saved && data.saved.length > 0) 
                        ? data.saved.map(p => `<span class="op-badge saved">${formatPlayerSeatLabel(p, isZh)}</span>`).join('') 
                        : `<span style="color:var(--text-muted); font-size:0.85rem;">${isZh ? '未使用' : 'None'}</span>`}
                </div>
                <div class="op-badges-list" style="align-items:center;">
                    <span style="font-size:0.9rem; font-weight:700;">💜 ${t.poisoned}:</span>
                    ${(data.poisoned && data.poisoned.length > 0) 
                        ? data.poisoned.map(p => `<span class="op-badge poisoned">${formatPlayerSeatLabel(p, isZh)}</span>`).join('') 
                        : `<span style="color:var(--text-muted); font-size:0.85rem;">${isZh ? '未使用' : 'None'}</span>`}
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
            const campLabel = isWerewolf ? (isZh ? '狼人阵营 🐺' : 'Werewolf 🐺') : (isZh ? '好人阵营 👱' : 'Good 👱');
            const roundPrefix = item.night ? (isZh ? `第 ${item.night} 夜 · ` : `Night ${item.night} · `) : '';
            html += `
                <div class="op-check-item">
                    <span style="font-weight:700;">${roundPrefix}${getAvatar(item.player)} ${formatPlayerSeatLabel(item.player, isZh)}</span>
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
                ${data.protected.map(p => `<span class="op-badge protected">${getAvatar(p)} ${formatPlayerSeatLabel(p, isZh)}</span>`).join('')}
            </div>
        </div>`;
    }

    if (data.shot && data.shot.length > 0) {
        hasOperations = true;
        html += `<div class="op-card">
            <div class="op-card-title">🏹 ${t.shot}</div>
            <div class="op-badges-list">
                ${data.shot.map(p => `<span class="op-badge shot">${getAvatar(p)} ${formatPlayerSeatLabel(p, isZh)}</span>`).join('')}
            </div>
        </div>`;
    }

    if (!hasOperations) {
        const villagerDesc = isZh
            ? '作为普通村民，夜间无需操作。请在白天的发言和投票中发挥你的智慧！'
            : 'As a Villager, you have no special night actions. Your strength lies in daytime discussion and voting!';
        html += `<div class="op-empty-card"><p>${villagerDesc}</p></div>`;
    }

    return html;
}

// Expose helper on window for debugging & testing
window.playStageCurtainTransition = playStageCurtainTransition;

// Start
init();
