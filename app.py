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
# AI API Key & Global High-Performance Servers Configuration
# ==============================================================================
API_KEY = "sk-FWE5lPc8aegQHHJZvk967w"
API_URL = "https://app.ai-grid.io/v1/chat/completions"
PORT = 8080

MODEL_NAME = "Qwen3-30B-A3B-Thinking"

# ==============================================================================
# Database & Session Management
# ==============================================================================
MOCK_DB = {}
MOCK_DB_DOC_ID = 1

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    try:
        return psycopg2.connect(database_url, sslmode='require', connect_timeout=5)
    except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
            pass
    
    if session_id in MOCK_DB:
        MOCK_DB[session_id] = [d for d in MOCK_DB[session_id] if str(d["id"]) != str(doc_id)]

# ==============================================================================
# HTML Frontend (World-Class Professional UI - English Edition)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ge_nius Assistant - Pro Edition</title>
    
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
            --bg-main: #0c0a09; 
            --surface: #1c1917; 
            --card: #292524;
            --primary: #3b82f6; 
            --accent-purple: #8b5cf6; 
            --accent-green: #10b981;
            --danger: #ef4444; 
            --text-main: #f5f5f4; 
            --text-dim: #a8a29e;
            --border: rgba(255, 255, 255, 0.08); 
            --ai-bubble-bg: #1e1b18;
        }

        body.light-mode {
            --bg-main: #f8fafc; --surface: #ffffff; --card: #f1f5f9;
            --primary: #2563eb; --text-main: #0f172a; --text-dim: #475569;
            --border: rgba(0, 0, 0, 0.08); --ai-bubble-bg: #ffffff;
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        html, body {
            font-family: 'Inter', sans-serif; 
            background-color: var(--bg-main); color: var(--text-main);
            margin: 0; padding: 0; width: 100vw; height: 100vh; height: 100dvh; overflow: hidden;
            background-image: radial-gradient(circle at 10% 20%, rgba(120, 53, 15, 0.12), transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(59, 130, 246, 0.08), transparent 40%);
            background-attachment: fixed;
        }

        .main-wrapper { 
            padding: 12px; display: flex; flex-direction: column; gap: 12px; 
            width: 100%; height: 100%; height: 100dvh; max-width: 950px; margin: 0 auto; 
        }

        .app-header {
            background: rgba(28, 25, 23, 0.85); backdrop-filter: blur(16px);
            padding: 12px 20px; border-radius: 18px; border: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center;
            flex-shrink: 0; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 10;
        }
        
        .header-actions { display: flex; gap: 12px; align-items: center; }
        
        .icon-btn {
            background: var(--card); border: 1px solid var(--border); color: var(--text-main);
            border-radius: 12px; width: 42px; height: 42px; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); flex-shrink: 0;
        }
        .icon-btn:hover { background: var(--primary); color: white; transform: translateY(-1px); }

        /* الغواصة باللون الأزرق الملكي */
        .submarine-logo {
            position: relative; background: linear-gradient(180deg, #3b82f6, #1d4ed8);
            padding: 6px 20px; border-radius: 40px; border: 2px solid #1e40af;
            display: inline-flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.35), inset 0 -3px 5px rgba(0,0,0,0.2);
            color: #ffffff; font-weight: 900; font-size: 1.15rem; letter-spacing: 1px; font-family: 'Outfit', sans-serif;
        }
        .submarine-logo::before { content: ''; position: absolute; top: -14px; left: 60%; width: 8px; height: 14px; background: #3b82f6; border-left: 2px solid #1e40af; border-right: 2px solid #1e40af; z-index: 1; }
        .submarine-logo::after { content: ''; position: absolute; top: -14px; left: calc(60% + 4px); width: 14px; height: 6px; background: #3b82f6; border: 2px solid #1e40af; border-radius: 2px; z-index: 2; }
        .submarine-propeller { position: absolute; right: -12px; top: 50%; transform: translateY(-50%); width: 8px; height: 20px; background: #93c5fd; border: 2px solid #1d4ed8; border-radius: 4px; }
        .submarine-propeller::after { content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 4px; height: 24px; background: #ffffff; border-radius: 2px; animation: spin-propeller 0.15s linear infinite; }
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
        .mode-selector label { font-size: 0.85rem; color: var(--text-dim); margin-bottom: 8px; display: block; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        .mode-selector select {
            width: 100%; background: var(--surface); color: var(--text-main); border: 1px solid var(--border);
            padding: 10px; border-radius: 10px; font-family: 'Inter', sans-serif; outline: none; cursor: pointer; font-size: 0.95rem;
        }

        .nav-menu-links { display: flex; flex-direction: column; gap: 8px; margin-bottom: 15px; }
        .nav-link-btn {
            background: var(--card); border: 1px solid var(--border); color: var(--text-main);
            padding: 12px 14px; border-radius: 12px; font-weight: 600; font-size: 0.95rem; cursor: pointer;
            display: flex; align-items: center; gap: 12px; transition: all 0.2s; text-align: left;
        }
        .nav-link-btn:hover { background: var(--primary); color: white; border-color: var(--primary); }

        .chat-history-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; margin-top: 5px; padding-right: 4px; }
        .history-item {
            background: transparent; border: 1px solid transparent; color: var(--text-main);
            padding: 10px 12px; border-radius: 10px; cursor: pointer; display: flex; align-items: center; gap: 10px;
            font-family: 'Inter', sans-serif; font-size: 0.9rem; transition: all 0.2s; text-align: left;
        }
        .history-item:hover { background: var(--card); }
        .history-item.active { background: rgba(59, 130, 246, 0.15); border: 1px solid var(--primary); color: var(--primary); font-weight: bold; }

        .tab-section { display: none; flex-direction: column; gap: 12px; flex: 1; min-height: 0; }
        .tab-section.active { display: flex; }
        
        .card { background: rgba(28, 25, 23, 0.85); backdrop-filter: blur(12px); border-radius: 20px; border: 1px solid var(--border); padding: 18px; display: flex; flex-direction: column; gap: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); }

        .chat-feed {
            display: flex; flex-direction: column; gap: 16px; flex: 1; overflow-y: auto; padding: 10px 6px;
            background: transparent; scroll-behavior: smooth;
        }
        .chat-bubble { padding: 16px 20px; border-radius: 20px; font-size: 1rem; line-height: 1.8; max-width: 90%; display: flex; gap: 12px; align-items: flex-start; position: relative; animation: slideUp 0.3s cubic-bezier(0.1, 0.9, 0.2, 1) forwards; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }
        @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .user-bubble { background: linear-gradient(135deg, var(--primary), var(--accent-purple)); color: white; align-self: flex-start; border-bottom-right-radius: 4px; }
        .ai-bubble { background: var(--ai-bubble-bg); color: var(--text-main); align-self: flex-end; border-bottom-left-radius: 4px; border: 1px solid var(--border); backdrop-filter: blur(8px); }
        .out-of-scope-bubble { background: rgba(239, 68, 68, 0.15); color: #fca5a5; border: 1px solid var(--danger); align-self: center; text-align: center; font-size: 0.9rem; }
        
        .ai-content { width: 100%; overflow-x: auto; }
        .ai-content h1, .ai-content h2, .ai-content h3 { margin-top: 8px; margin-bottom: 12px; color: #60a5fa; font-weight: 800; }
        .ai-content p { margin: 8px 0; }
        .ai-content strong { color: #34d399; }
        .cursor-blink { animation: blink 1s step-start infinite; color: var(--primary); font-weight: bold; }
        @keyframes blink { 50% { opacity: 0; } }
        
        .copy-btn { position: absolute; bottom: -16px; left: 16px; background: var(--card); color: var(--text-dim); border: 1px solid var(--border); border-radius: 10px; padding: 5px 12px; font-size: 0.8rem; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.2s; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .copy-btn:hover { background: var(--primary); color: white; }

        .bubble-icon { flex-shrink: 0; margin-top: 3px; }

        /* إطار الكتابة الأنيق على غرار ChatGPT */
        .chat-input-container { flex-shrink: 0; }
        .chat-input-box {
            background: var(--card); border: 1px solid var(--border); border-radius: 18px; padding: 12px 16px;
            display: flex; flex-direction: column; gap: 10px; box-shadow: 0 8px 30px rgba(0,0,0,0.2);
            transition: border-color 0.2s;
        }
        .chat-input-box:focus-within { border-color: var(--primary); }

        textarea {
            background: transparent; color: var(--text-main); border: none; outline: none;
            font-family: 'Inter', sans-serif; font-size: 1rem; resize: none; max-height: 130px; min-height: 24px; line-height: 1.5; width: 100%;
        }

        .image-preview-bar {
            display: none; align-items: center; justify-content: space-between; background: rgba(59, 130, 246, 0.15);
            border: 1px solid var(--primary); padding: 8px 12px; border-radius: 10px; font-size: 0.9rem; color: #93c5fd;
        }

        .input-actions-bar { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 10px; }
        .input-left-tools { display: flex; gap: 8px; align-items: center; }

        .tool-btn {
            background: transparent; border: none; color: var(--text-dim); border-radius: 10px; width: 38px; height: 38px;
            display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s;
        }
        .tool-btn:hover { background: var(--surface); color: var(--text-main); }

        .send-btn {
            background: var(--primary); color: white; border: none; border-radius: 12px; width: 40px; height: 40px;
            display: flex; align-items: center; justify-content: center; cursor: pointer; transition: transform 0.1s;
        }
        .send-btn:active { transform: scale(0.95); }

        .btn { background: var(--primary); color: white; border: none; padding: 12px 18px; border-radius: 14px; font-family: 'Inter', sans-serif; font-weight: 700; font-size: 1rem; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.2s; box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3); }
        .btn-purple { background: linear-gradient(135deg, #8b5cf6, #3b82f6); }
        .btn-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); padding: 8px 14px; border-radius: 10px; font-size: 0.9rem;}
        input[type="file"] { display: none; }

        .doc-item { background: var(--card); border-radius: 16px; padding: 16px; border: 1px solid var(--border); display: flex; flex-direction: column; gap: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        .doc-header { display: flex; justify-content: space-between; align-items: center; }
        .doc-title { font-weight: 700; font-size: 1rem; color: #60a5fa; display: flex; align-items: center; gap: 10px;}
        .doc-body { font-size: 0.9rem; color: var(--text-dim); line-height: 1.7; max-height: 140px; overflow-y: auto; background: var(--surface); padding: 12px; border-radius: 12px; white-space: pre-wrap; }

        .spin-icon { animation: spin 1.2s linear infinite; display: inline-block; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        .status-msg { display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 0.95rem; font-weight: bold;}
    </style>
</head>
<body>

    <!-- القائمة الجانبية الاحترافية -->
    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h3><i data-lucide="menu"></i> Navigation</h3>
            <button class="icon-btn" style="width:36px; height:36px; border:none; background:transparent;" onclick="toggleSidebar()"><i data-lucide="x"></i></button>
        </div>
        
        <button class="btn" onclick="createNewChatSession()" style="width: 100%; justify-content: center; margin-bottom: 12px;">
            <i data-lucide="plus-circle"></i> New Chat Session
        </button>

        <div class="nav-menu-links">
            <button class="nav-link-btn" onclick="switchSection('askTab', this)">
                <i data-lucide="message-square-text"></i> Smart Chat
            </button>
            <button class="nav-link-btn" onclick="switchSection('docsTab', this)">
                <i data-lucide="folder-kanban"></i> Curriculum Documents
            </button>
        </div>

        <div class="mode-selector">
            <label><i data-lucide="sliders" style="width:14px; height:14px;"></i> Assistant Mode:</label>
            <select id="chatModeSelect" onchange="updateChatMode()">
                <option value="study">🎓 Study Material (Curriculum Focus)</option>
                <option value="general">🌍 General Chat (Open AI)</option>
            </select>
        </div>

        <h4 style="font-size: 0.85rem; color: var(--text-dim); margin: 10px 0 6px; text-transform: uppercase; letter-spacing: 0.5px;"><i data-lucide="history" style="width:14px; height:14px;"></i> Chat History:</h4>
        <div class="chat-history-list" id="chatHistoryList"></div>

        <div style="margin-top: auto; padding-top: 15px; border-top: 1px solid var(--border);">
            <button class="btn" style="width: 100%; background: var(--card); color: var(--text-main); border: 1px solid var(--border);" onclick="toggleTheme()">
                <i data-lucide="sun" id="themeIcon"></i> Toggle Theme
            </button>
        </div>
    </aside>

    <div class="main-wrapper">
        <header class="app-header">
            <div class="header-actions">
                <button class="icon-btn" onclick="toggleSidebar()" title="Open Menu">
                    <i data-lucide="align-right"></i>
                </button>
                <div class="submarine-logo">
                    ge_nius
                    <div class="submarine-propeller"></div>
                </div>
            </div>
            
            <!-- مؤشر الوثائق الاحترافي العصري -->
            <div style="display: flex; align-items: center; gap: 8px; background: var(--card); padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);">
                <i data-lucide="database" style="width: 16px; height: 16px; color: var(--accent-green);"></i>
                <span style="font-size: 0.85rem; font-weight: 700; color: var(--text-main);" id="docCountBadge">0 Docs</span>
            </div>
        </header>

        <!-- TAB 1: Smart Chat -->
        <div class="tab-section active" id="askTab">
            <div class="chat-feed" id="chatFeed">
                <div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 40px 20px; display: flex; flex-direction: column; align-items: center; gap: 12px;">
                    <i data-lucide="sparkles" style="width: 36px; height: 36px; color: var(--primary);"></i>
                    <h3 style="margin: 0; color: var(--text-main); font-weight: 700;">How can I help you today?</h3>
                    <p style="margin: 0; font-size: 0.9rem;">Upload your study materials in the curriculum tab or switch to General Chat.</p>
                </div>
            </div>

            <!-- إطار الكتابة الراقي جداً -->
            <div class="chat-input-container">
                <div class="chat-input-box">
                    <div class="image-preview-bar" id="questionImgPreview">
                        <span style="display: flex; align-items: center; gap: 8px;"><i data-lucide="image" style="width: 16px; height: 16px;"></i> Image attached successfully</span>
                        <span style="cursor: pointer; color: #fca5a5; font-weight: bold; display: flex; align-items: center; gap: 4px;" onclick="removeQuestionImage()">
                            <i data-lucide="x" style="width: 16px; height: 16px;"></i> Remove
                        </span>
                    </div>

                    <textarea id="userQuery" placeholder="Message ge_nius..." rows="1" oninput="autoResizeTextarea(this)"></textarea>
                    
                    <div class="input-actions-bar">
                        <div class="input-left-tools">
                            <label for="qFileInputCamera" class="tool-btn" title="Capture Camera">
                                <i data-lucide="camera"></i>
                            </label>
                            <input type="file" id="qFileInputCamera" accept="image/*" capture="environment">

                            <label for="qFileInputGallery" class="tool-btn" title="Upload from Gallery">
                                <i data-lucide="image-plus"></i>
                            </label>
                            <input type="file" id="qFileInputGallery" accept="image/*">
                        </div>

                        <button class="send-btn" onclick="submitQuestion()" title="Send Message">
                            <i data-lucide="send-horizontal" style="width: 18px; height: 18px;"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- TAB 2: Curriculum Documents -->
        <div class="tab-section" id="docsTab">
            <div class="card">
                <span style="font-weight: 700; font-size: 1.05rem; color: #60a5fa; display: flex; align-items: center; gap: 10px;">
                    <i data-lucide="file-up"></i> Upload Study Materials & Curriculum
                </span>
                <p style="font-size: 0.9rem; color: var(--text-dim); margin: 0;">Capture book pages or upload multiple document images to empower your AI tutor:</p>
                
                <div style="display: flex; gap: 10px; margin-top: 8px;">
                    <label for="docFileInputCamera" class="btn btn-purple" style="flex: 1; text-align: center; margin:0; padding: 14px;">
                        <i data-lucide="camera"></i> Live Camera
                    </label>
                    <input type="file" id="docFileInputCamera" accept="image/*" capture="environment">

                    <label for="docFileInputGallery" class="btn btn-purple" style="flex: 1; text-align: center; margin:0; padding: 14px;">
                        <i data-lucide="images"></i> Gallery (Multiple)
                    </label>
                    <input type="file" id="docFileInputGallery" accept="image/*" multiple>
                </div>
                
                <div id="uploadStatus" class="status-msg"></div>
            </div>

            <div class="card" style="flex: 1; overflow-y: auto;">
                <span style="font-weight: 700; font-size: 0.95rem; color: var(--text-dim); display: flex; align-items: center; gap: 10px;">
                    <i data-lucide="archive"></i> Processed Document Archive:
                </span>
                <div id="docsList" style="display: flex; flex-direction: column; gap: 12px; padding-bottom: 20px;"></div>
            </div>
        </div>
    </div>

    <script>
        lucide.createIcons();

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

        function switchSection(sectionId, btnElement) {
            document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
            document.getElementById(sectionId).classList.add('active');
            toggleSidebar();
        }

        function autoResizeTextarea(el) {
            el.style.height = 'auto';
            el.style.height = (el.scrollHeight) + 'px';
        }

        // إدارة جلسات مستقلة وخاصة لكل مستخدم
        let chatSessions = JSON.parse(localStorage.getItem('ge_nius_sessions_pro')) || {};
        let currentSessionId = localStorage.getItem('ge_nius_current_session_pro');
        const chatFeed = document.getElementById('chatFeed');
        const modeSelect = document.getElementById('chatModeSelect');

        function initSessions() {
            if (!currentSessionId || !chatSessions[currentSessionId]) {
                createNewSessionQuiet();
            } else {
                loadChatSession(currentSessionId);
            }
            renderChatHistoryList();
        }

        function createNewSessionQuiet() {
            const id = Date.now().toString();
            chatSessions[id] = { id: id, title: "New Chat", html: "", mode: "study" };
            currentSessionId = id;
            saveSessionsData();
        }

        function createNewChatSession() {
            createNewSessionQuiet();
            loadChatSession(currentSessionId);
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
        }

        function loadChatSession(id) {
            currentSessionId = id;
            const session = chatSessions[id];
            if(session) modeSelect.value = session.mode || 'study';
            
            if (session && session.html && session.html.trim() !== '') {
                chatFeed.innerHTML = session.html;
            } else {
                chatFeed.innerHTML = `<div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 40px 20px; display: flex; flex-direction: column; align-items: center; gap: 12px;"><i data-lucide="sparkles" style="width: 36px; height: 36px; color: var(--primary);"></i><h3 style="margin: 0; color: var(--text-main); font-weight: 700;">New Chat Session</h3><p style="margin: 0; font-size: 0.9rem;">Ask any question or send your document image.</p></div>`;
            }
            
            lucide.createIcons({root: chatFeed});
            if (window.MathJax) MathJax.typesetPromise([chatFeed]);
            chatFeed.scrollTop = chatFeed.scrollHeight;
            saveSessionsData();
            renderChatHistoryList();
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
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
            
            if (userQueryText && chatSessions[currentSessionId].title === "New Chat") {
                chatSessions[currentSessionId].title = userQueryText.substring(0, 22) + "...";
            }
            saveSessionsData();
        }

        function saveSessionsData() {
            localStorage.setItem('ge_nius_sessions_pro', JSON.stringify(chatSessions));
            localStorage.setItem('ge_nius_current_session_pro', currentSessionId);
            renderChatHistoryList();
        }

        function renderChatHistoryList() {
            const listDiv = document.getElementById('chatHistoryList');
            if(!listDiv) return;
            listDiv.innerHTML = '';
            const sortedIds = Object.keys(chatSessions).sort((a, b) => b - a);
            
            sortedIds.forEach(id => {
                const session = chatSessions[id];
                const icon = session.mode === 'general' ? 'globe' : 'graduation-cap';
                const isActive = id === currentSessionId ? 'active' : '';
                
                listDiv.innerHTML += `
                    <div class="history-item ${isActive}" onclick="loadChatSession('${id}')">
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
                btn.innerHTML = `<i data-lucide="check"></i> Copied`;
                lucide.createIcons({root: btn});
                setTimeout(() => { btn.innerHTML = originalHtml; lucide.createIcons({root: btn}); }, 2000);
            });
        };

        let curriculumDocs = [];
        let attachedQuestionBase64 = null;
        fetchDocs();

        function fetchDocs() {
            fetch('/api/docs').then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }).catch(err => console.log(err));
        }

        function renderDocs() {
            const listDiv = document.getElementById('docsList');
            const countBadge = document.getElementById('docCountBadge');
            if(countBadge) { countBadge.innerHTML = `${curriculumDocs.length} Docs`; }
            if (!listDiv) return;
            if (curriculumDocs.length === 0) { listDiv.innerHTML = '<div style="color: var(--text-dim); font-style: italic; text-align: center; padding: 20px;">No curriculum documents uploaded yet.</div>'; return; }
            listDiv.innerHTML = curriculumDocs.map((item, index) => `
                <div class="doc-item">
                    <div class="doc-header">
                        <span class="doc-title"><i data-lucide="file-text"></i> Document ${index + 1}</span>
                        <button class="btn btn-danger" style="padding: 4px 10px; font-size: 0.8rem;" onclick="deleteDoc(${item.id})"><i data-lucide="trash-2" style="width: 14px; height: 14px;"></i> Delete</button>
                    </div>
                    <div class="doc-body">${item.concepts}</div>
                </div>
            `).join('');
            lucide.createIcons({root: listDiv});
        }

        function handleQuestionImageSelect(e) {
            const file = e.target.files[0]; if (!file) return;
            const reader = new FileReader();
            reader.onload = function(evt) {
                attachedQuestionBase64 = evt.target.result;
                document.getElementById('questionImgPreview').style.display = 'flex';
            };
            reader.readAsDataURL(file); e.target.value = '';
        }
        document.getElementById('qFileInputCamera').addEventListener('change', handleQuestionImageSelect);
        document.getElementById('qFileInputGallery').addEventListener('change', handleQuestionImageSelect);
        function removeQuestionImage() { attachedQuestionBase64 = null; document.getElementById('questionImgPreview').style.display = 'none'; }

        async function handleDocImageSelect(e) {
            const files = e.target.files; if (!files || files.length === 0) return;
            const statusDiv = document.getElementById('uploadStatus');
            for (let i = 0; i < files.length; i++) {
                if(statusDiv) { statusDiv.innerHTML = `<i data-lucide="loader" class="spin-icon"></i> Processing & extracting document ${i + 1} of ${files.length}...`; statusDiv.style.color = 'var(--primary)'; lucide.createIcons({root: statusDiv}); }
                await new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = async function(evt) {
                        try {
                            const res = await fetch('/api/docs/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: evt.target.result }) });
                            const data = await res.json(); if (data.docs) curriculumDocs = data.docs;
                        } catch (err) {} resolve();
                    }; reader.readAsDataURL(files[i]);
                });
            }
            renderDocs();
            if(statusDiv) { statusDiv.innerHTML = '<i data-lucide="check-circle-2"></i> Documents analyzed & saved successfully!'; statusDiv.style.color = 'var(--accent-green)'; lucide.createIcons({root: statusDiv}); }
        }
        document.getElementById('docFileInputCamera').addEventListener('change', handleDocImageSelect);
        document.getElementById('docFileInputGallery').addEventListener('change', handleDocImageSelect);

        function deleteDoc(id) { fetch('/api/docs/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) }).then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }); }

        function submitQuestion() {
            const queryInput = document.getElementById('userQuery');
            const query = queryInput.value.trim();
            const currentSession = chatSessions[currentSessionId];
            if (!currentSession) { createNewChatSession(); return; }
            const currentMode = currentSession.mode || 'study';

            if (!query && !attachedQuestionBase64) { alert('Please type a question or attach an image first!'); return; }
            if (currentMode === 'study' && curriculumDocs.length === 0) { alert('You are in Study mode. Please upload curriculum documents in the menu or switch to General Chat!'); return; }
            
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();

            let userTextDisplay = query.replace(/\\n/g, '<br>');
            if (attachedQuestionBase64) { userTextDisplay = (query ? userTextDisplay + '<br>' : '') + '<span style="color:#60a5fa; font-size:0.85em"><i data-lucide="image" style="width:14px;height:14px;"></i> Image attached</span>'; }

            const userBubble = document.createElement('div'); userBubble.className = 'chat-bubble user-bubble';
            userBubble.innerHTML = `<i data-lucide="user" class="bubble-icon"></i> <div>${userTextDisplay}</div>`;
            chatFeed.appendChild(userBubble); lucide.createIcons({root: userBubble});

            const loadingBubble = document.createElement('div'); loadingBubble.className = 'chat-bubble ai-bubble loading-bubble-temp';
            loadingBubble.innerHTML = `<i data-lucide="loader-circle" class="bubble-icon spin-icon"></i> <div class="thinking-text" style="color: #60a5fa; font-weight: bold;">Thinking & analyzing... ⏳</div>`;
            chatFeed.appendChild(loadingBubble); lucide.createIcons({root: loadingBubble});
            
            saveCurrentChatHtml(query);

            const payload = { query: query, image: attachedQuestionBase64, mode: currentMode };
            queryInput.value = ''; queryInput.style.height = 'auto'; removeQuestionImage(); chatFeed.scrollTop = chatFeed.scrollHeight;

            fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            .then(res => res.json())
            .then(data => {
                chatFeed.removeChild(loadingBubble);
                const aiBubble = document.createElement('div');

                if (data.status === 'out_of_scope') {
                    aiBubble.className = 'chat-bubble out-of-scope-bubble';
                    aiBubble.innerHTML = `<i data-lucide="alert-triangle"></i> Sorry, this question is out of scope for your uploaded curriculum. Switch to General Chat in the menu.`;
                    chatFeed.appendChild(aiBubble); lucide.createIcons({root: aiBubble}); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
                } else if (data.status === 'success') {
                    aiBubble.className = 'chat-bubble ai-bubble';
                    aiBubble.innerHTML = `<i data-lucide="bot" class="bubble-icon" style="color: #60a5fa"></i> <div class="ai-content"></div>`;
                    chatFeed.appendChild(aiBubble); lucide.createIcons({root: aiBubble});
                    
                    const contentDiv = aiBubble.querySelector('.ai-content'); 
                    const fullText = data.answer;
                    let charIndex = 0; 
                    let currentText = '';
                    
                    // ظهور الإجابة ببطء متوسط واحترافي لكي يقرأها المستخدم بسلاسة
                    function typeWriter() {
                        if (charIndex < fullText.length) {
                            currentText += fullText.substring(charIndex, charIndex + 4); 
                            charIndex += 4;
                            contentDiv.innerHTML = marked.parse(currentText) + '<span class="cursor-blink"> ▌</span>';
                            chatFeed.scrollTop = chatFeed.scrollHeight;
                            setTimeout(typeWriter, 18);
                        } else {
                            contentDiv.innerHTML = marked.parse(fullText);
                            const encodedAnswer = encodeURIComponent(fullText);
                            aiBubble.insertAdjacentHTML('beforeend', `<button class="copy-btn" onclick="copyText(this, '${encodedAnswer}')"><i data-lucide="copy" style="width:14px;height:14px;"></i> Copy</button>`);
                            lucide.createIcons({root: aiBubble});
                            if (window.MathJax) window.MathJax.typesetPromise([aiBubble]).catch(e => console.log(e));
                            saveCurrentChatHtml();
                        }
                    }
                    typeWriter();
                } else {
                    aiBubble.className = 'chat-bubble ai-bubble';
                    aiBubble.innerHTML = `<i data-lucide="alert-circle" class="bubble-icon" style="color: var(--danger)"></i> <div>Error: ${data.error || 'Failed to process.'}</div>`;
                    chatFeed.appendChild(aiBubble); lucide.createIcons({root: aiBubble}); chatFeed.scrollTop = chatFeed.scrollHeight; saveCurrentChatHtml();
                }
            }).catch(err => {
                chatFeed.removeChild(loadingBubble);
                const errBubble = document.createElement('div'); errBubble.className = 'chat-bubble ai-bubble';
                errBubble.innerHTML = `<i data-lucide="wifi-off" class="bubble-icon" style="color: var(--danger)"></i> <div>Connection failed. Check your network.</div>`;
                chatFeed.appendChild(errBubble); lucide.createIcons({root: errBubble}); chatFeed.scrollTop = chatFeed.scrollHeight;
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# Python Backend Server
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
        with urllib.request.urlopen(req, context=ssl_ctx) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            return res_json["choices"][0]["message"]["content"].strip()

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
                self.send_json_response({"error": "No image provided"})
                return
            try:
                prompt = "Read this lesson document image and extract all text, concepts, formulas, and rules clearly in English."
                payload = {
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_base64}}]}],
                    "max_tokens": 4096
                }
                extracted_concepts = self.send_api_request(payload)
                add_document_to_db(session_id, "Document Lesson", extracted_concepts)
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

            messages_content = []
            if question_image_base64:
                messages_content.append({"type": "image_url", "image_url": {"url": question_image_base64}})

            if mode == "general":
                full_prompt = (
                    f"You are a highly intelligent and helpful global AI assistant named ge_nius.\n"
                    f"User prompt/image request: \"{user_query}\"\n\n"
                    f"Respond to the question in a professional, accurate, and friendly manner in English.\n"
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
                    f"3. If it is within scope, provide a comprehensive, step-by-step explanation in English.\n\n"
                    f"--- Math Formatting ---\n"
                    f"- For inline variables/math, use single dollar signs strictly, e.g., $x=2$ or $v$.\n"
                    f"- For block equations, use double dollar signs strictly, e.g.,\n$$ \\vec{{u}} = \\sqrt{{x^2 + y^2}} $$\n"
                    f"- Use Markdown for headings (###) and lists (-)."
                )
                
            messages_content.append({"type": "text", "text": full_prompt})

            payload = {
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": messages_content}],
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
