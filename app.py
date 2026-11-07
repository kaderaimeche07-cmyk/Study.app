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
# HTML Frontend (ge_nius Royal World-Class UI Final Polish)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="en" dir="auto">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ge_nius Assistant - Royal Edition</title>
    
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
            --bg-main: #030304; 
            --surface: #0f1014; 
            --card: #18191f;
            --primary: #4169E1; 
            --primary-glow: rgba(65, 105, 225, 0.4);
            --danger: #ef4444; 
            --text-main: #f8fafc; 
            --text-dim: #94a3b8;
            --border: rgba(255, 255, 255, 0.06); 
            --glass: rgba(15, 16, 20, 0.75);
        }

        body.light-mode {
            --bg-main: #f8fafc; --surface: #ffffff; --card: #f1f5f9;
            --primary: #2563eb; --primary-glow: rgba(37, 99, 235, 0.3);
            --text-main: #0f172a; --text-dim: #64748b;
            --border: rgba(0, 0, 0, 0.08); --glass: rgba(255, 255, 255, 0.85);
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

        /* شريط التنقل العلوي مع الاسم المستقل وأيقونة الغواصة */
        .top-nav-bar {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 14px; flex-shrink: 0; gap: 12px; background: var(--glass);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border); border-radius: 24px; box-shadow: 0 4px 30px rgba(0,0,0,0.3);
            margin-bottom: 10px;
        }

        .nav-left-group { display: flex; align-items: center; gap: 10px; }

        .app-brand {
            font-family: 'Outfit', sans-serif;
            font-weight: 900;
            font-size: 1.2rem;
            color: var(--text-main);
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .app-brand span { color: var(--primary); }
        .brand-icon { width: 22px; height: 22px; color: var(--primary); }

        .icon-btn {
            background: transparent; border: none; color: var(--text-main);
            border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); flex-shrink: 0;
        }
        .icon-btn:hover { background: var(--card); color: var(--primary); transform: scale(1.05); }

        .mode-switcher-bar {
            display: flex; gap: 4px; background: rgba(0,0,0,0.2); padding: 3px; border-radius: 18px;
        }
        .mode-tab {
            padding: 6px 12px; background: transparent; border: none; color: var(--text-dim);
            font-family: 'Inter', sans-serif; font-weight: 600; font-size: 0.8rem; cursor: pointer;
            border-radius: 14px; white-space: nowrap; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.3s;
        }
        .mode-tab.active { background: var(--surface); color: var(--text-main); box-shadow: 0 2px 15px rgba(0,0,0,0.2); border: 1px solid var(--border); }

        .lucide { width: 18px; height: 18px; stroke-width: 2.2; display: inline-block; vertical-align: middle; }

        /* القائمة الجانبية (Sidebar) */
        .sidebar-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); backdrop-filter: blur(5px); z-index: 999; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; }
        .sidebar-overlay.active { opacity: 1; pointer-events: auto; }
        
        .sidebar {
            position: fixed; top: 0; left: -320px; width: 300px; height: 100vh; height: 100dvh;
            background: var(--surface); border-right: 1px solid var(--border);
            z-index: 1000; transition: left 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex; flex-direction: column; padding: 20px; box-shadow: 15px 0 50px rgba(0,0,0,0.5);
            overflow-y: auto;
        }
        .sidebar.open { left: 0; }
        
        .sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 15px;}
        .sidebar h3 { margin: 0; font-size: 1.15rem; color: var(--text-main); font-weight: 800; display: flex; align-items: center; gap: 8px;}
        
        .sidebar-section-title { font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; margin: 15px 0 8px 0; display: flex; align-items: center; gap: 6px;}
        
        .persona-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
        .persona-chip {
            background: var(--bg-main); border: 1px solid var(--border); border-radius: 12px;
            padding: 10px; font-size: 0.8rem; font-family: 'Inter', sans-serif; font-weight: 600;
            color: var(--text-dim); cursor: pointer; display: flex; flex-direction: column; align-items: center; gap: 6px;
            transition: all 0.2s ease;
        }
        .persona-chip:hover { background: var(--card); color: var(--text-main); }
        .persona-chip.active { background: rgba(65, 105, 225, 0.15); color: var(--primary); border-color: var(--primary); }

        .chat-history-list { flex: 1; display: flex; flex-direction: column; gap: 6px; }
        .history-item {
            background: transparent; border: 1px solid transparent; color: var(--text-main);
            padding: 10px 12px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; justify-content: space-between;
            font-family: 'Inter', sans-serif; font-size: 0.88rem; transition: all 0.2s;
        }
        .history-item:hover { background: var(--card); }
        .history-item.active { background: rgba(65, 105, 225, 0.1); border: 1px solid var(--primary); color: var(--primary); font-weight: bold; }
        .history-item-content { display: flex; align-items: center; gap: 8px; flex: 1; overflow: hidden; }
        .delete-history-btn { background: none; border: none; color: var(--text-dim); cursor: pointer; padding: 4px; border-radius: 6px; }
        .delete-history-btn:hover { color: var(--danger); background: rgba(239, 68, 68, 0.1); }

        .tab-section { display: none; flex-direction: column; gap: 10px; flex: 1; min-height: 0; }
        .tab-section.active { display: flex; }
        
        .card { background: var(--surface); border-radius: 20px; border: 1px solid var(--border); padding: 16px; display: flex; flex-direction: column; gap: 10px; }

        .chat-container-wrapper { position: relative; flex: 1; display: flex; flex-direction: column; min-height: 0; }
        .chat-feed {
            display: flex; flex-direction: column; gap: 24px; flex: 1; overflow-y: auto; padding: 10px 4px 20px 4px;
            background: transparent; scroll-behavior: smooth;
        }
        
        .message-row { display: flex; flex-direction: column; gap: 6px; width: 100%; animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
        @keyframes slideUp { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
        
        .message-sender { font-size: 0.75rem; font-weight: 700; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px; }
        
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
            display: flex; align-items: center; gap: 10px; color: var(--primary); font-weight: 600; font-size: 0.85rem;
            background: rgba(65, 105, 225, 0.05); border: 1px solid rgba(65, 105, 225, 0.15); padding: 12px 18px; border-radius: 16px; width: fit-content;
        }
        .pulse-dot { width: 8px; height: 8px; background: var(--primary); border-radius: 50%; animation: pulse-anim 1s infinite ease-in-out; }
        @keyframes pulse-anim { 0%, 100% { transform: scale(0.8); opacity: 0.3; } 50% { transform: scale(1.4); opacity: 1; box-shadow: 0 0 10px var(--primary); } }

        /* إطار الكتابة */
        .chat-input-container { flex-shrink: 0; padding-bottom: 6px; position: relative; }
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

        .btn { background: var(--card); color: var(--text-main); border: 1px solid var(--border); padding: 12px 18px; border-radius: 16px; font-family: 'Inter', sans-serif; font-weight: 600; font-size: 0.9rem; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.2s; }
        .btn:hover { background: var(--surface); border-color: var(--primary); color: var(--primary); }
        .btn-purple { background: linear-gradient(135deg, #1d4ed8, #4169E1); color: white; border: none; box-shadow: 0 4px 20px var(--primary-glow);}
        
        input[type="file"] { display: none; }
        .image-preview-bar { display: none; align-items: center; justify-content: space-between; background: rgba(65, 105, 225, 0.1); border: 1px solid rgba(65, 105, 225, 0.3); padding: 8px 12px; border-radius: 16px; font-size: 0.82rem; color: #93c5fd; margin-bottom: 8px; }
    </style>
</head>
<body>

    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h3><i data-lucide="menu"></i> Menu</h3>
            <button class="icon-btn" style="width:34px; height:34px;" onclick="toggleSidebar()"><i data-lucide="x"></i></button>
        </div>
        
        <button class="btn" onclick="createNewChatSession()" style="width: 100%; justify-content: center; margin-bottom: 12px; border-radius: 16px;">
            <i data-lucide="plus-circle"></i> New Session
        </button>

        <button class="btn btn-purple" onclick="switchSection('docsTab')" style="width: 100%; justify-content: center; margin-bottom: 15px; border-radius: 16px;">
            <i data-lucide="scan-line"></i> Curriculum Documents
        </button>

        <div class="sidebar-section-title"><i data-lucide="brain"></i> AI Persona</div>
        <div class="persona-grid" id="personaContainer">
            <button class="persona-chip active" data-val="human" onclick="selectPersona('human', this)"><i data-lucide="heart"></i> Human</button>
            <button class="persona-chip" data-val="strict" onclick="selectPersona('strict', this)"><i data-lucide="briefcase"></i> Strict</button>
            <button class="persona-chip" data-val="humor" onclick="selectPersona('humor', this)"><i data-lucide="smile"></i> Humor</button>
            <button class="persona-chip" data-val="roast" onclick="selectPersona('roast', this)"><i data-lucide="flame"></i> Roast</button>
        </div>

        <div class="sidebar-section-title"><i data-lucide="history"></i> History</div>
        <div class="chat-history-list" id="chatHistoryList"></div>

        <div style="margin-top: auto; padding-top: 15px; border-top: 1px solid var(--border); display:flex; gap:8px;">
            <button class="btn" style="flex:1; justify-content: center; padding: 10px;" onclick="toggleTheme()" title="Toggle Theme">
                <i data-lucide="moon" id="themeIcon"></i>
            </button>
        </div>
    </aside>

    <div class="main-wrapper">
        <!-- شريط التنقل العلوي مع الاسم المستقل وأيقونة الغواصة -->
        <div class="top-nav-bar">
            <div class="nav-left-group">
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
                <button class="mode-tab active" id="modeStudy" onclick="switchMode('study')">Study</button>
                <button class="mode-tab" id="modeGeneral" onclick="switchMode('general')">General</button>
                <button class="mode-tab" id="modeGames" onclick="switchMode('games')">Games</button>
            </div>
        </div>

        <div class="tab-section active" id="askTab">
            <div class="chat-container-wrapper">
                <div class="chat-feed" id="chatFeed">
                    <div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 80px 20px; display: flex; flex-direction: column; align-items: center; gap: 16px;">
                        <svg class="submarine-logo" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/>
                            <path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/>
                            <circle cx="12" cy="15" r="2"/><path d="M20 15h2"/><path d="M2 15h2"/>
                        </svg>
                        <p style="margin: 0; font-size: 1rem; max-width: 250px; line-height: 1.5; color: var(--text-dim);">How can I help you today?</p>
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
                        <i data-lucide="image-plus" style="color:var(--primary)"></i> Upload Image
                    </label>
                    <input type="file" id="qFileInputGallery" accept="image/*">
                </div>

                <div class="input-glass-panel" id="inputPanel">
                    <button class="tool-btn" id="magicBtn" onclick="toggleMagicMenu()" title="Attach">
                        <i data-lucide="plus"></i>
                    </button>

                    <textarea id="userQuery" placeholder="Ask ge_nius..." rows="1" oninput="autoResizeTextarea(this)"></textarea>
                    
                    <button class="tool-btn" id="voiceRecordBtn" onclick="toggleVoiceRecording()" title="Voice Input">
                        <i data-lucide="mic"></i>
                    </button>

                    <button class="send-btn-royal" id="sendBtn" onclick="submitQuestion()" title="Send">
                        <i data-lucide="arrow-up" id="sendIcon"></i>
                    </button>
                </div>
            </div>
        </div>

        <div class="tab-section" id="docsTab">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                <h3 style="margin:0; font-size: 1.15rem; color: var(--text-main); font-weight: 700;">Curriculum</h3>
                <button class="btn" style="padding: 8px 12px; font-size: 0.8rem;" onclick="switchSection('askTab')">
                    <i data-lucide="arrow-left"></i> Back
                </button>
            </div>
            <div class="card">
                <span style="font-weight: 700; font-size: 0.95rem; color: var(--primary); display: flex; align-items: center; gap: 8px;"><i data-lucide="file-up"></i> Upload Materials</span>
                <div style="display: flex; gap: 8px;">
                    <label for="docFileInputCamera" class="btn btn-purple" style="flex: 1; text-align: center; margin:0;"><i data-lucide="scan"></i> Scan</label>
                    <input type="file" id="docFileInputCamera" accept="image/*" capture="environment">
                    <label for="docFileInputGallery" class="btn btn-purple" style="flex: 1; text-align: center; margin:0;"><i data-lucide="images"></i> Gallery</label>
                    <input type="file" id="docFileInputGallery" accept="image/*" multiple>
                </div>
                <div id="uploadStatus" style="font-size: 0.82rem; font-weight: bold; text-align:center; margin-top:8px;"></div>
            </div>
            <div class="card" style="flex: 1; overflow-y: auto;">
                <div id="docsList" style="display: flex; flex-direction: column; gap: 10px;"></div>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener("DOMContentLoaded", () => { lucide.createIcons(); });

        let isAiThinking = false;

        function toggleMagicMenu() {
            if(isAiThinking) return;
            const menu = document.getElementById('magicMenu');
            const btn = document.getElementById('magicBtn');
            menu.classList.toggle('show');
            btn.classList.toggle('active-magic');
        }

        document.addEventListener('click', (e) => {
            const menu = document.getElementById('magicMenu');
            const btn = document.getElementById('magicBtn');
            if (!menu.contains(e.target) && !btn.contains(e.target)) {
                menu.classList.remove('show');
                btn.classList.remove('active-magic');
            }
        });

        let currentPersonaValue = 'human';
        window.selectPersona = function(val, btnElement) {
            currentPersonaValue = val;
            document.querySelectorAll('.persona-chip').forEach(btn => btn.classList.remove('active'));
            btnElement.classList.add('active');
            if(window.innerWidth < 768) toggleSidebar();
        };

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
        }

        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('open');
            document.getElementById('sidebarOverlay').classList.toggle('active');
        }

        function switchSection(sectionId) {
            document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
            document.getElementById(sectionId).classList.add('active');
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
        }

        function autoResizeTextarea(el) {
            el.style.height = 'auto';
            el.style.height = (el.scrollHeight) + 'px';
        }

        let modeContents = { study: "", general: "", games: "" };
        let currentMode = 'study';

        const chatFeed = document.getElementById('chatFeed');

        let recognition = null;
        function toggleVoiceRecording() {
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
                queryInput.value = event.results[0][0].transcript;
                autoResizeTextarea(queryInput);
                btn.classList.remove('recording');
            };
            recognition.onerror = () => { btn.classList.remove('recording'); };
            recognition.onend = () => { btn.classList.remove('recording'); };
            recognition.start();
        }

        let chatSessions = JSON.parse(localStorage.getItem('ge_nius_sessions_v5')) || {};
        let currentSessionId = localStorage.getItem('ge_nius_current_session_v5');

        function initSessions() {
            if (!currentSessionId || !chatSessions[currentSessionId]) { createNewSessionQuiet(); } 
            else { loadChatSession(currentSessionId); }
            renderChatHistoryList();
        }

        function createNewSessionQuiet() {
            const id = Date.now().toString();
            chatSessions[id] = { id: id, title: "New Session", mode: "study", modesData: { study: "", general: "", games: "" } };
            currentSessionId = id;
            saveSessionsData();
        }

        function createNewChatSession() {
            if(isAiThinking) return;
            createNewSessionQuiet();
            loadChatSession(currentSessionId);
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
        }

        function switchMode(mode) {
            if(isAiThinking) return;
            modeContents[currentMode] = chatFeed.innerHTML;
            currentMode = mode;
            document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
            if(mode === 'study') document.getElementById('modeStudy').classList.add('active');
            else if(mode === 'general') document.getElementById('modeGeneral').classList.add('active');
            else if(mode === 'games') document.getElementById('modeGames').classList.add('active');

            if (modeContents[mode] && modeContents[mode].trim() !== '') {
                chatFeed.innerHTML = modeContents[mode];
            } else {
                chatFeed.innerHTML = `<div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 80px 20px; display: flex; flex-direction: column; align-items: center; gap: 16px;"><svg class="submarine-logo" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/><circle cx="12" cy="15" r="2"/><path d="M20 15h2"/><path d="M2 15h2"/></svg><p style="margin: 0; font-size: 1rem; max-width: 250px; line-height: 1.5; color: var(--text-dim);">${mode.toUpperCase()} Workspace is ready.</p></div>`;
            }

            if(chatSessions[currentSessionId]) {
                chatSessions[currentSessionId].mode = mode;
                chatSessions[currentSessionId].modesData = modeContents;
                saveSessionsData();
            }
            lucide.createIcons({root: chatFeed});
        }

        function loadChatSession(id) {
            currentSessionId = id;
            const session = chatSessions[id];
            if (session && session.modesData) { modeContents = session.modesData; } 
            else { modeContents = { study: "", general: "", games: "" }; }
            if(session && session.mode) switchMode(session.mode); else switchMode('study');
            renderChatHistoryList();
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
        }

        function deleteSessionItem(e, id) {
            e.stopPropagation();
            if(confirm('Delete this session?')) {
                delete chatSessions[id];
                if(id === currentSessionId) {
                    const keys = Object.keys(chatSessions);
                    if(keys.length > 0) { currentSessionId = keys[0]; loadChatSession(currentSessionId); } 
                    else { createNewChatSession(); }
                } else { saveSessionsData(); renderChatHistoryList(); }
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
            localStorage.setItem('ge_nius_sessions_v5', JSON.stringify(chatSessions));
            localStorage.setItem('ge_nius_current_session_v5', currentSessionId);
            renderChatHistoryList();
        }

        function renderChatHistoryList() {
            const listDiv = document.getElementById('chatHistoryList');
            if(!listDiv) return;
            listDiv.innerHTML = '';
            const sortedIds = Object.keys(chatSessions).sort((a, b) => b - a);
            
            sortedIds.forEach(id => {
                const session = chatSessions[id];
                const isActive = id === currentSessionId ? 'active' : '';
                listDiv.innerHTML += `<div class="history-item ${isActive}" onclick="loadChatSession('${id}')"><div class="history-item-content"><i data-lucide="message-square" style="width: 14px; height: 14px;"></i><span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${session.title}</span></div><button class="delete-history-btn" onclick="deleteSessionItem(event, '${id}')"><i data-lucide="trash-2" style="width: 14px; height: 14px;"></i></button></div>`;
            });
            lucide.createIcons({root: listDiv});
        }

        initSessions();

        window.speakText = function(text) {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(decodeURIComponent(text));
                utterance.rate = 1.0; utterance.pitch = 1.0;
                window.speechSynthesis.speak(utterance);
            }
        };

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

        function fetchDocs() { fetch('/api/docs').then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }); }

        function renderDocs() {
            const listDiv = document.getElementById('docsList');
            if (!listDiv) return;
            if (curriculumDocs.length === 0) { listDiv.innerHTML = '<div style="color: var(--text-dim); text-align: center; padding: 20px;">No documents uploaded yet.</div>'; return; }
            listDiv.innerHTML = curriculumDocs.map((item, index) => `
                <div style="background:var(--bg-main); border:1px solid var(--border); border-radius:14px; padding:14px; display:flex; flex-direction:column; gap:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700; color:var(--primary);"><i data-lucide="file-text"></i> Document ${index + 1}</span>
                        <button class="btn" style="padding:4px 8px; font-size:0.75rem; color:var(--danger);" onclick="deleteDoc(${item.id})"><i data-lucide="trash-2"></i> Delete</button>
                    </div>
                    <div style="font-size:0.85rem; color:var(--text-dim); line-height:1.6; max-height:100px; overflow-y:auto; background:var(--surface); padding:10px; border-radius:10px;">${item.concepts}</div>
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
                document.getElementById('magicMenu').classList.remove('show');
                document.getElementById('magicBtn').classList.remove('active-magic');
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
                if(statusDiv) { statusDiv.innerHTML = `Processing ${i + 1}...`; statusDiv.style.color = 'var(--primary)'; }
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
            if(statusDiv) { statusDiv.innerHTML = 'Saved successfully!'; statusDiv.style.color = 'var(--accent-green)'; }
        }
        document.getElementById('docFileInputCamera').addEventListener('change', handleDocImageSelect);
        document.getElementById('docFileInputGallery').addEventListener('change', handleDocImageSelect);

        function deleteDoc(id) { fetch('/api/docs/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) }).then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }); }

        function submitQuestion() {
            if (isAiThinking) return;

            const queryInput = document.getElementById('userQuery');
            const query = queryInput.value.trim();
            const personaVal = currentPersonaValue;

            if (!query && !attachedQuestionBase64) return;
            if (currentMode === 'study' && curriculumDocs.length === 0) { alert('Study mode requires uploaded curriculum documents. Switch to General or Games!'); return; }
            
            isAiThinking = true;
            document.getElementById('inputPanel').classList.add('locked');
            const sendBtn = document.getElementById('sendBtn');
            sendBtn.classList.add('loading');
            sendBtn.innerHTML = `<i data-lucide="loader-2" class="spinner-icon" style="width:20px;height:20px;"></i>`;
            lucide.createIcons({root: sendBtn});
            
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();

            let userTextDisplay = query.replace(/\\n/g, '<br>');
            if (attachedQuestionBase64) { userTextDisplay = (query ? userTextDisplay + '<br>' : '') + `<span style="color:var(--primary); font-size:0.85em; display:flex; align-items:center; gap:4px; margin-top:6px;"><i data-lucide="image" style="width:14px;height:14px;"></i> Image attached</span>`; }

            const userRow = document.createElement('div'); userRow.className = 'message-row';
            userRow.style.alignItems = 'flex-end';
            userRow.innerHTML = `<div class="message-sender" style="justify-content:flex-end;">You <i data-lucide="user" style="width:12px;height:12px;"></i></div><div class="message-text-user">${userTextDisplay}</div>`;
            chatFeed.appendChild(userRow); lucide.createIcons({root: userRow});

            const loadingRow = document.createElement('div'); loadingRow.className = 'message-row loading-bubble-temp';
            loadingRow.innerHTML = `
                <div class="message-sender" style="color:var(--primary); display:flex; align-items:center; gap:5px;">
                    <svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/></svg> ge_nius
                </div>
                <div class="hologram-thinking">
                    <div class="pulse-dot"></div>
                    <span>Processing logic...</span>
                </div>
            `;
            chatFeed.appendChild(loadingRow); lucide.createIcons({root: loadingRow});
            
            saveCurrentChatHtml(query);

            const payload = { query: query, image: attachedQuestionBase64, mode: currentMode, persona: personaVal };
            queryInput.value = ''; queryInput.style.height = 'auto'; removeQuestionImage(); chatFeed.scrollTop = chatFeed.scrollHeight;

            fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            .then(res => res.json())
            .then(data => {
                chatFeed.removeChild(loadingRow);
                const aiRow = document.createElement('div'); aiRow.className = 'message-row';

                # رأس الرسالة (مع أيقونة الغواصة المصغرة بجانب اسم التطبيق)
                const aiHeaderHtml = `
                    <div class="message-sender" style="color:var(--primary); display:flex; align-items:center; gap:5px;">
                        <svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/></svg> ge_nius
                    </div>
                `;

                if (data.status === 'out_of_scope') {
                    aiRow.innerHTML = `${aiHeaderHtml}<div class="message-text-ai" style="color:#fca5a5;">Out of curriculum scope. Switch to General mode.</div>`;
                } else if (data.status === 'success') {
                    const fullText = data.answer;
                    const encoded = encodeURIComponent(fullText);
                    
                    if (fullText.includes("```") || fullText.length > 500) {
                        aiRow.innerHTML = `
                            ${aiHeaderHtml}
                            <div class="complex-card-box">
                                <div class="complex-card-header">
                                    <span>Detailed Output</span>
                                    <button class="copy-code-btn" onclick="copyCodeText(this, '${encoded}')"><i data-lucide="copy" style="width:12px;height:12px;"></i> Copy</button>
                                </div>
                                <div class="message-text-ai ai-content">${marked.parse(fullText)}</div>
                            </div>
                            <div><button class="audio-speech-btn" onclick="speakText('${encoded}')"><i data-lucide="volume-2" style="width:14px;height:14px;"></i> Listen</button></div>
                        `;
                    } else {
                        aiRow.innerHTML = `
                            ${aiHeaderHtml}
                            <div class="message-text-ai ai-content" style="padding-top:4px;">${marked.parse(fullText)}</div>
                            <div><button class="audio-speech-btn" onclick="speakText('${encoded}')"><i data-lucide="volume-2" style="width:14px;height:14px;"></i> Listen</button></div>
                        `;
                    }
                } else {
                    aiRow.innerHTML = `${aiHeaderHtml}<div class="message-text-ai">Error: ${data.error || 'Failed.'}</div>`;
                }
                
                chatFeed.appendChild(aiRow); lucide.createIcons({root: aiRow});
                chatFeed.scrollTop = chatFeed.scrollHeight;
                if (window.MathJax) window.MathJax.typesetPromise([aiRow]).catch(e => {});
                saveCurrentChatHtml();
            }).catch(err => {
                chatFeed.removeChild(loadingRow);
                const errRow = document.createElement('div'); errRow.className = 'message-row';
                errRow.innerHTML = `<div class="message-sender" style="color:var(--danger)">ge_nius</div><div class="message-text-ai">Connection error.</div>`;
                chatFeed.appendChild(errRow); lucide.createIcons({root: errRow});
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
                    "strict": "Persona: Strict & Professional. Be highly formal, precise, and academic.",
                    "humor": "Persona: Entertainment & Light Humor. Keep it witty and fun.",
                    "roast": "Persona: Witty & Playful Challenge. Gently challenge the user's logic.",
                    "human": "Persona: Human-like & Warm. Be friendly, empathetic, natural."
                }.get(persona, "Persona: Human-like & Warm.")

                if mode == "general":
                    full_prompt = f"You are an AI assistant named ge_nius.\n{persona_instructions}\nUser request: \"{user_query}\"\nRespond in the exact language the user used."
                elif mode == "games":
                    full_prompt = f"You are a Puzzle master named ge_nius.\n{persona_instructions}\nUser input: \"{user_query}\"\nRespond in the exact language the user used."
                else:
                    all_concepts_summary = "\n\n".join([f"Document {i+1}:\n{doc['concepts']}" for i, doc in enumerate(docs)])
                    full_prompt = (
                        f"You are an expert tutor.\n{persona_instructions}\n"
                        f"Curriculum:\n{all_concepts_summary}\n\n"
                        f"User question: \"{user_query}\"\n"
                        f"Respond in the user's language. If unrelated to curriculum, reply EXACTLY: OUT_OF_SCOPE"
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
