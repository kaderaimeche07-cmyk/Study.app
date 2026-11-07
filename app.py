import psycopg2
from urllib.parse import urlparse
import json
import ssl
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import uuid
from http import cookies
import zlib
import base64
import re

# ==============================================================================
# AI API Key & System Config
# ==============================================================================
API_KEY = "sk-FWE5lPc8aegQHHJZvk967w"
API_URL = "https://app.ai-grid.io/v1/chat/completions"
PORT = 8080
MODEL_NAME = "Qwen3-30B-A3B-Thinking"

# Mock Database structures
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
    except:
        return None

# ==============================================================================
# Backend Core Functions (Auth, Gamification, Compression)
# ==============================================================================
def compress_file_data(base64_data):
    """خوارزمية ذكية لضغط الملفات (PDF/Images) باستخدام zlib لتخفيف الحمل على السيرفر"""
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

def load_curriculum(session_id, user):
    # If student, load global curriculum for their level + their own docs.
    # For now, we simulate a shared database by returning all docs.
    return MOCK_DB.get("GLOBAL_DOCS", [])

def add_document_to_db(title, content):
    global MOCK_DB, MOCK_DB_DOC_ID
    if "GLOBAL_DOCS" not in MOCK_DB:
        MOCK_DB["GLOBAL_DOCS"] = []
    MOCK_DB["GLOBAL_DOCS"].append({"id": MOCK_DB_DOC_ID, "title": title, "concepts": content})
    MOCK_DB_DOC_ID += 1

