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
import zlib
import base64

# ==============================================================================
# AI API Key & System Config
# ==============================================================================
API_KEY = "sk-FWE5lPc8aegQHHJZvk967w"
API_URL = "https://app.ai-grid.io/v1/chat/completions"
PORT = 8080
MODEL_NAME = "Qwen3-30B-A3B-Thinking"

MOCK_DB = {}
MOCK_DB_DOC_ID = 1

MOCK_USERS = {}      
MOCK_SESSIONS = {}   

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    try:
        return psycopg2.connect(database_url, sslmode='require', connect_timeout=5)
    except Exception as e:
        return None

def compress_file_data(base64_data):
    try:
        header, encoded = base64_data.split(",", 1)
        data = base64.b64decode(encoded)
        compressed = zlib.compress(data, level=9)
        return header, compressed
    except:
        return None, None

def get_current_user(session_id):
    email = MOCK_SESSIONS.get(session_id)
    if email and email in MOCK_USERS:
        return MOCK_USERS[email]
    return None

def load_curriculum(session_id, user=None):
    docs = MOCK_DB.get("GLOBAL_DOCS", []).copy()
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS user_documents (id SERIAL PRIMARY KEY, session_id VARCHAR(255), title TEXT, content TEXT);")
            cur.execute("SELECT id, title, content FROM user_documents WHERE session_id = %s ORDER BY id ASC;", (session_id,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            for r in rows:
                docs.append({"id": r[0], "title": r[1], "concepts": r[2]})
        except Exception as e:
            pass
        finally:
            try: conn.close()
            except: pass
    else:
        docs.extend(MOCK_DB.get(session_id, []))
    return docs

def add_document_to_db(session_id, title, content, is_global=False):
    global MOCK_DB, MOCK_DB_DOC_ID
    if is_global:
        if "GLOBAL_DOCS" not in MOCK_DB:
            MOCK_DB["GLOBAL_DOCS"] = []
        MOCK_DB["GLOBAL_DOCS"].append({"id": MOCK_DB_DOC_ID, "title": title, "concepts": content})
        MOCK_DB_DOC_ID += 1
        return

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
        finally:
            try: conn.close()
            except: pass
    if session_id not in MOCK_DB:
        MOCK_DB[session_id] = []
    MOCK_DB[session_id].append({"id": MOCK_DB_DOC_ID, "title": title, "concepts": content})
    MOCK_DB_DOC_ID += 1

def delete_document_from_db(session_id, doc_id):
    global MOCK_DB
    if "GLOBAL_DOCS" in MOCK_DB:
        MOCK_DB["GLOBAL_DOCS"] = [d for d in MOCK_DB["GLOBAL_DOCS"] if str(d["id"]) != str(doc_id)]
    
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
        finally:
            try: conn.close()
            except: pass
    if session_id in MOCK_DB:
        MOCK_DB[session_id] = [d for d in MOCK_DB[session_id] if str(d["id"]) != str(doc_id)]

# ==============================================================================
# HTML Frontend (Axiom - Ultra Premium UI/UX)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="en" dir="auto">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Axiom | Advanced Intelligence</title>
    
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/lucide@latest"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>

    <script>
      window.MathJax = {
        tex: { inlineMath: [['$', '$']], displayMath: [['$$', '$$']], processEscapes: true },
        options: { skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre'] }
      };
    </script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" id="MathJax-script" async></script>

    <style>
        :root {
            /* Ultra Premium Dark Theme */
            --bg-main: #050505; --surface: #0a0a0a; --card: #121212;
            --primary: #ffffff; --primary-dim: #a1a1aa;
            --accent: #3b82f6; --accent-glow: rgba(59, 130, 246, 0.2);
            --danger: #ef4444; --success: #10b981; --warning: #f59e0b;
            --text-main: #ffffff; --text-dim: #71717a;
            --border: #27272a; --glass: rgba(10, 10, 10, 0.85);
            --font-size-base: 1rem;
        }

        body.light-mode {
            --bg-main: #fafafa; --surface: #ffffff; --card: #f4f4f5;
            --primary: #000000; --primary-dim: #52525b;
            --accent: #2563eb; --accent-glow: rgba(37, 99, 235, 0.15);
            --text-main: #09090b; --text-dim: #71717a;
            --border: #e4e4e7; --glass: rgba(255, 255, 255, 0.85);
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        html, body {
            font-family: 'Inter', sans-serif; 
            background-color: var(--bg-main); color: var(--text-main);
            margin: 0; padding: 0; width: 100vw; height: 100vh; height: 100dvh; overflow: hidden;
            font-size: var(--font-size-base);
            transition: background-color 0.3s, color 0.3s;
        }
        
        body[dir="rtl"] { font-family: 'Inter', sans-serif; }
        body[dir="rtl"] .sidebar { left: auto; right: -100%; border-right: none; border-left: 1px solid var(--border); }
        body[dir="rtl"] .sidebar.open { left: auto; right: 0; }

        .main-wrapper { 
            display: flex; flex-direction: column; 
            width: 100%; height: 100%; max-width: 1000px; margin: 0 auto; 
            position: relative;
        }

        /* --- Auth Screen (Masterpiece) --- */
        .auth-wrapper {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: radial-gradient(circle at 50% 0%, var(--card) 0%, var(--bg-main) 100%);
            z-index: 9999; display: flex; justify-content: center; align-items: center; padding: 20px;
            transition: opacity 0.5s ease;
        }
        .auth-card {
            background: var(--glass); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border); border-radius: 20px;
            padding: 40px 30px; width: 100%; max-width: 420px; 
            box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
            display: flex; flex-direction: column; gap: 20px;
        }
        .auth-logo { font-weight: 700; font-size: 2rem; letter-spacing: -1px; text-align: center; color: var(--primary); margin-bottom: 10px; }
        
        .custom-input, .custom-select {
            width: 100%; background: var(--surface); border: 1px solid var(--border); color: var(--text-main);
            padding: 14px 16px; border-radius: 12px; font-family: inherit; font-size: 0.95rem; outline: none; transition: border 0.2s;
        }
        .custom-input:focus, .custom-select:focus { border-color: var(--accent); }

        .btn-primary {
            background: var(--text-main); color: var(--bg-main); border: none;
            padding: 14px; border-radius: 12px; font-weight: 600; font-size: 0.95rem; 
            cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; transition: opacity 0.2s;
        }
        .btn-primary:hover { opacity: 0.9; }

        /* --- Minimalist Header --- */
        .top-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 16px 20px; flex-shrink: 0; z-index: 10;
        }
        .brand-text { font-weight: 600; font-size: 1.1rem; letter-spacing: -0.5px; display: flex; align-items: center; gap: 8px; }
        .icon-btn { background: transparent; border: none; color: var(--text-dim); border-radius: 8px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; }
        .icon-btn:hover { color: var(--text-main); background: var(--surface); }

        /* --- Sidebar Redesign --- */
        .sidebar-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); z-index: 999; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; }
        .sidebar-overlay.active { opacity: 1; pointer-events: auto; }
        .sidebar { position: fixed; top: 0; left: -100%; width: 280px; height: 100vh; background: var(--surface); border-right: 1px solid var(--border); z-index: 1000; transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); display: flex; flex-direction: column; }
        .sidebar.open { transform: translateX(100%); }
        body[dir="rtl"] .sidebar.open { transform: translateX(-100%); }

        .sb-section-title { font-size: 0.75rem; color: var(--text-dim); font-weight: 600; text-transform: uppercase; letter-spacing: 1px; padding: 0 20px; margin: 24px 0 10px 0; }
        .sb-item { display: flex; align-items: center; gap: 12px; padding: 10px 20px; color: var(--text-dim); text-decoration: none; font-size: 0.9rem; cursor: pointer; transition: 0.2s; border-left: 2px solid transparent;}
        .sb-item:hover { color: var(--text-main); background: var(--card); }
        .sb-item.active { color: var(--text-main); background: var(--card); border-left-color: var(--text-main); font-weight: 500;}
        body[dir="rtl"] .sb-item { border-left: none; border-right: 2px solid transparent; }
        body[dir="rtl"] .sb-item.active { border-right-color: var(--text-main); }

        .chat-history-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
        
        .user-profile-bottom { margin-top: auto; border-top: 1px solid var(--border); padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; }
        .user-info { display: flex; flex-direction: column; }
        .user-name { font-weight: 600; font-size: 0.9rem; }
        .user-role { font-size: 0.75rem; color: var(--text-dim); }

        /* --- Chat Interface (Seamless Document Flow) --- */
        .chat-feed { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 30px; scroll-behavior: smooth; }
        
        .msg-block { display: flex; flex-direction: column; gap: 8px; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* User looks like a sleek header */
        .msg-user { align-items: flex-start; margin-top: 10px;}
        .user-label { font-size: 0.8rem; font-weight: 600; color: var(--text-dim); display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
        .msg-user-text { font-size: 1.1rem; font-weight: 500; color: var(--text-main); line-height: 1.5; }

        /* AI looks like document content */
        .msg-ai { padding-left: 24px; border-left: 1px solid var(--border); }
        body[dir="rtl"] .msg-ai { padding-left: 0; padding-right: 24px; border-left: none; border-right: 1px solid var(--border); }
        
        .ai-label { font-size: 0.8rem; font-weight: 600; color: var(--text-main); display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
        .ai-content { font-size: 1rem; line-height: 1.7; color: var(--primary-dim); }
        
        .ai-content pre { background: var(--card); border: 1px solid var(--border); padding: 12px; border-radius: 8px; overflow-x: auto; }
        .ai-content code { font-family: monospace; font-size: 0.9em; }

        .hologram-thinking { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 0.9rem; color: var(--text-dim); animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 0.5; } 50% { opacity: 1; } }

        /* --- Input Area --- */
        .input-wrapper { padding: 0 20px 20px 20px; flex-shrink: 0; }
        .input-box { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 10px 14px; display: flex; align-items: flex-end; gap: 10px; transition: border 0.3s; }
        .input-box:focus-within { border-color: var(--text-dim); }
        
        textarea { background: transparent; color: var(--text-main); border: none; outline: none; font-family: inherit; font-size: 1rem; resize: none; max-height: 150px; min-height: 24px; line-height: 1.5; width: 100%; padding: 4px 0; }
        
        .send-btn { background: var(--text-main); color: var(--bg-main); border: none; border-radius: 10px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: 0.2s; flex-shrink: 0; }
        .send-btn:hover { opacity: 0.8; }
        .send-btn:disabled { opacity: 0.3; cursor: not-allowed; }

        /* --- Modals (Vault & Settings) --- */
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); backdrop-filter: blur(5px); z-index: 9999; display: none; justify-content: center; align-items: center; padding: 20px; opacity: 0; transition: opacity 0.3s; }
        .modal-card { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; width: 100%; max-width: 500px; padding: 24px; position: relative; max-height: 85vh; overflow-y: auto; }
        .modal-close { position: absolute; top: 16px; right: 16px; background: transparent; border: none; color: var(--text-dim); cursor: pointer; }
        body[dir="rtl"] .modal-close { right: auto; left: 16px; }

        /* Vault specifics */
        .drop-zone { border: 2px dashed var(--border); border-radius: 16px; padding: 30px; text-align: center; cursor: pointer; transition: 0.3s; margin-bottom: 16px; background: var(--card); }
        .drop-zone:hover { border-color: var(--text-dim); }
        .doc-item { background: var(--card); border: 1px solid var(--border); padding: 12px 16px; border-radius: 12px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }

        /* Settings specifics */
        .setting-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border); }
        .setting-row:last-child { border-bottom: none; }
        
        .toggle-switch { position: relative; width: 40px; height: 22px; }
        .toggle-switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: var(--border); transition: .4s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: var(--success); }
        input:checked + .slider:before { transform: translateX(18px); }

    </style>
