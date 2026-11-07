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
# AI API Key & Config (Optimized Global Servers)
# ==============================================================================
API_KEY = "sk-FWE5lPc8aegQHHJZvk967w"
API_URL = "https://app.ai-grid.io/v1/chat/completions"
PORT = 8080

MODEL_NAME = "Qwen3-30B-A3B-Thinking"

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    try:
        return psycopg2.connect(database_url, sslmode='require', connect_timeout=3)
    except Exception:
        return None

def load_curriculum(session_id):
    try:
        conn = get_db_connection()
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS user_documents (id SERIAL PRIMARY KEY, session_id VARCHAR(255), title TEXT, content TEXT);")
        cur.execute("SELECT id, title, content FROM user_documents WHERE session_id = %s ORDER BY id ASC;", (session_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"id": r[0], "title": r[1], "concepts": r[2]} for r in rows]
    except Exception as e:
        return []

def add_document_to_db(session_id, title, content):
    try:
        conn = get_db_connection()
        if not conn:
            return
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS user_documents (id SERIAL PRIMARY KEY, session_id VARCHAR(255), title TEXT, content TEXT);")
        cur.execute("INSERT INTO user_documents (session_id, title, content) VALUES (%s, %s, %s);", (session_id, title, content))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        pass

def delete_document_from_db(session_id, doc_id):
    try:
        conn = get_db_connection()
        if not conn:
            return
        cur = conn.cursor()
        cur.execute("DELETE FROM user_documents WHERE id = %s AND session_id = %s;", (doc_id, session_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        pass

# ==============================================================================
# HTML Frontend (World-Class Production UI & Layout)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ge_nius Assistant</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&family=Outfit:wght@700;900&display=swap" rel="stylesheet">
    
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
            --bg-main: #020617; --surface: #0f172a; --card: #1e293b;
            --primary: #6366f1; --accent-purple: #8b5cf6; --accent-green: #10b981;
            --danger: #ef4444; --text-main: #f8fafc; --text-dim: #94a3b8;
            --border: rgba(255, 255, 255, 0.08); --ai-bubble-bg: rgba(30, 41, 59, 0.7);
            --gradient-1: rgba(99, 102, 241, 0.15); --gradient-2: rgba(139, 92, 246, 0.15);
        }

        body.light-mode {
            --bg-main: #f8fafc; --surface: #ffffff; --card: #f1f5f9;
            --primary: #4f46e5; --text-main: #0f172a; --text-dim: #475569;
            --border: rgba(0, 0, 0, 0.08); --ai-bubble-bg: #ffffff;
            --gradient-1: rgba(99, 102, 241, 0.08); --gradient-2: rgba(139, 92, 246, 0.08);
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        html, body {
            font-family: 'Tajawal', sans-serif; 
            background-color: var(--bg-main); color: var(--text-main);
            margin: 0; padding: 0; height: 100dvh; overflow: hidden;
            background-image: radial-gradient(circle at 15% 50%, var(--gradient-1), transparent 25%),
                              radial-gradient(circle at 85% 30%, var(--gradient-2), transparent 25%);
            background-attachment: fixed;
        }

        .main-wrapper { 
            padding: 12px; display: flex; flex-direction: column; gap: 10px; 
            height: 100dvh; max-width: 900px; margin: 0 auto; 
        }

        .app-header {
            background: rgba(var(--surface), 0.8); backdrop-filter: blur(10px);
            padding: 10px 16px; border-radius: 16px; border: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center;
            flex-shrink: 0; box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        }
        
        .header-actions { display: flex; gap: 10px; align-items: center; }
        
        .icon-btn {
            background: var(--card); border: 1px solid var(--border); color: var(--text-main);
            border-radius: 10px; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: all 0.2s;
        }
        .icon-btn:hover { background: var(--primary); color: white; }

        .submarine-logo {
            position: relative; background: linear-gradient(180deg, #f59e0b, #d97706);
            padding: 4px 16px; border-radius: 40px; border: 2px solid #b45309;
            display: inline-flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 10px rgba(245, 158, 11, 0.25), inset 0 -3px 5px rgba(0,0,0,0.2);
            color: #451a03; font-weight: 900; font-size: 1.1rem; letter-spacing: 1px; font-family: 'Outfit', sans-serif;
        }
        .submarine-logo::before { content: ''; position: absolute; top: -12px; left: 60%; width: 8px; height: 12px; background: #f59e0b; border-left: 2px solid #b45309; border-right: 2px solid #b45309; z-index: 1; }
        .submarine-logo::after { content: ''; position: absolute; top: -12px; left: calc(60% + 4px); width: 12px; height: 5px; background: #f59e0b; border: 2px solid #b45309; border-radius: 2px; z-index: 2; }
        .submarine-propeller { position: absolute; right: -10px; top: 50%; transform: translateY(-50%); width: 8px; height: 18px; background: #94a3b8; border: 2px solid #475569; border-radius: 4px; }
        .submarine-propeller::after { content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 4px; height: 22px; background: #cbd5e1; border-radius: 2px; animation: spin-propeller 0.15s linear infinite; }
        @keyframes spin-propeller { 0% { transform: translate(-50%, -50%) scaleY(1); } 50% { transform: translate(-50%, -50%) scaleY(0.2); } 100% { transform: translate(-50%, -50%) scaleY(1); } }

        .lucide { width: 18px; height: 18px; stroke-width: 2.2; }

        /* Sidebar */
        .sidebar-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); backdrop-filter: blur(2px); z-index: 99; opacity: 0; pointer-events: none; transition: opacity 0.3s; }
        .sidebar-overlay.active { opacity: 1; pointer-events: auto; }
        
        .sidebar {
            position: fixed; top: 0; left: -300px; width: 280px; height: 100dvh;
            background: var(--surface); border-right: 1px solid var(--border);
            z-index: 100; transition: left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex; flex-direction: column; padding: 20px;
            box-shadow: 5px 0 20px rgba(0,0,0,0.2);
        }
        .sidebar.open { left: 0; }
        
        .sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 15px;}
        .sidebar h3 { margin: 0; font-size: 1.1rem; color: var(--text-main); display: flex; align-items: center; gap: 8px;}
        
        .mode-selector { margin: 15px 0; background: var(--card); padding: 10px; border-radius: 12px; border: 1px solid var(--border); }
        .mode-selector label { font-size: 0.85rem; color: var(--text-dim); margin-bottom: 5px; display: block; }
        .mode-selector select {
            width: 100%; background: var(--surface); color: var(--text-main); border: 1px solid var(--border);
            padding: 8px; border-radius: 8px; font-family: 'Tajawal', sans-serif; outline: none; cursor: pointer;
        }

        .chat-history-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
        .history-item {
            background: transparent; border: 1px solid transparent; color: var(--text-main);
            padding: 12px; border-radius: 10px; cursor: pointer; display: flex; align-items: center; gap: 10px;
            font-family: 'Tajawal', sans-serif; font-size: 0.9rem; transition: all 0.2s; text-align: right;
        }
        .history-item:hover { background: var(--card); }
        .history-item.active { background: var(--gradient-1); border: 1px solid var(--primary); color: var(--primary); font-weight: bold; }
        
        .tab-bar { display: flex; background: var(--surface); border-radius: 12px; padding: 4px; border: 1px solid var(--border); flex-shrink: 0; }
        .tab-btn { flex: 1; padding: 10px; background: none; border: none; color: var(--text-dim); font-family: 'Tajawal', sans-serif; font-weight: 700; font-size: 0.95rem; cursor: pointer; border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .tab-btn.active { background: var(--primary); color: white; box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3); }

        .tab-section { display: none; flex-direction: column; gap: 10px; flex: 1; min-height: 0; }
        .tab-section.active { display: flex; }
        
        .card { background: rgba(var(--surface), 0.7); backdrop-filter: blur(10px); border-radius: 16px; border: 1px solid var(--border); padding: 16px; display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }

        .chat-feed {
            display: flex; flex-direction: column; gap: 14px; flex: 1; overflow-y: auto; padding: 10px 4px;
            background: transparent; scroll-behavior: smooth;
        }
        .chat-bubble { padding: 14px 18px; border-radius: 18px; font-size: 0.95rem; line-height: 1.8; max-width: 90%; display: flex; gap: 10px; align-items: flex-start; position: relative; animation: slideUp 0.3s ease-out forwards; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        @keyframes slideUp { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
        .user-bubble { background: linear-gradient(135deg, var(--primary), var(--accent-purple)); color: white; align-self: flex-start; border-bottom-right-radius: 4px; }
        .ai-bubble { background: var(--ai-bubble-bg); color: var(--text-main); align-self: flex-end; border-bottom-left-radius: 4px; border: 1px solid var(--border); flex-direction: row-reverse; backdrop-filter: blur(5px); }
        
        .ai-content { width: 100%; overflow-x: auto; }
        .ai-content h1, .ai-content h2, .ai-content h3 { margin-top: 5px; margin-bottom: 10px; color: var(--accent-purple); }
        .ai-content p { margin: 5px 0; }
        .ai-content strong { color: var(--accent-green); }
        .cursor-blink { animation: blink 1s step-start infinite; color: var(--primary); font-weight: bold; }
        @keyframes blink { 50% { opacity: 0; } }
        
        .copy-btn { position: absolute; bottom: -14px; left: 14px; background: var(--card); color: var(--text-dim); border: 1px solid var(--border); border-radius: 8px; padding: 4px 10px; font-size: 0.75rem; cursor: pointer; display: flex; align-items: center; gap: 4px; transition: all 0.2s; }
        .copy-btn:hover { background: var(--primary); color: white; }

        .bubble-icon { flex-shrink: 0; margin-top: 2px; }

        .chat-input-container { flex-shrink: 0; padding-bottom: env(safe-area-inset-bottom); }
        .input-group { display: flex; flex-direction: column; gap: 6px; }
        textarea { background: var(--card); color: var(--text-main); border: 1px solid var(--border); padding: 12px; border-radius: 12px; font-family: 'Tajawal', sans-serif; font-size: 0.95rem; outline: none; resize: none; max-height: 100px; box-shadow: inset 0 2px 5px rgba(0,0,0,0.05); }

        .btn-controls { display: grid; grid-template-columns: 1fr auto auto; gap: 8px; }
        .btn { background: var(--primary); color: white; border: none; padding: 10px 14px; border-radius: 12px; font-family: 'Tajawal', sans-serif; font-weight: 700; font-size: 0.95rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; transition: transform 0.1s, box-shadow 0.2s; }
        .btn:active { transform: scale(0.96); }
        .btn-purple { background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%); }
        .btn-green { background: var(--accent-green); color: #042f2e; }
        .btn-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); padding: 6px 12px; border-radius: 8px; font-size: 0.85rem;}
        input[type="file"] { display: none; }

        .doc-item { background: var(--card); border-radius: 12px; padding: 14px; border: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
        .doc-header { display: flex; justify-content: space-between; align-items: center; }
        .doc-title { font-weight: 700; font-size: 0.95rem; color: var(--accent-purple); display: flex; align-items: center; gap: 8px;}
        .doc-body { font-size: 0.85rem; color: var(--text-dim); line-height: 1.6; max-height: 120px; overflow-y: auto; background: var(--surface); padding: 10px; border-radius: 8px; white-space: pre-wrap; }

        .spin-icon { animation: spin 1.2s linear infinite; display: inline-block; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.3); border-radius: 10px; }
    </style>
</head>
<body>

    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h3><i data-lucide="menu"></i> القائمة</h3>
            <button class="icon-btn" style="width:30px; height:30px; border:none; background:transparent;" onclick="toggleSidebar()"><i data-lucide="x"></i></button>
        </div>
        
        <button class="btn btn-purple" onclick="createNewChat()" style="margin-bottom: 15px;">
            <i data-lucide="plus-circle"></i> فتح محادثة جديدة
        </button>

        <div class="mode-selector">
            <label><i data-lucide="settings-2" style="width:14px; height:14px;"></i> نمط المساعد الحالي:</label>
            <select id="chatModeSelect" onchange="updateChatMode()">
                <option value="study">🎓 مساعد المنهج (شرح الدروس)</option>
                <option value="general">🌍 محادثة عامة (أسئلة حرة)</option>
            </select>
        </div>

        <h4 style="font-size: 0.85rem; color: var(--text-dim); margin-bottom: 5px;"><i data-lucide="history" style="width:14px; height:14px;"></i> سجل المحادثات:</h4>
        <div class="chat-history-list" id="chatHistoryList"></div>

        <div style="margin-top: auto; padding-top: 15px; border-top: 1px solid var(--border);">
            <button class="btn" style="width: 100%; background: var(--card); color: var(--text-main); border: 1px solid var(--border);" onclick="toggleTheme()">
                <i data-lucide="sun" id="themeIcon"></i> تغيير المظهر
            </button>
        </div>
    </aside>

    <div class="main-wrapper">
        <header class="app-header">
            <div class="header-actions">
                <button class="icon-btn" onclick="toggleSidebar()">
                    <i data-lucide="align-left"></i>
                </button>
                <div class="submarine-logo">
                    ge_nius
                    <div class="submarine-propeller"></div>
                </div>
            </div>
            <span style="font-size: 0.85rem; color: var(--accent-green); display: flex; align-items: center; gap: 5px;" id="docCountBadge">
                <i data-lucide="database"></i> <span>0</span>
            </span>
        </header>

        <div class="tab-bar">
            <button class="tab-btn active" id="btnAskTab" onclick="switchTab('askTab', this)">
                <i data-lucide="message-square"></i> الدردشة
            </button>
            <button class="tab-btn" id="btnDocsTab" onclick="switchTab('docsTab', this)">
                <i data-lucide="folder-open"></i> وثائقي
            </button>
        </div>

        <div class="tab-section active" id="askTab">
            <div class="chat-feed" id="chatFeed"></div>

            <div class="chat-input-container">
                <div class="card" style="margin-top: 0; padding: 12px;">
                    <div id="questionImgPreview" style="display: none; align-items: center; justify-content: space-between; background: rgba(139, 92, 246, 0.15); border: 1px solid var(--accent-purple); padding: 6px 10px; border-radius: 10px; font-size: 0.85rem; color: var(--accent-purple); margin-bottom: 6px;">
                        <span style="display: flex; align-items: center; gap: 6px;"><i data-lucide="image-check" style="width: 16px; height: 16px;"></i> تم الإرفاق</span>
                        <span style="cursor: pointer; color: var(--danger); font-weight: bold; display: flex; align-items: center; gap: 4px;" onclick="removeQuestionImage()">
                            <i data-lucide="x-circle" style="width: 16px; height: 16px;"></i> حذف
                        </span>
                    </div>

                    <div class="input-group">
                        <textarea id="userQuery" placeholder="اكتب سؤالك هنا..." rows="1"></textarea>
                    </div>
                    
                    <div class="btn-controls" style="margin-top: 6px;">
                        <button class="btn btn-green" onclick="submitQuestion()">
                            <i data-lucide="send"></i> إرسال
                        </button>
                        <label for="qFileInputCamera" class="btn btn-purple" title="كاميرا" style="margin:0;">
                            <i data-lucide="camera"></i>
                        </label>
                        <input type="file" id="qFileInputCamera" accept="image/*" capture="environment">

                        <label for="qFileInputGallery" class="btn btn-purple" title="معرض الصور" style="margin:0;">
                            <i data-lucide="image"></i>
                        </label>
                        <input type="file" id="qFileInputGallery" accept="image/*">
                    </div>
                </div>
            </div>
        </div>

        <div class="tab-section" id="docsTab">
            <div class="card">
                <span style="font-weight: 700; font-size: 1rem; color: var(--accent-purple); display: flex; align-items: center; gap: 8px;">
                    <i data-lucide="file-up"></i> رفع درس جديد للمنهج
                </span>
                <p style="font-size: 0.85rem; color: var(--text-dim); margin: 0;">اختر التصوير المباشر لصفحة الدرس أو ارفع عدة صور معاً:</p>
                
                <div style="display: flex; gap: 8px; margin-top: 5px;">
                    <label for="docFileInputCamera" class="btn btn-purple" style="flex: 1; text-align: center; margin:0;">
                        <i data-lucide="camera"></i> كاميرا
                    </label>
                    <input type="file" id="docFileInputCamera" accept="image/*" capture="environment">

                    <label for="docFileInputGallery" class="btn btn-purple" style="flex: 1; text-align: center; margin:0;">
                        <i data-lucide="images"></i> معرض (متعدد)
                    </label>
                    <input type="file" id="docFileInputGallery" accept="image/*" multiple>
                </div>
                
                <div id="uploadStatus" style="display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 0.9rem; margin-top: 10px; font-weight: bold;"></div>
            </div>

            <div class="card" style="flex: 1;">
                <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-dim); display: flex; align-items: center; gap: 8px;">
                    <i data-lucide="archive"></i> الأرشيف و الدروس المحللة:
                </span>
                <div id="docsList" style="display: flex; flex-direction: column; gap: 10px;"></div>
            </div>
        </div>
    </div>

    <script>
        lucide.createIcons();

        const userQuery = document.getElementById('userQuery');
        const chatFeed = document.getElementById('chatFeed');

        userQuery.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });

        userQuery.addEventListener('focus', () => {
            setTimeout(() => { chatFeed.scrollTop = chatFeed.scrollHeight; }, 300);
        });

        function compressImage(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.readAsDataURL(file);
                reader.onload = (event) => {
                    const img = new Image();
                    img.src = event.target.result;
                    img.onload = () => {
                        let width = img.width; let height = img.height;
                        const max_dim = 1024;
                        if (width > max_dim || height > max_dim) {
                            if (width > height) { height = Math.round((height * max_dim) / width); width = max_dim; }
                            else { width = Math.round((width * max_dim) / height); height = max_dim; }
                        }
                        const canvas = document.createElement('canvas');
                        canvas.width = width; canvas.height = height;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, width, height);
                        resolve(canvas.toDataURL('image/jpeg', 0.8));
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
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebarOverlay');
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        }

        let chatSessions = JSON.parse(localStorage.getItem('ge_nius_sessions_v5')) || {};
        let currentSessionId = localStorage.getItem('ge_nius_current_session_v5');
        const modeSelect = document.getElementById('chatModeSelect');

        function initSessions() {
            if (!currentSessionId || !chatSessions[currentSessionId]) {
                createNewChat();
            } else {
                loadChat(currentSessionId);
            }
            renderChatList();
        }

        function createNewChat() {
            const id = Date.now().toString();
            chatSessions[id] = { id: id, title: "محادثة جديدة", html: "", mode: "study" };
            currentSessionId = id;
            saveSessionsData();
            loadChat(id);
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
        }

        function loadChat(id) {
            currentSessionId = id;
            const session = chatSessions[id];
            modeSelect.value = session.mode || 'study';
            
            if (session.html && session.html.trim() !== '') {
                chatFeed.innerHTML = session.html;
            } else {
                chatFeed.innerHTML = `<div id="welcomeMsg" style="color: var(--text-dim); font-style: italic; text-align: center; padding: 20px; display: flex; flex-direction: column; align-items: center; gap: 8px;"><i data-lucide="sparkles" style="width: 32px; height: 32px; color: var(--accent-purple);"></i> ابدأ محادثة جديدة الآن!</div>`;
            }
            
            lucide.createIcons({root: chatFeed});
            if (window.MathJax) MathJax.typesetPromise([chatFeed]);
            setTimeout(() => { chatFeed.scrollTop = chatFeed.scrollHeight; }, 100);
            
            saveSessionsData();
            renderChatList();
        }

        function updateChatMode() {
            chatSessions[currentSessionId].mode = modeSelect.value;
            saveSessionsData();
        }

        function saveCurrentChatHtml(userQueryText = null) {
            const clones = chatFeed.cloneNode(true);
            clones.querySelectorAll('.loading-bubble-temp').forEach(l => l.remove());
            chatSessions[currentSessionId].html = clones.innerHTML;
            
            if (userQueryText && chatSessions[currentSessionId].title === "محادثة جديدة") {
                chatSessions[currentSessionId].title = userQueryText.substring(0, 20) + "...";
            }
            saveSessionsData();
        }

        function saveSessionsData() {
            localStorage.setItem('ge_nius_sessions_v5', JSON.stringify(chatSessions));
            localStorage.setItem('ge_nius_current_session_v5', currentSessionId);
            renderChatList();
        }

        function renderChatList() {
            const listDiv = document.getElementById('chatHistoryList');
            listDiv.innerHTML = '';
            const sortedIds = Object.keys(chatSessions).sort((a, b) => b - a);
            
            sortedIds.forEach(id => {
                const session = chatSessions[id];
                const icon = session.mode === 'general' ? 'globe' : 'graduation-cap';
                const isActive = id === currentSessionId ? 'active' : '';
                
                listDiv.innerHTML += `
                    <div class="history-item ${isActive}" onclick="loadChat('${id}')">
                        <i data-lucide="${icon}" style="width: 16px; height: 16px;"></i>
                        <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${session.title}</span>
                    </div>
                `;
            });
            lucide.createIcons({root: listDiv});
        }

        initSessions();

        window.copyText = function(btn, text) {
            navigator.clipboard.writeText(decodeURIComponent(text)).then(() => {
                const originalHtml = btn.innerHTML;
                btn.innerHTML = `<i data-lucide="check"></i> تم`;
                lucide.createIcons({root: btn});
                setTimeout(() => { btn.innerHTML = originalHtml; lucide.createIcons({root: btn}); }, 2000);
            });
        };

        function showLocalMessage(msg, isWarning = true) {
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();
            const bubble = document.createElement('div');
            bubble.className = 'chat-bubble ai-bubble';
            const icon = isWarning ? 'alert-triangle' : 'info';
            const color = isWarning ? 'var(--danger)' : 'var(--accent-purple)';
            bubble.innerHTML = `<i data-lucide="${icon}" class="bubble-icon" style="color: ${color}"></i> <div>${msg}</div>`;
            chatFeed.appendChild(bubble);
            lucide.createIcons({root: bubble});
            chatFeed.scrollTop = chatFeed.scrollHeight;
            saveCurrentChatHtml();
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

        function fetchDocs() {
            fetch('/api/docs').then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }).catch(err => console.log(err));
        }

        function renderDocs() {
            const listDiv = document.getElementById('docsList');
            const countBadge = document.getElementById('docCountBadge');
            if(countBadge) { countBadge.innerHTML = `<i data-lucide="database" style="width:14px; height:14px;"></i> <span>${curriculumDocs.length}</span>`; lucide.createIcons({root: countBadge}); }
            if (!listDiv) return;
            if (curriculumDocs.length === 0) { listDiv.innerHTML = '<div style="color: var(--text-dim); text-align: center; padding: 10px;">لا توجد وثائق.</div>'; return; }
            listDiv.innerHTML = curriculumDocs.map((item, i) => `
                <div class="doc-item">
                    <div class="doc-header">
                        <span class="doc-title"><i data-lucide="file-text"></i> صفحة ${i + 1}</span>
                        <button class="btn btn-danger" onclick="deleteDoc(${item.id})"><i data-lucide="trash-2" style="width:14px; height:14px;"></i> حذف</button>
                    </div>
                    <div class="doc-body">${item.concepts}</div>
                </div>
            `).join('');
            lucide.createIcons({root: listDiv});
        }

        async function handleQuestionImageSelect(e) {
            const file = e.target.files[0]; if (!file) return;
            try {
                attachedQuestionBase64 = await compressImage(file);
                document.getElementById('questionImgPreview').style.display = 'flex';
            } catch(err) { alert('خطأ في معالجة الصورة'); }
            e.target.value = '';
        }
        document.getElementById('qFileInputCamera').addEventListener('change', handleQuestionImageSelect);
        document.getElementById('qFileInputGallery').addEventListener('change', handleQuestionImageSelect);
        function removeQuestionImage() { attachedQuestionBase64 = null; document.getElementById('questionImgPreview').style.display = 'none'; }

        async function handleDocImageSelect(e) {
            const files = e.target.files; if (!files || files.length === 0) return;
            const statusDiv = document.getElementById('uploadStatus');
            for (let i = 0; i < files.length; i++) {
                if(statusDiv) { statusDiv.innerHTML = `<i data-lucide="loader" class="spin-icon"></i> جاري رفع وضغط ${i + 1}/${files.length}...`; statusDiv.style.color = 'var(--primary)'; lucide.createIcons({root: statusDiv}); }
                try {
                    const compressedBase64 = await compressImage(files[i]);
                    const res = await fetch('/api/docs/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: compressedBase64 }) });
                    const data = await res.json(); 
                    if (data.error) throw new Error(data.error);
                    if (data.docs) curriculumDocs = data.docs;
                } catch (err) {
                    if(statusDiv) { statusDiv.innerHTML = `<i data-lucide="alert-circle"></i> خطأ: ${err.message}`; statusDiv.style.color = 'var(--danger)'; lucide.createIcons({root: statusDiv}); }
                    return;
                }
            }
            renderDocs();
            if(statusDiv) { statusDiv.innerHTML = '<i data-lucide="check-circle-2"></i> اكتمل الرفع بنجاح!'; statusDiv.style.color = 'var(--accent-green)'; lucide.createIcons({root: statusDiv}); }
        }
        document.getElementById('docFileInputCamera').addEventListener('change', handleDocImageSelect);
        document.getElementById('docFileInputGallery').addEventListener('change', handleDocImageSelect);

        function deleteDoc(id) { fetch('/api/docs/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) }).then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }); }

        function submitQuestion() {
            const query = userQuery.value.trim();
            let currentSession = chatSessions[currentSessionId];
            if (!currentSession) { createNewChat(); currentSession = chatSessions[currentSessionId]; }
            const currentMode = currentSession.mode || 'study';

            if (!query && !attachedQuestionBase64) { 
                showLocalMessage('يرجى كتابة سؤالك أو إرفاق صورة أولاً!');
                return; 
            }
            if (currentMode === 'study' && curriculumDocs.length === 0) { 
                showLocalMessage('أنت حالياً في <b>وضع المنهج 🎓</b> ولم تقم برفع أي دروس بعد!<br><br>👉 يرجى رفع دروسك من تبويب "وثائقي" أولاً، أو افتح القائمة الجانبية (☰) وبدّل إلى <b>"محادثة عامة 🌍"</b> لأسألني بحرية.');
                return; 
            }
            
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();

            let userTextDisplay = query.replace(/\n/g, '<br>');
            if (attachedQuestionBase64) { userTextDisplay = (query ? userTextDisplay + '<br>' : '') + '<span style="color:#fbbf24; font-size:0.85em"><i data-lucide="image" style="width:14px;height:14px;"></i> تم إرفاق صورة</span>'; }

            const userBubble = document.createElement('div'); userBubble.className = 'chat-bubble user-bubble';
            userBubble.innerHTML = `<i data-lucide="user" class="bubble-icon"></i> <div>${userTextDisplay}</div>`;
            chatFeed.appendChild(userBubble); lucide.createIcons({root: userBubble});

            const loadingBubble = document.createElement('div'); loadingBubble.className = 'chat-bubble ai-bubble loading-bubble-temp';
            loadingBubble.innerHTML = `<i data-lucide="loader-circle" class="bubble-icon spin-icon"></i> <div class="thinking-text" style="color: var(--accent-purple); font-weight: bold;">أفكر... ⏳</div>`;
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
                    aiBubble.className = 'chat-bubble ai-bubble'; aiBubble.innerHTML = `<i data-lucide="alert-triangle"></i> عذراً، هذا خارج برنامجك الدراسي. بدل للوضع العام من القائمة الجانبية (☰).`;
                    chatFeed.appendChild(aiBubble); lucide.createIcons({root: aiBubble}); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
                } else if (data.status === 'success') {
                    aiBubble.className = 'chat-bubble ai-bubble';
                    aiBubble.innerHTML = `<i data-lucide="bot" class="bubble-icon" style="color: var(--accent-purple)"></i> <div class="ai-content"></div>`;
                    chatFeed.appendChild(aiBubble); lucide.createIcons({root: aiBubble});
                    
                    const contentDiv = aiBubble.querySelector('.ai-content'); const fullText = data.answer;
                    let charIndex = 0; let currentText = '';
                    
                    function typeWriter() {
                        if (charIndex < fullText.length) {
                            currentText += fullText.substring(charIndex, charIndex + 3); charIndex += 3;
                            contentDiv.innerHTML = marked.parse(currentText) + '<span class="cursor-blink"> ▌</span>';
                            chatFeed.scrollTop = chatFeed.scrollHeight;
                            setTimeout(typeWriter, 20);
                        } else {
                            contentDiv.innerHTML = marked.parse(fullText);
                            const encodedAnswer = encodeURIComponent(fullText);
                            aiBubble.insertAdjacentHTML('beforeend', `<button class="copy-btn" onclick="copyText(this, '${encodedAnswer}')"><i data-lucide="copy" style="width:14px;height:14px;"></i> نسخ</button>`);
                            lucide.createIcons({root: aiBubble});
                            if (window.MathJax) window.MathJax.typesetPromise([aiBubble]).catch(e => console.log(e));
                            saveCurrentChatHtml();
                        }
                    }
                    typeWriter();
                } else {
                    aiBubble.className = 'chat-bubble ai-bubble'; aiBubble.innerHTML = `<i data-lucide="alert-circle" class="bubble-icon" style="color: var(--danger)"></i> <div>خطأ: ${data.error}</div>`;
                    chatFeed.appendChild(aiBubble); lucide.createIcons({root: aiBubble}); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
                }
            }).catch(err => {
                chatFeed.removeChild(loadingBubble);
                const errBubble = document.createElement('div'); errBubble.className = 'chat-bubble ai-bubble'; errBubble.innerHTML = `<i data-lucide="wifi-off" class="bubble-icon" style="color: var(--danger)"></i> <div>تعذر الاتصال بالسيرفر.</div>`;
                chatFeed.appendChild(errBubble); lucide.createIcons({root: errBubble}); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# Backend Server (Robust Error & Payload Handling)
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
            self.send_json_response({"error": "الجلسة غير صالحة، يرجى تحديث الصفحة."})
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        req_json = json.loads(post_data.decode('utf-8')) if post_data else {}

        if self.path == "/api/docs/upload":
            image_base64 = req_json.get("image")
            if not image_base64:
                self.send_json_response({"error": "لم يتم إرسال صورة الوثيقة"})
                return
            try:
                prompt = "Read this lesson document image and extract all text, concepts, formulas, and rules in Arabic."
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
                add_document_to_db(session_id, "وثيقة درس", extracted_concepts)
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
                    f"أنت مساعد ذكي ومثقف واسع المعرفة اسمك ge_nius.\n"
                    f"سؤال المستخدم أو طلب الصورة هو: \"{user_query}\"\n\n"
                    f"أجب عن السؤال بأسلوب احترافي، دقيق، وودي باللغة العربية.\n"
                    f"يمكنك الإجابة عن أي سؤال في الثقافة، البرمجة، العلوم، التاريخ، أو مجرد الدردشة.\n\n"
                    f"--- تعليمات التنسيق ---\n"
                    f"- استخدم Markdown لتنظيم الإجابة.\n"
                    f"- استخدم رموز الدولار المفردة ($...$) للمتغيرات والمزدوجة ($$...$$) للمعادلات المستقلة."
                )
            else:
                all_concepts_summary = "\n\n".join([f"الوثيقة {i+1}:\n{doc['concepts']}" for i, doc in enumerate(docs)])
                full_prompt = (
                    f"أنت معلم ومساعد دراسي متخصص.\n"
                    f"إليك المحتوى والمفاهيم التي استخرجت من وثائق دروس الطالب:\n"
                    f"--- بداية المحتوى الدراسي ---\n"
                    f"{all_concepts_summary}\n"
                    f"--- نهاية المحتوى الدراسي ---\n\n"
                    f"سؤال الطالب النصي أو المرفق في الصورة هو: \"{user_query}\"\n\n"
                    f"قم بالتحليل باتباع الخطوات التالية:\n"
                    f"1. فكّر بدقة: هل يرتبط سؤال التمرين بالمحتوى الدراسي المرفوع أعلى بأي شكل؟\n"
                    f"2. إذا كان السؤال عن موضوع مختلف تماماً ولا علاقة له بالدروس المضافة، أجب بالكلمة الحرفية التالية فقط بدون زيادة: OUT_OF_SCOPE\n"
                    f"3. إذا كان ضمن الدروس والمحتوى المرفوع، قدم إجابة شاملة وشارحة خطوة بخطوة باللغة العربية.\n\n"
                    f"--- تعليمات التنسيق للمعادلات ---\n"
                    f"- لكتابة المتغيرات الرياضية داخل النص: يجب استخدام رمز الدولار المفرد حصراً، مثال: $x=2$ أو $v$.\n"
                    f"- لكتابة المعادلات الطويلة: استخدم رمز الدولار المزدوج حصراً، مثال:\n$$ \\vec{{u}} = \\sqrt{{x^2 + y^2}} $$\n"
                    f"- يمكنك استخدام Markdown لتنظيم العناوين الفرعية (بواسطة ###) والقوائم المقطعية (-)."
                )

            if question_image_base64:
                content_payload = [
                    {"type": "text", "text": full_prompt},
                    {"type": "image_url", "image_url": {"url": question_image_base64}}
                ]
            else:
                content_payload = [
                    {"type": "text", "text": full_prompt}
                ]

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
