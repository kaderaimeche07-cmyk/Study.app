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

MOCK_USERS = {}      # email -> {password, role, level, name, xp, hearts}
MOCK_SESSIONS = {}   # session_id -> email

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
            try:
                conn.close()
            except:
                pass
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
            try:
                conn.close()
            except:
                pass
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
            try:
                conn.close()
            except:
                pass
    if session_id in MOCK_DB:
        MOCK_DB[session_id] = [d for d in MOCK_DB[session_id] if str(d["id"]) != str(doc_id)]

# ==============================================================================
# HTML Frontend (ge_nius Royal World-Class UI - Seamless Drawer Refined)
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

        .main-wrapper { 
            padding: 10px; display: flex; flex-direction: column; gap: 0; 
            width: 100%; height: 100%; height: 100dvh; max-width: 900px; margin: 0 auto; 
        }

        /* --- Auth Overlay --- */
        #authOverlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(3, 3, 4, 0.95); backdrop-filter: blur(20px);
            z-index: 9999; display: flex; justify-content: center; align-items: center; padding: 20px;
            transition: opacity 0.4s ease;
        }
        .auth-card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 24px;
            padding: 30px; width: 100%; max-width: 400px; box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            display: flex; flex-direction: column; gap: 15px;
        }
        .role-selector { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 10px; }
        .role-card {
            background: var(--card); border: 1px solid var(--border); border-radius: 12px;
            padding: 12px 5px; text-align: center; cursor: pointer; font-size: 0.8rem; font-weight: 600;
            color: var(--text-dim); transition: all 0.2s; display: flex; flex-direction: column; align-items: center; gap: 6px;
        }
        .role-card.active { background: rgba(65, 105, 225, 0.15); color: var(--primary); border-color: var(--primary); }
        .custom-input, .custom-select {
            width: 100%; background: var(--bg-main); border: 1px solid var(--border); color: var(--text-main);
            padding: 12px 16px; border-radius: 12px; font-family: 'Inter', sans-serif; font-size: 0.95rem; outline: none;
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

        .app-brand {
            font-family: 'Outfit', sans-serif; font-weight: 900; font-size: 1.05rem;
            color: var(--text-main); letter-spacing: -0.5px; display: flex; align-items: center; gap: 6px;
        }
        .app-brand span { color: var(--primary); }
        .brand-icon { width: 18px; height: 18px; color: var(--primary); }

        .icon-btn {
            background: transparent; border: none; color: var(--text-main);
            border-radius: 50%; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: all 0.2s; flex-shrink: 0;
        }
        .icon-btn:hover { background: var(--card); color: var(--primary); transform: scale(1.05); }

        .mode-switcher-bar {
            display: flex; gap: 6px; background: rgba(0,0,0,0.25); padding: 4px; border-radius: 14px;
            justify-content: center; width: 100%; overflow-x: auto;
        }
        .mode-tab {
            padding: 6px 14px; background: transparent; border: none; color: var(--text-dim);
            font-family: 'Inter', sans-serif; font-weight: 600; font-size: 0.8rem; cursor: pointer;
            border-radius: 10px; white-space: nowrap; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.3s;
            flex: 1;
        }
        .mode-tab.active { background: var(--surface); color: var(--text-main); box-shadow: 0 2px 10px rgba(0,0,0,0.3); border: 1px solid var(--border); }
        .mode-tab.hidden { display: none !important; }

        .lucide { width: 18px; height: 18px; stroke-width: 2.2; display: inline-block; vertical-align: middle; }

        .games-stats-bar {
            display: none; background: rgba(65, 105, 225, 0.1); border: 1px solid rgba(65, 105, 225, 0.2);
            padding: 8px 16px; border-radius: 16px; align-items: center; justify-content: space-between; font-size: 0.85rem; color: #93c5fd; flex-shrink: 0; margin-bottom: 10px;
        }
        .games-stats-bar.active { display: flex; }
        .hud-hearts { color: var(--danger); letter-spacing: 2px;}

        /* --- REDESIGNED DRAWER SIDEBAR --- */
        .sidebar-overlay { 
            position: fixed; top: 0; left: 0; right: 0; bottom: 0; 
            background: rgba(0,0,0,0.75); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); 
            z-index: 999; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; 
        }
        .sidebar-overlay.active { opacity: 1; pointer-events: auto; }
        
        .sidebar {
            position: fixed; top: 0; left: -100%; width: 85%; max-width: 320px; height: 100vh; height: 100dvh;
            background: var(--surface); border-right: 1px solid var(--border);
            z-index: 1000; transition: left 0.35s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex; flex-direction: column; padding: 18px 16px; box-shadow: 10px 0 40px rgba(0,0,0,0.6);
            overflow-y: auto;
        }
        .sidebar.open { left: 0; }
        
        .sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 12px;}
        .sidebar h3 { margin: 0; font-size: 1.05rem; color: var(--text-main); font-weight: 800; display: flex; align-items: center; gap: 8px;}
        
        .user-profile-card {
            background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 12px 14px;
            display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;
        }
        .user-info-text { display: flex; flex-direction: column; gap: 2px; }
        .user-name-title { font-weight: 700; font-size: 0.9rem; color: var(--primary); }
        .user-role-subtitle { font-size: 0.72rem; color: var(--text-dim); }

        .btn-logout-mini {
            background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: var(--danger);
            padding: 6px 10px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; cursor: pointer;
            display: flex; align-items: center; gap: 4px; transition: all 0.2s;
        }
        .btn-logout-mini:hover { background: var(--danger); color: white; }

        .sidebar-section-title { font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; margin: 14px 0 8px 0; display: flex; align-items: center; gap: 6px;}
        .persona-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
        .persona-chip {
            background: var(--bg-main); border: 1px solid var(--border); border-radius: 12px;
            padding: 8px; font-size: 0.75rem; font-family: 'Inter', sans-serif; font-weight: 600;
            color: var(--text-dim); cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px;
            transition: all 0.2s ease;
        }
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

        /* --- Chat Layout & Micro-Avatars --- */
        .chat-container-wrapper { position: relative; flex: 1; display: flex; flex-direction: column; min-height: 0; }
        .chat-feed {
            display: flex; flex-direction: column; gap: 20px; flex: 1; overflow-y: auto; padding: 10px 4px 20px 4px;
            background: transparent; scroll-behavior: smooth;
        }
        
        .message-row { display: flex; flex-direction: column; gap: 4px; width: 100%; animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
        @keyframes slideUp { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
        
        .message-sender { display: flex; align-items: center; }
        .avatar-user { background: var(--primary); padding: 6px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px var(--primary-glow);}
        .avatar-ai { background: var(--card); padding: 6px; border-radius: 50%; border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; }

        .message-text-user { 
            font-size: 0.95rem; line-height: 1.6; color: var(--text-main); font-weight: 400; word-break: break-word;
            background: var(--surface); padding: 12px 16px; border-radius: 20px; border-top-right-radius: 4px; width: fit-content; max-width: 85%;
            border: 1px solid var(--border); box-shadow: 0 4px 15px rgba(0,0,0,0.1); align-self: flex-end;
        }
        
        .message-text-ai { font-size: 1.05rem; line-height: 1.75; color: var(--text-main); font-weight: 500; word-break: break-word; align-self: flex-start; max-width: 95%;}

        .submarine-logo { width: 72px; height: 72px; filter: drop-shadow(0 0 20px rgba(65, 105, 225, 0.5)); color: var(--primary); }

        .complex-card-box {
            background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 16px;
            margin: 6px 0; box-shadow: 0 4px 25px rgba(0,0,0,0.25); position: relative; overflow-x: auto;
        }
        .complex-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; font-size: 0.8rem; color: var(--primary); font-weight: bold; }
        
        .copy-code-btn { background: var(--card); color: var(--text-dim); border: 1px solid var(--border); border-radius: 8px; padding: 5px 10px; font-size: 0.75rem; cursor: pointer; display: flex; align-items: center; gap: 4px; transition: all 0.2s; }
        .copy-code-btn:hover { background: var(--primary); color: white; border-color: var(--primary); }

        .audio-speech-btn { background: transparent; border: 1px solid var(--border); color: var(--text-dim); border-radius: 12px; padding: 6px 14px; font-size: 0.8rem; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; margin-top: 8px; transition: all 0.2s;}
        .audio-speech-btn:hover { background: var(--card); color: var(--primary); }

        .hologram-thinking {
            display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 0.92rem; margin-top: 4px;
            background: linear-gradient(90deg, #4169E1, #8B5CF6, #fbbf24, #4169E1);
            background-size: 300% 100%;
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            animation: gradientMove 2s linear infinite;
        }
        @keyframes gradientMove { 0% { background-position: 100% 0; } 100% { background-position: 0 0; } }

        /* --- Input Box --- */
        .chat-input-container { flex-shrink: 0; padding-bottom: 6px; position: relative; margin-top: auto;}
        .input-glass-panel {
            background: rgba(15, 16, 20, 0.85); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
            border: 1px solid var(--border); border-radius: 28px; padding: 8px 10px 8px 16px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.5); display: flex; align-items: center; gap: 10px;
            transition: all 0.3s ease; position: relative; z-index: 10;
        }
        .input-glass-panel:focus-within { border-color: rgba(65, 105, 225, 0.5); box-shadow: 0 12px 40px rgba(65, 105, 225, 0.15); }
        .input-glass-panel.locked { opacity: 0.6; pointer-events: none; }

        textarea {
            background: transparent; color: var(--text-main); border: none; outline: none;
            font-family: 'Inter', sans-serif; font-size: 1rem; resize: none; max-height: 120px; min-height: 24px; line-height: 1.5; width: 100%;
            padding: 8px 0;
        }
        textarea::placeholder { color: #64748b; }

        .magic-menu {
            position: absolute; bottom: 70px; left: 10px; background: var(--surface); border: 1px solid var(--border);
            border-radius: 18px; padding: 8px; display: flex; flex-direction: column; gap: 4px;
            opacity: 0; transform: translateY(15px) scale(0.95); pointer-events: none;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); box-shadow: 0 12px 30px rgba(0,0,0,0.6); z-index: 20;
        }
        .magic-menu.show { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }
        
        .magic-item { 
            display: flex; align-items: center; gap: 10px; padding: 10px 16px; color: var(--text-main); 
            font-size: 0.9rem; font-weight: 500; border-radius: 12px; cursor: pointer; transition: all 0.2s;
        }
        .magic-item:hover { background: var(--card); color: var(--primary); }

        .tool-btn {
            background: transparent; border: none; color: var(--text-dim); border-radius: 50%; width: 36px; height: 36px;
            display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; flex-shrink: 0;
        }
        .tool-btn:hover { background: var(--card); color: var(--text-main); }
        .tool-btn.active-magic { background: var(--card); color: var(--primary); transform: rotate(45deg); }
        .tool-btn.recording { color: var(--danger) !important; animation: pulse 1.2s infinite; }

        @keyframes pulse { 0% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(1.1); } 100% { opacity: 1; transform: scale(1); } }

        .send-btn-royal {
            background: var(--primary); color: white; border: none; border-radius: 50%; width: 42px; height: 42px;
            display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            box-shadow: 0 4px 15px var(--primary-glow); flex-shrink: 0;
        }
        .send-btn-royal:active { transform: scale(0.9); }
        .send-btn-royal.loading { background: transparent; border: 2px solid var(--border); box-shadow: none; pointer-events: none; }
        .spinner-icon { animation: spin 1s linear infinite; color: var(--text-dim); }
        @keyframes spin { 100% { transform: rotate(360deg); } }

        .btn { background: var(--card); color: var(--text-main); border: 1px solid var(--border); padding: 10px 14px; border-radius: 14px; font-family: 'Inter', sans-serif; font-weight: 600; font-size: 0.85rem; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.2s; }
        .btn:hover { background: var(--surface); border-color: var(--primary); color: var(--primary); }
        .btn-purple { background: linear-gradient(135deg, #1d4ed8, #4169E1); color: white; border: none; box-shadow: 0 4px 15px var(--primary-glow);}
        
        input[type="file"] { display: none; }
        .image-preview-bar { display: none; align-items: center; justify-content: space-between; background: rgba(65, 105, 225, 0.1); border: 1px solid rgba(65, 105, 225, 0.3); padding: 8px 12px; border-radius: 16px; font-size: 0.82rem; color: #93c5fd; margin-bottom: 8px; }

        /* Compact Document Cards */
        .doc-card-compact { background: var(--bg-main); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 8px; }
        .doc-card-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; cursor: pointer; }
        .doc-card-title { font-weight: 700; color: var(--primary); font-size: 0.85rem; display: flex; align-items: center; gap: 6px; }
        .doc-card-body { padding: 10px 14px; border-top: 1px solid var(--border); font-size: 0.8rem; color: var(--text-dim); line-height: 1.6; display: none; background: var(--surface); border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;}
    </style>
</head>
<body>

    <!-- ================= AUTHENTICATION OVERLAY ================= -->
    <div id="authOverlay">
        <div class="auth-card">
            <div style="text-align: center; margin-bottom: 10px;">
                <svg viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:48px;height:48px;margin-bottom:10px;">
                    <path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/>
                </svg>
                <h2 style="margin:0; font-family:'Outfit';">Welcome to ge_nius</h2>
                <p style="color:var(--text-dim); font-size:0.85rem; margin-top:5px;">Select your role to configure the platform</p>
            </div>
            
            <div class="role-selector">
                <div class="role-card active" onclick="selectRole('student')" id="role-student"><i data-lucide="graduation-cap"></i> Student</div>
                <div class="role-card" onclick="selectRole('teacher')" id="role-teacher"><i data-lucide="presentation"></i> Teacher</div>
                <div class="role-card" onclick="selectRole('citizen')" id="role-citizen"><i data-lucide="globe"></i> Citizen</div>
            </div>

            <input type="text" id="authName" class="custom-input" placeholder="Full Name">
            <input type="email" id="authEmail" class="custom-input" placeholder="Email Address">
            <input type="password" id="authPassword" class="custom-input" placeholder="Password">
            
            <select id="authLevel" class="custom-select">
                <option value="" disabled selected>Select Study Level...</option>
                <option value="Middle School">Middle School (التعليم المتوسط)</option>
                <option value="High School">High School (التعليم الثانوي)</option>
                <option value="University - Civil Engineering (L2)">University - Civil Engineering (L2)</option>
                <option value="University - Computer Science">University - Computer Science</option>
                <option value="Other">Other</option>
            </select>

            <button class="btn btn-purple" id="authBtn" onclick="performAuth()">Enter Platform <i data-lucide="arrow-right"></i></button>
            <div id="authError" style="color:var(--danger); font-size:0.8rem; text-align:center;"></div>
        </div>
    </div>
    <!-- ========================================================= -->

    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h3><i data-lucide="menu"></i> Menu</h3>
            <button class="icon-btn" style="width:30px; height:30px;" onclick="toggleSidebar()"><i data-lucide="x"></i></button>
        </div>
        
        <!-- Redesigned User Profile Badge -->
        <div class="user-profile-card">
            <div class="user-info-text">
                <div class="user-name-title" id="sidebarUserName">User</div>
                <div class="user-role-subtitle" id="sidebarRoleLabel">Role</div>
            </div>
            <button class="btn-logout-mini" onclick="performLogout()"><i data-lucide="log-out" style="width:12px;height:12px;"></i> Logout</button>
        </div>

        <button class="btn" onclick="createNewChatSession()" style="width: 100%; justify-content: center; margin-bottom: 8px;">
            <i data-lucide="plus-circle"></i> New Session
        </button>

        <button class="btn btn-purple" onclick="switchSection('docsTab')" style="width: 100%; justify-content: center; margin-bottom: 12px;" id="btnCurriculum">
            <i data-lucide="folder-kanban"></i> Curriculum
        </button>

        <div class="sidebar-section-title"><i data-lucide="brain"></i> AI Persona</div>
        <div class="persona-grid" id="personaContainer">
            <button class="persona-chip active" data-val="human" onclick="selectPersona('human', this)"><i data-lucide="heart" style="width:13px;height:13px;"></i> Human</button>
            <button class="persona-chip" data-val="strict" onclick="selectPersona('strict', this)"><i data-lucide="briefcase" style="width:13px;height:13px;"></i> Strict</button>
            <button class="persona-chip" data-val="humor" onclick="selectPersona('humor', this)"><i data-lucide="smile" style="width:13px;height:13px;"></i> Humor</button>
            <button class="persona-chip" data-val="roast" onclick="selectPersona('roast', this)"><i data-lucide="flame" style="width:13px;height:13px;"></i> Roast</button>
        </div>

        <div class="sidebar-section-title"><i data-lucide="history"></i> History</div>
        <div class="chat-history-list" id="chatHistoryList"></div>

        <div style="margin-top: auto; padding-top: 12px; border-top: 1px solid var(--border); display:flex; gap:8px;">
            <button class="btn" style="flex:1; justify-content: center; padding: 8px;" onclick="toggleTheme()" title="Toggle Theme">
                <i data-lucide="moon" id="themeIcon"></i>
            </button>
        </div>
    </aside>

    <div class="main-wrapper">
        <div class="top-nav-bar">
            <div class="nav-header-row">
                <button class="icon-btn" onclick="toggleSidebar()" title="Menu">
                    <i data-lucide="align-left"></i>
                </button>
                <div class="app-brand">
                    <svg class="brand-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/>
                        <path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/>
                    </svg>
                    ge<span>_</span>nius
                </div>
            </div>

            <div class="mode-switcher-bar">
                <button class="mode-tab hidden" id="modeTeacher" onclick="switchMode('teacher')">Dashboard</button>
                <button class="mode-tab hidden" id="modeStudy" onclick="switchMode('study')">Study</button>
                <button class="mode-tab hidden" id="modeGames" onclick="switchMode('games')">Games</button>
                <button class="mode-tab active" id="modeGeneral" onclick="switchMode('general')">General</button>
            </div>
        </div>

        <div class="games-stats-bar" id="gamesStatsBar">
            <span class="hud-hearts" id="hudHearts">❤️❤️❤️❤️❤️</span>
            <span>⭐ XP: <strong id="userXp">0</strong></span>
            <span style="color: #93c5fd;">Ready to play!</span>
        </div>

        <!-- Teacher Dashboard Tab -->
        <div class="tab-section" id="teacherTab" style="gap:15px; overflow-y:auto; padding:0 4px;">
            <div class="card" style="text-align:center;">
                <h3 style="color:var(--primary); margin-top:0;"><i data-lucide="upload-cloud"></i> Upload Curriculum</h3>
                <p style="color:var(--text-dim); font-size:0.9rem;">Upload PDFs, DOCs, or Images. The ge_nius engine will automatically compress and integrate them globally.</p>
                <div style="display:flex; gap:10px; justify-content:center; margin-top:15px;">
                    <label for="teacherUploadBtn" class="btn btn-purple" style="width:auto; padding:12px 30px;"><i data-lucide="file-plus"></i> Select File (PDF/Image)</label>
                    <input type="file" id="teacherUploadBtn" accept=".pdf, .doc, .docx, image/*">
                </div>
                <div id="teacherUploadStatus" style="margin-top:10px; font-weight:bold; font-size:0.85rem;"></div>
            </div>
            <h4 style="margin:0; color:var(--text-main);">Global Curriculum Archive</h4>
            <div id="teacherDocsList" style="display:flex; flex-direction:column; gap:10px; padding-bottom:20px;"></div>
        </div>

        <!-- Chat / Ask Tab -->
        <div class="tab-section active" id="askTab">
            <div class="chat-container-wrapper">
                <div class="chat-feed" id="chatFeed">
                    <div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 80px 20px; display: flex; flex-direction: column; align-items: center; gap: 16px;">
                        <svg class="submarine-logo" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/>
                            <path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/>
                            <circle cx="12" cy="15" r="2"/><path d="M20 15h2"/><path d="M2 15h2"/>
                        </svg>
                        <p style="margin: 0; font-size: 1rem; max-width: 250px; line-height: 1.5; color: var(--text-dim);">Platform Ready.</p>
                    </div>
                </div>
            </div>

            <div class="chat-input-container">
                <div class="image-preview-bar" id="questionImgPreview">
                    <span style="display: flex; align-items: center; gap: 6px;"><i data-lucide="image" style="width: 14px; height: 14px;"></i> Document attached</span>
                    <span style="cursor: pointer; color: #fca5a5; font-weight: bold; display: flex; align-items: center;" onclick="removeQuestionImage()"><i data-lucide="x" style="width: 16px; height: 16px;"></i></span>
                </div>

                <div class="magic-menu" id="magicMenu">
                    <label for="qFileInputCamera" class="magic-item">
                        <i data-lucide="camera" style="color:var(--primary)"></i> Take Photo
                    </label>
                    <input type="file" id="qFileInputCamera" accept="image/*" capture="environment">
                    
                    <label for="qFileInputGallery" class="magic-item">
                        <i data-lucide="image-plus" style="color:var(--primary)"></i> Upload PDF/Doc
                    </label>
                    <input type="file" id="qFileInputGallery" accept=".pdf, .doc, .docx, image/*">

                    <div class="magic-item" id="btnSummarize" onclick="triggerSummarizer()" style="display:none; color:var(--accent-gold); font-weight:bold;">
                        <i data-lucide="sparkles"></i> AI Summarize Lesson
                    </div>
                </div>

                <div class="input-glass-panel" id="inputPanel">
                    <button class="tool-btn" id="magicBtn" onclick="toggleMagicMenu()" title="Attach">
                        <i data-lucide="plus"></i>
                    </button>

                    <textarea id="userQuery" placeholder