</head>
<body>

    <!-- ================= AUTHENTICATION OVERLAY ================= -->
    <div id="authOverlay" class="auth-wrapper">
        <div class="auth-card">
            <div class="auth-logo">AXIOM</div>
            <p style="text-align: center; color: var(--text-dim); margin-top: -15px; font-size: 0.9rem;" data-i18n="tagline">Intelligence, Structurized.</p>
            
            <div class="role-selector" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                <div class="sb-item active" style="justify-content:center; border: 1px solid var(--border); border-radius:10px; padding: 12px;" onclick="selectRole('student')" id="role-student"><i data-lucide="book-open"></i> <span data-i18n="student">Student</span></div>
                <div class="sb-item" style="justify-content:center; border: 1px solid var(--border); border-radius:10px; padding: 12px;" onclick="selectRole('teacher')" id="role-teacher"><i data-lucide="presentation"></i> <span data-i18n="teacher">Teacher</span></div>
            </div>

            <input type="text" id="authName" class="custom-input" placeholder="Full Name" data-i18n-ph="fullName">
            <input type="email" id="authEmail" class="custom-input" placeholder="Email Address" data-i18n-ph="email">
            <input type="password" id="authPassword" class="custom-input" placeholder="Password" data-i18n-ph="password">
            
            <select id="authLevel" class="custom-select">
                <option value="University" data-i18n="univ">University</option>
                <option value="High School" data-i18n="highSchool">High School</option>
                <option value="Other" data-i18n="other">Other</option>
            </select>

            <button class="btn-primary" onclick="performAuth()"><span data-i18n="enterPlatform">Enter Axiom</span> <i data-lucide="arrow-right" style="width:16px;"></i></button>
            <div id="authError" style="color:var(--danger); font-size:0.85rem; text-align:center;"></div>
        </div>
    </div>

    <!-- ================= SETTINGS MODAL ================= -->
    <div id="settingsModal" class="modal-overlay">
        <div class="modal-card">
            <button class="modal-close" onclick="closeModal('settingsModal')"><i data-lucide="x"></i></button>
            <h3 style="margin-top:0; display:flex; align-items:center; gap:8px;"><i data-lucide="settings"></i> <span data-i18n="settings">Preferences</span></h3>
            
            <div class="setting-row">
                <span><span data-i18n="uiLangLabel">Language</span></span>
                <select id="uiLangSelect" class="custom-select" style="width:auto; padding:6px 12px;" onchange="changeUILanguage()">
                    <option value="en">English</option>
                    <option value="ar">العربية</option>
                    <option value="fr">Français</option>
                </select>
            </div>
            
            <div class="setting-row">
                <span><span data-i18n="aiTemp">AI Creativity</span></span>
                <select id="aiTempSelect" class="custom-select" style="width:auto; padding:6px 12px;" onchange="updateSettings()">
                    <option value="precise" data-i18n="precise">Precise & Strict</option>
                    <option value="balanced" data-i18n="balanced" selected>Balanced</option>
                    <option value="creative" data-i18n="creative">Creative</option>
                </select>
            </div>

            <div class="setting-row">
                <span><span data-i18n="fontSize">Font Size</span></span>
                <select id="fontSizeSelect" class="custom-select" style="width:auto; padding:6px 12px;" onchange="updateSettings()">
                    <option value="14px">Small</option>
                    <option value="16px" selected>Medium</option>
                    <option value="18px">Large</option>
                </select>
            </div>

            <div class="setting-row">
                <span><span data-i18n="autoSpeech">Auto Speech (TTS)</span></span>
                <label class="toggle-switch">
                    <input type="checkbox" id="autoSpeechToggle" onchange="updateSettings()">
                    <span class="slider"></span>
                </label>
            </div>
            
            <div class="setting-row">
                <span><span data-i18n="theme">Theme Mode</span></span>
                <button class="icon-btn" onclick="toggleTheme()" style="border:1px solid var(--border)"><i data-lucide="moon" id="themeIcon"></i></button>
            </div>
        </div>
    </div>

    <!-- ================= KNOWLEDGE VAULT MODAL ================= -->
    <div id="vaultModal" class="modal-overlay">
        <div class="modal-card">
            <button class="modal-close" onclick="closeModal('vaultModal')"><i data-lucide="x"></i></button>
            <h3 style="margin-top:0; display:flex; align-items:center; gap:8px;"><i data-lucide="database"></i> <span data-i18n="vault">Knowledge Vault</span></h3>
            
            <div class="drop-zone" id="dropZone" onclick="document.getElementById('vaultFileInput').click()">
                <i data-lucide="upload-cloud" style="width:32px; height:32px; color:var(--text-dim); margin-bottom:10px;"></i>
                <div style="font-weight:500;" data-i18n="clickOrDrop">Click or Drag & Drop Documents Here</div>
                <div style="font-size:0.8rem; color:var(--text-dim); margin-top:6px;">PDF, DOCX, Images</div>
                <input type="file" id="vaultFileInput" accept=".pdf, .doc, .docx, image/*" multiple style="display:none;" onchange="handleVaultUpload(event)">
            </div>
            <div id="vaultUploadStatus" style="font-size:0.85rem; text-align:center; margin-bottom:15px; font-weight:600;"></div>

            <div id="vaultDocsList" style="max-height: 250px; overflow-y:auto;">
                <!-- Docs list via JS -->
            </div>
            
            <button class="btn-primary" style="width:100%; margin-top:15px;" onclick="closeModal('vaultModal'); triggerSmartSummary()"><i data-lucide="sparkles"></i> <span data-i18n="summarizeAll">Summarize Knowledge</span></button>
        </div>
    </div>

    <!-- ================= SIDEBAR ================= -->
    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <aside class="sidebar" id="sidebar">
        <div style="padding: 20px; font-weight: 700; font-size: 1.2rem; letter-spacing: -1px; border-bottom: 1px solid var(--border);">AXIOM</div>
        
        <div class="sb-item" style="margin-top: 10px;" onclick="createNewChatSession()">
            <i data-lucide="plus-square"></i> <span data-i18n="newChat">New Chat</span>
        </div>

        <div class="sb-section-title" data-i18n="workspaces">Workspaces</div>
        <div class="sb-item active" id="ws-general" onclick="switchWorkspace('general')"><i data-lucide="cpu"></i> <span data-i18n="general">General</span></div>
        <div class="sb-item" id="ws-study" onclick="switchWorkspace('study')"><i data-lucide="book-open"></i> <span data-i18n="study">Study / Curriculum</span></div>
        <div class="sb-item" id="ws-games" onclick="switchWorkspace('games')"><i data-lucide="gamepad-2"></i> <span data-i18n="games">Brain Games</span></div>

        <div class="sb-section-title" data-i18n="history">History</div>
        <div class="chat-history-list" id="chatHistoryList"></div>

        <div class="user-profile-bottom">
            <div class="user-info">
                <span class="user-name" id="sidebarUserName">User</span>
                <span class="user-role" id="sidebarRoleLabel">Role</span>
            </div>
            <button class="icon-btn" onclick="performLogout()" title="Logout"><i data-lucide="log-out"></i></button>
        </div>
    </aside>

    <!-- ================= MAIN CONTENT ================= -->
    <div class="main-wrapper">
        
        <header class="top-header">
            <div class="brand-text">
                <button class="icon-btn" onclick="toggleSidebar()"><i data-lucide="menu"></i></button>
                AXIOM
            </div>
            <div style="display:flex; gap:10px;">
                <button class="icon-btn" onclick="openModal('vaultModal')" title="Knowledge Vault"><i data-lucide="database"></i></button>
                <button class="icon-btn" onclick="openModal('settingsModal')" title="Settings"><i data-lucide="settings"></i></button>
            </div>
        </header>

        <!-- Chat Feed -->
        <div class="chat-feed" id="chatFeed">
            <div id="welcomeMsg" style="text-align: center; padding: 80px 20px; color: var(--text-dim);">
                <i data-lucide="box" style="width:48px;height:48px; margin-bottom:16px; opacity:0.5;"></i>
                <h3 style="margin:0; font-weight:500;" data-i18n="ready">System Ready</h3>
            </div>
        </div>

        <!-- Input Area -->
        <div class="input-wrapper">
            <div id="attachedFileIndicator" style="display:none; font-size:0.8rem; color:var(--text-dim); margin-bottom:8px; align-items:center; gap:6px;">
                <i data-lucide="paperclip" style="width:14px;"></i> <span data-i18n="docAttached">File attached</span>
                <i data-lucide="x" style="width:14px; cursor:pointer; color:var(--danger);" onclick="removeAttachedFile()"></i>
            </div>
            <div class="input-box" id="inputPanel">
                <button class="icon-btn" style="width:30px;height:30px;" onclick="document.getElementById('quickUpload').click()"><i data-lucide="paperclip"></i></button>
                <input type="file" id="quickUpload" accept="image/*,.pdf,.doc" style="display:none;" onchange="handleQuickUpload(event)">
                
                <textarea id="userQuery" placeholder="Message Axiom..." data-i18n-ph="askAnything" rows="1" oninput="autoResizeTextarea(this)" onkeydown="handleEnter(event)"></textarea>
                
                <button class="send-btn" id="sendBtn" onclick="submitQuestion()"><i data-lucide="arrow-up" style="width:18px;"></i></button>
            </div>
        </div>

    </div>

    <script>
        // ================= I18N DICTIONARY =================
        const dict = {
            en: { welcome: "AXIOM", tagline: "Intelligence, Structurized.", student: "Student", teacher: "Teacher", enterPlatform: "Enter Axiom", settings: "Preferences", uiLangLabel: "Language", aiTemp: "AI Creativity", precise: "Precise & Strict", balanced: "Balanced", creative: "Creative", fontSize: "Font Size", autoSpeech: "Auto Speech (TTS)", theme: "Theme Mode", vault: "Knowledge Vault", clickOrDrop: "Click or Drag & Drop Documents Here", summarizeAll: "Summarize Knowledge", workspaces: "Workspaces", general: "General", study: "Study / Curriculum", games: "Brain Games", history: "History", newChat: "New Chat", ready: "System Ready", docAttached: "File attached" },
            ar: { welcome: "أكسيوم", tagline: "ذكاء مهيكل.", student: "طالب", teacher: "أستاذ", enterPlatform: "دخول أكسيوم", settings: "التفضيلات", uiLangLabel: "اللغة", aiTemp: "مستوى الإبداع", precise: "دقيق وصارم", balanced: "متوازن", creative: "إبداعي", fontSize: "حجم الخط", autoSpeech: "النطق التلقائي", theme: "المظهر", vault: "خزنة المعرفة", clickOrDrop: "اضغط أو اسحب الملفات هنا", summarizeAll: "تلخيص المعرفة", workspaces: "مساحات العمل", general: "عام", study: "الدراسة / المنهج", games: "ألعاب التفكير", history: "السجل", newChat: "محادثة جديدة", ready: "النظام جاهز", docAttached: "ملف مرفق" },
            fr: { welcome: "AXIOM", tagline: "L'intelligence, Structurée.", student: "Étudiant", teacher: "Professeur", enterPlatform: "Entrer Axiom", settings: "Préférences", uiLangLabel: "Langue", aiTemp: "Créativité IA", precise: "Précis", balanced: "Équilibré", creative: "Créatif", fontSize: "Taille de police", autoSpeech: "Lecture Auto", theme: "Thème", vault: "Coffre de Connaissances", clickOrDrop: "Cliquez ou glissez-déposez ici", summarizeAll: "Résumer la Connaissance", workspaces: "Espaces", general: "Général", study: "Études / Cours", games: "Jeux", history: "Historique", newChat: "Nouveau Chat", ready: "Système Prêt", docAttached: "Fichier joint" }
        };
        const phDict = {
            en: { fullName: "Full Name", email: "Email Address", password: "Password", askAnything: "Message Axiom..." },
            ar: { fullName: "الاسم الكامل", email: "البريد الإلكتروني", password: "كلمة المرور", askAnything: "اسأل أكسيوم..." },
            fr: { fullName: "Nom Complet", email: "Adresse Email", password: "Mot de passe", askAnything: "Message Axiom..." }
        };

        let userSettings = { lang: 'en', temp: 'balanced', size: '16px', autoSpeech: false, theme: 'dark' };
        
        function changeUILanguage() {
            const lang = document.getElementById('uiLangSelect').value;
            userSettings.lang = lang;
            document.body.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');
            document.querySelectorAll('[data-i18n]').forEach(el => { const key = el.getAttribute('data-i18n'); if(dict[lang][key]) el.innerHTML = dict[lang][key]; });
            document.querySelectorAll('[data-i18n-ph]').forEach(el => { const key = el.getAttribute('data-i18n-ph'); if(phDict[lang][key]) el.setAttribute('placeholder', phDict[lang][key]); });
            saveSettings(); lucide.createIcons();
        }

        function updateSettings() {
            userSettings.temp = document.getElementById('aiTempSelect').value;
            userSettings.size = document.getElementById('fontSizeSelect').value;
            userSettings.autoSpeech = document.getElementById('autoSpeechToggle').checked;
            document.documentElement.style.setProperty('--font-size-base', userSettings.size);
            saveSettings();
        }

        function saveSettings() { localStorage.setItem('axiom_settings', JSON.stringify(userSettings)); }
        function loadSettings() {
            const saved = localStorage.getItem('axiom_settings');
            if(saved) {
                userSettings = JSON.parse(saved);
                document.getElementById('uiLangSelect').value = userSettings.lang;
                document.getElementById('aiTempSelect').value = userSettings.temp;
                document.getElementById('fontSizeSelect').value = userSettings.size;
                document.getElementById('autoSpeechToggle').checked = userSettings.autoSpeech;
                if(userSettings.theme === 'light') toggleTheme(true);
                document.documentElement.style.setProperty('--font-size-base', userSettings.size);
                changeUILanguage();
            }
        }

        function toggleTheme(forceLight = false) { 
            const isLight = forceLight || document.body.classList.toggle('light-mode'); 
            userSettings.theme = document.body.classList.contains('light-mode') ? 'light' : 'dark';
            document.getElementById('themeIcon').setAttribute('data-lucide', userSettings.theme === 'light' ? 'moon' : 'sun'); 
            saveSettings(); lucide.createIcons(); 
        }

        function openModal(id) { document.getElementById(id).style.display = 'flex'; setTimeout(() => document.getElementById(id).style.opacity = '1', 10); toggleSidebar(false); }
        function closeModal(id) { document.getElementById(id).style.opacity = '0'; setTimeout(() => document.getElementById(id).style.display = 'none', 300); }
        function toggleSidebar(forceClose = false) { 
            const sb = document.getElementById('sidebar'); const ov = document.getElementById('sidebarOverlay');
            if(forceClose) { sb.classList.remove('open'); ov.classList.remove('active'); return; }
            sb.classList.toggle('open'); ov.classList.toggle('active'); 
        }
        function autoResizeTextarea(el) { el.style.height = 'auto'; el.style.height = (el.scrollHeight) + 'px'; }
        function handleEnter(e) { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitQuestion(); } }

        // ================= PRE-PARSER FOR MATHJAX =================
        function processTextForMathJax(text) {
            let safeText = text;
            safeText = safeText.replace(/\\\\\[(.*?)\\\\\]/gs, '$$$$$1$$$$');
            safeText = safeText.replace(/\\\\\((.*?)\\\\\)/g, '$$$1$$');
            return marked.parse(safeText);
        }

        document.addEventListener("DOMContentLoaded", () => { 
            marked.setOptions({ breaks: true, gfm: true });
            lucide.createIcons(); loadSettings(); checkAuth(); 
            initDragAndDrop();
        });

        // Application State
        let isAiThinking = false; let currentUser = null; let attachedFileBase64 = null;
        let currentWorkspace = 'general';
        const chatFeed = document.getElementById('chatFeed');
        let chatSessions = JSON.parse(localStorage.getItem('axiom_sessions_v1')) || {};
        let currentSessionId = localStorage.getItem('axiom_current_session_v1');
        let curriculumDocs = [];

        // Auth Logic
        let selectedRole = 'student';
        function selectRole(role) { selectedRole = role; document.querySelectorAll('.role-selector .sb-item').forEach(c => c.classList.remove('active')); document.getElementById('role-' + role).classList.add('active'); }
        
        async function performAuth() {
            const name = document.getElementById('authName').value.trim(); const email = document.getElementById('authEmail').value.trim(); const pwd = document.getElementById('authPassword').value.trim(); const level = document.getElementById('authLevel').value; const err = document.getElementById('authError');
            if(!name || !email || !pwd) { err.innerText = "Please fill all fields."; return; }
            err.innerText = "Authenticating...";
            try { 
                const res = await fetch('/api/auth', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name, email, password: pwd, role: selectedRole, level}) }); 
                const data = await res.json(); 
                if(data.success) { document.getElementById('authOverlay').style.opacity = '0'; setTimeout(() => document.getElementById('authOverlay').style.display = 'none', 500); currentUser = data.user; setupUI(); fetchDocs(); } 
                else { err.innerText = data.error; } 
            } catch(e) { err.innerText = "Network error."; }
        }
        async function checkAuth() { try { const res = await fetch('/api/user/me'); const data = await res.json(); if(data.user) { document.getElementById('authOverlay').style.display = 'none'; currentUser = data.user; setupUI(); fetchDocs(); } } catch(e) {} }
        async function performLogout() { try { await fetch('/api/logout', { method: 'POST' }); document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;"; location.reload(); } catch(e) {} }

        function setupUI() {
            document.getElementById('sidebarUserName').innerText = currentUser.name;
            document.getElementById('sidebarRoleLabel').innerText = currentUser.role.toUpperCase();
            initSessions();
        }

        // Sessions & Workspaces
        function initSessions() { if (!currentSessionId || !chatSessions[currentSessionId]) { createNewSessionQuiet(); } else { loadChatSession(currentSessionId); } renderChatHistoryList(); }
        function createNewSessionQuiet() { 
            const id = Date.now().toString(); 
            chatSessions[id] = { id: id, title: "New Conversation", workspace: currentWorkspace, messages: [] }; 
            currentSessionId = id; saveSessionsData(); 
        }
        function createNewChatSession() { if(isAiThinking) return; createNewSessionQuiet(); loadChatSession(currentSessionId); toggleSidebar(true); }
        
        function switchWorkspace(ws) {
            if(isAiThinking) return; currentWorkspace = ws;
            document.querySelectorAll('.sb-section-title + .sb-item, .sb-section-title + .sb-item + .sb-item, .sb-section-title + .sb-item + .sb-item + .sb-item').forEach(i => i.classList.remove('active'));
            document.getElementById('ws-' + ws).classList.add('active');
            
            // If in a session that has messages, changing workspace creates a new session to keep contexts clean
            if(chatSessions[currentSessionId] && chatSessions[currentSessionId].messages.length > 0 && chatSessions[currentSessionId].workspace !== ws) {
                createNewChatSession();
            } else if (chatSessions[currentSessionId]) {
                chatSessions[currentSessionId].workspace = ws; saveSessionsData();
            }
            toggleSidebar(true); renderChat();
        }

        function loadChatSession(id) { 
            currentSessionId = id; const session = chatSessions[id]; 
            if(session) {
                currentWorkspace = session.workspace || 'general';
                document.querySelectorAll('[id^="ws-"]').forEach(i => i.classList.remove('active'));
                const wsElem = document.getElementById('ws-' + currentWorkspace);
                if(wsElem) wsElem.classList.add('active');
                renderChat();
            }
            renderChatHistoryList(); 
        }

        function saveSessionsData() { localStorage.setItem('axiom_sessions_v1', JSON.stringify(chatSessions)); localStorage.setItem('axiom_current_session_v1', currentSessionId); renderChatHistoryList(); }
        
        function renderChatHistoryList() { 
            const listDiv = document.getElementById('chatHistoryList'); if(!listDiv) return; listDiv.innerHTML = ''; 
            Object.values(chatSessions).sort((a,b) => b.id - a.id).forEach(session => { 
                const isActive = session.id === currentSessionId ? 'active' : ''; 
                listDiv.innerHTML += `<div class="sb-item ${isActive}" style="justify-content:space-between;" onclick="loadChatSession('${session.id}')"><span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:80%;">${session.title}</span> <i data-lucide="trash" style="width:14px; cursor:pointer;" onclick="deleteSession(event, '${session.id}')"></i></div>`; 
            }); 
            lucide.createIcons({root: listDiv}); 
        }
        function deleteSession(e, id) { e.stopPropagation(); delete chatSessions[id]; if(id === currentSessionId) createNewChatSession(); else saveSessionsData(); }

        // Render Chat Flow (Seamless UI)
        function renderChat() {
            chatFeed.innerHTML = '';
            const session = chatSessions[currentSessionId];
            if(!session || session.messages.length === 0) {
                chatFeed.innerHTML = `<div id="welcomeMsg" style="text-align: center; padding: 80px 20px; color: var(--text-dim);"><i data-lucide="box" style="width:48px;height:48px; margin-bottom:16px; opacity:0.5;"></i><h3 style="margin:0; font-weight:500;" data-i18n="ready">System Ready</h3></div>`;
                changeUILanguage(); return;
            }
            
            session.messages.forEach(msg => {
                if(msg.role === 'user') appendUserMessage(msg.content);
                else appendAIMessage(msg.content, false);
            });
            chatFeed.scrollTop = chatFeed.scrollHeight;
            if (window.MathJax) window.MathJax.typesetPromise([chatFeed]).catch(e => {});
        }

        function appendUserMessage(text) {
            const row = document.createElement('div'); row.className = 'msg-block msg-user';
            let cleanText = text.replace(/\[DOC_IDS:.*?\]/g, ''); // hide backend tokens
            row.innerHTML = `<div class="user-label">You</div><div class="msg-user-text">${cleanText.replace(/\\n/g, '<br>')}</div>`;
            chatFeed.appendChild(row);
        }
        
        function appendAIMessage(text, animate = true) {
            const row = document.createElement('div'); row.className = 'msg-block msg-ai';
            let html = processTextForMathJax(text);
            row.innerHTML = `<div class="ai-label"><i data-lucide="cpu" style="width:14px;"></i> Axiom</div><div class="ai-content">${html}</div>`;
            chatFeed.appendChild(row);
            lucide.createIcons({root: row});
            if(animate) chatFeed.scrollTop = chatFeed.scrollHeight;
            if(window.MathJax) window.MathJax.typesetPromise([row]).catch(e => {});
            
            if(animate && userSettings.autoSpeech && 'speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(text);
                window.speechSynthesis.speak(utterance);
            }
        }

        // Vault & Upload Logic
        function fetchDocs() { fetch('/api/docs').then(res => res.json()).then(data => { curriculumDocs = data; renderVaultDocs(); }); }
        function renderVaultDocs() {
            const list = document.getElementById('vaultDocsList');
            if(curriculumDocs.length === 0) { list.innerHTML = `<div style="text-align:center; color:var(--text-dim); font-size:0.85rem;">Vault is empty.</div>`; return; }
            list.innerHTML = curriculumDocs.map(d => `<div class="doc-item"><span><i data-lucide="file-text" style="width:14px; margin-right:6px;"></i> ${d.title}</span><i data-lucide="trash-2" style="width:14px; color:var(--danger); cursor:pointer;" onclick="deleteDoc(${d.id})"></i></div>`).join('');
            lucide.createIcons({root: list});
        }
        function deleteDoc(id) { fetch('/api/docs/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) }).then(res => res.json()).then(data => { curriculumDocs = data; renderVaultDocs(); }); }
        
        function initDragAndDrop() {
            const dz = document.getElementById('dropZone');
            dz.addEventListener('dragover', e => { e.preventDefault(); dz.style.borderColor = "var(--primary)"; });
            dz.addEventListener('dragleave', e => { e.preventDefault(); dz.style.borderColor = "var(--border)"; });
            dz.addEventListener('drop', e => { e.preventDefault(); dz.style.borderColor = "var(--border)"; handleVaultFiles(e.dataTransfer.files); });
        }
        function handleVaultUpload(e) { handleVaultFiles(e.target.files); }
        async function handleVaultFiles(files) {
            if(!files || files.length === 0) return;
            const status = document.getElementById('vaultUploadStatus');
            status.innerText = "Encrypting and storing in Vault..."; status.style.color = "var(--text-main)";
            
            const promises = Array.from(files).map(file => {
                return new Promise(resolve => {
                    const reader = new FileReader();
                    reader.onload = async evt => {
                        try { const res = await fetch('/api/docs/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: evt.target.result, name: file.name }) }); resolve(await res.json()); } catch(e) { resolve(null); }
                    }; reader.readAsDataURL(file);
                });
            });
            const results = await Promise.all(promises);
            const success = results.find(r => r && r.docs);
            if(success) { curriculumDocs = success.docs; renderVaultDocs(); status.innerText = "Secured in Vault."; status.style.color = "var(--success)"; }
            else { status.innerText = "Upload failed."; status.style.color = "var(--danger)"; }
        }

        // Quick Attachment
        function handleQuickUpload(e) {
            const file = e.target.files[0]; if(!file) return;
            const reader = new FileReader();
            reader.onload = evt => { attachedFileBase64 = evt.target.result; document.getElementById('attachedFileIndicator').style.display = 'flex'; };
            reader.readAsDataURL(file); e.target.value = '';
        }
        function removeAttachedFile() { attachedFileBase64 = null; document.getElementById('attachedFileIndicator').style.display = 'none'; }

        function triggerSmartSummary() {
            if(curriculumDocs.length === 0) return alert("Vault is empty.");
            document.getElementById('userQuery').value = `Provide a master summary of all Vault documents. Format professionally with LaTeX for math. [DOC_IDS: ${curriculumDocs.map(d=>d.id).join(',')}]`;
            submitQuestion();
        }

        // Main AI Submission Logic with History
        function submitQuestion() {
            if (isAiThinking) return;
            const queryInput = document.getElementById('userQuery');
            let query = queryInput.value.trim();
            if (!query && !attachedFileBase64) return;

            isAiThinking = true;
            document.getElementById('sendBtn').disabled = true; document.getElementById('sendBtn').innerHTML = `<i data-lucide="loader-2" style="animation: spin 1s linear infinite; width:18px;"></i>`; lucide.createIcons({root: document.getElementById('sendBtn')});
            
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();

            appendUserMessage(query + (attachedFileBase64 ? " [File Attached]" : ""));
            
            // Add to session memory
            const session = chatSessions[currentSessionId];
            if(session.messages.length === 0) session.title = query.substring(0, 30) + "...";
            session.messages.push({role: 'user', content: query + (attachedFileBase64 ? "\n[System: A file was attached by user]" : "")});
            saveSessionsData();

            const loadingRow = document.createElement('div'); loadingRow.className = 'msg-block msg-ai';
            loadingRow.innerHTML = `<div class="ai-label"><i data-lucide="cpu" style="width:14px;"></i> Axiom</div><div class="hologram-thinking">Synthesizing...</div>`;
            chatFeed.appendChild(loadingRow); lucide.createIcons({root: loadingRow});
            chatFeed.scrollTop = chatFeed.scrollHeight;

            const payload = { 
                query: query, 
                file: attachedFileBase64, 
                mode: currentWorkspace, 
                history: session.messages.slice(0, -1), // Send past messages
                temp: userSettings.temp,
                lang: userSettings.lang
            };
            
            queryInput.value = ''; queryInput.style.height = 'auto'; removeAttachedFile();

            fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            .then(res => res.json())
            .then(data => {
                chatFeed.removeChild(loadingRow);
                let finalAnswer = data.answer;
                if (data.status === 'out_of_scope') finalAnswer = "Query out of Vault scope. Please switch to General Workspace.";
                
                session.messages.push({role: 'assistant', content: finalAnswer});
                saveSessionsData();
                appendAIMessage(finalAnswer);
            }).catch(err => {
                chatFeed.removeChild(loadingRow);
                appendAIMessage("**System Error:** Connection disrupted. Please retry.");
            }).finally(() => {
                isAiThinking = false;
                document.getElementById('sendBtn').disabled = false; document.getElementById('sendBtn').innerHTML = `<i data-lucide="arrow-up" style="width:18px;"></i>`; lucide.createIcons({root: document.getElementById('sendBtn')});
                queryInput.focus();
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
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=50) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            return res_json["choices"][0]["message"]["content"].strip()

    def do_GET(self):
        try:
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
                
            elif self.path == "/api/user/me":
                sess_id = self.get_session_id()
                user = get_current_user(sess_id)
                self.send_json_response({"user": user})

        except Exception as e:
            self.send_json_response({"error": str(e)})

    def do_POST(self):
        try:
            session_id = self.get_session_id()
            if not session_id:
                self.send_json_response({"error": "Invalid session."})
                return

            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            req_json = json.loads(post_data.decode('utf-8')) if post_data else {}

            if self.path == "/api/auth":
                email = req_json.get("email")
                if email not in MOCK_USERS:
                    MOCK_USERS[email] = {
                        "name": req_json.get("name"), "email": email, "password": req_json.get("password"),
                        "role": req_json.get("role"), "level": req_json.get("level")
                    }
                MOCK_SESSIONS[session_id] = email
                self.send_json_response({"success": True, "user": MOCK_USERS[email]})
            
            elif self.path == "/api/logout":
                if session_id in MOCK_SESSIONS:
                    del MOCK_SESSIONS[session_id]
                self.send_json_response({"success": True})

            elif self.path == "/api/docs/upload":
                image_base64 = req_json.get("image")
                filename = req_json.get("name", "Document")
                if not image_base64:
                    self.send_json_response({"error": "No data"})
                    return
                try:
                    # If it's a PDF/DOC handled via b64, extract text/concepts. For simplicity, mock extraction logic via AI:
                    prompt = f"Extract all educational concepts, structured text, and math formulas from this document clearly."
                    payload = {
                        "model": MODEL_NAME,
                        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_base64}}]}],
                        "max_tokens": 4096
                    }
                    extracted_concepts = self.send_api_request(payload)
                    add_document_to_db(session_id, filename, extracted_concepts)
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
                user = get_current_user(session_id)
                user_query = req_json.get("query", "")
                file_b64 = req_json.get("file")
                mode = req_json.get("mode", "general") 
                history = req_json.get("history", [])
                temp_setting = req_json.get("temp", "balanced")
                pref_lang = req_json.get("lang", "en")
                
                docs = load_curriculum(session_id, user)

                # Filter summary DOCs if requested
                if "[DOC_IDS:" in user_query:
                    import re
                    match = re.search(r'\[DOC_IDS:\s*([\d,]+)\]', user_query)
                    if match:
                        selected_ids = match.group(1).split(',')
                        docs = [d for d in docs if str(d['id']) in selected_ids]
                        user_query = re.sub(r'\[DOC_IDS:\s*[\d,]+\]', '', user_query).strip()

                # Build System Prompt based on mode
                persona = "You are Axiom, a highly advanced, professional, and precise AI."
                if temp_setting == "precise":
                    persona += " Be extremely strict, factual, and concise."
                elif temp_setting == "creative":
                    persona += " Be creative, expansive, and engaging."

                sys_prompt = f"{persona}\nRespond seamlessly in the user's language (preferred UI lang: {pref_lang}). Ensure all math uses valid LaTeX $inline$ or $$display$$.\n"
                
                if mode == "study" and docs:
                    all_concepts = "\n\n".join([f"Doc '{d['title']}':\n{d['concepts']}" for d in docs])
                    sys_prompt += f"\nVAULT KNOWLEDGE BASE:\n{all_concepts}\n\nAct as an expert tutor. Ground your answers in the vault knowledge. If entirely unrelated, reply exactly: OUT_OF_SCOPE."
                elif mode == "games":
                    sys_prompt += "\nAct as a Brain Game Master. Challenge the user's logic."

                # Construct Messages with Context Memory
                api_messages = [{"role": "system", "content": sys_prompt}]
                
                # Append History (limit to last 10 for token safety)
                for msg in history[-10:]:
                    api_messages.append({"role": msg["role"], "content": msg["content"]})
                
                # Append Current Query
                current_content = []
                if file_b64:
                    if file_b64.startswith("data:image"):
                        current_content.append({"type": "image_url", "image_url": {"url": file_b64}})
                    else:
                        current_content.append({"type": "text", "text": "[File Attached]"})
                current_content.append({"type": "text", "text": user_query})
                
                api_messages.append({"role": "user", "content": current_content})

                payload = {
                    "model": MODEL_NAME,
                    "messages": api_messages,
                    "max_tokens": 4096,
                    "temperature": 0.2 if temp_setting == "precise" else (0.8 if temp_setting == "creative" else 0.5)
                }

                try:
                    ai_reply = self.send_api_request(payload)
                    if mode == "study" and "OUT_OF_SCOPE" in ai_reply:
                        self.send_json_response({"status": "out_of_scope", "answer": ""})
                    else:
                        self.send_json_response({"status": "success", "answer": ai_reply})
                except Exception as e:
                    self.send_json_response({"status": "error", "error": str(e)})
        except Exception as e:
            self.send_json_response({"error": str(e)})

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
