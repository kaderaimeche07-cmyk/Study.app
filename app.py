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
# [1] إعدادات الاتصال ومفاتيح النظام العالمي
# ==============================================================================
API_KEY = "sk-FWE5lPc8aegQHHJZvk967w"
API_URL = "https://app.ai-grid.io/v1/chat/completions"
PORT = 8080
MODEL_NAME = "Qwen3-30B-A3B-Thinking"

MOCK_DB = {}
MOCK_DB_DOC_ID = 1

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    try:
        return psycopg2.connect(database_url, sslmode='require', connect_timeout=5)
    except Exception as e:
        print(f"Database Connection Error: {e}")
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
        except Exception as e:
            print(f"Load Curriculum DB Error: {e}")
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
        except Exception as e:
            print(f"Add Document DB Error: {e}")
    
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
        except Exception as e:
            print(f"Delete Document DB Error: {e}")
    
    if session_id in MOCK_DB:
        MOCK_DB[session_id] = [d for d in MOCK_DB[session_id] if str(d["id"]) != str(doc_id)]

# ==============================================================================
# [2] واجهة المستخدم العالمية (HTML / CSS / JS المتكاملة والمنظمة بدقة)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ge_nius Assistant - Professional Edition</title>
    
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
            --bg-main: #020617; 
            --surface: #0f172a; 
            --card: #1e293b;
            --primary: #6366f1; 
            --accent-purple: #8b5cf6; 
            --accent-green: #10b981;
            --danger: #ef4444; 
            --text-main: #f8fafc; 
            --text-dim: #94a3b8;
            --border: rgba(255, 255, 255, 0.08); 
            --ai-bubble-bg: rgba(30, 41, 59, 0.85);
            --gradient-1: rgba(99, 102, 241, 0.15); 
            --gradient-2: rgba(139, 92, 246, 0.15);
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
            margin: 0; padding: 0; width: 100vw; height: 100vh; height: 100dvh; overflow: hidden;
            background-image: radial-gradient(circle at 15% 50%, var(--gradient-1), transparent 25%),
                              radial-gradient(circle at 85% 30%, var(--gradient-2), transparent 25%);
            background-attachment: fixed;
        }

        .main-wrapper { 
            padding: 12px; display: flex; flex-direction: column; gap: 12px; 
            width: 100%; height: 100%; height: 100dvh; max-width: 950px; margin: 0 auto; 
        }

        .app-header {
            background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(16px);
            padding: 12px 20px; border-radius: 18px; border: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center;
            flex-shrink: 0; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 10;
        }
        
        .header-actions { display: flex; gap: 12px; align-items: center; }
        
        .icon-btn {
            background: var(--card); border: 1px solid var(--border); color: var(--text-main);
            border-radius: 12px; width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); flex-shrink: 0;
        }
        .icon-btn:hover { background: var(--primary); color: white; transform: translateY(-1px); }

        .submarine-logo {
            position: relative; background: linear-gradient(180deg, #f59e0b, #d97706);
            padding: 6px 20px; border-radius: 40px; border: 2px solid #b45309;
            display: inline-flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 15px rgba(245, 158, 11, 0.3), inset 0 -3px 5px rgba(0,0,0,0.2);
            color: #451a03; font-weight: 900; font-size: 1.2rem; letter-spacing: 1px; font-family: 'Outfit', sans-serif;
        }
        .submarine-logo::before { content: ''; position: absolute; top: -14px; left: 60%; width: 8px; height: 14px; background: #f59e0b; border-left: 2px solid #b45309; border-right: 2px solid #b45309; z-index: 1; }
        .submarine-logo::after { content: ''; position: absolute; top: -14px; left: calc(60% + 4px); width: 14px; height: 6px; background: #f59e0b; border: 2px solid #b45309; border-radius: 2px; z-index: 2; }
        .submarine-propeller { position: absolute; right: -12px; top: 50%; transform: translateY(-50%); width: 8px; height: 20px; background: #94a3b8; border: 2px solid #475569; border-radius: 4px; }
        .submarine-propeller::after { content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 4px; height: 24px; background: #cbd5e1; border-radius: 2px; animation: spin-propeller 0.15s linear infinite; }
        @keyframes spin-propeller { 0% { transform: translate(-50%, -50%) scaleY(1); } 50% { transform: translate(-50%, -50%) scaleY(0.2); } 100% { transform: translate(-50%, -50%) scaleY(1); } }

        .lucide { width: 20px; height: 20px; stroke-width: 2.2; display: inline-block; vertical-align: middle; }

        /* Sidebar & Overlay */
        .sidebar-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); z-index: 999; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; }
        .sidebar-overlay.active { opacity: 1; pointer-events: auto; }
        
        .sidebar {
            position: fixed; top: 0; left: -340px; width: 310px; height: 100vh; height: 100dvh;
            background: var(--surface); border-right: 1px solid var(--border);
            z-index: 1000; transition: left 0.35s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex; flex-direction: column; padding: 24px;
            box-shadow: 15px 0 40px rgba(0,0,0,0.4);
        }
        .sidebar.open { left: 0; }
        
        .sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 15px;}
        .sidebar h3 { margin: 0; font-size: 1.25rem; color: var(--text-main); display: flex; align-items: center; gap: 10px;}
        
        .mode-selector { margin: 15px 0; background: var(--card); padding: 14px; border-radius: 14px; border: 1px solid var(--border); }
        .mode-selector label { font-size: 0.9rem; color: var(--text-dim); margin-bottom: 8px; display: block; font-weight: 600; }
        .mode-selector select {
            width: 100%; background: var(--surface); color: var(--text-main); border: 1px solid var(--border);
            padding: 10px; border-radius: 10px; font-family: 'Tajawal', sans-serif; outline: none; cursor: pointer; font-size: 1rem;
        }

        .chat-history-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-top: 10px; padding-right: 4px; }
        .history-item {
            background: transparent; border: 1px solid transparent; color: var(--text-main);
            padding: 12px 14px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; gap: 12px;
            font-family: 'Tajawal', sans-serif; font-size: 0.95rem; transition: all 0.2s; text-align: right;
        }
        .history-item:hover { background: var(--card); }
        .history-item.active { background: var(--gradient-1); border: 1px solid var(--primary); color: var(--primary); font-weight: bold; }
        
        .tab-bar { display: flex; background: var(--surface); border-radius: 16px; padding: 6px; border: 1px solid var(--border); flex-shrink: 0; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        .tab-btn { flex: 1; padding: 12px; background: none; border: none; color: var(--text-dim); font-family: 'Tajawal', sans-serif; font-weight: 700; font-size: 1rem; cursor: pointer; border-radius: 12px; display: flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.2s; }
        .tab-btn.active { background: var(--primary); color: white; box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4); }

        .tab-section { display: none; flex-direction: column; gap: 12px; flex: 1; min-height: 0; }
        .tab-section.active { display: flex; }
        
        .card { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(12px); border-radius: 20px; border: 1px solid var(--border); padding: 18px; display: flex; flex-direction: column; gap: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); }

        .chat-feed {
            display: flex; flex-direction: column; gap: 16px; flex: 1; overflow-y: auto; padding: 10px 6px;
            background: transparent; scroll-behavior: smooth;
        }
        .chat-bubble { padding: 16px 20px; border-radius: 20px; font-size: 1rem; line-height: 1.8; max-width: 90%; display: flex; gap: 12px; align-items: flex-start; position: relative; animation: slideUp 0.3s cubic-bezier(0.1, 0.9, 0.2, 1) forwards; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }
        @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .user-bubble { background: linear-gradient(135deg, var(--primary), var(--accent-purple)); color: white; align-self: flex-start; border-bottom-right-radius: 4px; }
        .ai-bubble { background: var(--ai-bubble-bg); color: var(--text-main); align-self: flex-end; border-bottom-left-radius: 4px; border: 1px solid var(--border); flex-direction: row-reverse; backdrop-filter: blur(8px); }
        
        .ai-content { width: 100%; overflow-x: auto; }
        .ai-content h1, .ai-content h2, .ai-content h3 { margin-top: 8px; margin-bottom: 12px; color: var(--accent-purple); font-weight: 800; }
        .ai-content p { margin: 8px 0; }
        .ai-content strong { color: var(--accent-green); }
        .cursor-blink { animation: blink 1s step-start infinite; color: var(--primary); font-weight: bold; }
        @keyframes blink { 50% { opacity: 0; } }
        
        .copy-btn { position: absolute; bottom: -16px; left: 16px; background: var(--card); color: var(--text-dim); border: 1px solid var(--border); border-radius: 10px; padding: 5px 12px; font-size: 0.8rem; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.2s; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .copy-btn:hover { background: var(--primary); color: white; }

        .bubble-icon { flex-shrink: 0; margin-top: 3px; }

        .chat-input-container { flex-shrink: 0; }
        .input-group { display: flex; flex-direction: column; gap: 8px; }
        
        textarea { 
            background: var(--card); color: var(--text-main); border: 1px solid var(--border); 
            padding: 14px 16px; border-radius: 16px; font-family: 'Tajawal', sans-serif; 
            font-size: 1rem; outline: none; resize: none; max-height: 130px; 
            box-shadow: inset 0 2px 8px rgba(0,0,0,0.1); line-height: 1.5; width: 100%;
        }

        .btn-controls { display: grid; grid-template-columns: 1fr auto auto; gap: 10px; align-items: center; }
        .btn { background: var(--primary); color: white; border: none; padding: 12px 18px; border-radius: 14px; font-family: 'Tajawal', sans-serif; font-weight: 700; font-size: 1rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.2s; box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3); }
        .btn:active { transform: scale(0.97); }
        .btn-purple { background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%); }
        .btn-green { background: var(--accent-green); color: #042f2e; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3); }
        .btn-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); padding: 8px 14px; border-radius: 10px; font-size: 0.9rem;}
        input[type="file"] { display: none; }

        .doc-item { background: var(--card); border-radius: 16px; padding: 16px; border: 1px solid var(--border); display: flex; flex-direction: column; gap: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        .doc-header { display: flex; justify-content: space-between; align-items: center; }
        .doc-title { font-weight: 700; font-size: 1rem; color: var(--accent-purple); display: flex; align-items: center; gap: 10px;}
        .doc-body { font-size: 0.9rem; color: var(--text-dim); line-height: 1.7; max-height: 140px; overflow-y: auto; background: var(--surface); padding: 12px; border-radius: 12px; white-space: pre-wrap; }

        .spin-icon { animation: spin 1.2s linear infinite; display: inline-block; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.3); border-radius: 10px; }
    </style>
