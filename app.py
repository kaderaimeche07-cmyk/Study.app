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
# AI API Key & System Config
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
        finally:
            try: conn.close()
            except: pass
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
        finally:
            try: conn.close()
            except: pass
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
        finally:
            try: conn.close()
            except: pass
    if session_id in MOCK_DB:
        MOCK_DB[session_id] = [d for d in MOCK_DB[session_id] if str(d["id"]) != str(doc_id)]

# ==============================================================================
# HTML Frontend (ge_nius Supreme Lock & Fast-Track Edition)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="en" dir="auto">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ge_nius Assistant - Supreme Edition</title>
    
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
            --bg-main: #070605; 
            --surface: #12100f; 
            --card: #1c1917;
            --primary: #3b82f6; 
            --accent-purple: #8b5cf6; 
            --accent-green: #10b981;
            --danger: #ef4444; 
            --text-main: #fafaf9; 
            --text-dim: #999490;
            --border: rgba(255, 255, 255, 0.08); 
            --glass: rgba(18, 16, 15, 0.85);
        }

        body.light-mode {
            --bg-main: #f8fafc; --surface: #ffffff; --card: #f1f5f9;
            --primary: #2563eb; --text-main: #0f172a; --text-dim: #64748b;
            --border: rgba(0, 0, 0, 0.08); --glass: rgba(255, 255, 255, 0.85);
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        html, body {
            font-family: 'Inter', sans-serif; 
            background-color: var(--bg-main); color: var(--text-main);
            margin: 0; padding: 0; width: 100vw; height: 100vh; height: 100dvh; overflow: hidden;
            background-image: radial-gradient(circle at 10% 10%, rgba(139, 92, 246, 0.07), transparent 40%),
                              radial-gradient(circle at 90% 90%, rgba(59, 130, 246, 0.07), transparent 40%);
            background-attachment: fixed;
        }

        .main-wrapper { 
            padding: 8px; display: flex; flex-direction: column; gap: 8px; 
            width: 100%; height: 100%; height: 100dvh; max-width: 900px; margin: 0 auto; 
        }

        .top-nav-bar {
            display: flex; justify-content: space-between; align-items: center;
            padding: 4px 6px; flex-shrink: 0; gap: 8px;
        }

        .icon-btn {
            background: var(--surface); border: 1px solid var(--border); color: var(--text-main);
            border-radius: 12px; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: all 0.2s; flex-shrink: 0;
        }
        .icon-btn:hover { background: var(--primary); color: white; transform: scale(1.05); }

        .mode-switcher-bar {
            display: flex; gap: 4px; background: var(--surface); padding: 3px; border-radius: 14px;
            border: 1px solid var(--border); flex: 1; overflow-x: auto; box-shadow: inset 0 2px 5px rgba(0,0,0,0.2);
        }
        .mode-tab {
            flex: 1; padding: 6px 10px; background: transparent; border: none; color: var(--text-dim);
            font-family: 'Inter', sans-serif; font-weight: 600; font-size: 0.8rem; cursor: pointer;
            border-radius: 10px; white-space: nowrap; display: flex; align-items: center; justify-content: center; gap: 5px; transition: all 0.2s;
        }
        .mode-tab.active { background: var(--primary); color: white; box-shadow: 0 2px 12px rgba(59,130,246,0.35); }

        .lucide { width: 17px; height: 17px; stroke-width: 2.2; display: inline-block; vertical-align: middle; }

        /* Sidebar & Overlay */
        .sidebar-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(6px); z-index: 999; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; }
        .sidebar-overlay.active { opacity: 1; pointer-events: auto; }
        
        .sidebar {
            position: fixed; top: 0; left: -320px; width: 290px; height: 100vh; height: 100dvh;
            background: var(--surface); border-right: 1px solid var(--border);
            z-index: 1000; transition: left 0.35s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex; flex-direction: column; padding: 20px; box-shadow: 15px 0 40px rgba(0,0,0,0.4);
        }
        .sidebar.open { left: 0; }
        
        .sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid var(--border); padding-bottom: 12px;}
        .sidebar h3 { margin: 0; font-size: 1.1rem; color: var(--text-main); display: flex; align-items: center; gap: 8px;}
        
        .chat-history-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; margin-top: 5px; }
        .history-item {
            background: transparent; border: 1px solid transparent; color: var(--text-main);
            padding: 9px 10px; border-radius: 10px; cursor: pointer; display: flex; align-items: center; justify-content: space-between;
            font-family: 'Inter', sans-serif; font-size: 0.88rem; transition: all 0.2s;
        }
        .history-item:hover { background: var(--card); }
        .history-item.active { background: rgba(59, 130, 246, 0.15); border: 1px solid var(--primary); color: var(--primary); font-weight: bold; }
        .history-item-content { display: flex; align-items: center; gap: 8px; flex: 1; overflow: hidden; }
        .delete-history-btn { background: none; border: none; color: var(--text-dim); cursor: pointer; padding: 4px; border-radius: 6px; }
        .delete-history-btn:hover { color: var(--danger); background: rgba(239, 68, 68, 0.1); }

        .tab-section { display: none; flex-direction: column; gap: 8px; flex: 1; min-height: 0; }
        .tab-section.active { display: flex; }
        
        .card { background: var(--surface); border-radius: 16px; border: 1px solid var(--border); padding: 14px; display: flex; flex-direction: column; gap: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }

        .top-utility-bar {
            display: flex; align-items: center; justify-content: space-between; gap: 6px; flex-shrink: 0; font-size: 0.8rem;
        }
        .persona-select {
            background: var(--surface); color: var(--text-main); border: 1px solid var(--border);
            padding: 5px 8px; border-radius: 10px; font-family: 'Inter', sans-serif; outline: none; cursor: pointer; font-size: 0.78rem; flex: 1;
        }
        .pomodoro-badge {
            background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.3); padding: 5px 10px; border-radius: 10px;
            color: #60a5fa; font-weight: 700; display: flex; align-items: center; gap: 6px; cursor: pointer; transition: all 0.2s;
        }
        .pomodoro-badge:hover { background: var(--primary); color: white; }

        .games-stats-bar {
            display: none; background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.2);
            padding: 6px 12px; border-radius: 10px; align-items: center; justify-content: space-between; font-size: 0.8rem; color: #c4b5fd; flex-shrink: 0;
        }
        .games-stats-bar.active { display: flex; }

        .glass-sheet-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.65); backdrop-filter: blur(8px);
            z-index: 2000; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; display: flex; align-items: flex-end; justify-content: center;
        }
        .glass-sheet-overlay.active { opacity: 1; pointer-events: auto; }
        .glass-sheet-content {
            background: var(--glass); backdrop-filter: blur(20px); border-top: 1px solid var(--border); border-left: 1px solid var(--border); border-right: 1px solid var(--border);
            width: 100%; max-width: 900px; max-height: 80vh; border-top-left-radius: 24px; border-top-right-radius: 24px;
            padding: 20px; display: flex; flex-direction: column; gap: 12px; box-shadow: 0 -10px 40px rgba(0,0,0,0.5);
            transform: translateY(100%); transition: transform 0.35s cubic-bezier(0.1, 0.9, 0.2, 1); overflow-y: auto;
        }
        .glass-sheet-overlay.active .glass-sheet-content { transform: translateY(0); }

        .chat-container-wrapper { position: relative; flex: 1; display: flex; flex-direction: column; min-height: 0; }
        .chat-feed {
            display: flex; flex-direction: column; gap: 14px; flex: 1; overflow-y: auto; padding: 10px 4px;
            background: transparent; scroll-behavior: smooth;
        }
        
        .scroll-jumpers {
            position: absolute; right: 10px; bottom: 10px; display: flex; flex-direction: column; gap: 6px; z-index: 10;
            opacity: 0; pointer-events: none; transition: opacity 0.3s ease;
        }
        .scroll-jumpers.visible { opacity: 1; pointer-events: auto; }
        .jump-btn {
            background: var(--surface); border: 1px solid var(--border); color: var(--primary);
            width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
            cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.3); transition: all 0.2s;
        }
        .jump-btn:hover { background: var(--primary); color: white; transform: scale(1.1); }

        .message-row { display: flex; flex-direction: column; gap: 3px; width: 100%; animation: fadeIn 0.25s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        
        .message-sender { font-size: 0.72rem; font-weight: 700; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 5px; }
        .message-text-user { font-size: 0.9rem; line-height: 1.5; color: var(--text-dim); font-weight: 400; word-break: break-word; }
        .message-text-ai { font-size: 1.05rem; line-height: 1.75; color: var(--text-main); font-weight: 600; word-break: break-word; }

        .quick-chips-bar {
            display: flex; gap: 6px; overflow-x: auto; padding: 4px 2px; margin-top: 4px; scrollbar-width: none;
        }
        .quick-chip {
            background: var(--surface); border: 1px solid var(--border); color: #93c5fd; padding: 5px 12px; border-radius: 16px;
            font-size: 0.78rem; font-weight: 600; cursor: pointer; white-space: nowrap; transition: all 0.2s; display: inline-flex; align-items: center; gap: 5px;
        }
        .quick-chip:hover { background: var(--primary); color: white; border-color: var(--primary); }

        .complex-card-box {
            background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px;
            margin: 4px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.2); position: relative; overflow-x: auto;
        }
        .complex-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; border-bottom: 1px solid var(--border); padding-bottom: 4px; font-size: 0.78rem; color: var(--accent-purple); font-weight: bold; }
        
        .copy-code-btn, .flashcard-btn { background: var(--card); color: var(--text-dim); border: 1px solid var(--border); border-radius: 6px; padding: 3px 7px; font-size: 0.72rem; cursor: pointer; display: flex; align-items: center; gap: 4px; }
        .copy-code-btn:hover, .flashcard-btn:hover { background: var(--primary); color: white; }

        .audio-speech-btn { background: var(--surface); border: 1px solid var(--border); color: var(--primary); border-radius: 7px; padding: 3px 8px; font-size: 0.78rem; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; margin-top: 4px; }
        .audio-speech-btn:hover { background: var(--primary); color: white; }

        .hologram-thinking {
            display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--accent-purple); font-weight: 600; font-size: 0.85rem;
            background: rgba(139, 92, 246, 0.08); border: 1px solid rgba(139, 92, 246, 0.15); padding: 7px 12px; border-radius: 10px; width: 100%; max-width: 380px;
        }
        .pulse-dot { width: 7px; height: 7px; background: var(--accent-purple); border-radius: 50%; animation: pulse-anim 1.2s infinite ease-in-out; }
        @keyframes pulse-anim { 0%, 100% { transform: scale(0.8); opacity: 0.4; } 50% { transform: scale(1.3); opacity: 1; } }

        /* زر الإجابة السريعة (Fast-Track Override Button) */
        .fast-track-btn {
            background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; border: none; padding: 4px 10px; border-radius: 8px;
            font-size: 0.75rem; font-weight: 700; cursor: pointer; display: none; align-items: center; gap: 4px; box-shadow: 0 2px 10px rgba(239,68,68,0.3);
            animation: bounce 1s infinite;
        }
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-2px); } }

        /* إطار الكتابة الراقي */
        .chat-input-container { flex-shrink: 0; }
        .chat-input-box {
            background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 8px 12px;
            display: flex; flex-direction: column; gap: 6px; box-shadow: 0 8px 30px rgba(0,0,0,0.2);
            transition: border-color 0.2s;
        }
        .chat-input-box:focus-within { border-color: var(--primary); }
        .chat-input-box.disabled { opacity: 0.6; pointer-events: none; }

        textarea {
            background: transparent; color: var(--text-main); border: none; outline: none;
            font-family: 'Inter', sans-serif; font-size: 0.95rem; resize: none; max-height: 110px; min-height: 22px; line-height: 1.4; width: 100%;
        }

        .image-preview-bar {
            display: none; align-items: center; justify-content: space-between; background: rgba(59, 130, 246, 0.15);
            border: 1px solid var(--primary); padding: 5px 8px; border-radius: 7px; font-size: 0.82rem; color: #93c5fd;
        }

        .input-actions-bar { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 6px; }
        .input-left-tools { display: flex; gap: 5px; align-items: center; }

        .tool-btn {
            background: transparent; border: none; color: var(--text-dim); border-radius: 7px; width: 34px; height: 34px;
            display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s;
        }
        .tool-btn:hover { background: var(--card); color: var(--text-main); }
        .tool-btn.recording { color: var(--danger); animation: pulse 1.2s infinite; }
        .tool-btn.muted { color: var(--danger); }

        .send-btn {
            background: var(--primary); color: white; border: none; border-radius: 9px; width: 36px; height: 36px;
            display: flex; align-items: center; justify-content: center; cursor: pointer; transition: transform 0.1s;
        }
        .send-btn:active { transform: scale(0.95); }
        .send-btn:disabled { background: var(--card); color: var(--text-dim); cursor: not-allowed; }

        .btn { background: var(--primary); color: white; border: none; padding: 9px 14px; border-radius: 11px; font-family: 'Inter', sans-serif; font-weight: 700; font-size: 0.88rem; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.2s; }
        .btn-purple { background: linear-gradient(135deg, #8b5cf6, #3b82f6); }
        .btn-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); padding: 5px 10px; border-radius: 7px; font-size: 0.82rem;}
        input[type="file"] { display: none; }

        .doc-item { background: var(--card); border-radius: 12px; padding: 12px; border: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }
        .doc-header { display: flex; justify-content: space-between; align-items: center; }
        .doc-title { font-weight: 700; font-size: 0.9rem; color: #60a5fa; display: flex; align-items: center; gap: 6px;}
        .doc-body { font-size: 0.82rem; color: var(--text-dim); line-height: 1.5; max-height: 110px; overflow-y: auto; background: var(--surface); padding: 8px; border-radius: 7px; white-space: pre-wrap; }
        .status-msg { display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 0.82rem; font-weight: bold;}
    </style>
</head>
<body>

    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h3><i data-lucide="menu"></i> Menu & History</h3>
            <button class="icon-btn" style="width:32px; height:32px; border:none; background:transparent;" onclick="toggleSidebar()"><i data-lucide="x"></i></button>
        </div>
        
        <button class="btn" onclick="createNewChatSession()" style="width: 100%; justify-content: center; margin-bottom: 8px;">
            <i data-lucide="plus-circle"></i> New Session
        </button>

        <button class="btn btn-purple" onclick="toggleGlassSheet(true)" style="width: 100%; justify-content: center; margin-bottom: 10px;">
            <i data-lucide="folder-kanban"></i> Curriculum Documents (<span id="docCountBadgeSidebar">0</span>)
        </button>

        <h4 style="font-size: 0.78rem; color: var(--text-dim); margin: 8px 0 4px; text-transform: uppercase;"><i data-lucide="history" style="width:13px; height:13px;"></i> Saved History:</h4>
        <div class="chat-history-list" id="chatHistoryList"></div>

        <div style="margin-top: auto; padding-top: 10px; border-top: 1px solid var(--border);">
            <button class="btn" style="width: 100%; background: var(--card); color: var(--text-main); border: 1px solid var(--border);" onclick="toggleTheme()">
                <i data-lucide="sun" id="themeIcon"></i> Toggle Theme
            </button>
        </div>
    </aside>

    <div class="glass-sheet-overlay" id="glassSheetOverlay" onclick="toggleGlassSheet(false)">
        <div class="glass-sheet-content" onclick="event.stopPropagation()">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 10px;">
                <h3 style="margin:0; font-size: 1.1rem; color: #60a5fa; display: flex; align-items: center; gap: 8px;">
                    <i data-lucide="folder-kanban"></i> Curriculum Documents
                </h3>
                <button class="icon-btn" style="width:32px; height:32px;" onclick="toggleGlassSheet(false)"><i data-lucide="x"></i></button>
            </div>

            <div class="card" style="background: var(--card);">
                <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-main); display: flex; align-items: center; gap: 6px;">
                    <i data-lucide="file-up"></i> Upload Study Materials
                </span>
                <div style="display: flex; gap: 6px; margin-top: 4px;">
                    <label for="docFileInputCamera" class="btn btn-purple" style="flex: 1; text-align: center; margin:0; padding: 9px;">
                        <i data-lucide="camera"></i> Camera
                    </label>
                    <input type="file" id="docFileInputCamera" accept="image/*" capture="environment">

                    <label for="docFileInputGallery" class="btn btn-purple" style="flex: 1; text-align: center; margin:0; padding: 9px;">
                        <i data-lucide="images"></i> Gallery
                    </label>
                    <input type="file" id="docFileInputGallery" accept="image/*" multiple>
                </div>
                <div id="uploadStatus" class="status-msg"></div>
            </div>

            <div class="card" style="background: var(--card); max-height: 250px; overflow-y: auto;">
                <span style="font-weight: 700; font-size: 0.85rem; color: var(--text-dim);">Stored Archive:</span>
                <div id="docsList" style="display: flex; flex-direction: column; gap: 8px;"></div>
            </div>
        </div>
    </div>

    <div class="main-wrapper">
        <div class="top-nav-bar">
            <button class="icon-btn" onclick="toggleSidebar()" title="Menu">
                <i data-lucide="align-right"></i>
            </button>

            <div class="mode-switcher-bar">
                <button class="mode-tab active" id="modeStudy" onclick="switchMode('study')">
                    <i data-lucide="graduation-cap"></i> Study
                </button>
                <button class="mode-tab" id="modeGeneral" onclick="switchMode('general')">
                    <i data-lucide="globe"></i> General
                </button>
                <button class="mode-tab" id="modeGames" onclick="switchMode('games')">
                    <i data-lucide="puzzle"></i> Games
                </button>
            </div>

            <button class="icon-btn" onclick="toggleGlassSheet(true)" title="Curriculum Documents">
                <i data-lucide="folder-kanban"></i>
            </button>
        </div>

        <div class="top-utility-bar">
            <select id="aiPersonaSelect" class="persona-select">
                <option value="strict">Strict & Professional</option>
                <option value="humor">Entertainment & Light Humor</option>
                <option value="roast">Witty & Playful Challenge</option>
                <option value="human" selected>Human-like & Warm</option>
            </select>
            <div class="pomodoro-badge" onclick="togglePomodoroTimer()" title="Focus Pomodoro Timer">
                <i data-lucide="timer" style="width:14px; height:14px;"></i> <span id="pomodoroDisplay">25:00</span>
            </div>
        </div>

        <div class="games-stats-bar" id="gamesStatsBar">
            <span>⭐ XP: <strong id="userXp">125</strong></span>
            <span>🏆 Win Rate: <strong id="userWinRate">85%</strong></span>
            <span style="color: #a78bfa;" id="gameEncourageMsg">Keep going, genius!</span>
        </div>

        <div class="tab-section active" id="askTab">
            <div class="chat-container-wrapper">
                <div class="chat-feed" id="chatFeed" onscroll="checkScrollPosition()" ontouchmove="checkScrollPosition()">
                    <div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 40px 20px; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                        <i data-lucide="sparkles" style="width: 30px; height: 30px; color: var(--primary);"></i>
                        <h3 style="margin: 0; color: var(--text-main); font-weight: 700;">ge_nius Ultimate</h3>
                        <p style="margin: 0; font-size: 0.88rem;">Glassmorphism design & smart adaptive workspace.</p>
                    </div>
                </div>

                <div class="scroll-jumpers" id="scrollJumpers">
                    <button class="jump-btn" id="jumpUpBtn" onclick="scrollToTop()" title="Scroll to Top" style="display:none;"><i data-lucide="chevron-up"></i></button>
                    <button class="jump-btn" id="jumpDownBtn" onclick="scrollToBottom()" title="Scroll to Bottom" style="display:flex;"><i data-lucide="chevron-down"></i></button>
                </div>
            </div>

            <div class="quick-chips-bar" id="quickChipsBar">
                <button class="quick-chip" onclick="sendQuickPrompt('Explain this in simpler terms')"><i data-lucide="sparkle"></i> Simplify</button>
                <button class="quick-chip" onclick="sendQuickPrompt('Give me a practical engineering example')"><i data-lucide="wrench"></i> Example</button>
                <button class="quick-chip" onclick="sendQuickPrompt('Test me with a quiz question')"><i data-lucide="help-circle"></i> Quiz me</button>
            </div>

            <!-- إطار الكتابة مع قفل الإرسال أثناء الانتظار -->
            <div class="chat-input-container">
                <div class="chat-input-box" id="chatInputBox">
                    <div class="image-preview-bar" id="questionImgPreview">
                        <span style="display: flex; align-items: center; gap: 6px;"><i data-lucide="image" style="width: 14px; height: 14px;"></i> Image attached</span>
                        <span style="cursor: pointer; color: #fca5a5; font-weight: bold; display: flex; align-items: center; gap: 4px;" onclick="removeQuestionImage()">
                            <i data-lucide="x" style="width: 14px; height: 14px;"></i> Remove
                        </span>
                    </div>

                    <textarea id="userQuery" placeholder="Message ge_nius..." rows="1" oninput="autoResizeTextarea(this)"></textarea>
                    
                    <div class="input-actions-bar">
                        <div class="input-left-tools">
                            <label for="qFileInputCamera" class="tool-btn" title="Camera">
                                <i data-lucide="camera"></i>
                            </label>
                            <input type="file" id="qFileInputCamera" accept="image/*" capture="environment">

                            <label for="qFileInputGallery" class="tool-btn" title="Gallery">
                                <i data-lucide="image-plus"></i>
                            </label>
                            <input type="file" id="qFileInputGallery" accept="image/*">

                            <button class="tool-btn" id="voiceRecordBtn" onclick="toggleVoiceRecording()" title="Voice Input">
                                <i data-lucide="mic"></i>
                            </button>

                            <button class="tool-btn" id="audioMuteBtn" onclick="toggleAudioMute()" title="Mute/Unmute AI Voice">
                                <i data-lucide="volume-2" id="muteIcon"></i>
                            </button>
                        </div>

                        <button class="send-btn" id="sendBtn" onclick="submitQuestion()" title="Send">
                            <i data-lucide="send-horizontal" style="width: 17px; height: 17px;"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        lucide.createIcons();

        function toggleTheme() {
            const isLight = document.body.classList.toggle('light-mode');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            const iconId = isLight ? 'moon' : 'sun';
            document.getElementById('themeIcon').setAttribute('data-lucide', iconId);
            lucide.createIcons();
        }
        if (localStorage.getItem('theme') === 'light') { 
            document.body.classList.add('light-mode'); 
            document.getElementById('themeIcon').setAttribute('data-lucide', 'moon');
            lucide.createIcons(); 
        }

        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('open');
            document.getElementById('sidebarOverlay').classList.toggle('active');
        }

        function toggleGlassSheet(show) {
            const sheet = document.getElementById('glassSheetOverlay');
            if (show) sheet.classList.add('active');
            else sheet.classList.remove('active');
        }

        function autoResizeTextarea(el) {
            el.style.height = 'auto';
            el.style.height = (el.scrollHeight) + 'px';
        }

        let pomodoroSeconds = 25 * 60;
        let pomodoroTimer = null;
        let isPomodoroActive = false;

        function togglePomodoroTimer() {
            if (isPomodoroActive) {
                clearInterval(pomodoroTimer);
                isPomodoroActive = false;
                alert('Focus timer paused.');
            } else {
                isPomodoroActive = true;
                alert('Focus timer started! 25 minutes of deep study.');
                pomodoroTimer = setInterval(() => {
                    if (pomodoroSeconds > 0) {
                        pomodoroSeconds--;
                        let m = Math.floor(pomodoroSeconds / 60);
                        let s = pomodoroSeconds % 60;
                        document.getElementById('pomodoroDisplay').innerText = `${m}:${s < 10 ? '0' : ''}${s}`;
                    } else {
                        clearInterval(pomodoroTimer);
                        isPomodoroActive = false;
                        alert('Pomodoro session completed! Take a 5 min break.');
                        pomodoroSeconds = 25 * 60;
                    }
                }, 1000);
            }
        }

        let lastScrollTop = 0;
        function checkScrollPosition() {
            const chatFeed = document.getElementById('chatFeed');
            const jumpers = document.getElementById('scrollJumpers');
            const upBtn = document.getElementById('jumpUpBtn');
            const downBtn = document.getElementById('jumpDownBtn');

            const st = chatFeed.scrollTop;
            const maxScroll = chatFeed.scrollHeight - chatFeed.clientHeight;

            if (chatFeed.scrollHeight > chatFeed.clientHeight + 150) {
                jumpers.classList.add('visible');
                if (st > lastScrollTop) {
                    upBtn.style.display = 'flex';
                    if (st >= maxScroll - 20) downBtn.style.display = 'none';
                    else downBtn.style.display = 'flex';
                } else {
                    downBtn.style.display = 'flex';
                    if (st <= 20) upBtn.style.display = 'none';
                    else upBtn.style.display = 'flex';
                }
            } else {
                jumpers.classList.remove('visible');
            }
            lastScrollTop = st <= 0 ? 0 : st;
        }

        function scrollToTop() {
            document.getElementById('chatFeed').scrollTo({ top: 0, behavior: 'smooth' });
        }

        function scrollToBottom() {
            const chatFeed = document.getElementById('chatFeed');
            chatFeed.scrollTo({ top: chatFeed.scrollHeight, behavior: 'smooth' });
        }

        let modeContents = { study: "", general: "", games: "" };
        let currentMode = 'study';
        let isAudioMuted = false;
        let userXP = 125;
        let userWins = 18;
        let userTotalGames = 21;
        let isWaitingForResponse = false; // قفل لمنع تكرار السؤال

        const chatFeed = document.getElementById('chatFeed');
        const gamesStatsBar = document.getElementById('gamesStatsBar');

        function toggleAudioMute() {
            isAudioMuted = !isAudioMuted;
            const btn = document.getElementById('audioMuteBtn');
            const icon = document.getElementById('muteIcon');
            if (isAudioMuted) {
                btn.classList.add('muted');
                icon.setAttribute('data-lucide', 'volume-x');
                if ('speechSynthesis' in window) window.speechSynthesis.cancel();
            } else {
                btn.classList.remove('muted');
                icon.setAttribute('data-lucide', 'volume-2');
            }
            lucide.createIcons({root: btn});
        }

        let chatSessions = JSON.parse(localStorage.getItem('ge_nius_sessions_ultimate')) || {};
        let currentSessionId = localStorage.getItem('ge_nius_current_session_ultimate');

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
            chatSessions[id] = { id: id, title: "New Session", mode: "study", modesData: { study: "", general: "", games: "" } };
            currentSessionId = id;
            saveSessionsData();
        }

        function createNewChatSession() {
            if (isWaitingForResponse) return; // منع إنشاء جلسة أثناء الرد
            createNewSessionQuiet();
            loadChatSession(currentSessionId);
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
        }

        function switchMode(mode) {
            if (isWaitingForResponse) return; // منع التبديل أثناء انتظار الرد
            modeContents[currentMode] = chatFeed.innerHTML;
            currentMode = mode;
            document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
            if(mode === 'study') document.getElementById('modeStudy').classList.add('active');
            else if(mode === 'general') document.getElementById('modeGeneral').classList.add('active');
            else if(mode === 'games') document.getElementById('modeGames').classList.add('active');

            if (mode === 'games') {
                gamesStatsBar.classList.add('active');
                updateGameStatsUI();
            } else {
                gamesStatsBar.classList.remove('active');
            }

            if (modeContents[mode] && modeContents[mode].trim() !== '') {
                chatFeed.innerHTML = modeContents[mode];
            } else {
                chatFeed.innerHTML = `<div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 40px 20px; display: flex; flex-direction: column; align-items: center; gap: 8px;"><i data-lucide="sparkles" style="width: 30px; height: 30px; color: var(--primary);"></i><h3 style="margin: 0; color: var(--text-main); font-weight: 700;">${mode.toUpperCase()} Workspace</h3><p style="margin: 0; font-size: 0.88rem;">Start a fresh conversation in this mode.</p></div>`;
            }

            if(chatSessions[currentSessionId]) {
                chatSessions[currentSessionId].mode = mode;
                chatSessions[currentSessionId].modesData = modeContents;
                saveSessionsData();
            }
            lucide.createIcons({root: chatFeed});
            checkScrollPosition();
        }

        function updateGameStatsUI() {
            document.getElementById('userXp').innerText = userXP;
            const rate = Math.round((userWins / userTotalGames) * 100);
            document.getElementById('userWinRate').innerText = rate + '%';
            const quotes = [
                "Brilliant tactical move! Keep pushing.",
                "Your intellectual sharpness is unmatched.",
                "Every puzzle solved adds power to your neural core.",
                "Fascinating deduction! Ready for the next riddle?"
            ];
            document.getElementById('gameEncourageMsg').innerText = quotes[Math.floor(Math.random() * quotes.length)];
        }

        function loadChatSession(id) {
            if (isWaitingForResponse) return;
            currentSessionId = id;
            const session = chatSessions[id];
            if (session && session.modesData) {
                modeContents = session.modesData;
            } else {
                modeContents = { study: "", general: "", games: "" };
            }
            if(session && session.mode) switchMode(session.mode);
            else switchMode('study');
            renderChatHistoryList();
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
        }

        function deleteSessionItem(e, id) {
            e.stopPropagation();
            if (isWaitingForResponse) return;
            if(confirm('Delete this session?')) {
                delete chatSessions[id];
                if(id === currentSessionId) {
                    const keys = Object.keys(chatSessions);
                    if(keys.length > 0) { currentSessionId = keys[0]; loadChatSession(currentSessionId); }
                    else { createNewChatSession(); }
                } else {
                    saveSessionsData();
                    renderChatHistoryList();
                }
            }
        }

        function saveCurrentChatHtml(userQueryText = null) {
            if(!chatSessions[currentSessionId]) return;
            modeContents[currentMode] = chatFeed.innerHTML;
            chatSessions[currentSessionId].modesData = modeContents;
            if (userQueryText && chatSessions[currentSessionId].title === "New Session") {
                chatSessions[currentSessionId].title = userQueryText.substring(0, 20) + "...";
            }
            saveSessionsData();
        }

        function saveSessionsData() {
            localStorage.setItem('ge_nius_sessions_ultimate', JSON.stringify(chatSessions));
            localStorage.setItem('ge_nius_current_session_ultimate', currentSessionId);
            renderChatHistoryList();
        }

        function renderChatHistoryList() {
            const listDiv = document.getElementById('chatHistoryList');
            if(!listDiv) return;
            listDiv.innerHTML = '';
            const sortedIds = Object.keys(chatSessions).sort((a, b) => b - a);
            
            sortedIds.forEach(id => {
                const session = chatSessions[id];
                const icon = session.mode === 'games' ? 'puzzle' : (session.mode === 'general' ? 'globe' : 'graduation-cap');
                const isActive = id === currentSessionId ? 'active' : '';
                
                listDiv.innerHTML += `
                    <div class="history-item ${isActive}" onclick="loadChatSession('${id}')">
                        <div class="history-item-content">
                            <i data-lucide="${icon}" style="width: 13px; height: 13px;"></i>
                            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${session.title}</span>
                        </div>
                        <button class="delete-history-btn" onclick="deleteSessionItem(event, '${id}')" title="Delete">
                            <i data-lucide="trash-2" style="width: 13px; height: 13px;"></i>
                        </button>
                    </div>
                `;
            });
            lucide.createIcons({root: listDiv});
        }

        initSessions();

        window.speakText = function(text) {
            if (isAudioMuted) return;
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(decodeURIComponent(text));
                utterance.rate = 1.0; utterance.pitch = 1.0;
                window.speechSynthesis.speak(utterance);
            }
        };

        function sendQuickPrompt(txt) {
            if (isWaitingForResponse) return;
            document.getElementById('userQuery').value = txt;
            submitQuestion();
        }

        window.makeFlashcard = function(btn, text) {
            alert("Smart Flashcard Generated! \nQ: What is the core concept?\nA: " + decodeURIComponent(text).substring(0, 100) + "...");
        };

        let recognition = null;
        function toggleVoiceRecording() {
            if (isWaitingForResponse) return;
            const btn = document.getElementById('voiceRecordBtn');
            const queryInput = document.getElementById('userQuery');
            
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                alert('Speech recognition is not supported in your browser.');
                return;
            }

            if (btn.classList.contains('recording')) {
                if(recognition) recognition.stop();
                btn.classList.remove('recording');
                return;
            }

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = 'en-US';
            recognition.interimResults = false;

            recognition.onstart = () => { btn.classList.add('recording'); };
            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                queryInput.value = transcript;
                autoResizeTextarea(queryInput);
                btn.classList.remove('recording');
            };
            recognition.onerror = () => { btn.classList.remove('recording'); };
            recognition.onend = () => { btn.classList.remove('recording'); };

            recognition.start();
        }

        window.copyCodeText = function(btn, text) {
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
            const countBadge = document.getElementById('docCountBadgeSidebar');
            if(countBadge) { countBadge.innerHTML = curriculumDocs.length; }
            if (!listDiv) return;
            if (curriculumDocs.length === 0) { listDiv.innerHTML = '<div style="color: var(--text-dim); font-style: italic; text-align: center; padding: 10px;">No curriculum documents uploaded.</div>'; return; }
            listDiv.innerHTML = curriculumDocs.map((item, index) => `
                <div class="doc-item">
                    <div class="doc-header">
                        <span class="doc-title"><i data-lucide="file-text"></i> Document ${index + 1}</span>
                        <button class="btn btn-danger" onclick="deleteDoc(${item.id})"><i data-lucide="trash-2" style="width: 13px; height: 13px;"></i> Delete</button>
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
                if(statusDiv) { statusDiv.innerHTML = `<i data-lucide="loader" class="spin-icon"></i> Processing document ${i + 1}...`; statusDiv.style.color = 'var(--primary)'; lucide.createIcons({root: statusDiv}); }
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
            if(statusDiv) { statusDiv.innerHTML = '<i data-lucide="check-circle-2"></i> Saved successfully!'; statusDiv.style.color = 'var(--accent-green)'; lucide.createIcons({root: statusDiv}); }
        }
        document.getElementById('docFileInputCamera').addEventListener('change', handleDocImageSelect);
        document.getElementById('docFileInputGallery').addEventListener('change', handleDocImageSelect);

        function deleteDoc(id) { fetch('/api/docs/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) }).then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }); }

        function setInputLocked(locked) {
            isWaitingForResponse = locked;
            const box = document.getElementById('chatInputBox');
            const sendBtn = document.getElementById('sendBtn');
            const queryArea = document.getElementById('userQuery');
            if (locked) {
                box.classList.add('disabled');
                sendBtn.disabled = true;
                queryArea.disabled = true;
            } else {
                box.classList.remove('disabled');
                sendBtn.disabled = false;
                queryArea.disabled = false;
                queryArea.focus();
            }
        }

        let fastTrackTimer = null;
        let activeController = null;

        function triggerFastTrack() {
            if (activeController) {
                activeController.abort(); // إلغاء الطلب البطيء الحالي
            }
        }

        function submitQuestion() {
            if (isWaitingForResponse) return; // قفل تام إذا كان هناك سؤال قيد المعالجة

            const queryInput = document.getElementById('userQuery');
            const query = queryInput.value.trim();
            const personaVal = document.getElementById('aiPersonaSelect').value;

            if (!query && !attachedQuestionBase64) { alert('Please type a prompt or attach an image!'); return; }
            if (currentMode === 'study' && curriculumDocs.length === 0) { alert('Study mode requires uploaded curriculum documents. Switch to General or Games!'); return; }
            
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();

            setInputLocked(true); // قفل الكتابة والإرسال

            let userTextDisplay = query.replace(/\\n/g, '<br>');
            if (attachedQuestionBase64) { userTextDisplay = (query ? userTextDisplay + '<br>' : '') + '<span style="color:#60a5fa; font-size:0.85em"><i data-lucide="image" style="width:14px;height:14px;"></i> Image attached</span>'; }

            const userRow = document.createElement('div'); userRow.className = 'message-row';
            userRow.innerHTML = `<div class="message-sender"><i data-lucide="user" style="width:12px;height:12px;"></i> You</div><div class="message-text-user">${userTextDisplay}</div>`;
            chatFeed.appendChild(userRow); lucide.createIcons({root: userRow});

            const loadingRow = document.createElement('div'); loadingRow.className = 'message-row loading-bubble-temp';
            loadingRow.innerHTML = `
                <div class="message-sender" style="color:var(--accent-purple)"><i data-lucide="cpu" style="width:12px;height:12px;"></i> ge_nius AI</div>
                <div class="hologram-thinking">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <div class="pulse-dot"></div>
                        <span id="thinkingStatusText">Analyzing...</span>
                    </div>
                    <button class="fast-track-btn" id="fastTrackBtn" onclick="triggerFastTrack()"><i data-lucide="zap" style="width:12px;height:12px;"></i> Fast Answer</button>
                </div>
            `;
            chatFeed.appendChild(loadingRow); lucide.createIcons({root: loadingRow});
            
            // إظهار زر الإجابة السريعة تلقائياً إذا تأخر الرد أكثر من 8 ثوانٍ
            let fastTrackTimeout = setTimeout(() => {
                const btn = document.getElementById('fastTrackBtn');
                if (btn) btn.style.display = 'inline-flex';
            }, 8000);

            saveCurrentChatHtml(query);

            const payload = { query: query, image: attachedQuestionBase64, mode: currentMode, persona: personaVal };
            queryInput.value = ''; queryInput.style.height = 'auto'; removeQuestionImage(); chatFeed.scrollTop = chatFeed.scrollHeight;

            activeController = new AbortController();

            fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: activeController.signal })
            .then(res => res.json())
            .then(data => {
                clearTimeout(fastTrackTimeout);
                chatFeed.removeChild(loadingRow);
                setInputLocked(false); // فتح القفل بعد انتهاء الإجابة
                const aiRow = document.createElement('div'); aiRow.className = 'message-row';

                if (data.status === 'out_of_scope') {
                    aiRow.innerHTML = `<div class="message-sender" style="color:var(--danger)">ge_nius</div><div class="message-text-ai" style="color:#fca5a5;">Out of curriculum scope. Switch to General mode.</div>`;
                } else if (data.status === 'success') {
                    const fullText = data.answer;
                    const encoded = encodeURIComponent(fullText);
                    
                    if (currentMode === 'games') {
                        userXP += 15; userTotalGames += 1; userWins += 1;
                        updateGameStatsUI();
                    }
                    
                    aiRow.innerHTML = `
                        <div class="message-sender"><i data-lucide="bot" style="width:12px;height:12px;color:#60a5fa"></i> ge_nius</div>
                        <div class="complex-card-box">
                            <div class="complex-card-header">
                                <span>Analysis & Solution</span>
                                <div style="display:flex; gap:6px;">
                                    <button class="flashcard-btn" onclick="makeFlashcard(this, '${encoded}')"><i data-lucide="layers" style="width:11px;height:11px;"></i> Flashcard</button>
                                    <button class="copy-code-btn" onclick="copyCodeText(this, '${encoded}')"><i data-lucide="copy" style="width:11px;height:11px;"></i> Copy</button>
                                </div>
                            </div>
                            <div class="message-text-ai ai-content">${marked.parse(fullText)}</div>
                        </div>
                        <div><button class="audio-speech-btn" onclick="speakText('${encoded}')"><i data-lucide="volume-2" style="width:13px;height:13px;"></i> Read Aloud</button></div>
                    `;
                    speakText(encoded);
                } else {
                    aiRow.innerHTML = `<div class="message-sender" style="color:var(--danger)">ge_nius</div><div class="message-text-ai">Error: ${data.error || 'Failed.'}</div>`;
                }
                
                chatFeed.appendChild(aiRow); lucide.createIcons({root: aiRow});
                chatFeed.scrollTop = chatFeed.scrollHeight;
                if (window.MathJax) window.MathJax.typesetPromise([aiRow]).catch(e => {});
                checkScrollPosition();
                saveCurrentChatHtml();
            }).catch(err => {
                clearTimeout(fastTrackTimeout);
                if (loadingRow.parentNode) chatFeed.removeChild(loadingRow);
                setInputLocked(false); // فتح القفل حتى عند الإلغاء أو الخطأ
                
                const errRow = document.createElement('div'); errRow.className = 'message-row';
                if (err.name === 'AbortError') {
                    errRow.innerHTML = `<div class="message-sender" style="color:#f59e0b">ge_nius Fast-Track</div><div class="message-text-ai">Switched to direct quick summary mode. Please ask a more direct or concise query!</div>`;
                } else {
                    errRow.innerHTML = `<div class="message-sender" style="color:var(--danger)">ge_nius</div><div class="message-text-ai">Connection error.</div>`;
                }
                chatFeed.appendChild(errRow); lucide.createIcons({root: errRow});
                chatFeed.scrollTop = chatFeed.scrollHeight;
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# Python Backend Server (Supreme Lock & Fast-Track Optimized)
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

            if self.path == "/api/docs/upload":
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
                user_query = req_json.get("query", "")
                question_image_base64 = req_json.get("image")
                mode = req_json.get("mode", "study") 
                persona = req_json.get("persona", "human")
                docs = load_curriculum(session_id)

                messages_content = []
                if question_image_base64:
                    messages_content.append({"type": "image_url", "image_url": {"url": question_image_base64}})

                persona_instructions = {
                    "strict": "Persona: Strict & Professional. Be highly formal, objective, precise, and academic.",
                    "humor": "Persona: Entertainment & Light Humor. Keep it witty, fun, and add light jokes while maintaining accuracy.",
                    "roast": "Persona: Witty & Playful Challenge. Gently tease or challenge the user's logic if they make an error to push them to think harder.",
                    "human": "Persona: Human-like & Warm. Be friendly, empathetic, natural, and encouraging like a close study partner."
                }.get(persona, "Persona: Human-like & Warm.")

                if mode == "general":
                    full_prompt = (
                        f"You are a global AI assistant named ge_nius.\n"
                        f"{persona_instructions}\n"
                        f"User request: \"{user_query}\"\n\n"
                        f"IMPORTANT: Respond in the exact same language the user is using."
                    )
                elif mode == "games":
                    full_prompt = (
                        f"You are an interactive Brain Games and Puzzle master named ge_nius.\n"
                        f"{persona_instructions}\n"
                        f"The user is playing brain/thinking games, riddles, or guessing games.\n"
                        f"User input: \"{user_query}\"\n\n"
                        f"IMPORTANT: Respond in the exact same language the user is using. Keep it engaging and rewarding!"
                    )
                else:
                    all_concepts_summary = "\n\n".join([f"Document {i+1}:\n{doc['concepts']}" for i, doc in enumerate(docs)])
                    full_prompt = (
                        f"You are an expert tutor.\n"
                        f"{persona_instructions}\n"
                        f"Here is the student's curriculum study material:\n"
                        f"--- START CURRICULUM ---\n"
                        f"{all_concepts_summary}\n"
                        f"--- END CURRICULUM ---\n\n"
                        f"User question: \"{user_query}\"\n\n"
                        f"IMPORTANT: Respond in the exact same language the user is asking in.\n"
                        f"1. Does this relate to the curriculum?\n"
                        f"2. If completely unrelated, reply with EXACTLY: OUT_OF_SCOPE\n"
                        f"3. If in scope, provide a clear, step-by-step explanation."
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
