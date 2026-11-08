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
# HTML Frontend (ge_nius Royal World-Class UI - Ultimate Fixes + I18N + Settings)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="en" dir="auto">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ge_nius Assistant</title>
    
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Outfit:wght@700;900&display=swap" rel="stylesheet">
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
            --bg-main: #030304; --surface: #0f1014; --card: #16181e;
            --primary: #4169E1; --primary-glow: rgba(65, 105, 225, 0.35);
            --danger: #ef4444; --accent-gold: #fbbf24; --accent-green: #10b981;
            --text-main: #f8fafc; --text-dim: #94a3b8;
            --border: rgba(255, 255, 255, 0.07); --glass: rgba(15, 16, 20, 0.8);
        }

        body.light-mode {
            --bg-main: #f8fafc; --surface: #ffffff; --card: #f1f5f9;
            --primary: #2563eb; --primary-glow: rgba(37, 99, 235, 0.25);
            --text-main: #0f172a; --text-dim: #64748b;
            --border: rgba(0, 0, 0, 0.08); --glass: rgba(255, 255, 255, 0.88);
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        html, body {
            font-family: 'Inter', sans-serif; 
            background-color: var(--bg-main); color: var(--text-main);
            margin: 0; padding: 0; width: 100vw; height: 100vh; height: 100dvh; overflow: hidden;
            background-image: 
                radial-gradient(ellipse at 10% 10%, rgba(65, 105, 225, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 90% 90%, rgba(139, 92, 246, 0.05) 0%, transparent 50%);
            background-attachment: fixed;
        }
        
        /* RTL support for Arabic */
        body[dir="rtl"] { font-family: 'Cairo', 'Inter', sans-serif; }
        body[dir="rtl"] .sidebar { left: auto; right: -100%; border-right: none; border-left: 1px solid var(--border); }
        body[dir="rtl"] .sidebar.open { left: auto; right: 0; }
        body[dir="rtl"] .chat-input-container { direction: rtl; }
        body[dir="rtl"] textarea { direction: rtl; }

        .main-wrapper { 
            padding: 10px; display: flex; flex-direction: column; gap: 0; 
            width: 100%; height: 100%; height: 100dvh; max-width: 900px; margin: 0 auto; 
        }

        /* --- Overlays (Auth, Settings, Modals) --- */
        .full-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(3, 3, 4, 0.90); backdrop-filter: blur(15px);
            z-index: 9999; display: flex; justify-content: center; align-items: center; padding: 20px;
            transition: opacity 0.3s ease;
        }
        .auth-card, .settings-card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 24px;
            padding: 25px; width: 100%; max-width: 400px; box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            display: flex; flex-direction: column; gap: 15px; position: relative;
        }
        .close-modal-btn { position: absolute; top: 15px; right: 15px; background: transparent; border: none; color: var(--text-dim); cursor: pointer; }
        .close-modal-btn:hover { color: var(--danger); }

        .role-selector { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 10px; }
        .role-card {
            background: var(--card); border: 1px solid var(--border); border-radius: 12px;
            padding: 12px 5px; text-align: center; cursor: pointer; font-size: 0.8rem; font-weight: 600;
            color: var(--text-dim); transition: all 0.2s; display: flex; flex-direction: column; align-items: center; gap: 6px;
        }
        .role-card.active { background: rgba(65, 105, 225, 0.15); color: var(--primary); border-color: var(--primary); }
        .custom-input, .custom-select {
            width: 100%; background: var(--bg-main); border: 1px solid var(--border); color: var(--text-main);
            padding: 12px 16px; border-radius: 12px; font-family: inherit; font-size: 0.95rem; outline: none;
        }
        
        /* --- Top Nav Bar --- */
        .top-nav-bar {
            display: flex; flex-direction: column; align-items: stretch;
            padding: 10px 14px; flex-shrink: 0; gap: 10px; background: var(--glass);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border); border-radius: 20px; box-shadow: 0 4px 30px rgba(0,0,0,0.3);
            margin-bottom: 10px;
        }
        .nav-header-row { display: flex; align-items: center; gap: 10px; width: 100%; }
        .app-brand { font-family: 'Outfit', sans-serif; font-weight: 900; font-size: 1.05rem; color: var(--text-main); letter-spacing: -0.5px; display: flex; align-items: center; gap: 6px; }
        .app-brand span { color: var(--primary); }
        .brand-icon { width: 18px; height: 18px; color: var(--primary); }
        
        .icon-btn { background: transparent; border: none; color: var(--text-main); border-radius: 50%; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; flex-shrink: 0; }
        .icon-btn:hover { background: var(--card); color: var(--primary); transform: scale(1.05); }

        .mode-switcher-bar { display: flex; gap: 6px; background: rgba(0,0,0,0.25); padding: 4px; border-radius: 14px; justify-content: center; width: 100%; overflow-x: auto; }
        .mode-tab { padding: 6px 14px; background: transparent; border: none; color: var(--text-dim); font-family: inherit; font-weight: 600; font-size: 0.8rem; cursor: pointer; border-radius: 10px; white-space: nowrap; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.3s; flex: 1; }
        .mode-tab.active { background: var(--surface); color: var(--text-main); box-shadow: 0 2px 10px rgba(0,0,0,0.3); border: 1px solid var(--border); }
        .mode-tab.hidden { display: none !important; }

        .lucide { width: 18px; height: 18px; stroke-width: 2.2; display: inline-block; vertical-align: middle; }

        .games-stats-bar { display: none; background: rgba(65, 105, 225, 0.1); border: 1px solid rgba(65, 105, 225, 0.2); padding: 8px 16px; border-radius: 16px; align-items: center; justify-content: space-between; font-size: 0.85rem; color: #93c5fd; flex-shrink: 0; margin-bottom: 10px; }
        .games-stats-bar.active { display: flex; }
        .hud-hearts { color: var(--danger); letter-spacing: 2px;}

        /* --- Sidebar --- */
        .sidebar-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.75); backdrop-filter: blur(8px); z-index: 999; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; }
        .sidebar-overlay.active { opacity: 1; pointer-events: auto; }
        .sidebar { position: fixed; top: 0; left: -100%; width: 85%; max-width: 320px; height: 100vh; background: var(--surface); border-right: 1px solid var(--border); z-index: 1000; transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1); display: flex; flex-direction: column; padding: 18px 16px; box-shadow: 10px 0 40px rgba(0,0,0,0.6); overflow-y: auto; }
        .sidebar.open { left: 0; }
        .sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 12px;}
        
        .user-profile-card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 12px 14px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
        .user-info-text { display: flex; flex-direction: column; gap: 2px; }
        .user-name-title { font-weight: 700; font-size: 0.9rem; color: var(--primary); }
        .user-role-subtitle { font-size: 0.72rem; color: var(--text-dim); }
        .btn-logout-mini { background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: var(--danger); padding: 6px 10px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 4px; transition: all 0.2s; }
        .btn-logout-mini:hover { background: var(--danger); color: white; }

        .sidebar-section-title { font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; margin: 14px 0 8px 0; display: flex; align-items: center; gap: 6px;}
        .persona-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
        .persona-chip { background: var(--bg-main); border: 1px solid var(--border); border-radius: 12px; padding: 8px; font-size: 0.75rem; font-weight: 600; color: var(--text-dim); cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.2s ease; }
        .persona-chip:hover { background: var(--card); color: var(--text-main); }
        .persona-chip.active { background: rgba(65, 105, 225, 0.15); color: var(--primary); border-color: var(--primary); }

        .chat-history-list { flex: 1; display: flex; flex-direction: column; gap: 6px; }
        .history-item { background: var(--bg-main); border: 1px solid var(--border); color: var(--text-main); padding: 8px 10px; border-radius: 10px; cursor: pointer; display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem; transition: all 0.2s;}
        .history-item:hover { background: var(--card); }
        .history-item.active { background: rgba(65, 105, 225, 0.12); border: 1px solid var(--primary); color: var(--primary); font-weight: bold; }
        .history-item-content { display: flex; align-items: center; gap: 6px; flex: 1; overflow: hidden; }
        .delete-history-btn { background: none; border: none; color: var(--text-dim); cursor: pointer; padding: 2px; border-radius: 4px; }
        .delete-history-btn:hover { color: var(--danger); background: rgba(239, 68, 68, 0.1); }

        .tab-section { display: none; flex-direction: column; flex: 1; min-height: 0; }
        .tab-section.active { display: flex; }
        .card { background: var(--surface); border-radius: 20px; border: 1px solid var(--border); padding: 16px; display: flex; flex-direction: column; gap: 10px; }

        /* --- Chat Feed --- */
        .chat-container-wrapper { position: relative; flex: 1; display: flex; flex-direction: column; min-height: 0; }
        .chat-feed { display: flex; flex-direction: column; gap: 20px; flex: 1; overflow-y: auto; padding: 10px 4px 20px 4px; background: transparent; scroll-behavior: smooth; }
        
        .message-row { display: flex; flex-direction: column; gap: 4px; width: 100%; animation: slideUp 0.3s; }
        @keyframes slideUp { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
        
        .message-sender { display: flex; align-items: center; }
        .avatar-user { background: var(--primary); padding: 6px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px var(--primary-glow);}
        .avatar-ai { background: var(--card); padding: 6px; border-radius: 50%; border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; }

        .message-text-user { font-size: 0.95rem; line-height: 1.6; background: var(--surface); padding: 12px 16px; border-radius: 20px; border-top-right-radius: 4px; width: fit-content; max-width: 85%; border: 1px solid var(--border); box-shadow: 0 4px 15px rgba(0,0,0,0.1); align-self: flex-end; }
        .message-text-ai { font-size: 1.05rem; line-height: 1.75; font-weight: 500; align-self: flex-start; max-width: 95%;}

        .submarine-logo { width: 72px; height: 72px; filter: drop-shadow(0 0 20px rgba(65, 105, 225, 0.5)); color: var(--primary); }

        .complex-card-box { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 16px; margin: 6px 0; box-shadow: 0 4px 25px rgba(0,0,0,0.25); position: relative; overflow-x: auto; }
        .complex-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; font-size: 0.8rem; color: var(--primary); font-weight: bold; }
        
        .action-btn { background: var(--card); color: var(--text-dim); border: 1px solid var(--border); border-radius: 8px; padding: 5px 10px; font-size: 0.75rem; cursor: pointer; display: flex; align-items: center; gap: 4px; transition: all 0.2s; }
        .action-btn:hover { background: var(--primary); color: white; border-color: var(--primary); }

        .hologram-thinking { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 0.92rem; margin-top: 4px; background: linear-gradient(90deg, #4169E1, #8B5CF6, #fbbf24, #4169E1); background-size: 300% 100%; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: gradientMove 2s linear infinite; }
        @keyframes gradientMove { 0% { background-position: 100% 0; } 100% { background-position: 0 0; } }

        /* Retry System */
        .error-bubble { background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 10px 14px; border-radius: 12px; color: var(--danger); font-size: 0.9rem; display:flex; align-items:center; justify-content:space-between; max-width:85%; }

        /* --- Input Box --- */
        .chat-input-container { flex-shrink: 0; padding-bottom: 6px; position: relative; margin-top: auto;}
        .input-glass-panel { background: rgba(15, 16, 20, 0.85); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); border: 1px solid var(--border); border-radius: 28px; padding: 8px 10px 8px 16px; box-shadow: 0 12px 40px rgba(0,0,0,0.5); display: flex; align-items: center; gap: 10px; transition: all 0.3s ease; position: relative; z-index: 10; }
        .input-glass-panel:focus-within { border-color: rgba(65, 105, 225, 0.5); box-shadow: 0 12px 40px rgba(65, 105, 225, 0.15); }
        textarea { background: transparent; color: var(--text-main); border: none; outline: none; font-family: inherit; font-size: 1rem; resize: none; max-height: 120px; min-height: 24px; line-height: 1.5; width: 100%; padding: 8px 0; }
        
        .magic-menu { position: absolute; bottom: 70px; left: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 18px; padding: 8px; display: flex; flex-direction: column; gap: 4px; opacity: 0; transform: translateY(15px) scale(0.95); pointer-events: none; transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); box-shadow: 0 12px 30px rgba(0,0,0,0.6); z-index: 20; }
        .magic-menu.show { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }
        .magic-item { display: flex; align-items: center; gap: 10px; padding: 10px 16px; font-size: 0.9rem; font-weight: 500; border-radius: 12px; cursor: pointer; transition: all 0.2s; }
        .magic-item:hover { background: var(--card); color: var(--primary); }

        .tool-btn { background: transparent; border: none; color: var(--text-dim); border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; flex-shrink: 0; }
        .tool-btn:hover { background: var(--card); color: var(--text-main); }
        .tool-btn.active-magic { background: var(--card); color: var(--primary); transform: rotate(45deg); }

        .send-btn-royal { background: var(--primary); color: white; border: none; border-radius: 50%; width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.3s; box-shadow: 0 4px 15px var(--primary-glow); flex-shrink: 0; }
        .send-btn-royal.loading { background: transparent; border: 2px solid var(--border); box-shadow: none; pointer-events: none; }
        .spinner-icon { animation: spin 1s linear infinite; color: var(--text-dim); }
        @keyframes spin { 100% { transform: rotate(360deg); } }

        .btn { background: var(--card); color: var(--text-main); border: 1px solid var(--border); padding: 10px 14px; border-radius: 14px; font-weight: 600; font-size: 0.85rem; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.2s; }
        .btn-purple { background: linear-gradient(135deg, #1d4ed8, #4169E1); color: white; border: none; box-shadow: 0 4px 15px var(--primary-glow);}
        
        input[type="file"] { display: none; }
        .image-preview-bar { display: none; align-items: center; justify-content: space-between; background: rgba(65, 105, 225, 0.1); border: 1px solid rgba(65, 105, 225, 0.3); padding: 8px 12px; border-radius: 16px; font-size: 0.82rem; color: #93c5fd; margin-bottom: 8px; }

        .doc-card-compact { background: var(--bg-main); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 8px; }
        .doc-card-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; cursor: pointer; }
        .doc-card-title { font-weight: 700; color: var(--primary); font-size: 0.85rem; display: flex; align-items: center; gap: 6px; }
        .doc-card-body { padding: 10px 14px; border-top: 1px solid var(--border); font-size: 0.8rem; color: var(--text-dim); line-height: 1.6; display: none; background: var(--surface); border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;}
        
        .checkbox-container { display: flex; align-items: center; gap: 8px; font-size: 0.9rem; padding: 8px; border-radius: 8px; cursor: pointer; }
        .checkbox-container:hover { background: var(--card); }
        .custom-checkbox { width: 18px; height: 18px; cursor: pointer; }

    </style>
</head>
<body>

    <!-- ================= AUTHENTICATION OVERLAY ================= -->
    <div id="authOverlay" class="full-overlay">
        <div class="auth-card">
            <div style="text-align: center; margin-bottom: 10px;">
                <svg viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:48px;height:48px;margin-bottom:10px;">
                    <path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/>
                </svg>
                <h2 style="margin:0; font-family:'Outfit';" data-i18n="welcome">Welcome to ge_nius</h2>
            </div>
            
            <div class="role-selector">
                <div class="role-card active" onclick="selectRole('student')" id="role-student"><i data-lucide="graduation-cap"></i> <span data-i18n="student">Student</span></div>
                <div class="role-card" onclick="selectRole('teacher')" id="role-teacher"><i data-lucide="presentation"></i> <span data-i18n="teacher">Teacher</span></div>
                <div class="role-card" onclick="selectRole('citizen')" id="role-citizen"><i data-lucide="globe"></i> <span data-i18n="citizen">Citizen</span></div>
            </div>

            <input type="text" id="authName" class="custom-input" placeholder="Full Name" data-i18n-ph="fullName">
            <input type="email" id="authEmail" class="custom-input" placeholder="Email Address" data-i18n-ph="email">
            <input type="password" id="authPassword" class="custom-input" placeholder="Password" data-i18n-ph="password">
            
            <select id="authLevel" class="custom-select">
                <option value="Middle School" data-i18n="middleSchool">Middle School</option>
                <option value="High School" data-i18n="highSchool">High School</option>
                <option value="University (L2)" data-i18n="univL2">University (L2)</option>
                <option value="Other" data-i18n="other">Other</option>
            </select>

            <button class="btn btn-purple" onclick="performAuth()"><span data-i18n="enterPlatform">Enter Platform</span> <i data-lucide="arrow-right"></i></button>
            <div id="authError" style="color:var(--danger); font-size:0.8rem; text-align:center;"></div>
        </div>
    </div>

    <!-- ================= SETTINGS OVERLAY ================= -->
    <div id="settingsOverlay" class="full-overlay" style="display:none; opacity:0;">
        <div class="settings-card">
            <button class="close-modal-btn" onclick="closeSettings()"><i data-lucide="x"></i></button>
            <h3 style="margin:0; color:var(--primary); display:flex; align-items:center; gap:8px;"><i data-lucide="settings"></i> <span data-i18n="settings">Settings</span></h3>
            
            <label style="font-size:0.85rem; color:var(--text-dim); margin-top:10px;" data-i18n="uiLangLabel">Interface Language</label>
            <select id="uiLangSelect" class="custom-select" onchange="changeUILanguage()">
                <option value="en">English</option>
                <option value="ar">العربية</option>
                <option value="fr">Français</option>
            </select>

            <label style="font-size:0.85rem; color:var(--text-dim); margin-top:5px;" data-i18n="sumLangLabel">Smart Summary Language</label>
            <select id="sumLangSelect" class="custom-select">
                <option value="en">English (Professional)</option>
                <option value="ar">العربية (تلخيص دقيق واحترافي)</option>
                <option value="fr">Français (Professionnel)</option>
            </select>
        </div>
    </div>

    <!-- ================= SUMMARY SELECTION OVERLAY ================= -->
    <div id="summaryOverlay" class="full-overlay" style="display:none; opacity:0;">
        <div class="settings-card">
            <button class="close-modal-btn" onclick="closeSummaryModal()"><i data-lucide="x"></i></button>
            <h3 style="margin:0; color:var(--accent-gold); display:flex; align-items:center; gap:8px;"><i data-lucide="sparkles"></i> <span data-i18n="selectDocsSumm">Select Docs to Summarize</span></h3>
            
            <div id="summaryDocsList" style="max-height: 200px; overflow-y: auto; background:var(--bg-main); border:1px solid var(--border); border-radius:12px; padding:10px; display:flex; flex-direction:column; gap:5px;">
                <!-- Filled via JS -->
            </div>

            <button class="btn btn-purple" onclick="executeSummary()"><i data-lucide="zap"></i> <span data-i18n="generateSummary">Generate Summary</span></button>
        </div>
    </div>
    <!-- ========================================================= -->

    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h3 data-i18n="menu"><i data-lucide="menu"></i> Menu</h3>
            <button class="icon-btn" style="width:30px; height:30px;" onclick="toggleSidebar()"><i data-lucide="x"></i></button>
        </div>
        
        <div class="user-profile-card">
            <div class="user-info-text">
                <div class="user-name-title" id="sidebarUserName">User</div>
                <div class="user-role-subtitle" id="sidebarRoleLabel">Role</div>
            </div>
            <button class="btn-logout-mini" onclick="performLogout()"><i data-lucide="log-out" style="width:12px;height:12px;"></i> <span data-i18n="logout">Logout</span></button>
        </div>

        <button class="btn" onclick="createNewChatSession()" style="width: 100%; justify-content: center; margin-bottom: 8px;">
            <i data-lucide="plus-circle"></i> <span data-i18n="newSession">New Session</span>
        </button>

        <button class="btn btn-purple" onclick="switchSection('docsTab')" style="width: 100%; justify-content: center; margin-bottom: 12px;" id="btnCurriculum">
            <i data-lucide="folder-kanban"></i> <span data-i18n="curriculum">Curriculum</span>
        </button>

        <div class="sidebar-section-title"><i data-lucide="brain"></i> <span data-i18n="aiPersona">AI Persona</span></div>
        <div class="persona-grid" id="personaContainer">
            <button class="persona-chip active" data-val="human" onclick="selectPersona('human', this)"><i data-lucide="heart" style="width:13px;height:13px;"></i> <span data-i18n="human">Human</span></button>
            <button class="persona-chip" data-val="strict" onclick="selectPersona('strict', this)"><i data-lucide="briefcase" style="width:13px;height:13px;"></i> <span data-i18n="strict">Strict</span></button>
            <button class="persona-chip" data-val="humor" onclick="selectPersona('humor', this)"><i data-lucide="smile" style="width:13px;height:13px;"></i> <span data-i18n="humor">Humor</span></button>
            <button class="persona-chip" data-val="roast" onclick="selectPersona('roast', this)"><i data-lucide="flame" style="width:13px;height:13px;"></i> <span data-i18n="roast">Roast</span></button>
        </div>

        <div class="sidebar-section-title"><i data-lucide="history"></i> <span data-i18n="history">History</span></div>
        <div class="chat-history-list" id="chatHistoryList"></div>

        <div style="margin-top: auto; padding-top: 12px; border-top: 1px solid var(--border); display:flex; gap:8px;">
            <button class="btn" style="flex:1; justify-content: center; padding: 8px;" onclick="openSettings()" title="Settings">
                <i data-lucide="settings"></i>
            </button>
            <button class="btn" style="flex:1; justify-content: center; padding: 8px;" onclick="toggleTheme()" title="Toggle Theme">
                <i data-lucide="moon" id="themeIcon"></i>
            </button>
        </div>
    </aside>

    <div class="main-wrapper">
        <div class="top-nav-bar">
            <div class="nav-header-row">
                <button class="icon-btn" onclick="toggleSidebar()">
                    <i data-lucide="align-left"></i>
                </button>
                <div class="app-brand">
                    <svg class="brand-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/>
                    </svg>
                    ge<span>_</span>nius
                </div>
            </div>

            <div class="mode-switcher-bar">
                <button class="mode-tab hidden" id="modeTeacher" onclick="switchMode('teacher')" data-i18n="dashboard">Dashboard</button>
                <button class="mode-tab hidden" id="modeStudy" onclick="switchMode('study')" data-i18n="study">Study</button>
                <button class="mode-tab hidden" id="modeGames" onclick="switchMode('games')" data-i18n="games">Games</button>
                <button class="mode-tab active" id="modeGeneral" onclick="switchMode('general')" data-i18n="general">General</button>
            </div>
        </div>

        <div class="games-stats-bar" id="gamesStatsBar">
            <span class="hud-hearts" id="hudHearts">❤️❤️❤️❤️❤️</span>
            <span>⭐ XP: <strong id="userXp">0</strong></span>
        </div>

        <!-- Chat Tab -->
        <div class="tab-section active" id="askTab">
            <div class="chat-container-wrapper">
                <div class="chat-feed" id="chatFeed">
                    <div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 80px 20px; display: flex; flex-direction: column; align-items: center; gap: 16px;">
                        <svg class="submarine-logo" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/><circle cx="12" cy="15" r="2"/><path d="M20 15h2"/><path d="M2 15h2"/>
                        </svg>
                        <p style="margin: 0; font-size: 1rem; max-width: 250px; line-height: 1.5; color: var(--text-dim);" data-i18n="platformReady">Platform Ready.</p>
                    </div>
                </div>
            </div>

            <div class="chat-input-container">
                <div class="image-preview-bar" id="questionImgPreview">
                    <span style="display: flex; align-items: center; gap: 6px;"><i data-lucide="image" style="width: 14px; height: 14px;"></i> <span data-i18n="docAttached">Document attached</span></span>
                    <span style="cursor: pointer; color: #fca5a5; font-weight: bold; display: flex; align-items: center;" onclick="removeQuestionImage()"><i data-lucide="x" style="width: 16px; height: 16px;"></i></span>
                </div>

                <div class="magic-menu" id="magicMenu">
                    <label for="qFileInputCamera" class="magic-item">
                        <i data-lucide="camera" style="color:var(--primary)"></i> <span data-i18n="takePhoto">Take Photo</span>
                    </label>
                    <input type="file" id="qFileInputCamera" accept="image/*" capture="environment">
                    
                    <label for="qFileInputGallery" class="magic-item">
                        <i data-lucide="image-plus" style="color:var(--primary)"></i> <span data-i18n="uploadFile">Upload PDF/Doc</span>
                    </label>
                    <input type="file" id="qFileInputGallery" accept=".pdf, .doc, .docx, image/*">

                    <div class="magic-item" id="btnSummarize" onclick="openSummaryModal()" style="display:none; color:var(--accent-gold); font-weight:bold;">
                        <i data-lucide="sparkles"></i> <span data-i18n="aiSummarize">AI Summarize</span>
                    </div>
                </div>

                <div class="input-glass-panel" id="inputPanel">
                    <button class="tool-btn" id="magicBtn" onclick="toggleMagicMenu()" title="Attach">
                        <i data-lucide="plus"></i>
                    </button>

                    <textarea id="userQuery" placeholder="Ask anything..." data-i18n-ph="askAnything" rows="1" oninput="autoResizeTextarea(this)"></textarea>
                    
                    <button class="tool-btn" id="voiceRecordBtn" onclick="toggleVoiceRecording()" title="Voice Input">
                        <i data-lucide="mic"></i>
                    </button>

                    <button class="send-btn-royal" id="sendBtn" onclick="submitQuestion()" title="Send">
                        <i data-lucide="arrow-up" id="sendIcon"></i>
                    </button>
                </div>
            </div>
        </div>

        <!-- Curriculum Docs Tab -->
        <div class="tab-section" id="docsTab" style="gap:15px; overflow-y:auto; padding:0 4px;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <h3 style="margin:0; font-size: 1.15rem; color: var(--text-main); font-weight: 700;" data-i18n="curriculumArchive">Curriculum Archive</h3>
                <button class="btn" style="padding: 6px 10px; font-size: 0.75rem;" onclick="switchSection('askTab')">
                    <i data-lucide="arrow-left" style="width:14px;height:14px;"></i> <span data-i18n="back">Back</span>
                </button>
            </div>
            <div class="card" id="studentUploadArea" style="padding: 12px;">
                <span style="font-weight: 700; font-size: 0.85rem; color: var(--primary); display: flex; align-items: center; gap: 8px; margin-bottom:8px;"><i data-lucide="file-up" style="width:14px;height:14px;"></i> <span data-i18n="uploadMaterials">Upload Materials</span></span>
                <div style="display: flex; gap: 6px;">
                    <label for="docFileInputCamera" class="btn btn-purple" style="flex: 1; padding:8px; font-size:0.8rem; text-align: center; margin:0;"><i data-lucide="scan" style="width:14px;height:14px;"></i> <span data-i18n="scan">Scan</span></label>
                    <input type="file" id="docFileInputCamera" accept="image/*" capture="environment">
                    
                    <label for="docFileInputGallery" class="btn btn-purple" style="flex: 1; padding:8px; font-size:0.8rem; text-align: center; margin:0;"><i data-lucide="folder" style="width:14px;height:14px;"></i> <span data-i18n="files">Files</span></label>
                    <input type="file" id="docFileInputGallery" accept=".pdf, .doc, .docx, image/*" multiple>
                </div>
                <div id="uploadStatus" style="font-size: 0.75rem; font-weight: bold; text-align:center; margin-top:8px;"></div>
            </div>
            <div id="docsList" style="display: flex; flex-direction: column; gap: 6px;"></div>
        </div>

        <!-- Teacher Tab -->
        <div class="tab-section" id="teacherTab" style="gap:15px; overflow-y:auto; padding:0 4px;">
            <div class="card" style="text-align:center;">
                <h3 style="color:var(--primary); margin-top:0;"><i data-lucide="upload-cloud"></i> <span data-i18n="uploadCurriculum">Upload Curriculum</span></h3>
                <div style="display:flex; gap:10px; justify-content:center; margin-top:15px;">
                    <label for="teacherUploadBtn" class="btn btn-purple" style="width:auto; padding:12px 30px;"><i data-lucide="file-plus"></i> <span data-i18n="selectFile">Select File</span></label>
                    <input type="file" id="teacherUploadBtn" accept=".pdf, .doc, .docx, image/*">
                </div>
                <div id="teacherUploadStatus" style="margin-top:10px; font-weight:bold; font-size:0.85rem;"></div>
            </div>
            <div id="teacherDocsList" style="display:flex; flex-direction:column; gap:10px; padding-bottom:20px;"></div>
        </div>
    </div>

    <script>
        // ================= I18N DICTIONARY =================
        const dict = {
            en: { welcome: "Welcome to ge_nius", student: "Student", teacher: "Teacher", citizen: "Citizen", enterPlatform: "Enter Platform", settings: "Settings", uiLangLabel: "Interface Language", sumLangLabel: "Smart Summary Language", selectDocsSumm: "Select Docs to Summarize", generateSummary: "Generate Summary", menu: "Menu", logout: "Logout", newSession: "New Session", curriculum: "Curriculum", aiPersona: "AI Persona", human: "Human", strict: "Strict", humor: "Humor", roast: "Roast", history: "History", dashboard: "Dashboard", study: "Study", games: "Games", general: "General", platformReady: "Platform Ready.", docAttached: "Document attached", takePhoto: "Take Photo", uploadFile: "Upload PDF/Doc", aiSummarize: "AI Summarize", curriculumArchive: "Curriculum Archive", back: "Back", uploadMaterials: "Upload Materials", scan: "Scan", files: "Files", uploadCurriculum: "Upload Curriculum", selectFile: "Select File", retry: "Retry", copy: "Copy", listen: "Listen", selectAll: "Select All" },
            ar: { welcome: "مرحباً في ge_nius", student: "طالب", teacher: "أستاذ", citizen: "مواطن", enterPlatform: "دخول المنصة", settings: "الإعدادات", uiLangLabel: "لغة الواجهة", sumLangLabel: "لغة التلخيص الذكي", selectDocsSumm: "اختر الوثائق للتلخيص", generateSummary: "إنشاء التلخيص", menu: "القائمة", logout: "تسجيل خروج", newSession: "جلسة جديدة", curriculum: "المنهج الدراسي", aiPersona: "شخصية الذكاء", human: "ودود", strict: "صارم", humor: "مرح", roast: "تحدي", history: "السجل", dashboard: "لوحة التحكم", study: "دراسة", games: "ألعاب", general: "عام", platformReady: "المنصة جاهزة.", docAttached: "تم إرفاق مستند", takePhoto: "التقاط صورة", uploadFile: "رفع ملف", aiSummarize: "تلخيص ذكي", curriculumArchive: "أرشيف الدروس", back: "رجوع", uploadMaterials: "رفع المواد", scan: "مسح ضوئي", files: "ملفات", uploadCurriculum: "رفع المناهج", selectFile: "اختر ملف", retry: "إعادة المحاولة", copy: "نسخ", listen: "استماع", selectAll: "تحديد الكل" },
            fr: { welcome: "Bienvenue sur ge_nius", student: "Étudiant", teacher: "Professeur", citizen: "Citoyen", enterPlatform: "Entrer", settings: "Paramètres", uiLangLabel: "Langue de l'interface", sumLangLabel: "Langue du résumé", selectDocsSumm: "Sélectionner les docs", generateSummary: "Générer le résumé", menu: "Menu", logout: "Déconnexion", newSession: "Nouvelle Session", curriculum: "Programme", aiPersona: "Personnage IA", human: "Humain", strict: "Strict", humor: "Humour", roast: "Défi", history: "Historique", dashboard: "Tableau de bord", study: "Études", games: "Jeux", general: "Général", platformReady: "Plateforme prête.", docAttached: "Document joint", takePhoto: "Prendre Photo", uploadFile: "Téléverser Fichier", aiSummarize: "Résumé IA", curriculumArchive: "Archives des cours", back: "Retour", uploadMaterials: "Téléverser Matériel", scan: "Scanner", files: "Fichiers", uploadCurriculum: "Téléverser Programme", selectFile: "Choisir Fichier", retry: "Réessayer", copy: "Copier", listen: "Écouter", selectAll: "Tout sélectionner" }
        };
        const phDict = {
            en: { fullName: "Full Name", email: "Email Address", password: "Password", askAnything: "Ask anything..." },
            ar: { fullName: "الاسم الكامل", email: "البريد الإلكتروني", password: "كلمة المرور", askAnything: "اسأل أي شيء..." },
            fr: { fullName: "Nom Complet", email: "Adresse Email", password: "Mot de passe", askAnything: "Demandez n'importe quoi..." }
        };

        function changeUILanguage() {
            const lang = document.getElementById('uiLangSelect').value;
            document.body.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');
            
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if(dict[lang][key]) el.innerHTML = dict[lang][key];
            });
            document.querySelectorAll('[data-i18n-ph]').forEach(el => {
                const key = el.getAttribute('data-i18n-ph');
                if(phDict[lang][key]) el.setAttribute('placeholder', phDict[lang][key]);
            });
            localStorage.setItem('ge_nius_ui_lang', lang);
            lucide.createIcons();
        }

        // ================= PRE-PARSER FOR MATHJAX =================
        function processTextForMathJax(text) {
            // Protect LaTeX before Marked parses it to prevent underscores from becoming italics
            let safeText = text;
            safeText = safeText.replace(/\\\\\[(.*?)\\\\\]/gs, '$$$$$1$$$$');
            safeText = safeText.replace(/\\\\\((.*?)\\\\\)/g, '$$$1$$');
            let htmlText = marked.parse(safeText);
            return htmlText;
        }
        
        // Settings / Overlays Logic
        function openSettings() { document.getElementById('settingsOverlay').style.display = 'flex'; setTimeout(() => document.getElementById('settingsOverlay').style.opacity = '1', 10); toggleSidebar(); }
        function closeSettings() { document.getElementById('settingsOverlay').style.opacity = '0'; setTimeout(() => document.getElementById('settingsOverlay').style.display = 'none', 300); }

        function openSummaryModal() {
            document.getElementById('magicMenu').classList.remove('show');
            const listDiv = document.getElementById('summaryDocsList');
            listDiv.innerHTML = `<label class="checkbox-container"><input type="checkbox" class="custom-checkbox" id="selectAllDocs" onchange="toggleAllDocs(this)"> <strong data-i18n="selectAll">Select All</strong></label><hr style="border-color:var(--border); width:100%; margin:4px 0;">`;
            
            curriculumDocs.forEach((doc, i) => {
                listDiv.innerHTML += `<label class="checkbox-container"><input type="checkbox" class="custom-checkbox doc-check" value="${doc.id}"> Doc ${i+1}: ${doc.title || 'Document'}</label>`;
            });

            document.getElementById('summaryOverlay').style.display = 'flex'; 
            setTimeout(() => document.getElementById('summaryOverlay').style.opacity = '1', 10);
            changeUILanguage(); // re-apply lang to dynamic content
        }
        function closeSummaryModal() { document.getElementById('summaryOverlay').style.opacity = '0'; setTimeout(() => document.getElementById('summaryOverlay').style.display = 'none', 300); }
        function toggleAllDocs(chk) { document.querySelectorAll('.doc-check').forEach(c => c.checked = chk.checked); }

        function executeSummary() {
            const selected = Array.from(document.querySelectorAll('.doc-check:checked')).map(c => c.value);
            if(selected.length === 0) { alert("Please select at least one document."); return; }
            closeSummaryModal();
            const sumLang = document.getElementById('sumLangSelect').value;
            const langName = sumLang === 'ar' ? 'Arabic (Professional & Accurate, avoid literal translation)' : (sumLang === 'fr' ? 'French (Professional)' : 'English');
            
            document.getElementById('userQuery').value = `Please provide a highly professional, structured summary for the selected documents. Focus on: Core concepts, LaTeX math formulas, examples, and exam notes. Write it beautifully in ${langName}. [DOC_IDS: ${selected.join(',')}]`;
            submitQuestion(true);
        }

        // Export to PDF
        window.exportToPDF = function(btn) {
            const containerId = btn.getAttribute('data-target');
            const element = document.getElementById(containerId);
            if(!element) return;
            const opt = {
                margin:       0.5,
                filename:     'ge_nius_summary.pdf',
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2, useCORS: true },
                jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
            };
            btn.innerHTML = `<i data-lucide="loader"></i> Exporting...`;
            lucide.createIcons({root:btn});
            html2pdf().set(opt).from(element).save().then(()=>{
                btn.innerHTML = `<i data-lucide="download"></i> PDF`;
                lucide.createIcons({root:btn});
            });
        };

        // --- Init & Start ---
        document.addEventListener("DOMContentLoaded", () => { 
            marked.setOptions({ breaks: true, gfm: true });
            const savedLang = localStorage.getItem('ge_nius_ui_lang');
            if(savedLang) { document.getElementById('uiLangSelect').value = savedLang; changeUILanguage(); }
            lucide.createIcons(); checkAuth(); 
        });

        let isAiThinking = false; let currentUser = null; let attachedQuestionBase64 = null;
        let currentMode = 'general'; let currentPersonaValue = 'human';
        let modeContents = { study: "", general: "", games: "" };
        let lastPayload = null; // for Retry
        const chatFeed = document.getElementById('chatFeed');

        let selectedRole = 'student';
        function selectRole(role) { selectedRole = role; document.querySelectorAll('.role-card').forEach(c => c.classList.remove('active')); document.getElementById('role-' + role).classList.add('active'); const levelSelect = document.getElementById('authLevel'); if(role === 'student') levelSelect.style.display = 'block'; else levelSelect.style.display = 'none'; }
        async function performAuth() {
            const name = document.getElementById('authName').value.trim(); const email = document.getElementById('authEmail').value.trim(); const pwd = document.getElementById('authPassword').value.trim(); const level = document.getElementById('authLevel').value; const err = document.getElementById('authError');
            if(!name || !email || !pwd) { err.innerText = "Please fill all fields."; return; } if(selectedRole === 'student' && !level) { err.innerText = "Please select your study level."; return; }
            err.innerText = "Authenticating...";
            try { const res = await fetch('/api/auth', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name, email, password: pwd, role: selectedRole, level}) }); const data = await res.json(); if(data.success) { document.getElementById('authOverlay').style.opacity = '0'; setTimeout(() => document.getElementById('authOverlay').style.display = 'none', 400); currentUser = data.user; configureUIForRole(); } else { err.innerText = data.error || "Authentication failed."; } } catch(e) { err.innerText = "Network error."; }
        }
        async function checkAuth() { try { const res = await fetch('/api/user/me'); const data = await res.json(); if(data.user) { document.getElementById('authOverlay').style.display = 'none'; currentUser = data.user; configureUIForRole(); } } catch(e) {} }
        async function performLogout() { try { await fetch('/api/logout', { method: 'POST' }); document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;"; currentUser = null; document.getElementById('authName').value = ''; document.getElementById('authEmail').value = ''; document.getElementById('authPassword').value = ''; document.getElementById('authOverlay').style.display = 'flex'; setTimeout(() => document.getElementById('authOverlay').style.opacity = '1', 10); if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar(); } catch(e) { console.error(e); } }

        function configureUIForRole() {
            document.getElementById('sidebarUserName').innerText = currentUser.name;
            document.getElementById('sidebarRoleLabel').innerText = currentUser.role.toUpperCase() + (currentUser.level ? ` • ${currentUser.level}` : '');
            document.querySelectorAll('.mode-tab').forEach(t => t.classList.add('hidden'));
            document.getElementById('modeGeneral').classList.remove('hidden');
            document.getElementById('btnCurriculum').style.display = 'none';

            if (currentUser.role === 'teacher') { document.getElementById('modeTeacher').classList.remove('hidden'); switchMode('teacher'); } 
            else if (currentUser.role === 'student') { document.getElementById('modeStudy').classList.remove('hidden'); document.getElementById('modeGames').classList.remove('hidden'); document.getElementById('btnCurriculum').style.display = 'flex'; updateGamificationHUD(currentUser.hearts, currentUser.xp); switchMode('study'); } 
            else { switchMode('general'); }
        }

        function updateGamificationHUD(hearts, xp) { let heartStr = ""; for(let i=0; i<5; i++) { heartStr += (i < hearts) ? "❤️" : "🤍"; } document.getElementById('hudHearts').innerText = heartStr; document.getElementById('userXp').innerText = xp; }
        window.selectPersona = function(val, btnElement) { currentPersonaValue = val; document.querySelectorAll('.persona-chip').forEach(btn => btn.classList.remove('active')); btnElement.classList.add('active'); if(window.innerWidth < 768) toggleSidebar(); };
        function toggleMagicMenu() { if(isAiThinking) return; const menu = document.getElementById('magicMenu'); const btn = document.getElementById('magicBtn'); menu.classList.toggle('show'); btn.classList.toggle('active-magic'); }
        document.addEventListener('click', (e) => { const menu = document.getElementById('magicMenu'); const btn = document.getElementById('magicBtn'); if (menu && btn && !menu.contains(e.target) && !btn.contains(e.target)) { menu.classList.remove('show'); btn.classList.remove('active-magic'); } });
        function toggleTheme() { const isLight = document.body.classList.toggle('light-mode'); localStorage.setItem('theme', isLight ? 'light' : 'dark'); const iconId = isLight ? 'moon' : 'sun'; document.getElementById('themeIcon').setAttribute('data-lucide', iconId); lucide.createIcons(); }
        if (localStorage.getItem('theme') === 'light') { document.body.classList.add('light-mode'); document.getElementById('themeIcon').setAttribute('data-lucide', 'moon'); }
        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); document.getElementById('sidebarOverlay').classList.toggle('active'); }
        function switchSection(sectionId) { document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active')); document.getElementById(sectionId).classList.add('active'); if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar(); }
        function autoResizeTextarea(el) { el.style.height = 'auto'; el.style.height = (el.scrollHeight) + 'px'; }

        // Sessions
        let chatSessions = JSON.parse(localStorage.getItem('ge_nius_sessions_royal_v6')) || {};
        let currentSessionId = localStorage.getItem('ge_nius_current_session_royal_v6');
        function initSessions() { if (!currentSessionId || !chatSessions[currentSessionId]) { createNewSessionQuiet(); } else { loadChatSession(currentSessionId); } renderChatHistoryList(); }
        function createNewSessionQuiet() { const id = Date.now().toString(); chatSessions[id] = { id: id, title: "New Session", mode: "study", modesData: { study: "", general: "", games: "" } }; currentSessionId = id; saveSessionsData(); }
        function createNewChatSession() { if(isAiThinking) return; createNewSessionQuiet(); loadChatSession(currentSessionId); if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar(); }
        function switchMode(mode) {
            if(isAiThinking) return;
            if (currentMode !== 'teacher') { modeContents[currentMode] = chatFeed.innerHTML; }
            currentMode = mode;
            document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
            const btnSumm = document.getElementById('btnSummarize');
            if(btnSumm) btnSumm.style.display = (mode === 'study') ? 'flex' : 'none';
            if (mode === 'teacher') { document.getElementById('modeTeacher').classList.add('active'); switchSection('teacherTab'); fetchTeacherDocs(); return; } 
            else { switchSection('askTab'); if(mode === 'study') document.getElementById('modeStudy').classList.add('active'); else if(mode === 'general') document.getElementById('modeGeneral').classList.add('active'); else if(mode === 'games') document.getElementById('modeGames').classList.add('active'); }
            
            const gamesStatsBar = document.getElementById('gamesStatsBar');
            if (mode === 'games' && currentUser && currentUser.role === 'student') { gamesStatsBar.classList.add('active'); updateGamificationHUD(currentUser.hearts, currentUser.xp); } else { gamesStatsBar.classList.remove('active'); }

            if (modeContents[mode] && modeContents[mode].trim() !== '') { chatFeed.innerHTML = modeContents[mode]; } 
            else { chatFeed.innerHTML = `<div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 80px 20px; display: flex; flex-direction: column; align-items: center; gap: 16px;"><svg class="submarine-logo" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/><circle cx="12" cy="15" r="2"/><path d="M20 15h2"/><path d="M2 15h2"/></svg><p style="margin: 0; font-size: 1rem; color: var(--text-dim);"><span data-i18n="platformReady">Platform Ready.</span></p></div>`; changeUILanguage(); }
            if(chatSessions[currentSessionId]) { chatSessions[currentSessionId].mode = mode; chatSessions[currentSessionId].modesData = modeContents; saveSessionsData(); }
            lucide.createIcons({root: chatFeed}); if (window.MathJax) window.MathJax.typesetPromise([chatFeed]).catch(e => {});
        }
        function loadChatSession(id) { currentSessionId = id; const session = chatSessions[id]; if (session && session.modesData) { modeContents = session.modesData; } else { modeContents = { study: "", general: "", games: "" }; } if(session && session.mode) switchMode(session.mode); else switchMode('study'); renderChatHistoryList(); if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar(); }
        function deleteSessionItem(e, id) { e.stopPropagation(); if(confirm('Delete this session?')) { delete chatSessions[id]; if(id === currentSessionId) { const keys = Object.keys(chatSessions); if(keys.length > 0) { currentSessionId = keys[0]; loadChatSession(currentSessionId); } else { createNewChatSession(); } } else { saveSessionsData(); renderChatHistoryList(); } } }
        function saveCurrentChatHtml(userQueryText = null) { if(!chatSessions[currentSessionId] || currentMode === 'teacher') return; modeContents[currentMode] = chatFeed.innerHTML; chatSessions[currentSessionId].modesData = modeContents; if (userQueryText && chatSessions[currentSessionId].title === "New Session") { chatSessions[currentSessionId].title = userQueryText.substring(0, 20) + "..."; } saveSessionsData(); }
        function saveSessionsData() { localStorage.setItem('ge_nius_sessions_royal_v6', JSON.stringify(chatSessions)); localStorage.setItem('ge_nius_current_session_royal_v6', currentSessionId); renderChatHistoryList(); }
        function renderChatHistoryList() { const listDiv = document.getElementById('chatHistoryList'); if(!listDiv) return; listDiv.innerHTML = ''; const sortedIds = Object.keys(chatSessions).sort((a, b) => b - a); sortedIds.forEach(id => { const session = chatSessions[id]; const isActive = id === currentSessionId ? 'active' : ''; listDiv.innerHTML += `<div class="history-item ${isActive}" onclick="loadChatSession('${id}')"><div class="history-item-content"><i data-lucide="message-square" style="width: 13px; height: 13px;"></i><span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${session.title}</span></div><button class="delete-history-btn" onclick="deleteSessionItem(event, '${id}')"><i data-lucide="trash-2" style="width: 13px; height: 13px;"></i></button></div>`; }); lucide.createIcons({root: listDiv}); }
        initSessions();

        window.speakText = function(text) { if ('speechSynthesis' in window) { window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(decodeURIComponent(text)); utterance.rate = 1.0; utterance.pitch = 1.0; window.speechSynthesis.speak(utterance); } };
        window.copyCodeText = function(btn) { const container = btn.closest('.complex-card-box'); if(container) { const contentText = container.querySelector('.ai-content').innerText; navigator.clipboard.writeText(contentText).then(() => { const originalHtml = btn.innerHTML; btn.innerHTML = `<i data-lucide="check" style="width:12px;height:12px;"></i> Copied`; lucide.createIcons({root: btn}); setTimeout(() => { btn.innerHTML = originalHtml; lucide.createIcons({root: btn}); }, 2000); }); } };

        // Docs System
        let curriculumDocs = []; fetchDocs();
        function fetchDocs() { fetch('/api/docs').then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }); }
        window.toggleDocCollapse = function(id) { const el = document.getElementById('doc-body-' + id); const icon = document.getElementById('doc-icon-' + id); if(el.style.display === 'none' || el.style.display === '') { el.style.display = 'block'; icon.style.transform = 'rotate(180deg)'; } else { el.style.display = 'none'; icon.style.transform = 'rotate(0deg)'; } };
        function renderDocs() { const listDiv = document.getElementById('docsList'); if (!listDiv) return; if (curriculumDocs.length === 0) { listDiv.innerHTML = '<div style="color: var(--text-dim); text-align: center; padding: 20px; font-size:0.8rem;">No documents uploaded yet.</div>'; return; } listDiv.innerHTML = curriculumDocs.map((item, index) => `<div class="doc-card-compact"><div class="doc-card-header" onclick="toggleDocCollapse(${item.id})"><span class="doc-card-title"><i data-lucide="file-text" style="width:14px;height:14px;"></i> Doc ${index + 1}</span><div style="display:flex; align-items:center; gap:8px;"><button class="btn" style="padding:2px 6px; font-size:0.7rem; color:var(--danger); border:none; background:transparent;" onclick="event.stopPropagation(); deleteDoc(${item.id})"><i data-lucide="trash-2" style="width:14px;height:14px;"></i></button><i data-lucide="chevron-down" id="doc-icon-${item.id}" style="width:16px;height:16px;color:var(--text-dim);transition:0.3s;"></i></div></div><div class="doc-card-body" id="doc-body-${item.id}">${item.concepts}</div></div>`).join(''); lucide.createIcons({root: listDiv}); }

        // PARALLEL UPLOAD FIX
        async function handleDocImageSelect(e) {
            const files = e.target.files; if (!files || files.length === 0) return;
            const statusDiv = document.getElementById('uploadStatus');
            if(statusDiv) { statusDiv.innerHTML = `Processing ${files.length} file(s) fast...`; statusDiv.style.color = 'var(--primary)'; }
            
            const uploadPromises = Array.from(files).map(file => {
                return new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = async function(evt) {
                        try {
                            const res = await fetch('/api/docs/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: evt.target.result }) });
                            const data = await res.json(); resolve(data);
                        } catch(e) { resolve(null); }
                    }; reader.readAsDataURL(file);
                });
            });
            
            const results = await Promise.all(uploadPromises);
            const successResult = results.reverse().find(r => r && r.docs);
            if(successResult) curriculumDocs = successResult.docs;
            
            renderDocs();
            if(statusDiv) { statusDiv.innerHTML = 'Saved successfully!'; statusDiv.style.color = 'var(--accent-green)'; }
        }
        document.getElementById('docFileInputCamera').addEventListener('change', handleDocImageSelect);
        document.getElementById('docFileInputGallery').addEventListener('change', handleDocImageSelect);

        async function handleFileSelect(e, isTeacher) {
            const file = e.target.files[0]; if(!file) return;
            const reader = new FileReader();
            reader.onload = async function(evt) {
                const b64 = evt.target.result;
                if(isTeacher) { const stat = document.getElementById('teacherUploadStatus'); stat.innerText = "Compressing & Uploading to Curriculum..."; stat.style.color = "var(--primary)"; await fetch('/api/teacher/upload', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({file: b64, filename: file.name}) }); stat.innerText = "Uploaded successfully!"; stat.style.color = "var(--accent-green)"; fetchTeacherDocs(); } 
                else { attachedQuestionBase64 = b64; document.getElementById('questionImgPreview').style.display = 'flex'; document.getElementById('magicMenu').classList.remove('show'); const btn = document.getElementById('magicBtn'); if(btn) btn.classList.remove('active-magic'); }
            }; reader.readAsDataURL(file); e.target.value = '';
        }
        document.getElementById('teacherUploadBtn').addEventListener('change', (e) => handleFileSelect(e, true));
        document.getElementById('qFileInputGallery').addEventListener('change', (e) => handleFileSelect(e, false));
        document.getElementById('qFileInputCamera').addEventListener('change', (e) => handleFileSelect(e, false));
        function removeQuestionImage() { attachedQuestionBase64 = null; document.getElementById('questionImgPreview').style.display = 'none'; }
        function deleteDoc(id) { fetch('/api/docs/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) }).then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }); }
        async function fetchTeacherDocs() { const res = await fetch('/api/teacher/docs'); const data = await res.json(); const list = document.getElementById('teacherDocsList'); list.innerHTML = data.docs.map(d => `<div style="background:var(--card); padding:10px 14px; border-radius:12px; border:1px solid var(--border); display:flex; justify-content:space-between; align-items:center;"><span style="font-weight:600; font-size:0.85rem;"><i data-lucide="file-check" style="width:14px;height:14px; margin-right:4px;"></i> ${d.title}</span><span style="font-size:0.75rem; color:var(--text-dim);">Compressed</span></div>`).join('') || "<div style='color:var(--text-dim); font-size:0.85rem; text-align:center;'>No materials uploaded yet.</div>"; lucide.createIcons({root: list}); }

        // Retry Function
        window.retryRequest = function(btn) {
            const row = btn.closest('.message-row');
            if(row) chatFeed.removeChild(row);
            if(lastPayload) {
                document.getElementById('userQuery').value = lastPayload.query;
                submitQuestion(lastPayload.isSummary, true);
            }
        };

        function submitQuestion(isSummary = false, isRetry = false) {
            if (isAiThinking) return;
            const queryInput = document.getElementById('userQuery');
            let query = queryInput.value.trim();

            if(isSummary) {
                // Remove the manual [DOC_IDS: ...] injected earlier so user doesn't see it raw if we clean it, but we need it.
                // It's fine to leave it for backend parsing.
            }

            if (!query && !attachedQuestionBase64) return;
            if (currentMode === 'study' && curriculumDocs.length === 0) { alert('Study mode requires uploaded curriculum documents. Switch to General or Games!'); return; }
            if (currentUser && currentUser.role === 'student' && currentMode === 'games' && currentUser.hearts <= 0) { alert("You have 0 hearts left! Take a break."); return; }
            
            isAiThinking = true; document.getElementById('inputPanel').classList.add('locked');
            const sendBtn = document.getElementById('sendBtn'); sendBtn.classList.add('loading'); sendBtn.innerHTML = `<i data-lucide="loader-2" class="spinner-icon" style="width:20px;height:20px;"></i>`; lucide.createIcons({root: sendBtn});
            
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();

            if(!isRetry) {
                let userTextDisplay = query.replace(/\\n/g, '<br>');
                if (attachedQuestionBase64) { userTextDisplay = (query ? userTextDisplay + '<br>' : '') + `<span style="color:var(--primary); font-size:0.85em; display:flex; align-items:center; gap:4px; margin-top:6px;"><i data-lucide="image" style="width:14px;height:14px;"></i> <span data-i18n="docAttached">Document attached</span></span>`; }
                const userRow = document.createElement('div'); userRow.className = 'message-row'; userRow.style.alignItems = 'flex-end';
                userRow.innerHTML = `<div class="message-sender" style="justify-content:flex-end; margin-bottom: 2px;"><div class="avatar-user"><i data-lucide="user" style="width:14px;height:14px;color:#fff;"></i></div></div><div class="message-text-user">${userTextDisplay}</div>`;
                chatFeed.appendChild(userRow); lucide.createIcons({root: userRow});
            }

            const loadingRow = document.createElement('div'); loadingRow.className = 'message-row loading-bubble-temp';
            loadingRow.innerHTML = `<div class="message-sender" style="margin-bottom: 2px;"><div class="avatar-ai"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;color:var(--primary);"><path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/><circle cx="12" cy="15" r="2"/><path d="M20 15h2"/><path d="M2 15h2"/></svg></div></div><div class="hologram-thinking">Processing logic...</div>`;
            chatFeed.appendChild(loadingRow); lucide.createIcons({root: loadingRow});
            saveCurrentChatHtml(query);

            const payload = { query: query, file: attachedQuestionBase64, mode: currentMode, isSummary: isSummary, persona: currentPersonaValue };
            lastPayload = payload; // save for retry
            
            queryInput.value = ''; queryInput.style.height = 'auto'; removeQuestionImage(); chatFeed.scrollTop = chatFeed.scrollHeight;

            fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            .then(res => res.json())
            .then(data => {
                chatFeed.removeChild(loadingRow);
                const aiRow = document.createElement('div'); aiRow.className = 'message-row';

                let avatarHtml = `<div class="message-sender" style="margin-bottom: 2px;"><div class="avatar-ai"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;color:var(--primary);"><path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/><circle cx="12" cy="15" r="2"/><path d="M20 15h2"/><path d="M2 15h2"/></svg></div></div>`;

                if (data.status === 'out_of_scope') {
                    aiRow.innerHTML = avatarHtml + `<div class="message-text-ai" style="color:#fca5a5;">Out of curriculum scope. Switch to General mode.</div>`;
                } else if (data.status === 'success') {
                    let fullText = data.answer;
                    
                    if(data.hearts !== undefined && data.xp !== undefined && currentUser.role === 'student' && currentMode === 'games') {
                        currentUser.hearts = data.hearts; currentUser.xp = data.xp;
                        updateGamificationHUD(data.hearts, data.xp);
                    }

                    // Process text for MathJax safely
                    let finalHtml = processTextForMathJax(fullText);
                    const encoded = encodeURIComponent(fullText);
                    const blockId = 'res-' + Date.now();
                    
                    if (isSummary) {
                        // Advanced Summary Card with PDF Export
                        aiRow.innerHTML = avatarHtml + `
                            <div class="complex-card-box" style="border: 1px solid var(--accent-gold);">
                                <div class="complex-card-header" style="color:var(--accent-gold);">
                                    <span><i data-lucide="sparkles" style="width:12px;height:12px;"></i> Smart Summary</span>
                                    <div style="display:flex;gap:5px;">
                                        <button class="action-btn" data-target="${blockId}" onclick="exportToPDF(this)"><i data-lucide="download" style="width:12px;height:12px;"></i> PDF</button>
                                        <button class="action-btn" onclick="copyCodeText(this)"><i data-lucide="copy" style="width:12px;height:12px;"></i> <span data-i18n="copy">Copy</span></button>
                                    </div>
                                </div>
                                <div class="message-text-ai ai-content" id="${blockId}" style="padding:15px; background:var(--bg-main); border-radius:10px;">${finalHtml}</div>
                            </div>
                            <div><button class="audio-speech-btn" onclick="speakText('${encoded}')"><i data-lucide="volume-2" style="width:14px;height:14px;"></i> <span data-i18n="listen">Listen</span></button></div>
                        `;
                    } else if (fullText.includes("```") || fullText.length > 500) {
                        aiRow.innerHTML = avatarHtml + `
                            <div class="complex-card-box">
                                <div class="complex-card-header">
                                    <span>Detailed Output</span>
                                    <button class="action-btn" onclick="copyCodeText(this)"><i data-lucide="copy" style="width:12px;height:12px;"></i> <span data-i18n="copy">Copy</span></button>
                                </div>
                                <div class="message-text-ai ai-content" id="${blockId}">${finalHtml}</div>
                            </div>
                            <div><button class="audio-speech-btn" onclick="speakText('${encoded}')"><i data-lucide="volume-2" style="width:14px;height:14px;"></i> <span data-i18n="listen">Listen</span></button></div>
                        `;
                    } else {
                        aiRow.innerHTML = avatarHtml + `
                            <div class="message-text-ai ai-content" id="${blockId}" style="padding-top:4px;">${finalHtml}</div>
                            <div><button class="audio-speech-btn" onclick="speakText('${encoded}')"><i data-lucide="volume-2" style="width:14px;height:14px;"></i> <span data-i18n="listen">Listen</span></button></div>
                        `;
                    }
                } else {
                    aiRow.innerHTML = avatarHtml + `<div class="error-bubble"><span>Error: ${data.error || 'Failed.'}</span> <button class="btn" style="padding:4px 10px; font-size:0.75rem;" onclick="retryRequest(this)"><i data-lucide="refresh-cw" style="width:12px;height:12px;"></i> <span data-i18n="retry">Retry</span></button></div>`;
                }
                
                chatFeed.appendChild(aiRow); lucide.createIcons({root: aiRow});
                chatFeed.scrollTop = chatFeed.scrollHeight;
                if (window.MathJax) window.MathJax.typesetPromise([aiRow]).catch(e => {});
                saveCurrentChatHtml();
                changeUILanguage();
            }).catch(err => {
                chatFeed.removeChild(loadingRow);
                const errRow = document.createElement('div'); errRow.className = 'message-row';
                errRow.innerHTML = `
                    <div class="message-sender"><div class="avatar-ai"><i data-lucide="alert-circle" style="width:14px;height:14px;color:var(--danger);"></i></div></div>
                    <div class="error-bubble"><span>Connection Error.</span> <button class="btn" style="padding:4px 10px; font-size:0.75rem;" onclick="retryRequest(this)"><i data-lucide="refresh-cw" style="width:12px;height:12px;"></i> <span data-i18n="retry">Retry</span></button></div>`;
                chatFeed.appendChild(errRow); lucide.createIcons({root: errRow});
                changeUILanguage();
            }).finally(() => {
                isAiThinking = false;
                document.getElementById('inputPanel').classList.remove('locked');
                sendBtn.classList.remove('loading');
                sendBtn.innerHTML = `<i data-lucide="arrow-up" id="sendIcon"></i>`;
                lucide.createIcons({root: sendBtn});
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

            elif self.path == "/api/teacher/docs":
                self.send_json_response({"docs": MOCK_DB.get("GLOBAL_DOCS", [])})

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
                        "role": req_json.get("role"), "level": req_json.get("level"), "hearts": 5, "xp": 0
                    }
                MOCK_SESSIONS[session_id] = email
                self.send_json_response({"success": True, "user": MOCK_USERS[email]})
            
            elif self.path == "/api/logout":
                if session_id in MOCK_SESSIONS:
                    del MOCK_SESSIONS[session_id]
                self.send_json_response({"success": True})

            elif self.path == "/api/teacher/upload":
                b64_file = req_json.get("file", "")
                filename = req_json.get("filename", "Document")
                if b64_file:
                    head, comp = compress_file_data(b64_file)
                    add_document_to_db(session_id, filename, f"Content extracted and compressed by ge_nius for {filename}.", is_global=True)
                self.send_json_response({"success": True})

            elif self.path == "/api/docs/upload":
                image_base64 = req_json.get("image")
                if not image_base64:
                    self.send_json_response({"error": "No image"})
                    return
                try:
                    prompt = "Read this document image and extract all concepts, text, and rules clearly."
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
                user = get_current_user(session_id)
                user_query = req_json.get("query", "")
                file_b64 = req_json.get("file")
                mode = req_json.get("mode", "study") 
                is_summary = req_json.get("isSummary", False)
                persona = req_json.get("persona", "human")
                docs = load_curriculum(session_id, user)

                # Summary specific doc filtering based on user selection logic parsing
                if is_summary and "[DOC_IDS:" in user_query:
                    import re
                    match = re.search(r'\[DOC_IDS:\s*([\d,]+)\]', user_query)
                    if match:
                        selected_ids = match.group(1).split(',')
                        docs = [d for d in docs if str(d['id']) in selected_ids]
                        # Remove the tag so the AI doesn't get confused
                        user_query = re.sub(r'\[DOC_IDS:\s*[\d,]+\]', '', user_query).strip()

                messages_content = []
                if file_b64:
                    if file_b64.startswith("data:image"):
                        messages_content.append({"type": "image_url", "image_url": {"url": file_b64}})
                    else:
                        messages_content.append({"type": "text", "text": "[File Attached. Read context.]"})

                persona_instructions = {
                    "strict": "Persona: Strict & Professional. Be highly formal, precise, and academic.",
                    "humor": "Persona: Entertainment & Light Humor. Keep it witty and fun.",
                    "roast": "Persona: Witty & Playful Challenge. Gently challenge the user's logic.",
                    "human": "Persona: Human-like & Warm. Be friendly, empathetic, natural."
                }.get(persona, "Persona: Human-like & Warm.")

                if mode == "general":
                    full_prompt = f"You are a global AI assistant named ge_nius.\n{persona_instructions}\nUser request: \"{user_query}\"\nIMPORTANT: Respond in the exact same language the user is using."
                elif mode == "games":
                    full_prompt = (
                        f"You are an interactive Brain Games and Puzzle master named ge_nius.\n{persona_instructions}\n"
                        f"The user is playing brain/thinking games.\nUser input: \"{user_query}\"\n"
                        f"IMPORTANT: If the user answers WRONG, prefix your response EXACTLY with [WRONG]. If CORRECT, prefix with [CORRECT]. Respond in their language."
                    )
                else:
                    all_concepts_summary = "\n\n".join([f"Document {d['id']} Title: {d['title']}\nContent: {d['concepts']}" for d in docs])
                    full_prompt = (
                        f"You are an expert tutor.\n{persona_instructions}\nHere is the student's curriculum study material:\n"
                        f"--- START CURRICULUM ---\n{all_concepts_summary}\n--- END CURRICULUM ---\n\n"
                    )
                    if is_summary:
                        full_prompt += f"User Request: {user_query}\n(Ensure LaTeX is formatted correctly, and use professional language translation without literal meaning loss)."
                    else:
                        full_prompt += f"User question: \"{user_query}\"\nIMPORTANT: Respond in the exact same language the user is asking in.\nIf completely unrelated to the curriculum, reply with EXACTLY: OUT_OF_SCOPE\nIf in scope, provide a clear, step-by-step explanation using proper LaTeX formatting for math."
                    
                messages_content.append({"type": "text", "text": full_prompt})

                payload = {
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": messages_content}],
                    "max_tokens": 4096
                }

                try:
                    ai_reply = self.send_api_request(payload)
                    resp_data = {"status": "success"}
                    
                    if mode == "study" and ("OUT_OF_SCOPE" in ai_reply or ai_reply.startswith("OUT_OF_SCOPE")):
                        resp_data["status"] = "out_of_scope"
                    else:
                        if user and user["role"] == "student" and mode == "games":
                            if "[WRONG]" in ai_reply:
                                user["hearts"] = max(0, user["hearts"] - 1)
                                ai_reply = ai_reply.replace("[WRONG]", "").strip()
                            elif "[CORRECT]" in ai_reply:
                                user["xp"] += 50
                                ai_reply = ai_reply.replace("[CORRECT]", "").strip()
                            resp_data["hearts"] = user["hearts"]
                            resp_data["xp"] = user["xp"]
                        
                        resp_data["answer"] = ai_reply

                    self.send_json_response(resp_data)
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