</head>
<body>

    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h3><i data-lucide="menu"></i> القائمة الرئيسية</h3>
            <button class="icon-btn" style="width:38px; height:38px; border:none; background:transparent;" onclick="toggleSidebar()"><i data-lucide="x"></i></button>
        </div>
        
        <button class="btn btn-purple" onclick="createNewChat()" style="margin-bottom: 15px; width: 100%;">
            <i data-lucide="plus-circle"></i> محادثة جديدة
        </button>

        <div class="mode-selector">
            <label><i data-lucide="settings-2" style="width:16px; height:16px;"></i> نمط المساعد الذكي:</label>
            <select id="chatModeSelect" onchange="updateChatMode()">
                <option value="study">🎓 مساعد المنهج (شرح الدروس)</option>
                <option value="general">🌍 محادثة عامة (أسئلة حرة)</option>
            </select>
        </div>

        <h4 style="font-size: 0.9rem; color: var(--text-dim); margin-bottom: 8px;"><i data-lucide="history" style="width:16px; height:16px;"></i> أرشيف المحادثات:</h4>
        <div class="chat-history-list" id="chatHistoryList"></div>

        <div style="margin-top: auto; padding-top: 15px; border-top: 1px solid var(--border);">
            <button class="btn" style="width: 100%; background: var(--card); color: var(--text-main); border: 1px solid var(--border);" onclick="toggleTheme()">
                <i data-lucide="sun" id="themeIcon"></i> تبديل المظهر
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
            <span style="font-size: 0.9rem; color: var(--accent-green); display: flex; align-items: center; gap: 6px; font-weight: 700;" id="docCountBadge">
                <i data-lucide="database"></i> <span>0</span> وثائق
            </span>
        </header>

        <div class="tab-bar">
            <button class="tab-btn active" id="btnAskTab" onclick="switchTab('askTab', this)">
                <i data-lucide="message-square"></i> الدردشة الذكية
            </button>
            <button class="tab-btn" id="btnDocsTab" onclick="switchTab('docsTab', this)">
                <i data-lucide="folder-open"></i> وثائق المنهج
            </button>
        </div>

        <div class="tab-section active" id="askTab">
            <div class="chat-feed" id="chatFeed"></div>

            <div class="chat-input-container">
                <div class="card" style="margin-top: 0; padding: 14px;">
                    <div id="questionImgPreview" style="display: none; align-items: center; justify-content: space-between; background: rgba(139, 92, 246, 0.15); border: 1px solid var(--accent-purple); padding: 8px 12px; border-radius: 12px; font-size: 0.9rem; color: var(--accent-purple); margin-bottom: 8px;">
                        <span style="display: flex; align-items: center; gap: 8px;"><i data-lucide="image-check" style="width: 18px; height: 18px;"></i> تم إرفاق الصورة بنجاح</span>
                        <span style="cursor: pointer; color: var(--danger); font-weight: bold; display: flex; align-items: center; gap: 4px;" onclick="removeQuestionImage()">
                            <i data-lucide="x-circle" style="width: 18px; height: 18px;"></i> إزالة
                        </span>
                    </div>

                    <div class="input-group">
                        <textarea id="userQuery" placeholder="اكتب سؤالك هنا أو ارفع صورة الدرس..." rows="1"></textarea>
                    </div>
                    
                    <div class="btn-controls" style="margin-top: 8px;">
                        <button class="btn btn-green" onclick="submitQuestion()">
                            <i data-lucide="send"></i> إرسال
                        </button>
                        <label for="qFileInputCamera" class="icon-btn btn-purple" title="كاميرا" style="margin:0; width: 44px; height: 44px; border-radius: 14px; background: linear-gradient(135deg, #8b5cf6, #6366f1); color: white; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer;">
                            <i data-lucide="camera"></i>
                        </label>
                        <input type="file" id="qFileInputCamera" accept="image/*" capture="environment">

                        <label for="qFileInputGallery" class="icon-btn btn-purple" title="معرض الصور" style="margin:0; width: 44px; height: 44px; border-radius: 14px; background: linear-gradient(135deg, #8b5cf6, #6366f1); color: white; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer;">
                            <i data-lucide="image"></i>
                        </label>
                        <input type="file" id="qFileInputGallery" accept="image/*">
                    </div>
                </div>
            </div>
        </div>

        <div class="tab-section" id="docsTab">
            <div class="card">
                <span style="font-weight: 700; font-size: 1.05rem; color: var(--accent-purple); display: flex; align-items: center; gap: 10px;">
                    <i data-lucide="file-up"></i> رفع صفحة أو درس جديد للمنهج
                </span>
                <p style="font-size: 0.9rem; color: var(--text-dim); margin: 0;">صور صفحات الكتاب أو ارفع صوراً متعددة لتحليلها وربطها بالمساعد الذكي:</p>
                
                <div style="display: flex; gap: 10px; margin-top: 8px;">
                    <label for="docFileInputCamera" class="btn btn-purple" style="flex: 1; text-align: center; margin:0; padding: 14px; cursor: pointer;">
                        <i data-lucide="camera"></i> تصوير بالكاميرا
                    </label>
                    <input type="file" id="docFileInputCamera" accept="image/*" capture="environment">

                    <label for="docFileInputGallery" class="btn btn-purple" style="flex: 1; text-align: center; margin:0; padding: 14px; cursor: pointer;">
                        <i data-lucide="images"></i> معرض الصور (متعدد)
                    </label>
                    <input type="file" id="docFileInputGallery" accept="image/*" multiple>
                </div>
                
                <div id="uploadStatus" style="display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 0.95rem; margin-top: 10px; font-weight: bold;"></div>
            </div>

            <div class="card" style="flex: 1;">
                <span style="font-weight: 700; font-size: 0.95rem; color: var(--text-dim); display: flex; align-items: center; gap: 10px;">
                    <i data-lucide="archive"></i> الأرشيف والدروس المحللة مسبقاً:
                </span>
                <div id="docsList" style="display: flex; flex-direction: column; gap: 12px; padding-bottom: 20px;"></div>
            </div>
        </div>
    </div>

    <script>
        // تهيئة الأيقونات بأمان تام
        function initIcons() {
            if (window.lucide) {
                lucide.createIcons();
            }
        }
        initIcons();

        const userQuery = document.getElementById('userQuery');
        const chatFeed = document.getElementById('chatFeed');

        userQuery.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });

        userQuery.addEventListener('focus', () => {
            setTimeout(() => { chatFeed.scrollTop = chatFeed.scrollHeight; }, 300);
        });

        userQuery.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); 
                submitQuestion();
            }
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
                        const max_dim = 1200;
                        if (width > max_dim || height > max_dim) {
                            if (width > height) { height = Math.round((height * max_dim) / width); width = max_dim; }
                            else { width = Math.round((width * max_dim) / height); height = max_dim; }
                        }
                        const canvas = document.createElement('canvas');
                        canvas.width = width; canvas.height = height;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, width, height);
                        resolve(canvas.toDataURL('image/jpeg', 0.85));
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
            if(themeIcon) {
                themeIcon.setAttribute('data-lucide', isLight ? 'moon' : 'sun');
                initIcons();
            }
        }
        if (localStorage.getItem('theme') === 'light') { 
            document.body.classList.add('light-mode'); 
            const themeIcon = document.getElementById('themeIcon');
            if(themeIcon) themeIcon.setAttribute('data-lucide', 'moon'); 
            initIcons(); 
        }

        function toggleSidebar() {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebarOverlay');
            if(sidebar && overlay) {
                sidebar.classList.toggle('open');
                overlay.classList.toggle('active');
            }
        }

        let chatSessions = JSON.parse(localStorage.getItem('ge_nius_sessions_v7')) || {};
        let currentSessionId = localStorage.getItem('ge_nius_current_session_v7');
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
            if(modeSelect && session) modeSelect.value = session.mode || 'study';
            
            if (session && session.html && session.html.trim() !== '') {
                chatFeed.innerHTML = session.html;
            } else {
                chatFeed.innerHTML = `<div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 40px 20px; display: flex; flex-direction: column; align-items: center; gap: 12px;"><div class="submarine-logo" style="transform: scale(1.2); margin-bottom:10px;">ge_nius<div class="submarine-propeller"></div></div><h3 style="margin:0; font-weight:700; color:var(--text-main);">كيف يمكنني مساعدتك في دراستك اليوم؟</h3></div>`;
            }
            
            initIcons();
            if (window.MathJax) MathJax.typesetPromise([chatFeed]);
            setTimeout(() => { chatFeed.scrollTop = chatFeed.scrollHeight; }, 100);
            
            saveSessionsData();
            renderChatList();
        }

        function updateChatMode() {
            if(chatSessions[currentSessionId]) {
                chatSessions[currentSessionId].mode = modeSelect.value;
                saveSessionsData();
            }
        }

        function saveCurrentChatHtml(userQueryText = null) {
            if(!chatSessions[currentSessionId]) return;
            const clones = chatFeed.cloneNode(true);
            clones.querySelectorAll('.loading-bubble-temp').forEach(l => l.remove());
            chatSessions[currentSessionId].html = clones.innerHTML;
            
            if (userQueryText && chatSessions[currentSessionId].title === "محادثة جديدة") {
                chatSessions[currentSessionId].title = userQueryText.substring(0, 22) + "...";
            }
            saveSessionsData();
        }

        function saveSessionsData() {
            localStorage.setItem('ge_nius_sessions_v7', JSON.stringify(chatSessions));
            localStorage.setItem('ge_nius_current_session_v7', currentSessionId);
            renderChatList();
        }

        function renderChatList() {
            const listDiv = document.getElementById('chatHistoryList');
            if(!listDiv) return;
            listDiv.innerHTML = '';
            const sortedIds = Object.keys(chatSessions).sort((a, b) => b - a);
            
            sortedIds.forEach(id => {
                const session = chatSessions[id];
                const icon = session.mode === 'general' ? 'globe' : 'graduation-cap';
                const isActive = id === currentSessionId ? 'active' : '';
                
                listDiv.innerHTML += `
                    <div class="history-item ${isActive}" onclick="loadChat('${id}')">
                        <i data-lucide="${icon}" style="width: 18px; height: 18px;"></i>
                        <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${session.title}</span>
                    </div>
                `;
            });
            initIcons();
        }

        initSessions();

        window.copyText = function(btn, text) {
            navigator.clipboard.writeText(decodeURIComponent(text)).then(() => {
                const originalHtml = btn.innerHTML;
                btn.innerHTML = `<i data-lucide="check"></i> تم النسخ`;
                initIcons();
                setTimeout(() => { btn.innerHTML = originalHtml; initIcons(); }, 2000);
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
            initIcons();
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
            const targetTab = document.getElementById(tabId);
            if(targetTab) targetTab.classList.add('active');
        }

        function fetchDocs() {
            fetch('/api/docs').then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }).catch(err => console.log(err));
        }

        function renderDocs() {
            const listDiv = document.getElementById('docsList');
            const countBadge = document.getElementById('docCountBadge');
            if(countBadge) { 
                countBadge.innerHTML = `<i data-lucide="database" style="width:16px; height:16px;"></i> <span>${curriculumDocs.length}</span> وثائق`; 
                initIcons(); 
            }
            if (!listDiv) return;
            if (curriculumDocs.length === 0) { 
                listDiv.innerHTML = '<div style="color: var(--text-dim); text-align: center; padding: 20px;">لم تقم برفع أي وثائق أو دروس بعد.</div>'; 
                return; 
            }
            listDiv.innerHTML = curriculumDocs.map((item, i) => `
                <div class="doc-item">
                    <div class="doc-header">
                        <span class="doc-title"><i data-lucide="file-text"></i> درس رقم ${i + 1}</span>
                        <button class="btn btn-danger" onclick="deleteDoc(${item.id})"><i data-lucide="trash-2" style="width:14px; height:14px;"></i> حذف</button>
                    </div>
                    <div class="doc-body">${item.concepts}</div>
                </div>
            `).join('');
            initIcons();
        }

        async function handleQuestionImageSelect(e) {
            const file = e.target.files[0]; if (!file) return;
            try {
                attachedQuestionBase64 = await compressImage(file);
                const preview = document.getElementById('questionImgPreview');
                if(preview) preview.style.display = 'flex';
            } catch(err) { alert('فشل معالجة الصورة المرفقة'); }
            e.target.value = '';
        }
        const qCam = document.getElementById('qFileInputCamera');
        const qGal = document.getElementById('qFileInputGallery');
        if(qCam) qCam.addEventListener('change', handleQuestionImageSelect);
        if(qGal) qGal.addEventListener('change', handleQuestionImageSelect);
        
        function removeQuestionImage() { 
            attachedQuestionBase64 = null; 
            const preview = document.getElementById('questionImgPreview');
            if(preview) preview.style.display = 'none'; 
        }

        async function handleDocImageSelect(e) {
            const files = e.target.files; if (!files || files.length === 0) return;
            const statusDiv = document.getElementById('uploadStatus');
            for (let i = 0; i < files.length; i++) {
                if(statusDiv) { 
                    statusDiv.innerHTML = `<i data-lucide="loader" class="spin-icon"></i> جاري معالجة ورفع الملف ${i + 1}/${files.length}...`; 
                    statusDiv.style.color = 'var(--primary)'; 
                    initIcons(); 
                }
                try {
                    const compressedBase64 = await compressImage(files[i]);
                    const res = await fetch('/api/docs/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: compressedBase64 }) });
                    const data = await res.json(); 
                    if (data.error) throw new Error(data.error);
                    if (data.docs) curriculumDocs = data.docs;
                } catch (err) {
                    if(statusDiv) { 
                        statusDiv.innerHTML = `<i data-lucide="alert-circle"></i> خطأ بالرفع: ${err.message}`; 
                        statusDiv.style.color = 'var(--danger)'; 
                        initIcons(); 
                    }
                    return;
                }
            }
            renderDocs();
            if(statusDiv) { 
                statusDiv.innerHTML = '<i data-lucide="check-circle-2"></i> تم رفع وتحليل الوثائق بنجاح!'; 
                statusDiv.style.color = 'var(--accent-green)'; 
                initIcons(); 
            }
        }
        const dCam = document.getElementById('docFileInputCamera');
        const dGal = document.getElementById('docFileInputGallery');
        if(dCam) dCam.addEventListener('change', handleDocImageSelect);
        if(dGal) dGal.addEventListener('change', handleDocImageSelect);

        function deleteDoc(id) { 
            fetch('/api/docs/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) })
            .then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }); 
        }

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
                showLocalMessage('أنت حالياً في <b>وضع المنهج 🎓</b> ولم تقم برفع أي دروس بعد!<br><br>👉 يرجى رفع دروسك من تبويب "وثائق المنهج" أولاً، أو افتح القائمة الجانبية (☰) وبدّل إلى <b>"محادثة عامة 🌍"</b> للدردشة بحرية.');
                return; 
            }
            
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();

            let userTextDisplay = query.replace(/\n/g, '<br>');
            if (attachedQuestionBase64) { userTextDisplay = (query ? userTextDisplay + '<br>' : '') + '<span style="color:#fbbf24; font-size:0.85em"><i data-lucide="image" style="width:14px;height:14px;"></i> صورة مرفقة</span>'; }

            const userBubble = document.createElement('div'); userBubble.className = 'chat-bubble user-bubble';
            userBubble.innerHTML = `<i data-lucide="user" class="bubble-icon"></i> <div>${userTextDisplay}</div>`;
            chatFeed.appendChild(userBubble); initIcons();

            const loadingBubble = document.createElement('div'); loadingBubble.className = 'chat-bubble ai-bubble loading-bubble-temp';
            loadingBubble.innerHTML = `<i data-lucide="loader-circle" class="bubble-icon spin-icon"></i> <div class="thinking-text" style="color: var(--accent-purple); font-weight: bold;">جاري معالجة الإجابة... ⏳</div>`;
            chatFeed.appendChild(loadingBubble); initIcons();
            
            saveCurrentChatHtml(query);

            const payload = { query: query, image: attachedQuestionBase64, mode: currentMode };
            userQuery.value = ''; userQuery.style.height = 'auto'; removeQuestionImage(); chatFeed.scrollTop = chatFeed.scrollHeight;

            fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            .then(res => res.json())
            .then(data => {
                chatFeed.removeChild(loadingBubble);
                const aiBubble = document.createElement('div');

                if (data.status === 'out_of_scope') {
                    aiBubble.className = 'chat-bubble ai-bubble'; aiBubble.innerHTML = `<i data-lucide="alert-triangle"></i> عذراً، هذا السؤال خارج نطاق المنهج الدراسي المرفوع. يمكنك التبديل إلى "محادثة عامة" من القائمة الجانبية (☰).`;
                    chatFeed.appendChild(aiBubble); initIcons(); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
                } else if (data.status === 'success') {
                    aiBubble.className = 'chat-bubble ai-bubble';
                    aiBubble.innerHTML = `<i data-lucide="bot" class="bubble-icon" style="color: var(--accent-purple)"></i> <div class="ai-content"></div>`;
                    chatFeed.appendChild(aiBubble); initIcons();
                    
                    const contentDiv = aiBubble.querySelector('.ai-content'); const fullText = data.answer;
                    let charIndex = 0; let currentText = '';
                    
                    function typeWriter() {
                        if (charIndex < fullText.length) {
                            currentText += fullText.substring(charIndex, charIndex + 3); charIndex += 3;
                            contentDiv.innerHTML = marked.parse(currentText) + '<span class="cursor-blink"> ▌</span>';
                            chatFeed.scrollTop = chatFeed.scrollHeight;
                            setTimeout(typeWriter, 15);
                        } else {
                            contentDiv.innerHTML = marked.parse(fullText);
                            const encodedAnswer = encodeURIComponent(fullText);
                            aiBubble.insertAdjacentHTML('beforeend', `<button class="copy-btn" onclick="copyText(this, '${encodedAnswer}')"><i data-lucide="copy" style="width:14px;height:14px;"></i> نسخ</button>`);
                            initIcons();
                            if (window.MathJax) window.MathJax.typesetPromise([aiBubble]).catch(e => console.log(e));
                            saveCurrentChatHtml();
                        }
                    }
                    typeWriter();
                } else {
                    aiBubble.className = 'chat-bubble ai-bubble'; aiBubble.innerHTML = `<i data-lucide="alert-circle" class="bubble-icon" style="color: var(--danger)"></i> <div>خطأ في الاتصال بالذكاء الاصطناعي: ${data.error}</div>`;
                    chatFeed.appendChild(aiBubble); initIcons(); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
                }
            }).catch(err => {
                chatFeed.removeChild(loadingBubble);
                const errBubble = document.createElement('div'); errBubble.className = 'chat-bubble ai-bubble'; errBubble.innerHTML = `<i data-lucide="wifi-off" class="bubble-icon" style="color: var(--danger)"></i> <div>فشل الاتصال بالخادم. تحقق من الإنترنت.</div>`;
                chatFeed.appendChild(errBubble); initIcons(); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# [3] خادم بايثون الخلفي (Python Backend Server)
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
            self.send_json_response({"error": "انتهت صلاحية الجلسة، يرجى تحديث الصفحة."})
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        req_json = json.loads(post_data.decode('utf-8')) if post_data else {}

        if self.path == "/api/docs/upload":
            image_base64 = req_json.get("image")
            if not image_base64:
                self.send_json_response({"error": "لم يتم العثور على صورة الوثيقة"})
                return
            try:
                prompt = "Read this lesson document image and extract all text, concepts, formulas, and rules in Arabic clearly."
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
                add_document_to_db(session_id, "وثيقة درس تعليمي", extracted_concepts)
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
                    f"أنت مساعد ذكي ومثقف عالمي واسع المعرفة اسمك ge_nius.\n"
                    f"سؤال المستخدم أو طلب الصورة هو: \"{user_query}\"\n\n"
                    f"أجب عن السؤال بأسلوب احترافي، دقيق، وودي باللغة العربية.\n"
                    f"يمكنك الإجابة عن أي سؤال في الثقافة، البرمجة، العلوم، التاريخ، أو مجرد الدردشة العامة.\n\n"
                    f"--- تعليمات التنسيق الاحترافي ---\n"
                    f"- استخدم Markdown لتنظيم الإجابة بشكل جميل.\n"
                    f"- استخدم رموز الدولار المفردة ($...$) للمتغيرات والمزدوجة ($$...$$) للمعادلات الرياضية المستقلة."
                )
            else:
                all_concepts_summary = "\n\n".join([f"الوثيقة {i+1}:\n{doc['concepts']}" for i, doc in enumerate(docs)])
                full_prompt = (
                    f"أنت معلم ومساعد دراسي عالمي متخصص.\n"
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
                    f"- يمكنك استخدام Markdown لتنظيم العناوين الفرعية (بواسطة ###) والقوائم (-) لتكون الإجابة عالمية وواضحة."
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
    print(f"Professional Global server started on port {port}")
    server.serve_forever()
