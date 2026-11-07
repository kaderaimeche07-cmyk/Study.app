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
# HTML Frontend (Cyberpunk Luxe & Ultimate Pro Edition)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="en" dir="auto">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ge_nius Assistant - Elite Pro</title>
    
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
            --ai-bubble-bg: #171513;
        }

        body.light-mode {
            --bg-main: #f8fafc; --surface: #ffffff; --card: #f1f5f9;
            --primary: #2563eb; --text-main: #0f172a; --text-dim: #475569;
            --border: rgba(0, 0, 0, 0.08); --ai-bubble-bg: #f1f5f9;
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        html, body {
            font-family: 'Inter', sans-serif; 
            background-color: var(--bg-main); color: var(--text-main);
            margin: 0; padding: 0; width: 100vw; height: 100vh; height: 100dvh; overflow: hidden;
            background-image: radial-gradient(circle at 15% 15%, rgba(139, 92, 246, 0.08), transparent 40%),
                              radial-gradient(circle at 85% 85%, rgba(59, 130, 246, 0.08), transparent 40%);
            background-attachment: fixed;
        }

        .main-wrapper { 
            padding: 10px; display: flex; flex-direction: column; gap: 10px; 
            width: 100%; height: 100%; height: 100dvh; max-width: 900px; margin: 0 auto; 
        }

        .top-nav-bar {
            display: flex; justify-content: space-between; align-items: center;
            padding: 4px 8px; flex-shrink: 0;
        }

        .icon-btn {
            background: var(--surface); border: 1px solid var(--border); color: var(--text-main);
            border-radius: 12px; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: all 0.2s; flex-shrink: 0;
        }
        .icon-btn:hover { background: var(--primary); color: white; transform: scale(1.05); }

        .mode-switcher-bar {
            display: flex; gap: 6px; background: var(--surface); padding: 4px; border-radius: 14px;
            border: 1px solid var(--border); flex-shrink: 0; overflow-x: auto;
        }
        .mode-tab {
            flex: 1; padding: 8px 12px; background: transparent; border: none; color: var(--text-dim);
            font-family: 'Inter', sans-serif; font-weight: 600; font-size: 0.85rem; cursor: pointer;
            border-radius: 10px; white-space: nowrap; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.2s;
        }
        .mode-tab.active { background: var(--primary); color: white; box-shadow: 0 2px 12px rgba(59,130,246,0.35); }

        .lucide { width: 18px; height: 18px; stroke-width: 2.2; display: inline-block; vertical-align: middle; }

        /* Sidebar & Overlay */
        .sidebar-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); z-index: 999; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; }
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
            padding: 10px; border-radius: 10px; cursor: pointer; display: flex; align-items: center; justify-content: space-between;
            font-family: 'Inter', sans-serif; font-size: 0.9rem; transition: all 0.2s;
        }
        .history-item:hover { background: var(--card); }
        .history-item.active { background: rgba(59, 130, 246, 0.15); border: 1px solid var(--primary); color: var(--primary); font-weight: bold; }
        .history-item-content { display: flex; align-items: center; gap: 8px; flex: 1; overflow: hidden; }
        .delete-history-btn { background: none; border: none; color: var(--text-dim); cursor: pointer; padding: 4px; border-radius: 6px; }
        .delete-history-btn:hover { color: var(--danger); background: rgba(239, 68, 68, 0.1); }

        .tab-section { display: none; flex-direction: column; gap: 10px; flex: 1; min-height: 0; }
        .tab-section.active { display: flex; }
        
        .card { background: rgba(28, 25, 23, 0.85); backdrop-filter: blur(12px); border-radius: 18px; border: 1px solid var(--border); padding: 16px; display: flex; flex-direction: column; gap: 10px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); }

        /* Chat Feed & Scroll Jumpers */
        .chat-container-wrapper { position: relative; flex: 1; display: flex; flex-direction: column; min-height: 0; }
        .chat-feed {
            display: flex; flex-direction: column; gap: 16px; flex: 1; overflow-y: auto; padding: 12px 6px;
            background: transparent; scroll-behavior: smooth;
        }
        
        /* أزرار التنقل الفوري للأسفل والأعلى */
        .scroll-jumpers {
            position: absolute; right: 12px; bottom: 15px; display: flex; flex-direction: column; gap: 6px; z-index: 10;
        }
        .jump-btn {
            background: var(--surface); border: 1px solid var(--border); color: var(--primary);
            width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
            cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.3); transition: all 0.2s; opacity: 0.85;
        }
        .jump-btn:hover { background: var(--primary); color: white; opacity: 1; transform: scale(1.1); }

        .message-row { display: flex; flex-direction: column; gap: 4px; width: 100%; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .message-sender { font-size: 0.75rem; font-weight: 700; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px; }
        .message-text { font-size: 0.98rem; line-height: 1.7; color: var(--text-main); word-break: break-word; }

        .complex-card-box {
            background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 14px;
            margin: 6px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.2); position: relative; overflow-x: auto;
        }
        .complex-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 6px; font-size: 0.8rem; color: var(--accent-purple); font-weight: bold; }
        
        .copy-code-btn { background: var(--card); color: var(--text-dim); border: 1px solid var(--border); border-radius: 6px; padding: 4px 8px; font-size: 0.75rem; cursor: pointer; display: flex; align-items: center; gap: 4px; }
        .copy-code-btn:hover { background: var(--primary); color: white; }

        .audio-speech-btn { background: var(--surface); border: 1px solid var(--border); color: var(--primary); border-radius: 8px; padding: 4px 10px; font-size: 0.8rem; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; margin-top: 6px; }
        .audio-speech-btn:hover { background: var(--primary); color: white; }

        /* مؤشر التفكير الرقمي الهولوجرام */
        .hologram-thinking {
            display: flex; align-items: center; gap: 8px; color: var(--accent-purple); font-weight: 600; font-size: 0.9rem;
            background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.2); padding: 8px 14px; border-radius: 12px; width: fit-content;
        }
        .pulse-dot { width: 8px; height: 8px; background: var(--accent-purple); border-radius: 50%; animation: pulse-anim 1.2s infinite ease-in-out; }
        @keyframes pulse-anim { 0%, 100% { transform: scale(0.8); opacity: 0.4; } 50% { transform: scale(1.3); opacity: 1; } }

        /* إطار الكتابة الراقي */
        .chat-input-container { flex-shrink: 0; }
        .chat-input-box {
            background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 10px 14px;
            display: flex; flex-direction: column; gap: 8px; box-shadow: 0 8px 30px rgba(0,0,0,0.2);
            transition: border-color 0.2s;
        }
        .chat-input-box:focus-within { border-color: var(--primary); }

        textarea {
            background: transparent; color: var(--text-main); border: none; outline: none;
            font-family: 'Inter', sans-serif; font-size: 0.95rem; resize: none; max-height: 120px; min-height: 24px; line-height: 1.5; width: 100%;
        }

        .image-preview-bar {
            display: none; align-items: center; justify-content: space-between; background: rgba(59, 130, 246, 0.15);
            border: 1px solid var(--primary); padding: 6px 10px; border-radius: 8px; font-size: 0.85rem; color: #93c5fd;
        }

        .input-actions-bar { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 8px; }
        .input-left-tools { display: flex; gap: 6px; align-items: center; }

        .tool-btn {
            background: transparent; border: none; color: var(--text-dim); border-radius: 8px; width: 36px; height: 36px;
            display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s;
        }
        .tool-btn:hover { background: var(--card); color: var(--text-main); }
        .tool-btn.recording { color: var(--danger); animation: pulse 1.2s infinite; }
        .tool-btn.muted { color: var(--danger); }

        .send-btn {
            background: var(--primary); color: white; border: none; border-radius: 10px; width: 38px; height: 38px;
            display: flex; align-items: center; justify-content: center; cursor: pointer; transition: transform 0.1s;
        }
        .send-btn:active { transform: scale(0.95); }

        .btn { background: var(--primary); color: white; border: none; padding: 10px 16px; border-radius: 12px; font-family: 'Inter', sans-serif; font-weight: 700; font-size: 0.9rem; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.2s; }
        .btn-purple { background: linear-gradient(135deg, #8b5cf6, #3b82f6); }
        .btn-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); padding: 6px 12px; border-radius: 8px; font-size: 0.85rem;}
        input[type="file"] { display: none; }

        .doc-item { background: var(--card); border-radius: 14px; padding: 14px; border: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
        .doc-header { display: flex; justify-content: space-between; align-items: center; }
        .doc-title { font-weight: 700; font-size: 0.95rem; color: #60a5fa; display: flex; align-items: center; gap: 8px;}
        .doc-body { font-size: 0.85rem; color: var(--text-dim); line-height: 1.6; max-height: 120px; overflow-y: auto; background: var(--surface); padding: 10px; border-radius: 8px; white-space: pre-wrap; }
        .status-msg { display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 0.85rem; font-weight: bold;}
    </style>
</head>
<body>

    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h3><i data-lucide="menu"></i> Menu & History</h3>
            <button class="icon-btn" style="width:34px; height:34px; border:none; background:transparent;" onclick="toggleSidebar()"><i data-lucide="x"></i></button>
        </div>
        
        <button class="btn" onclick="createNewChatSession()" style="width: 100%; justify-content: center; margin-bottom: 10px;">
            <i data-lucide="plus-circle"></i> New Chat Session
        </button>

        <button class="btn btn-purple" onclick="switchSection('docsTab')" style="width: 100%; justify-content: center; margin-bottom: 12px;">
            <i data-lucide="folder-kanban"></i> Curriculum Documents (<span id="docCountBadgeSidebar">0</span>)
        </button>

        <h4 style="font-size: 0.8rem; color: var(--text-dim); margin: 10px 0 4px; text-transform: uppercase;"><i data-lucide="history" style="width:14px; height:14px;"></i> Chat History:</h4>
        <div class="chat-history-list" id="chatHistoryList"></div>

        <div style="margin-top: auto; padding-top: 12px; border-top: 1px solid var(--border);">
            <button class="btn" style="width: 100%; background: var(--card); color: var(--text-main); border: 1px solid var(--border);" onclick="toggleTheme()">
                <i data-lucide="sun" id="themeIcon"></i> Toggle Theme
            </button>
        </div>
    </aside>

    <div class="main-wrapper">
        <div class="top-nav-bar">
            <button class="icon-btn" onclick="toggleSidebar()" title="Menu">
                <i data-lucide="align-right"></i>
            </button>

            <!-- شريط تغيير الأنماط مع حفظ واجهة كل منهج مستقلة -->
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

            <button class="icon-btn" onclick="toggleTheme()" title="Theme">
                <i data-lucide="sun" id="themeIconTop"></i>
            </button>
        </div>

        <div class="tab-section active" id="askTab">
            <div class="chat-container-wrapper">
                <div class="chat-feed" id="chatFeed">
                    <div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 40px 20px; display: flex; flex-direction: column; align-items: center; gap: 10px;">
                        <i data-lucide="sparkles" style="width: 32px; height: 32px; color: var(--primary);"></i>
                        <h3 style="margin: 0; color: var(--text-main); font-weight: 700;">Welcome to ge_nius Elite</h3>
                        <p style="margin: 0; font-size: 0.9rem;">Ask questions, study your curriculum, or play brain games!</p>
                    </div>
                </div>

                <!-- أزرار التنقل السريع للأسفل والأعلى -->
                <div class="scroll-jumpers">
                    <button class="jump-btn" onclick="scrollToTop()" title="Scroll to Top"><i data-lucide="chevron-up"></i></button>
                    <button class="jump-btn" onclick="scrollToBottom()" title="Scroll to Bottom"><i data-lucide="chevron-down"></i></button>
                </div>
            </div>

            <div class="chat-input-container">
                <div class="chat-input-box">
                    <div class="image-preview-bar" id="questionImgPreview">
                        <span style="display: flex; align-items: center; gap: 6px;"><i data-lucide="image" style="width: 14px; height: 14px;"></i> Image attached</span>
                        <span style="cursor: pointer; color: #fca5a5; font-weight: bold; display: flex; align-items: center; gap: 4px;" onclick="removeQuestionImage()">
                            <i data-lucide="x" style="width: 14px; height: 14px;"></i> Remove
                        </span>
                    </div>

                    <textarea id="userQuery" placeholder="Type your prompt or question..." rows="1" oninput="autoResizeTextarea(this)"></textarea>
                    
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

                            <!-- زر كتم وتشغيل الصوت الاحترافي -->
                            <button class="tool-btn" id="audioMuteBtn" onclick="toggleAudioMute()" title="Mute/Unmute AI Voice">
                                <i data-lucide="volume-2" id="muteIcon"></i>
                            </button>
                        </div>

                        <button class="send-btn" onclick="submitQuestion()" title="Send">
                            <i data-lucide="send-horizontal" style="width: 18px; height: 18px;"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div class="tab-section" id="docsTab">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                <h3 style="margin:0; font-size: 1.1rem; color: var(--text-main);">Curriculum Documents</h3>
                <button class="btn" onclick="switchSection('askTab')" style="padding: 6px 12px; font-size: 0.8rem;">
                    <i data-lucide="arrow-left"></i> Back to Chat
                </button>
            </div>

            <div class="card">
                <span style="font-weight: 700; font-size: 0.95rem; color: #60a5fa; display: flex; align-items: center; gap: 8px;">
                    <i data-lucide="file-up"></i> Upload Study Materials
                </span>
                <div style="display: flex; gap: 8px; margin-top: 5px;">
                    <label for="docFileInputCamera" class="btn btn-purple" style="flex: 1; text-align: center; margin:0; padding: 10px;">
                        <i data-lucide="camera"></i> Camera
                    </label>
                    <input type="file" id="docFileInputCamera" accept="image/*" capture="environment">

                    <label for="docFileInputGallery" class="btn btn-purple" style="flex: 1; text-align: center; margin:0; padding: 10px;">
                        <i data-lucide="images"></i> Gallery
                    </label>
                    <input type="file" id="docFileInputGallery" accept="image/*" multiple>
                </div>
                <div id="uploadStatus" class="status-msg"></div>
            </div>

            <div class="card" style="flex: 1; overflow-y: auto;">
                <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-dim);">Stored Documents Archive:</span>
                <div id="docsList" style="display: flex; flex-direction: column; gap: 10px;"></div>
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
            document.getElementById('themeIconTop').setAttribute('data-lucide', iconId);
            lucide.createIcons();
        }
        if (localStorage.getItem('theme') === 'light') { 
            document.body.classList.add('light-mode'); 
            document.getElementById('themeIcon').setAttribute('data-lucide', 'moon');
            document.getElementById('themeIconTop').setAttribute('data-lucide', 'moon');
            lucide.createIcons(); 
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

        function scrollToTop() {
            const chatFeed = document.getElementById('chatFeed');
            chatFeed.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function scrollToBottom() {
            const chatFeed = document.getElementById('chatFeed');
            chatFeed.scrollTo({ top: chatFeed.scrollHeight, behavior: 'smooth' });
        }

        // نظام الجلسات والمناهج المتعددة مع حفظ حالة كل واجهة بشكل مستقل تماماً
        let chatSessions = JSON.parse(localStorage.getItem('ge_nius_sessions_elite')) || {};
        let currentSessionId = localStorage.getItem('ge_nius_current_session_elite');
        let currentMode = 'study';
        let isAudioMuted = false;

        const chatFeed = document.getElementById('chatFeed');

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
            chatSessions[id] = { id: id, title: "New Session", html: "", mode: "study" };
            currentSessionId = id;
            saveSessionsData();
        }

        function createNewChatSession() {
            createNewSessionQuiet();
            loadChatSession(currentSessionId);
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
        }

        function switchMode(mode) {
            currentMode = mode;
            document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
            if(mode === 'study') document.getElementById('modeStudy').classList.add('active');
            else if(mode === 'general') document.getElementById('modeGeneral').classList.add('active');
            else if(mode === 'games') document.getElementById('modeGames').classList.add('active');

            if(chatSessions[currentSessionId]) {
                chatSessions[currentSessionId].mode = mode;
                saveSessionsData();
            }
        }

        function loadChatSession(id) {
            // حفظ الواجهة الحالية قبل التبديل
            saveCurrentChatHtml();
            
            currentSessionId = id;
            const session = chatSessions[id];
            if(session && session.mode) switchMode(session.mode);
            
            if (session && session.html && session.html.trim() !== '') {
                chatFeed.innerHTML = session.html;
            } else {
                chatFeed.innerHTML = `<div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 40px 20px; display: flex; flex-direction: column; align-items: center; gap: 10px;"><i data-lucide="sparkles" style="width: 32px; height: 32px; color: var(--primary);"></i><h3 style="margin: 0; color: var(--text-main); font-weight: 700;">New Elite Session</h3><p style="margin: 0; font-size: 0.9rem;">Type your question or choose a mode above.</p></div>`;
            }
            
            lucide.createIcons({root: chatFeed});
            if (window.MathJax) MathJax.typesetPromise([chatFeed]);
            chatFeed.scrollTop = chatFeed.scrollHeight;
            saveSessionsData();
            renderChatHistoryList();
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
        }

        function deleteSessionItem(e, id) {
            e.stopPropagation();
            if(confirm('Delete this session?')) {
                delete chatSessions[id];
                if(id === currentSessionId) {
                    const keys = Object.keys(chatSessions);
                    if(keys.length > 0) {
                        currentSessionId = keys[0];
                        loadChatSession(currentSessionId);
                    } else {
                        createNewChatSession();
                    }
                } else {
                    saveSessionsData();
                    renderChatHistoryList();
                }
            }
        }

        function saveCurrentChatHtml(userQueryText = null) {
            if(!chatSessions[currentSessionId]) return;
            const clones = chatFeed.cloneNode(true);
            clones.querySelectorAll('.loading-bubble-temp').forEach(l => l.remove());
            chatSessions[currentSessionId].html = clones.innerHTML;
            
            if (userQueryText && chatSessions[currentSessionId].title === "New Session") {
                chatSessions[currentSessionId].title = userQueryText.substring(0, 20) + "...";
            }
            saveSessionsData();
        }

        function saveSessionsData() {
            localStorage.setItem('ge_nius_sessions_elite', JSON.stringify(chatSessions));
            localStorage.setItem('ge_nius_current_session_elite', currentSessionId);
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
                            <i data-lucide="${icon}" style="width: 14px; height: 14px;"></i>
                            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${session.title}</span>
                        </div>
                        <button class="delete-history-btn" onclick="deleteSessionItem(event, '${id}')" title="Delete session">
                            <i data-lucide="trash-2" style="width: 14px; height: 14px;"></i>
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
                utterance.rate = 1.0;
                utterance.pitch = 1.0;
                window.speechSynthesis.speak(utterance);
            }
        };

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
                        <button class="btn btn-danger" onclick="deleteDoc(${item.id})"><i data-lucide="trash-2" style="width: 14px; height: 14px;"></i> Delete</button>
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

        function submitQuestion() {
            const queryInput = document.getElementById('userQuery');
            const query = queryInput.value.trim();
            if (!query && !attachedQuestionBase64) { alert('Please type a prompt or attach an image!'); return; }
            if (currentMode === 'study' && curriculumDocs.length === 0) { alert('Study mode requires uploaded curriculum documents. Switch to General or Games!'); return; }
            
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();

            let userTextDisplay = query.replace(/\\n/g, '<br>');
            if (attachedQuestionBase64) { userTextDisplay = (query ? userTextDisplay + '<br>' : '') + '<span style="color:#60a5fa; font-size:0.85em"><i data-lucide="image" style="width:14px;height:14px;"></i> Image attached</span>'; }

            const userRow = document.createElement('div'); userRow.className = 'message-row';
            userRow.innerHTML = `<div class="message-sender"><i data-lucide="user" style="width:14px;height:14px;"></i> You</div><div class="message-text">${userTextDisplay}</div>`;
            chatFeed.appendChild(userRow); lucide.createIcons({root: userRow});

            // مؤشر التفكير الرقمي الهولوجرام المتحرك
            const loadingRow = document.createElement('div'); loadingRow.className = 'message-row loading-bubble-temp';
            loadingRow.innerHTML = `
                <div class="message-sender" style="color:var(--accent-purple)"><i data-lucide="cpu" style="width:14px;height:14px;"></i> ge_nius AI</div>
                <div class="hologram-thinking">
                    <div class="pulse-dot"></div>
                    <span>Neural core processing...</span>
                </div>
            `;
            chatFeed.appendChild(loadingRow); lucide.createIcons({root: loadingRow});
            
            saveCurrentChatHtml(query);

            const payload = { query: query, image: attachedQuestionBase64, mode: currentMode };
            queryInput.value = ''; queryInput.style.height = 'auto'; removeQuestionImage(); chatFeed.scrollTop = chatFeed.scrollHeight;

            fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            .then(res => res.json())
            .then(data => {
                chatFeed.removeChild(loadingRow);
                const aiRow = document.createElement('div'); aiRow.className = 'message-row';

                if (data.status === 'out_of_scope') {
                    aiRow.innerHTML = `<div class="message-sender" style="color:var(--danger)">ge_nius</div><div class="message-text" style="color:#fca5a5;">Out of curriculum scope. Switch to General mode.</div>`;
                } else if (data.status === 'success') {
                    const fullText = data.answer;
                    const encoded = encodeURIComponent(fullText);
                    
                    if (fullText.includes("```") || fullText.length > 500) {
                        aiRow.innerHTML = `
                            <div class="message-sender"><i data-lucide="bot" style="width:14px;height:14px;color:#60a5fa"></i> ge_nius</div>
                            <div class="complex-card-box">
                                <div class="complex-card-header">
                                    <span>Detailed Solution / Complex Exercise</span>
                                    <button class="copy-code-btn" onclick="copyCodeText(this, '${encoded}')"><i data-lucide="copy" style="width:12px;height:12px;"></i> Copy</button>
                                </div>
                                <div class="message-text ai-content">${marked.parse(fullText)}</div>
                            </div>
                            <div><button class="audio-speech-btn" onclick="speakText('${encoded}')"><i data-lucide="volume-2" style="width:14px;height:14px;"></i> Read Aloud</button></div>
                        `;
                    } else {
                        aiRow.innerHTML = `
                            <div class="message-sender"><i data-lucide="bot" style="width:14px;height:14px;color:#60a5fa"></i> ge_nius</div>
                            <div class="message-text ai-content">${marked.parse(fullText)}</div>
                            <div><button class="audio-speech-btn" onclick="speakText('${encoded}')"><i data-lucide="volume-2" style="width:14px;height:14px;"></i> Read Aloud</button></div>
                        `;
                    }
                    
                    // تشغيل الصوت تلقائياً إذا لم يكن مكتوماً
                    speakText(encoded);
                } else {
                    aiRow.innerHTML = `<div class="message-sender" style="color:var(--danger)">ge_nius</div><div class="message-text">Error: ${data.error || 'Failed.'}</div>`;
                }
                
                chatFeed.appendChild(aiRow); lucide.createIcons({root: aiRow});
                chatFeed.scrollTop = chatFeed.scrollHeight;
                if (window.MathJax) window.MathJax.typesetPromise([aiRow]).catch(e => {});
                saveCurrentChatHtml();
            }).catch(err => {
                chatFeed.removeChild(loadingRow);
                const errRow = document.createElement('div'); errRow.className = 'message-row';
                errRow.innerHTML = `<div class="message-sender" style="color:var(--danger)">ge_nius</div><div class="message-text">Connection error.</div>`;
                chatFeed.appendChild(errRow); lucide.createIcons({root: errRow});
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# Python Backend Server (Elite Optimized)
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
                docs = load_curriculum(session_id)

                messages_content = []
                if question_image_base64:
                    messages_content.append({"type": "image_url", "image_url": {"url": question_image_base64}})

                if mode == "general":
                    full_prompt = (
                        f"You are a global AI assistant named ge_nius.\n"
                        f"User prompt/request: \"{user_query}\"\n\n"
                        f"IMPORTANT: Respond in the exact same language the user is using.\n"
                        f"Provide a professional, accurate, and structured response using Markdown."
                    )
                elif mode == "games":
                    full_prompt = (
                        f"You are an interactive Brain Games and Puzzle master named ge_nius.\n"
                        f"The user wants to play a thinking game, crossword, guess the animal/place, or solve a puzzle.\n"
                        f"User input: \"{user_query}\"\n\n"
                        f"IMPORTANT: Respond in the exact same language the user is using.\n"
                        f"Engage the user interactively, propose fun puzzles, riddle questions, or guessing games, and make it exciting!"
                    )
                else:
                    all_concepts_summary = "\n\n".join([f"Document {i+1}:\n{doc['concepts']}" for i, doc in enumerate(docs)])
                    full_prompt = (
                        f"You are an expert tutor.\n"
                        f"Here is the student's curriculum study material:\n"
                        f"--- START CURRICULUM ---\n"
                        f"{all_concepts_summary}\n"
                        f"--- END CURRICULUM ---\n\n"
                        f"User question/request: \"{user_query}\"\n\n"
                        f"IMPORTANT: Respond in the exact same language the user is asking in.\n"
                        f"1. Does this relate to the curriculum?\n"
                        f"2. If completely unrelated, reply with EXACTLY: OUT_OF_SCOPE\n"
                        f"3. If in scope, provide a clear, step-by-step explanation using Markdown and equations if needed."
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