# ==============================================================================
# HTML Frontend (Super Platform - Authentication, Roles, Gamification, Summarizer)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="en" dir="auto">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ge_nius - The Ultimate Educational Platform</title>
    
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
            --bg-main: #030304; --surface: #0f1014; --card: #18191f;
            --primary: #4169E1; --primary-glow: rgba(65, 105, 225, 0.4);
            --danger: #ef4444; --accent-gold: #fbbf24; --accent-green: #10b981;
            --text-main: #f8fafc; --text-dim: #94a3b8;
            --border: rgba(255, 255, 255, 0.06); --glass: rgba(15, 16, 20, 0.75);
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        html, body {
            font-family: 'Inter', sans-serif; 
            background-color: var(--bg-main); color: var(--text-main);
            margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden;
            background-image: radial-gradient(ellipse at 10% 10%, rgba(65, 105, 225, 0.08) 0%, transparent 50%);
        }

        .main-wrapper { padding: 10px; display: flex; flex-direction: column; width: 100%; height: 100%; max-width: 900px; margin: 0 auto; position: relative;}

        /* Auth Overlay */
        #authOverlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(3, 3, 4, 0.95); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            z-index: 9999; display: flex; justify-content: center; align-items: center; padding: 20px;
            transition: opacity 0.4s ease;
        }
        .auth-card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 24px;
            padding: 30px; width: 100%; max-width: 400px; box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            display: flex; flex-direction: column; gap: 15px;
        }
        .auth-header { text-align: center; margin-bottom: 10px; }
        .role-selector { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 10px; }
        .role-card {
            background: var(--card); border: 1px solid var(--border); border-radius: 12px;
            padding: 12px 5px; text-align: center; cursor: pointer; font-size: 0.8rem; font-weight: 600;
            color: var(--text-dim); transition: all 0.2s; display: flex; flex-direction: column; align-items: center; gap: 6px;
        }
        .role-card:hover { color: var(--text-main); }
        .role-card.active { background: rgba(65, 105, 225, 0.15); color: var(--primary); border-color: var(--primary); }
        
        .custom-input, .custom-select {
            width: 100%; background: var(--bg-main); border: 1px solid var(--border); color: var(--text-main);
            padding: 12px 16px; border-radius: 12px; font-family: 'Inter', sans-serif; font-size: 0.95rem; outline: none;
        }
        .custom-input:focus, .custom-select:focus { border-color: var(--primary); }
        .custom-select { appearance: none; cursor: pointer; }
        
        /* Top Navbar */
        .top-nav-bar {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 14px; flex-shrink: 0; gap: 12px; background: var(--glass);
            border: 1px solid var(--border); border-radius: 24px; margin-bottom: 10px;
        }
        .nav-left-group { display: flex; align-items: center; gap: 10px; }
        .app-brand { font-family: 'Outfit', sans-serif; font-weight: 900; font-size: 1.2rem; display: flex; align-items: center; gap: 6px; }
        .app-brand span { color: var(--primary); }
        
        /* Gamification HUD */
        .hud-container { display: none; align-items: center; gap: 10px; background: rgba(0,0,0,0.3); padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; border: 1px solid var(--border);}
        .hud-hearts { color: var(--danger); letter-spacing: 2px;}
        .hud-xp { color: var(--accent-gold); display: flex; align-items: center; gap: 4px;}

        .icon-btn { background: transparent; border: none; color: var(--text-main); border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s;}
        .icon-btn:hover { background: var(--card); color: var(--primary); }

        .mode-switcher-bar { display: flex; gap: 4px; background: rgba(0,0,0,0.2); padding: 3px; border-radius: 18px; overflow-x: auto;}
        .mode-tab { padding: 6px 12px; background: transparent; border: none; color: var(--text-dim); font-weight: 600; font-size: 0.8rem; cursor: pointer; border-radius: 14px; white-space: nowrap; transition: all 0.3s; }
        .mode-tab.active { background: var(--surface); color: var(--text-main); border: 1px solid var(--border); }
        .mode-tab.hidden { display: none !important; }

        .tab-section { display: none; flex-direction: column; gap: 10px; flex: 1; min-height: 0; }
        .tab-section.active { display: flex; }

        /* Chat UI */
        .chat-container-wrapper { position: relative; flex: 1; display: flex; flex-direction: column; min-height: 0; }
        .chat-feed { display: flex; flex-direction: column; gap: 24px; flex: 1; overflow-y: auto; padding: 10px 4px 20px 4px; }
        .message-row { display: flex; flex-direction: column; gap: 6px; width: 100%; animation: slideUp 0.3s ease; }
        @keyframes slideUp { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
        
        .message-sender { font-size: 0.75rem; font-weight: 700; color: var(--text-dim); text-transform: uppercase; display: flex; align-items: center; gap: 6px; }
        .message-text-user { font-size: 0.95rem; line-height: 1.6; background: var(--surface); padding: 12px 16px; border-radius: 20px; border-top-right-radius: 4px; width: fit-content; max-width: 85%; border: 1px solid var(--border); align-self: flex-end; }
        .message-text-ai { font-size: 1.05rem; line-height: 1.75; font-weight: 500; align-self: flex-start; max-width: 95%;}

        /* Buttons & Inputs */
        .btn { background: var(--card); color: var(--text-main); border: 1px solid var(--border); padding: 12px 18px; border-radius: 16px; font-weight: 600; font-size: 0.9rem; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.2s; width: 100%; }
        .btn:hover { background: var(--surface); border-color: var(--primary); color: var(--primary); }
        .btn-purple { background: linear-gradient(135deg, #1d4ed8, #4169E1); color: white; border: none; }
        .btn-gold { background: linear-gradient(135deg, #d97706, #fbbf24); color: #fff; border: none;}

        .chat-input-container { flex-shrink: 0; padding-bottom: 6px; position: relative; }
        .input-glass-panel { background: rgba(15, 16, 20, 0.85); backdrop-filter: blur(24px); border: 1px solid var(--border); border-radius: 28px; padding: 8px 10px 8px 16px; display: flex; align-items: center; gap: 10px; z-index: 10;}
        textarea { background: transparent; color: var(--text-main); border: none; outline: none; font-size: 1rem; resize: none; max-height: 120px; min-height: 24px; width: 100%; padding: 8px 0;}
        
        .send-btn-royal { background: var(--primary); color: white; border: none; border-radius: 50%; width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 4px 15px var(--primary-glow); flex-shrink: 0; }
        .send-btn-royal.loading { background: transparent; border: 2px solid var(--border); pointer-events: none; }
        
        .magic-menu { position: absolute; bottom: 70px; left: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 18px; padding: 8px; display: flex; flex-direction: column; gap: 4px; opacity: 0; pointer-events: none; transition: all 0.3s; box-shadow: 0 12px 30px rgba(0,0,0,0.6); z-index: 20; }
        .magic-menu.show { opacity: 1; pointer-events: auto; }
        .magic-item { display: flex; align-items: center; gap: 10px; padding: 10px 16px; font-size: 0.9rem; border-radius: 12px; cursor: pointer; }
        .magic-item:hover { background: var(--card); color: var(--primary); }
        input[type="file"] { display: none; }

        /* Tools */
        .audio-speech-btn, .copy-code-btn { background: transparent; border: 1px solid var(--border); color: var(--text-dim); border-radius: 12px; padding: 6px 14px; font-size: 0.8rem; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; margin-top: 8px; }
        
        .sidebar-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); opacity: 0; pointer-events: none; z-index: 999; }
        .sidebar-overlay.active { opacity: 1; pointer-events: auto; }
        .sidebar { position: fixed; top: 0; left: -320px; width: 300px; height: 100vh; background: var(--surface); border-right: 1px solid var(--border); z-index: 1000; transition: left 0.4s; display: flex; flex-direction: column; padding: 20px; overflow-y: auto;}
        .sidebar.open { left: 0; }
    </style>
</head>
<body>

    <!-- ================= AUTHENTICATION OVERLAY ================= -->
    <div id="authOverlay">
        <div class="auth-card">
            <div class="auth-header">
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
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h3 style="margin:0; display:flex; align-items:center; gap:8px;"><i data-lucide="user"></i> <span id="sidebarUserName">User</span></h3>
            <button class="icon-btn" onclick="toggleSidebar()"><i data-lucide="x"></i></button>
        </div>
        <p style="color:var(--text-dim); font-size:0.8rem; margin-top:-10px; margin-bottom: 20px;" id="sidebarRoleLabel">Role / Level</p>
        
        <button class="btn" onclick="logout()" style="margin-bottom: 20px; border-color:var(--danger); color:var(--danger);"><i data-lucide="log-out"></i> Logout</button>
        
        <div style="font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase; font-weight: 700; margin: 15px 0 8px 0;"><i data-lucide="history"></i> History</div>
        <div id="chatHistoryList" style="flex:1; display:flex; flex-direction:column; gap:6px;"></div>
    </aside>

    <div class="main-wrapper">
        <!-- Top Nav -->
        <div class="top-nav-bar">
            <div class="nav-left-group">
                <button class="icon-btn" onclick="toggleSidebar()"><i data-lucide="align-left"></i></button>
                <div class="app-brand">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:22px; height:22px; color:var(--primary);">
                        <path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/>
                    </svg>
                    ge<span>_</span>nius
                </div>
            </div>
            
            <!-- Gamification HUD -->
            <div class="hud-container" id="gameHud">
                <div class="hud-hearts" id="hudHearts">❤️❤️❤️❤️❤️</div>
                <div class="hud-xp"><i data-lucide="zap" style="width:14px; height:14px;"></i> <span id="hudXpVal">0</span> XP</div>
            </div>

            <div class="mode-switcher-bar">
                <button class="mode-tab hidden" id="tabTeacher" onclick="switchMode('teacher')">Dashboard</button>
                <button class="mode-tab hidden" id="tabStudy" onclick="switchMode('study')">Study</button>
                <button class="mode-tab hidden" id="tabGames" onclick="switchMode('games')">Games</button>
                <button class="mode-tab active" id="tabGeneral" onclick="switchMode('general')">General</button>
            </div>
        </div>

        <!-- TEACHER DASHBOARD TAB -->
        <div class="tab-section" id="teacherSection">
            <div style="background:var(--surface); border:1px solid var(--border); border-radius:20px; padding:20px; text-align:center;">
                <h3 style="color:var(--primary); margin-top:0;"><i data-lucide="upload-cloud"></i> Upload Curriculum Materials</h3>
                <p style="color:var(--text-dim); font-size:0.9rem;">Upload PDFs, DOCs, or Images. The ge_nius engine will automatically compress and integrate them into the students' curriculum.</p>
                
                <div style="display:flex; gap:10px; justify-content:center; margin-top:20px;">
                    <label for="teacherUploadBtn" class="btn btn-purple" style="width:auto; padding:12px 30px;"><i data-lucide="file-plus"></i> Select File (PDF/Image)</label>
                    <input type="file" id="teacherUploadBtn" accept=".pdf,image/*">
                </div>
                <div id="teacherUploadStatus" style="margin-top:15px; font-weight:bold; font-size:0.85rem;"></div>
            </div>
            <h4 style="margin-bottom:0;">Uploaded Curriculum</h4>
            <div id="teacherDocsList" style="display:flex; flex-direction:column; gap:10px; overflow-y:auto; flex:1;"></div>
        </div>

        <!-- MAIN CHAT TAB (Study/Games/General) -->
        <div class="tab-section active" id="chatSection">
            <div class="chat-container-wrapper">
                <div class="chat-feed" id="chatFeed">
                    <div id="welcomeMsg" style="color: var(--text-dim); text-align: center; padding: 80px 20px; display: flex; flex-direction: column; align-items: center; gap: 16px;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:72px; height:72px; filter: drop-shadow(0 0 20px rgba(65,105,225,0.5));">
                            <path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/><circle cx="12" cy="15" r="2"/><path d="M20 15h2"/><path d="M2 15h2"/>
                        </svg>
                        <p style="margin: 0; font-size: 1rem; color: var(--text-dim);">Platform Ready.</p>
                    </div>
                </div>
            </div>

            <div class="chat-input-container">
                <div id="attachmentPreview" style="display:none; align-items:center; justify-content:space-between; background:rgba(65,105,225,0.1); border:1px solid rgba(65,105,225,0.3); padding:8px 12px; border-radius:16px; font-size:0.82rem; color:#93c5fd; margin-bottom:8px;">
                    <span style="display:flex; align-items:center; gap:6px;"><i data-lucide="paperclip" style="width:14px;height:14px;"></i> File Attached</span>
                    <span style="cursor:pointer; color:#fca5a5;" onclick="removeAttachment()"><i data-lucide="x" style="width:16px;height:16px;"></i></span>
                </div>

                <div class="magic-menu" id="magicMenu">
                    <label for="qFileInputCamera" class="magic-item"><i data-lucide="camera" style="color:var(--primary)"></i> Take Photo</label>
                    <input type="file" id="qFileInputCamera" accept="image/*" capture="environment">
                    <label for="qFilePDF" class="magic-item"><i data-lucide="file-text" style="color:var(--primary)"></i> Upload PDF/Doc</label>
                    <input type="file" id="qFilePDF" accept=".pdf,image/*">
                    <div class="magic-item" id="btnSummarize" onclick="triggerSummarizer()" style="display:none; color:var(--accent-gold); font-weight:bold;">
                        <i data-lucide="sparkles"></i> AI Summarize Lesson
                    </div>
                </div>

                <div class="input-glass-panel" id="inputPanel">
                    <button style="background:transparent; border:none; color:var(--text-dim); padding:5px; cursor:pointer;" id="magicBtn" onclick="toggleMagicMenu()"><i data-lucide="plus"></i></button>
                    <textarea id="userQuery" placeholder="Ask ge_nius..." rows="1" oninput="this.style.height='auto'; this.style.height=(this.scrollHeight)+'px';"></textarea>
                    <button style="background:transparent; border:none; color:var(--text-dim); padding:5px; cursor:pointer;" onclick="toggleVoice()"><i data-lucide="mic"></i></button>
                    <button class="send-btn-royal" id="sendBtn" onclick="submitQuestion()"><i data-lucide="arrow-up"></i></button>
                </div>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener("DOMContentLoaded", () => { lucide.createIcons(); checkAuth(); });

        let currentUser = null;
        let currentMode = 'general';
        let attachedFileB64 = null;
        let isAiThinking = false;

        // AUTHENTICATION LOGIC
        let selectedRole = 'student';
        function selectRole(role) {
            selectedRole = role;
            document.querySelectorAll('.role-card').forEach(c => c.classList.remove('active'));
            document.getElementById('role-' + role).classList.add('active');
            
            const levelSelect = document.getElementById('authLevel');
            if(role === 'student') levelSelect.style.display = 'block';
            else levelSelect.style.display = 'none';
        }

        async function performAuth() {
            const name = document.getElementById('authName').value.trim();
            const email = document.getElementById('authEmail').value.trim();
            const pwd = document.getElementById('authPassword').value.trim();
            const level = document.getElementById('authLevel').value;
            const err = document.getElementById('authError');

            if(!name || !email || !pwd) { err.innerText = "Please fill all fields."; return; }
            if(selectedRole === 'student' && !level) { err.innerText = "Please select your study level."; return; }
            
            err.innerText = "Authenticating...";
            try {
                const res = await fetch('/api/auth', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({name, email, password: pwd, role: selectedRole, level})
                });
                const data = await res.json();
                if(data.success) {
                    document.getElementById('authOverlay').style.opacity = '0';
                    setTimeout(() => document.getElementById('authOverlay').style.display = 'none', 400);
                    currentUser = data.user;
                    configureUIForRole();
                } else {
                    err.innerText = data.error || "Authentication failed.";
                }
            } catch(e) { err.innerText = "Network error."; }
        }

        async function checkAuth() {
            try {
                const res = await fetch('/api/user/me');
                const data = await res.json();
                if(data.user) {
                    document.getElementById('authOverlay').style.display = 'none';
                    currentUser = data.user;
                    configureUIForRole();
                }
            } catch(e) {}
        }

        function logout() { document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;"; location.reload(); }

        function configureUIForRole() {
            document.getElementById('sidebarUserName').innerText = currentUser.name;
            document.getElementById('sidebarRoleLabel').innerText = currentUser.role.toUpperCase() + (currentUser.level ? ` • ${currentUser.level}` : '');
            
            // Hide all tabs first
            document.querySelectorAll('.mode-tab').forEach(t => t.classList.add('hidden'));
            document.getElementById('tabGeneral').classList.remove('hidden');

            if (currentUser.role === 'teacher') {
                document.getElementById('tabTeacher').classList.remove('hidden');
                switchMode('teacher');
            } else if (currentUser.role === 'student') {
                document.getElementById('tabStudy').classList.remove('hidden');
                document.getElementById('tabGames').classList.remove('hidden');
                document.getElementById('gameHud').style.display = 'flex';
                updateGamificationHUD(currentUser.hearts, currentUser.xp);
                switchMode('study');
            } else {
                switchMode('general');
            }
        }

        // GAMIFICATION & HUD
        function updateGamificationHUD(hearts, xp) {
            let heartStr = "";
            for(let i=0; i<5; i++) { heartStr += (i < hearts) ? "❤️" : "🤍"; }
            document.getElementById('hudHearts').innerText = heartStr;
            document.getElementById('hudXpVal').innerText = xp;
        }

        // UI & NAVIGATION
        function switchMode(mode) {
            currentMode = mode;
            document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-section').forEach(t => t.classList.remove('active'));
            
            const btnSumm = document.getElementById('btnSummarize');
            if(mode === 'study') btnSumm.style.display = 'flex';
            else btnSumm.style.display = 'none';

            if (mode === 'teacher') {
                document.getElementById('tabTeacher').classList.add('active');
                document.getElementById('teacherSection').classList.add('active');
                fetchTeacherDocs();
            } else {
                let tabId = mode.charAt(0).toUpperCase() + mode.slice(1);
                document.getElementById('tab' + tabId).classList.add('active');
                document.getElementById('chatSection').classList.add('active');
            }
        }

        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('open');
            document.getElementById('sidebarOverlay').classList.toggle('active');
        }

        function toggleMagicMenu() { document.getElementById('magicMenu').classList.toggle('show'); }
        document.addEventListener('click', (e) => {
            const menu = document.getElementById('magicMenu');
            const btn = document.getElementById('magicBtn');
            if (!menu.contains(e.target) && !btn.contains(e.target)) menu.classList.remove('show');
        });

        // FILE UPLOADS (Teacher & Chat)
        async function handleFileSelect(e, isTeacher) {
            const file = e.target.files[0]; if(!file) return;
            const reader = new FileReader();
            reader.onload = async function(evt) {
                const b64 = evt.target.result;
                if(isTeacher) {
                    const stat = document.getElementById('teacherUploadStatus');
                    stat.innerText = "Compressing & Uploading to Curriculum...";
                    stat.style.color = "var(--primary)";
                    await fetch('/api/teacher/upload', {
                        method: 'POST', headers: {'Content-Type':'application/json'},
                        body: JSON.stringify({file: b64, filename: file.name})
                    });
                    stat.innerText = "Uploaded & Compressed successfully!";
                    stat.style.color = "var(--accent-green)";
                    fetchTeacherDocs();
                } else {
                    attachedFileB64 = b64;
                    document.getElementById('attachmentPreview').style.display = 'flex';
                    toggleMagicMenu();
                }
            };
            reader.readAsDataURL(file); e.target.value = '';
        }
        document.getElementById('teacherUploadBtn').addEventListener('change', (e) => handleFileSelect(e, true));
        document.getElementById('qFilePDF').addEventListener('change', (e) => handleFileSelect(e, false));
        document.getElementById('qFileInputCamera').addEventListener('change', (e) => handleFileSelect(e, false));
        
        function removeAttachment() { attachedFileB64 = null; document.getElementById('attachmentPreview').style.display = 'none'; }

        async function fetchTeacherDocs() {
            const res = await fetch('/api/teacher/docs');
            const data = await res.json();
            const list = document.getElementById('teacherDocsList');
            list.innerHTML = data.docs.map(d => `
                <div style="background:var(--card); padding:12px; border-radius:12px; border:1px solid var(--border); display:flex; justify-content:space-between;">
                    <span style="font-weight:600;"><i data-lucide="file-check"></i> ${d.title}</span>
                    <span style="font-size:0.8rem; color:var(--text-dim);">Compressed (zlib)</span>
                </div>
            `).join('') || "<div style='color:var(--text-dim)'>No materials uploaded yet.</div>";
            lucide.createIcons({root: list});
        }

        // CHAT & AI ENGINE
        function triggerSummarizer() {
            toggleMagicMenu();
            document.getElementById('userQuery').value = "Please summarize the current lesson focusing on: 1. Core Concepts, 2. Formulas (LaTeX), 3. Examples, 4. Exam notes.";
            submitQuestion(true);
        }

        let recognition = null;
        function toggleVoice() {
            const input = document.getElementById('userQuery');
            if(!('webkitSpeechRecognition' in window)) return alert('Not supported.');
            if(recognition) { recognition.stop(); recognition=null; return; }
            recognition = new webkitSpeechRecognition();
            recognition.lang = 'ar-SA';
            recognition.onresult = (e) => { input.value = e.results[0][0].transcript; };
            recognition.onend = () => { recognition=null; };
            recognition.start();
        }

        function submitQuestion(isSummary = false) {
            if(isAiThinking) return;
            const input = document.getElementById('userQuery');
            const text = input.value.trim();
            if(!text && !attachedFileB64) return;
            
            if(currentUser && currentUser.role === 'student' && currentUser.hearts <= 0) {
                alert("You have 0 hearts left! Take a break to regenerate.");
                return;
            }

            isAiThinking = true;
            document.getElementById('inputPanel').style.opacity = '0.5';
            document.getElementById('sendBtn').classList.add('loading');
            document.getElementById('welcomeMsg')?.remove();

            const feed = document.getElementById('chatFeed');
            
            // Append User Message
            const uRow = document.createElement('div'); uRow.className = 'message-row'; uRow.style.alignItems = 'flex-end';
            let uText = text.replace(/\\n/g, '<br>');
            if(attachedFileB64) uText += `<br><span style="color:var(--primary); font-size:0.8em;"><i data-lucide="file"></i> File Attached</span>`;
            uRow.innerHTML = `<div class="message-sender" style="justify-content:flex-end;">You <i data-lucide="user" style="width:12px;height:12px;"></i></div><div class="message-text-user">${uText}</div>`;
            feed.appendChild(uRow);

            // Loading state
            const lRow = document.createElement('div'); lRow.className = 'message-row';
            lRow.innerHTML = `<div class="message-sender" style="color:var(--primary);"><i data-lucide="cpu" style="width:14px;height:14px;"></i> ge_nius Processing...</div>`;
            feed.appendChild(lRow);
            
            const payload = { query: text, file: attachedFileB64, mode: currentMode, isSummary };
            input.value = ''; removeAttachment(); feed.scrollTop = feed.scrollHeight; lucide.createIcons();

            fetch('/api/ask', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) })
            .then(res => res.json())
            .then(data => {
                feed.removeChild(lRow);
                const aiRow = document.createElement('div'); aiRow.className = 'message-row';
                const aiHeader = `<div class="message-sender" style="color:var(--primary); display:flex; align-items:center; gap:5px;"><svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 13v-2a2 2 0 0 0-2-2h-1v-2a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v2H7a2 2 0 0 0-2 2v2"/><path d="M4 11h16a2 2 0 0 1 2 2v2a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2a2 2 0 0 1 2-2z"/></svg> ge_nius</div>`;
                
                aiRow.innerHTML = `${aiHeader}<div class="message-text-ai">${marked.parse(data.answer || "Error")}</div>`;
                feed.appendChild(aiRow);

                // Handle Gamification Sync
                if(data.hearts !== undefined && data.xp !== undefined && currentUser.role === 'student') {
                    currentUser.hearts = data.hearts; currentUser.xp = data.xp;
                    updateGamificationHUD(data.hearts, data.xp);
                }

                feed.scrollTop = feed.scrollHeight;
                if(window.MathJax) MathJax.typesetPromise([aiRow]);
                lucide.createIcons();
            }).finally(() => {
                isAiThinking = false;
                document.getElementById('inputPanel').style.opacity = '1';
                document.getElementById('sendBtn').classList.remove('loading');
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
        c_header = self.headers.get('Cookie')
        if c_header:
            c = cookies.SimpleCookie(c_header)
            if 'session_id' in c: return c['session_id'].value
        return None

    def send_ai_request(self, payload):
        req_data = json.dumps(payload).encode("utf-8")
        headers = { "Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}" }
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(API_URL, data=req_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, context=ctx, timeout=50) as res:
            return json.loads(res.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()

    def do_GET(self):
        try:
            if self.path == "/":
                sess_id = self.get_session_id()
                is_new = False
                if not sess_id:
                    sess_id = str(uuid.uuid4())
                    is_new = True

                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                if is_new:
                    self.send_header("Set-Cookie", f"session_id={sess_id}; Path=/; Max-Age=31536000")
                self.end_headers()
                self.wfile.write(HTML_CODE.encode("utf-8"))
            
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
            sess_id = self.get_session_id()
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length).decode('utf-8')) if length > 0 else {}

            if self.path == "/api/auth":
                # Handle Login/Register simultaneously for mock
                email = data.get("email")
                if email not in MOCK_USERS:
                    MOCK_USERS[email] = {
                        "name": data.get("name"), "email": email, "password": data.get("password"),
                        "role": data.get("role"), "level": data.get("level"), "hearts": 5, "xp": 0
                    }
                MOCK_SESSIONS[sess_id] = email
                self.send_json_response({"success": True, "user": MOCK_USERS[email]})

            elif self.path == "/api/teacher/upload":
                # Smart Compression Simulation
                b64_file = data.get("file", "")
                filename = data.get("filename", "Document")
                if b64_file:
                    head, comp = compress_file_data(b64_file)
                    # Simulate saving compressed file to DB...
                    add_document_to_db(filename, f"Compressed content of {filename}. Extracted for AI.")
                self.send_json_response({"success": True})

            elif self.path == "/api/ask":
                user = get_current_user(sess_id)
                query = data.get("query", "")
                file_b64 = data.get("file")
                mode = data.get("mode")
                is_summary = data.get("isSummary", False)

                msgs = []
                if file_b64:
                    if file_b64.startswith("data:image"):
                        msgs.append({"type": "image_url", "image_url": {"url": file_b64}})
                    else:
                        msgs.append({"type": "text", "text": "[File Attached. Read context.]"})
                
                # Context based on Role & Mode
                system_prompt = "You are ge_nius, an advanced AI tutor."
                if user and user.get("level"):
                    system_prompt += f"\nThe user is a student in: {user['level']}."
                
                if mode == "games":
                    system_prompt += "\nThis is GAME MODE. Ask puzzles or test the user. If they answer wrongly, prefix your response EXACTLY with [WRONG]. If correct, prefix with [CORRECT]."
                elif is_summary:
                    system_prompt += "\nOutput a highly structured summary: 1. Core Concepts, 2. Formulas (LaTeX), 3. Examples, 4. Exam traps."

                msgs.append({"type": "text", "text": f"{system_prompt}\nUser: {query}"})
                
                answer = self.send_ai_request({"model": MODEL_NAME, "messages": [{"role": "user", "content": msgs}], "max_tokens": 4096})

                # Gamification Logic Parsing
                resp_data = {"status": "success", "answer": answer}
                if user and user["role"] == "student" and mode == "games":
                    if "[WRONG]" in answer:
                        user["hearts"] = max(0, user["hearts"] - 1)
                        answer = answer.replace("[WRONG]", "").strip()
                    elif "[CORRECT]" in answer:
                        user["xp"] += 50
                        answer = answer.replace("[CORRECT]", "").strip()
                    
                    resp_data["answer"] = answer
                    resp_data["hearts"] = user["hearts"]
                    resp_data["xp"] = user["xp"]

                self.send_json_response(resp_data)
                
        except Exception as e:
            self.send_json_response({"error": str(e)})

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args): pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), StudyAppRequestHandler)
    print(f"Server started on port {port}")
    server.serve_forever()
