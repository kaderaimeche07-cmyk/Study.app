import psycopg2
from urllib.parse import urlparse
import json
import ssl
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
import os
import uuid
from http import cookies

# ==============================================================================
# AI API Key & Config
# ==============================================================================
API_KEY = "sk-FWE5lPc8aegQHHJZvk967w"
API_URL = "https://app.ai-grid.io/v1/chat/completions"
PORT = 8080

MODEL_NAME = "Qwen3-30B-A3B-Thinking"

# ==============================================================================
# Database & Fallback System
# ==============================================================================
MOCK_DB = {}
MOCK_DB_DOC_ID = 1

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    try:
        return psycopg2.connect(database_url, sslmode='require', connect_timeout=3)
    except Exception:
        return None

def load_curriculum(session_id):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS user_documents (id SERIAL PRIMARY KEY, session_id VARCHAR(255), title TEXT, content TEXT);")
            cur.execute("SELECT id, title, content FROM user_documents WHERE session_id = %s ORDER BY id ASC;", (session_id,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [{"id": r[0], "title": r[1], "concepts": r[2]} for r in rows]
        except Exception:
            pass
    return MOCK_DB.get(session_id, [])

def add_document_to_db(session_id, title, content):
    global MOCK_DB, MOCK_DB_DOC_ID
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS user_documents (id SERIAL PRIMARY KEY, session_id VARCHAR(255), title TEXT, content TEXT);")
            cur.execute("INSERT INTO user_documents (session_id, title, content) VALUES (%s, %s, %s);", (session_id, title, content))
            conn.commit()
            cur.close()
            conn.close()
            return
        except Exception:
            pass
    
    if session_id not in MOCK_DB:
        MOCK_DB[session_id] = []
    MOCK_DB[session_id].append({"id": MOCK_DB_DOC_ID, "title": title, "concepts": content})
    MOCK_DB_DOC_ID += 1

def delete_document_from_db(session_id, doc_id):
    global MOCK_DB
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_documents WHERE id = %s AND session_id = %s;", (doc_id, session_id))
            conn.commit()
            cur.close()
            conn.close()
            return
        except Exception:
            pass
    
    if session_id in MOCK_DB:
        MOCK_DB[session_id] = [d for d in MOCK_DB[session_id] if str(d["id"]) != str(doc_id)]

# ==============================================================================
# HTML Frontend (Dynamic Height, Image Compression, and Robust API)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ge_nius</title>
    
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@700;900&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/lucide@latest"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

    <script>
      window.MathJax = {
        tex: { inlineMath: [['$', '$']], displayMath: [['$$', '$$']], processEscapes: true },
        options: { skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre'] }
      };
    </script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" id="MathJax-script" async></script>

    <style>
        :root {
            /* Onion Dark Theme */
            --bg-main: #1f1025; --surface: #2d1836; --card: #3a1f44;
            --primary: #c9184a; --accent-purple: #9d4edd; --accent-green: #10b981;
            --danger: #ef4444; --text-main: #f8fafc; --text-dim: #d8b4e2;
            --border: rgba(255, 255, 255, 0.08); --ai-bubble-bg: transparent;
            --gradient-1: rgba(201, 24, 74, 0.15); --gradient-2: rgba(157, 78, 221, 0.15); 
        }

        body.light-mode {
            --bg-main: #fff0f3; --surface: #ffffff; --card: #ffe5ec;
            --primary: #c9184a; --text-main: #3a0ca3; --text-dim: #7209b7;
            --border: rgba(201, 24, 74, 0.15); --ai-bubble-bg: transparent;
            --gradient-1: rgba(201, 24, 74, 0.08); --gradient-2: rgba(157, 78, 221, 0.08);
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        html, body {
            font-family: 'Inter', sans-serif; 
            background-color: var(--bg-main); color: var(--text-main);
            margin: 0; padding: 0; 
            height: 100%; height: 100dvh; /* FIX for Mobile Keyboard */
            overflow: hidden; /* Prevent body scrolling */
        }

        /* Fixed Background gradient */
        .bg-layer {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: -1;
            background-image: radial-gradient(circle at 15% 50%, var(--gradient-1), transparent 25%),
                              radial-gradient(circle at 85% 30%, var(--gradient-2), transparent 25%);
        }

        .main-wrapper {
            display: flex; flex-direction: column; gap: 10px;
            width: 100%; max-width: 900px; margin: 0 auto;
            height: 100%; height: 100dvh; /* Adapts to keyboard */
            padding: 12px;
        }

        .app-header {
            background: rgba(var(--surface), 0.8); backdrop-filter: blur(10px);
            padding: 10px 14px; border-radius: 16px; border: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center;
            flex-shrink: 0; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        }
        
        .header-actions { display: flex; gap: 10px; align-items: center; }
        
        .icon-btn {
            background: var(--card); border: 1px solid var(--border); color: var(--text-main);
            border-radius: 10px; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; cursor: pointer;
        }

        .submarine-logo {
            position: relative; background: linear-gradient(180deg, #3b82f6, #1d4ed8);
            padding: 4px 16px; border-radius: 40px; border: 2px solid #1e3a8a;
            display: inline-flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25), inset 0 -3px 5px rgba(0,0,0,0.2);
            color: #ffffff; font-weight: 900; font-size: 1.05rem; letter-spacing: 1px; font-family: 'Outfit', sans-serif;
        }
        .submarine-logo::before { content: ''; position: absolute; top: -10px; left: 60%; width: 8px; height: 10px; background: #3b82f6; border-left: 2px solid #1e3a8a; border-right: 2px solid #1e3a8a; z-index: 1; }
        .submarine-logo::after { content: ''; position: absolute; top: -10px; left: calc(60% + 4px); width: 12px; height: 4px; background: #3b82f6; border: 2px solid #1e3a8a; border-radius: 2px; z-index: 2; }
        .submarine-propeller { position: absolute; right: -10px; top: 50%; transform: translateY(-50%); width: 6px; height: 16px; background: #94a3b8; border: 2px solid #475569; border-radius: 4px; }
        .submarine-propeller::after { content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 4px; height: 20px; background: #cbd5e1; border-radius: 2px; animation: spin-propeller 0.15s linear infinite; }
        @keyframes spin-propeller { 0% { transform: translate(-50%, -50%) scaleY(1); } 50% { transform: translate(-50%, -50%) scaleY(0.2); } 100% { transform: translate(-50%, -50%) scaleY(1); } }

        .lucide { width: 18px; height: 18px; stroke-width: 2.2; }

        .sidebar-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); backdrop-filter: blur(2px); z-index: 99; opacity: 0; pointer-events: none; transition: opacity 0.3s; }
        .sidebar-overlay.active { opacity: 1; pointer-events: auto; }
        
        .sidebar {
            position: fixed; top: 0; left: -300px; width: 280px; height: 100dvh;
            background: var(--surface); border-right: 1px solid var(--border);
            z-index: 100; transition: left 0.3s ease; display: flex; flex-direction: column; padding: 20px;
        }
        .sidebar.open { left: 0; }
        .sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 15px;}
        .sidebar h3 { margin: 0; font-size: 1.1rem; display: flex; align-items: center; gap: 8px;}
        
        .mode-toggle { display: flex; background: var(--card); border-radius: 12px; padding: 4px; position: relative; margin: 15px 0; border: 1px solid var(--border); }
        .mode-btn { flex: 1; text-align: center; padding: 10px; font-size: 0.85rem; font-weight: 600; cursor: pointer; z-index: 1; color: var(--text-dim); transition: color 0.3s; display: flex; align-items: center; justify-content: center; gap: 6px; }
        .mode-btn.active { color: white; }
        .mode-slider { position: absolute; top: 4px; bottom: 4px; width: calc(50% - 4px); background: var(--primary); border-radius: 8px; transition: left 0.3s ease; }

        .chat-history-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
        .history-item { background: transparent; padding: 12px; border-radius: 10px; cursor: pointer; display: flex; align-items: center; gap: 10px; font-size: 0.9rem; }
        .history-item.active { background: var(--gradient-1); border: 1px solid var(--primary); font-weight: 600; }
        
        .tab-bar { display: flex; background: var(--surface); border-radius: 12px; padding: 4px; border: 1px solid var(--border); flex-shrink: 0; }
        .tab-btn { flex: 1; padding: 10px; background: none; border: none; color: var(--text-dim); font-family: 'Inter', sans-serif; font-weight: 600; font-size: 0.95rem; cursor: pointer; border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .tab-btn.active { background: var(--primary); color: white; }

        .tab-section { display: none; flex-direction: column; gap: 12px; flex: 1; min-height: 0; }
        .tab-section.active { display: flex; }
        .card { background: rgba(var(--surface), 0.7); backdrop-filter: blur(10px); border-radius: 16px; border: 1px solid var(--border); padding: 16px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto;}

        .chat-feed {
            flex: 1; overflow-y: auto; padding: 10px 4px; display: flex; flex-direction: column; gap: 20px;
            scroll-behavior: smooth;
        }
        
        .chat-bubble { font-size: 0.95rem; line-height: 1.6; max-width: 95%; display: flex; gap: 12px; position: relative; animation: slideUp 0.3s ease; }
        @keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .user-bubble { align-self: flex-end; flex-direction: row-reverse; }
        .user-bubble .bubble-content { background: var(--surface); padding: 12px 16px; border-radius: 18px; border-bottom-right-radius: 4px; border: 1px solid var(--border); }
        .ai-bubble { align-self: flex-start; }
        .ai-bubble .bubble-content { padding: 5px 0; flex: 1; min-width: 0; overflow-x: auto;}
        
        .ai-content h1, .ai-content h2, .ai-content h3 { margin-top: 15px; margin-bottom: 10px; color: var(--text-main); font-weight: 600; }
        .ai-content p { margin: 8px 0; }
        .cursor-blink { animation: blink 1s step-start infinite; color: var(--primary); font-weight: bold; }
        @keyframes blink { 50% { opacity: 0; } }
        
        .copy-btn { margin-top: 8px; background: transparent; color: var(--text-dim); border: none; font-size: 0.8rem; cursor: pointer; display: flex; align-items: center; gap: 4px; padding: 0; }
        
        .bubble-icon { flex-shrink: 0; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
        .user-bubble .bubble-icon { background: var(--primary); color: white; }
        .ai-bubble .bubble-icon { background: linear-gradient(180deg, #3b82f6, #1d4ed8); color: #ffffff; box-shadow: 0 2px 5px rgba(37, 99, 235, 0.3); }

        .chat-input-container { flex-shrink: 0; padding-bottom: env(safe-area-inset-bottom); }
        .chat-input-wrapper {
            background: var(--surface); border: 1px solid var(--border); border-radius: 24px;
            padding: 8px 12px; display: flex; align-items: flex-end; gap: 8px;
        }
        .chat-input-wrapper textarea {
            flex: 1; background: transparent; border: none; color: var(--text-main);
            font-family: 'Inter', sans-serif; font-size: 0.95rem; resize: none; max-height: 100px;
            outline: none; padding: 10px 0; line-height: 1.4;
        }
        .chat-input-actions { display: flex; gap: 4px; padding-bottom: 6px; }
        .action-icon { color: var(--text-dim); cursor: pointer; padding: 6px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
        .send-btn { background: var(--text-main); color: var(--bg-main); border: none; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; padding: 0; }

        .image-preview-bar { display: none; align-items: center; justify-content: space-between; background: rgba(201, 24, 74, 0.1); border: 1px solid var(--primary); padding: 8px 12px; border-radius: 12px; font-size: 0.85rem; color: var(--primary); margin-bottom: 10px; }

        .btn { background: var(--card); color: var(--text-main); border: 1px solid var(--border); padding: 10px 16px; border-radius: 8px; font-family: 'Inter', sans-serif; font-weight: 600; font-size: 0.9rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .btn-primary { background: var(--primary); color: white; border: none; }
        .btn-danger { background: rgba(239, 68, 68, 0.1); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.2); }

        input[type="file"] { display: none; }
        
        .doc-item { background: var(--surface); border-radius: 12px; padding: 14px; border: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
        .doc-header { display: flex; justify-content: space-between; align-items: center; }
        .doc-title { font-weight: 600; font-size: 0.95rem; display: flex; align-items: center; gap: 8px;}
        .doc-body { font-size: 0.85rem; color: var(--text-dim); max-height: 100px; overflow-y: auto; background: var(--bg-main); padding: 10px; border-radius: 8px; white-space: pre-wrap; }

        .spin-icon { animation: spin 1.2s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.2); border-radius: 10px; }
    </style>
</head>
<body>
    <div class="bg-layer"></div>

    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h3><i data-lucide="menu"></i> Menu</h3>
            <button class="icon-btn" style="width:30px; height:30px; border:none; background:transparent;" onclick="toggleSidebar()"><i data-lucide="x"></i></button>
        </div>
        <button class="btn btn-primary" onclick="createNewChat()" style="margin-bottom: 15px;">
            <i data-lucide="plus"></i> New Chat
        </button>
        <div style="font-size: 0.8rem; color: var(--text-dim); margin-bottom: 5px; font-weight: 600;">Assistant Mode</div>
        <div class="mode-toggle" id="modeToggle">
            <div class="mode-slider" id="modeSlider" style="left: 4px;"></div>
            <div class="mode-btn active" id="btnModeStudy" onclick="setMode('study')"><i data-lucide="graduation-cap"></i> Study</div>
            <div class="mode-btn" id="btnModeGeneral" onclick="setMode('general')"><i data-lucide="globe"></i> General</div>
        </div>
        <h4 style="font-size: 0.85rem; color: var(--text-dim); margin-bottom: 5px; margin-top: 10px;"><i data-lucide="history" style="width:14px; height:14px;"></i> Chat History</h4>
        <div class="chat-history-list" id="chatHistoryList"></div>
        <div style="margin-top: auto; padding-top: 15px; border-top: 1px solid var(--border);">
            <button class="btn" style="width: 100%;" onclick="toggleTheme()">
                <i data-lucide="sun" id="themeIcon"></i> Toggle Theme
            </button>
        </div>
    </aside>

    <div class="main-wrapper">
        <header class="app-header">
            <div class="header-actions">
                <button class="icon-btn" onclick="toggleSidebar()"><i data-lucide="menu"></i></button>
                <div class="submarine-logo">ge_nius<div class="submarine-propeller"></div></div>
            </div>
            <span style="font-size: 0.85rem; color: var(--text-dim); display: flex; align-items: center; gap: 5px;" id="docCountBadge">
                <i data-lucide="database"></i> <span>0</span> Docs
            </span>
        </header>

        <div class="tab-bar">
            <button class="tab-btn active" id="btnAskTab" onclick="switchTab('askTab', this)"><i data-lucide="message-square"></i> Chat</button>
            <button class="tab-btn" id="btnDocsTab" onclick="switchTab('docsTab', this)"><i data-lucide="folder-open"></i> My Documents</button>
        </div>

        <div class="tab-section active" id="askTab">
            <div class="chat-feed" id="chatFeed"></div>

            <div class="chat-input-container">
                <div id="questionImgPreview" class="image-preview-bar">
                    <span style="display: flex; align-items: center; gap: 6px;"><i data-lucide="image-check"></i> Image attached</span>
                    <span style="cursor: pointer; display: flex; align-items: center; gap: 4px;" onclick="removeQuestionImage()"><i data-lucide="x"></i> Remove</span>
                </div>
                <div class="chat-input-wrapper">
                    <div class="chat-input-actions">
                        <label for="qFileInputCamera" class="action-icon" title="Camera"><i data-lucide="camera"></i></label>
                        <input type="file" id="qFileInputCamera" accept="image/*" capture="environment">
                        <label for="qFileInputGallery" class="action-icon" title="Gallery"><i data-lucide="image"></i></label>
                        <input type="file" id="qFileInputGallery" accept="image/*">
                    </div>
                    <textarea id="userQuery" placeholder="Message ge_nius..." rows="1"></textarea>
                    <div class="chat-input-actions">
                        <button class="send-btn" onclick="submitQuestion()" title="Send"><i data-lucide="arrow-up"></i></button>
                    </div>
                </div>
            </div>
        </div>

        <div class="tab-section" id="docsTab">
            <div class="card" style="flex-shrink: 0;">
                <span style="font-weight: 600; font-size: 1rem; display: flex; align-items: center; gap: 8px;"><i data-lucide="upload-cloud"></i> Upload Documents</span>
                <div style="display: flex; gap: 8px; margin-top: 5px;">
                    <label for="docFileInputCamera" class="btn" style="flex: 1;"><i data-lucide="camera"></i> Camera</label>
                    <input type="file" id="docFileInputCamera" accept="image/*" capture="environment">
                    <label for="docFileInputGallery" class="btn btn-primary" style="flex: 1;"><i data-lucide="images"></i> Gallery</label>
                    <input type="file" id="docFileInputGallery" accept="image/*" multiple>
                </div>
                <div id="uploadStatus" style="display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 0.85rem; margin-top: 10px; font-weight: 500; color: var(--text-dim);"></div>
            </div>
            <div class="card" style="flex: 1;">
                <span style="font-weight: 600; font-size: 0.9rem; display: flex; align-items: center; gap: 8px;"><i data-lucide="archive"></i> Processed Documents:</span>
                <div id="docsList" style="display: flex; flex-direction: column; gap: 10px; padding-bottom: 20px;"></div>
            </div>
        </div>
    </div>

    <script>
        lucide.createIcons();

        const userQuery = document.getElementById('userQuery');
        const chatFeed = document.getElementById('chatFeed');

        // FIX Keyboard Issue: Auto-resize and Scroll on Focus
        userQuery.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
        
        userQuery.addEventListener('focus', () => {
            setTimeout(() => { chatFeed.scrollTop = chatFeed.scrollHeight; }, 300);
        });

        userQuery.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); submitQuestion();
            }
        });

        // SMART COMPRESSION FUNCTION: Fixes the API crash from large mobile images
        function compressImage(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.readAsDataURL(file);
                reader.onload = (event) => {
                    const img = new Image();
                    img.src = event.target.result;
                    img.onload = () => {
                        let width = img.width; let height = img.height;
                        const max_dim = 1024; // Reduce to max 1024px to save API bandwidth
                        if (width > max_dim || height > max_dim) {
                            if (width > height) { height = Math.round((height * max_dim) / width); width = max_dim; }
                            else { width = Math.round((width * max_dim) / height); height = max_dim; }
                        }
                        const canvas = document.createElement('canvas');
                        canvas.width = width; canvas.height = height;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, width, height);
                        resolve(canvas.toDataURL('image/jpeg', 0.8)); // 80% Quality
                    };
                    img.onerror = reject;
                };
                reader.onerror = reject;
            });
        }

        function toggleTheme() {
            const isLight = document.body.classList.toggle('light-mode');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            const themeIcon = document.getElementById('themeIcon');
            themeIcon.setAttribute('data-lucide', isLight ? 'moon' : 'sun');
            lucide.createIcons();
        }
        if (localStorage.getItem('theme') === 'light') { document.body.classList.add('light-mode'); document.getElementById('themeIcon').setAttribute('data-lucide', 'moon'); lucide.createIcons(); }

        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('open');
            document.getElementById('sidebarOverlay').classList.toggle('active');
        }

        let chatSessions = JSON.parse(localStorage.getItem('ge_nius_sessions')) || {};
        let currentSessionId = localStorage.getItem('ge_nius_current_session');
        
        function setMode(mode) {
            const slider = document.getElementById('modeSlider');
            document.getElementById('btnModeStudy').classList.remove('active');
            document.getElementById('btnModeGeneral').classList.remove('active');
            if (mode === 'study') { slider.style.left = '4px'; document.getElementById('btnModeStudy').classList.add('active'); } 
            else { slider.style.left = 'calc(50% + 0px)'; document.getElementById('btnModeGeneral').classList.add('active'); }
            if(chatSessions[currentSessionId]) { chatSessions[currentSessionId].mode = mode; saveSessionsData(); }
        }

        function initSessions() {
            if (!currentSessionId || !chatSessions[currentSessionId]) createNewChat();
            else loadChat(currentSessionId);
            renderChatList();
        }

        function createNewChat() {
            const id = Date.now().toString();
            chatSessions[id] = { id: id, title: "New Chat", html: "", mode: "study" };
            currentSessionId = id;
            saveSessionsData(); loadChat(id);
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
        }

        function loadChat(id) {
            currentSessionId = id; const session = chatSessions[id];
            setMode(session.mode || 'study');
            if (session.html && session.html.trim() !== '') chatFeed.innerHTML = session.html;
            else chatFeed.innerHTML = `<div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 40px 20px; display: flex; flex-direction: column; align-items: center; gap: 12px;"><div class="submarine-logo" style="transform: scale(1.2); margin-bottom:10px;">ge_nius<div class="submarine-propeller"></div></div><h3 style="margin:0; font-weight:600; color:var(--text-main);">How can I help you today?</h3></div>`;
            lucide.createIcons({root: chatFeed});
            if (window.MathJax) MathJax.typesetPromise([chatFeed]);
            setTimeout(() => { chatFeed.scrollTop = chatFeed.scrollHeight; }, 100);
            saveSessionsData(); renderChatList();
        }

        function saveCurrentChatHtml(userQueryText = null) {
            const clones = chatFeed.cloneNode(true);
            clones.querySelectorAll('.loading-bubble-temp').forEach(l => l.remove());
            chatSessions[currentSessionId].html = clones.innerHTML;
            if (userQueryText && chatSessions[currentSessionId].title === "New Chat") chatSessions[currentSessionId].title = userQueryText.substring(0, 25) + "...";
            saveSessionsData();
        }

        function saveSessionsData() {
            localStorage.setItem('ge_nius_sessions', JSON.stringify(chatSessions));
            localStorage.setItem('ge_nius_current_session', currentSessionId);
            renderChatList();
        }

        function renderChatList() {
            const listDiv = document.getElementById('chatHistoryList'); listDiv.innerHTML = '';
            const sortedIds = Object.keys(chatSessions).sort((a, b) => b - a);
            sortedIds.forEach(id => {
                const session = chatSessions[id];
                const icon = session.mode === 'general' ? 'globe' : 'graduation-cap';
                const isActive = id === currentSessionId ? 'active' : '';
                listDiv.innerHTML += `<div class="history-item ${isActive}" onclick="loadChat('${id}')"><i data-lucide="${icon}"></i><span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: ltr;">${session.title}</span></div>`;
            });
            lucide.createIcons({root: listDiv});
        }

        initSessions();

        window.copyText = function(btn, text) {
            navigator.clipboard.writeText(decodeURIComponent(text)).then(() => {
                const originalHtml = btn.innerHTML;
                btn.innerHTML = `<i data-lucide="check"></i> Copied`;
                lucide.createIcons({root: btn});
                setTimeout(() => { btn.innerHTML = originalHtml; lucide.createIcons({root: btn}); }, 2000);
            });
        };

        function showLocalMessage(msg, isWarning = true) {
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();
            const bubble = document.createElement('div'); bubble.className = 'chat-bubble ai-bubble';
            const icon = isWarning ? 'alert-triangle' : 'info'; const color = isWarning ? 'var(--danger)' : 'var(--text-main)';
            bubble.innerHTML = `<div class="bubble-icon" style="background:transparent; color:${color};"><i data-lucide="${icon}"></i></div> <div class="bubble-content" style="color:${color}; border:1px solid ${color}33; background:transparent;">${msg}</div>`;
            chatFeed.appendChild(bubble); lucide.createIcons({root: bubble});
            chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
        }

        let curriculumDocs = [];
        let attachedQuestionBase64 = null;
        fetchDocs();

        function switchTab(tabId, btnElement) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
            if(btnElement) btnElement.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }

        function fetchDocs() { fetch('/api/docs').then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }).catch(e => {}); }

        function renderDocs() {
            const listDiv = document.getElementById('docsList'); const countBadge = document.getElementById('docCountBadge');
            if(countBadge) { countBadge.innerHTML = `<i data-lucide="database"></i> <span>${curriculumDocs.length}</span> Docs`; lucide.createIcons({root: countBadge}); }
            if (!listDiv) return;
            if (curriculumDocs.length === 0) { listDiv.innerHTML = '<div style="color: var(--text-dim); text-align: center; padding: 20px;">No documents uploaded yet.</div>'; return; }
            listDiv.innerHTML = curriculumDocs.map((item, i) => `
                <div class="doc-item">
                    <div class="doc-header">
                        <span class="doc-title"><i data-lucide="file-text"></i> Document ${i + 1}</span>
                        <button class="btn btn-danger" style="padding: 6px 10px;" onclick="deleteDoc(${item.id})"><i data-lucide="trash-2" style="width:14px; height:14px;"></i></button>
                    </div>
                    <div class="doc-body">${item.concepts}</div>
                </div>
            `).join('');
            lucide.createIcons({root: listDiv});
        }

        async function handleQuestionImageSelect(e) {
            const file = e.target.files[0]; if (!file) return;
            attachedQuestionBase64 = await compressImage(file);
            document.getElementById('questionImgPreview').style.display = 'flex';
            e.target.value = '';
        }
        document.getElementById('qFileInputCamera').addEventListener('change', handleQuestionImageSelect);
        document.getElementById('qFileInputGallery').addEventListener('change', handleQuestionImageSelect);
        function removeQuestionImage() { attachedQuestionBase64 = null; document.getElementById('questionImgPreview').style.display = 'none'; }

        async function handleDocImageSelect(e) {
            const files = e.target.files; if (!files || files.length === 0) return;
            const statusDiv = document.getElementById('uploadStatus');
            for (let i = 0; i < files.length; i++) {
                if(statusDiv) { statusDiv.innerHTML = `<i data-lucide="loader" class="spin-icon"></i> Uploading doc ${i + 1}/${files.length}...`; statusDiv.style.color = 'var(--text-main)'; lucide.createIcons({root: statusDiv}); }
                try {
                    const compressedBase64 = await compressImage(files[i]);
                    const res = await fetch('/api/docs/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: compressedBase64 }) });
                    const data = await res.json(); 
                    if (data.error) throw new Error(data.error);
                    if (data.docs) curriculumDocs = data.docs;
                } catch (err) {
                    if(statusDiv) { statusDiv.innerHTML = `<i data-lucide="alert-circle"></i> Upload failed: ${err.message}`; statusDiv.style.color = 'var(--danger)'; lucide.createIcons({root: statusDiv}); }
                    return;
                }
            }
            renderDocs();
            if(statusDiv) { statusDiv.innerHTML = '<i data-lucide="check-circle-2"></i> Documents saved successfully.'; statusDiv.style.color = 'var(--accent-green)'; lucide.createIcons({root: statusDiv}); }
        }
        document.getElementById('docFileInputCamera').addEventListener('change', handleDocImageSelect);
        document.getElementById('docFileInputGallery').addEventListener('change', handleDocImageSelect);

        function deleteDoc(id) { fetch('/api/docs/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) }).then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }); }

        function submitQuestion() {
            const query = userQuery.value.trim();
            let currentSession = chatSessions[currentSessionId];
            if (!currentSession) { createNewChat(); currentSession = chatSessions[currentSessionId]; }
            const currentMode = currentSession.mode || 'study';

            if (!query && !attachedQuestionBase64) return;
            if (currentMode === 'study' && curriculumDocs.length === 0) { 
                showLocalMessage('You are in <b>Study Mode 🎓</b> but have no documents uploaded.<br><br>Please upload your study materials in the "My Documents" tab first, or switch to <b>General Chat 🌍</b> from the Menu.');
                return; 
            }
            
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();

            let userTextDisplay = query.replace(/\n/g, '<br>'); // FIXED Line break handling
            if (attachedQuestionBase64) { userTextDisplay = (query ? userTextDisplay + '<br><br>' : '') + '<span style="color:var(--text-dim); font-size:0.85em"><i data-lucide="image" style="width:14px;height:14px; vertical-align:middle;"></i> Image Attached</span>'; }

            const userBubble = document.createElement('div'); userBubble.className = 'chat-bubble user-bubble';
            userBubble.innerHTML = `<div class="bubble-content" dir="auto">${userTextDisplay}</div>`;
            chatFeed.appendChild(userBubble); lucide.createIcons({root: userBubble});

            const loadingBubble = document.createElement('div'); loadingBubble.className = 'chat-bubble ai-bubble loading-bubble-temp';
            loadingBubble.innerHTML = `<div class="bubble-icon"><i data-lucide="bot"></i></div> <div class="bubble-content"><i data-lucide="loader-circle" class="spin-icon" style="width:16px;height:16px;"></i> <span class="thinking-text" style="color:var(--text-dim);">Thinking...</span></div>`;
            chatFeed.appendChild(loadingBubble); lucide.createIcons({root: loadingBubble});
            
            saveCurrentChatHtml(query);

            const payload = { query: query, image: attachedQuestionBase64, mode: currentMode };
            userQuery.value = ''; userQuery.style.height = 'auto'; removeQuestionImage(); chatFeed.scrollTop = chatFeed.scrollHeight;

            fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            .then(res => res.json())
            .then(data => {
                chatFeed.removeChild(loadingBubble);
                const aiBubble = document.createElement('div');
                if (data.status === 'out_of_scope') {
                    aiBubble.className = 'chat-bubble ai-bubble'; aiBubble.innerHTML = `<div class="bubble-icon" style="background:var(--danger);"><i data-lucide="alert-triangle"></i></div> <div class="bubble-content">I'm sorry, this is outside your curriculum scope. Please switch to General mode for unrestricted chat.</div>`;
                    chatFeed.appendChild(aiBubble); lucide.createIcons({root: aiBubble}); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
                } else if (data.status === 'success') {
                    aiBubble.className = 'chat-bubble ai-bubble';
                    aiBubble.innerHTML = `<div class="bubble-icon"><i data-lucide="bot"></i></div> <div class="bubble-content" dir="auto"><div class="ai-content"></div></div>`;
                    chatFeed.appendChild(aiBubble); lucide.createIcons({root: aiBubble});
                    
                    const contentDiv = aiBubble.querySelector('.ai-content'); const fullText = data.answer;
                    let charIndex = 0; let currentText = '';
                    function typeWriter() {
                        if (charIndex < fullText.length) {
                            currentText += fullText.substring(charIndex, charIndex + 4); charIndex += 4;
                            contentDiv.innerHTML = marked.parse(currentText) + '<span class="cursor-blink"> ▌</span>';
                            chatFeed.scrollTop = chatFeed.scrollHeight;
                            setTimeout(typeWriter, 15);
                        } else {
                            contentDiv.innerHTML = marked.parse(fullText);
                            const encodedAnswer = encodeURIComponent(fullText);
                            aiBubble.querySelector('.bubble-content').insertAdjacentHTML('beforeend', `<button class="copy-btn" onclick="copyText(this, '${encodedAnswer}')"><i data-lucide="copy" style="width:14px;height:14px;"></i> Copy</button>`);
                            lucide.createIcons({root: aiBubble});
                            if (window.MathJax) window.MathJax.typesetPromise([aiBubble]).catch(e => console.log(e));
                            saveCurrentChatHtml();
                        }
                    }
                    typeWriter();
                } else {
                    aiBubble.className = 'chat-bubble ai-bubble'; aiBubble.innerHTML = `<div class="bubble-icon" style="background:var(--danger);"><i data-lucide="alert-circle"></i></div> <div class="bubble-content">API Error: ${data.error}</div>`;
                    chatFeed.appendChild(aiBubble); lucide.createIcons({root: aiBubble}); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
                }
            }).catch(err => {
                chatFeed.removeChild(loadingBubble);
                const errBubble = document.createElement('div'); errBubble.className = 'chat-bubble ai-bubble'; errBubble.innerHTML = `<div class="bubble-icon" style="background:var(--danger);"><i data-lucide="wifi-off"></i></div> <div class="bubble-content">Connection Failed. Check your internet or API key.</div>`;
                chatFeed.appendChild(errBubble); lucide.createIcons({root: errBubble}); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# Python Backend Server (Fixes General Text Payload)
# ==============================================================================
class StudyAppRequestHandler(BaseHTTPRequestHandler):

    def get_session_id(self):
        cookie_header = self.headers.get('Cookie')
        if cookie_header:
            c = cookies.SimpleCookie(cookie_header)
            if 'session_id' in c:
                return c['session_id'].value
        return None

    def send_api_request(self, payload):
        req_data = json.dumps(payload).encode("utf-8")
        headers = { "Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}" }
        ssl_ctx = ssl._create_unverified_context()
        req = urllib.request.Request(API_URL, data=req_data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=60) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                return res_json["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            error_info = e.read().decode("utf-8")
            raise Exception(f"HTTP {e.code}: {error_info}")
        except Exception as e:
            raise Exception(str(e))

    def do_GET(self):
        if self.path == "/":
            session_id = self.get_session_id()
            is_new_session = False
            if not session_id:
                session_id = str(uuid.uuid4())
                is_new_session = True

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            if is_new_session:
                self.send_header("Set-Cookie", f"session_id={session_id}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax")
            self.end_headers()
            self.wfile.write(HTML_CODE.encode("utf-8"))
            
        elif self.path == "/api/docs":
            session_id = self.get_session_id()
            if not session_id:
                self.send_json_response([])
                return
            docs = load_curriculum(session_id)
            self.send_json_response(docs)

    def do_POST(self):
        session_id = self.get_session_id()
        if not session_id:
            self.send_json_response({"error": "Invalid session. Please refresh."})
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        req_json = json.loads(post_data.decode('utf-8')) if post_data else {}

        if self.path == "/api/docs/upload":
            image_base64 = req_json.get("image")
            if not image_base64:
                self.send_json_response({"error": "No image provided."})
                return
            try:
                prompt = "Read this lesson document image and extract all text, concepts, formulas, and rules clearly in English."
                
                # FIXED Image Payload Format
                content_payload = [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_base64}}
                ]
                
                payload = {
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": content_payload}],
                    "max_tokens": 4096
                }
                extracted_concepts = self.send_api_request(payload)
                add_document_to_db(session_id, "Document", extracted_concepts)
                docs = load_curriculum(session_id)
                self.send_json_response({"status": "success", "docs": docs})
            except Exception as e:
                self.send_json_response({"error": str(e)})

        elif self.path == "/api/docs/delete":
            doc_id = req_json.get("id")
            if doc_id is not None:
                delete_document_from_db(session_id, doc_id)
            docs = load_curriculum(session_id)
            self.send_json_response(docs)

        elif self.path == "/api/ask":
            user_query = req_json.get("query", "")
            question_image_base64 = req_json.get("image")
            mode = req_json.get("mode", "study") 
            
            docs = load_curriculum(session_id)
            
            if mode == "general":
                full_prompt = (
                    f"You are a highly intelligent and helpful assistant named ge_nius.\n"
                    f"User prompt/image request: \"{user_query}\"\n\n"
                    f"Respond to the question in a professional, accurate, and friendly manner in Arabic/English depending on the user's language.\n"
                    f"You can answer anything (general knowledge, coding, science, history, etc.).\n\n"
                    f"--- Formatting Instructions ---\n"
                    f"- Use Markdown for structuring your response.\n"
                    f"- Use single dollar signs ($...$) for inline math and double dollar signs ($$...$$) for block math equations."
                )
            else:
                all_concepts_summary = "\n\n".join([f"Document {i+1}:\n{doc['concepts']}" for i, doc in enumerate(docs)])
                full_prompt = (
                    f"You are an expert tutor and study assistant.\n"
                    f"Here is the study material extracted from the student's curriculum documents:\n"
                    f"--- START CURRICULUM ---\n"
                    f"{all_concepts_summary}\n"
                    f"--- END CURRICULUM ---\n\n"
                    f"User's question or image attachment: \"{user_query}\"\n\n"
                    f"Follow these instructions exactly:\n"
                    f"1. Analyze carefully: Does the question relate to the provided curriculum documents in any way?\n"
                    f"2. If the question is completely off-topic or out of scope of the uploaded documents, reply with EXACTLY this word and nothing else: OUT_OF_SCOPE\n"
                    f"3. If it is within scope, provide a comprehensive, step-by-step explanation in Arabic/English.\n\n"
                    f"--- Math Formatting ---\n"
                    f"- For inline variables/math, use single dollar signs strictly, e.g., $x=2$ or $v$.\n"
                    f"- For block equations, use double dollar signs strictly, e.g.,\n$$ \\vec{{u}} = \\sqrt{{x^2 + y^2}} $$\n"
                    f"- Use Markdown for headings (###) and lists (-)."
                )

            # FIXED: Robust Payload structure. Prevent API crashes for text-only messages!
            if question_image_base64:
                content_payload = [
                    {"type": "text", "text": full_prompt},
                    {"type": "image_url", "image_url": {"url": question_image_base64}}
                ]
            else:
                content_payload = full_prompt # Pure String format when no image is attached

            payload = {
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": content_payload}],
                "max_tokens": 4096
            }

            try:
                ai_reply = self.send_api_request(payload)
                if mode == "study" and ("OUT_OF_SCOPE" in ai_reply or ai_reply.startswith("OUT_OF_SCOPE")):
                    self.send_json_response({"status": "out_of_scope"})
                else:
                    self.send_json_response({"status": "success", "answer": ai_reply})
            except Exception as e:
                self.send_json_response({"status": "error", "error": str(e)})

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), StudyAppRequestHandler)
    print(f"Server started on port {port}")
    server.serve_forever()
