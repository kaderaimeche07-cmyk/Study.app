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
# مفتاح Qwen3 الخاص بك
# ==============================================================================
API_KEY = "sk-FWE5lPc8aegQHHJZvk967w"
API_URL = "https://app.ai-grid.io/v1/chat/completions"
PORT = 8080

MODEL_NAME = "Qwen3-30B-A3B-Thinking"

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    return psycopg2.connect(database_url, sslmode='require')

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
# الواجهة الرسومية (النسخة الخرافية الكاملة: Markdown + Sounds + Theme + History)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ge_nius Assistant</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&family=Outfit:wght@700;900&display=swap" rel="stylesheet">
    
    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>
    
    <!-- Marked.js لتحويل النصوص إلى تنسيق جميل -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

    <!-- MathJax للمعادلات الرياضية -->
    <script>
      window.MathJax = {
        tex: {
          inlineMath: [['$', '$']],
          displayMath: [['$$', '$$']],
          processEscapes: true
        },
        options: { skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre'] }
      };
    </script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" id="MathJax-script" async></script>

    <style>
        :root {
            /* الألوان الافتراضية (الوضع الليلي) */
            --bg-main: #0f172a; --surface: #1e293b; --card: #334155;
            --primary: #6366f1; --accent-purple: #8b5cf6; --accent-green: #10b981;
            --danger: #ef4444; --text-main: #f8fafc; --text-dim: #94a3b8;
            --border: rgba(255, 255, 255, 0.08); --ai-bubble-bg: #17223b;
        }

        /* الوضع النهاري */
        body.light-mode {
            --bg-main: #f1f5f9; --surface: #ffffff; --card: #e2e8f0;
            --primary: #4f46e5; --text-main: #0f172a; --text-dim: #475569;
            --border: rgba(0, 0, 0, 0.1); --ai-bubble-bg: #e0e7ff;
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; transition: background-color 0.3s ease; }

        body {
            font-family: 'Tajawal', sans-serif; background-color: var(--bg-main);
            color: var(--text-main); margin: 0; padding: 12px;
            min-height: 100vh; display: flex; flex-direction: column; gap: 12px;
        }

        .app-header {
            background: var(--surface); padding: 18px 18px 12px; border-radius: 16px;
            border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;
        }
        
        .header-actions { display: flex; gap: 10px; align-items: center; }
        
        .theme-btn {
            background: var(--card); border: 1px solid var(--border); color: var(--text-main);
            border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;
            cursor: pointer;
        }

        .submarine-logo {
            position: relative; background: linear-gradient(180deg, #f59e0b, #d97706);
            padding: 4px 18px; border-radius: 40px; border: 2px solid #b45309;
            display: inline-flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 10px rgba(245, 158, 11, 0.25), inset 0 -3px 5px rgba(0,0,0,0.2);
            color: #451a03; font-weight: 900; font-size: 1.15rem; letter-spacing: 1px;
            font-family: 'Outfit', sans-serif; margin-right: 8px; margin-top: 5px;
        }
        .submarine-logo::before {
            content: ''; position: absolute; top: -12px; left: 60%; width: 8px; height: 12px;
            background: #f59e0b; border-left: 2px solid #b45309; border-right: 2px solid #b45309; z-index: 1;
        }
        .submarine-logo::after {
            content: ''; position: absolute; top: -12px; left: calc(60% + 4px); width: 12px; height: 5px;
            background: #f59e0b; border: 2px solid #b45309; border-radius: 2px; z-index: 2;
        }
        .submarine-propeller {
            position: absolute; right: -10px; top: 50%; transform: translateY(-50%); width: 8px; height: 18px;
            background: #94a3b8; border: 2px solid #475569; border-radius: 4px;
        }
        .submarine-propeller::after {
            content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 4px; height: 22px;
            background: #cbd5e1; border-radius: 2px; animation: spin-propeller 0.15s linear infinite;
        }
        @keyframes spin-propeller { 0% { transform: translate(-50%, -50%) scaleY(1); } 50% { transform: translate(-50%, -50%) scaleY(0.2); } 100% { transform: translate(-50%, -50%) scaleY(1); } }

        .lucide { width: 18px; height: 18px; stroke-width: 2.2; }

        .tab-bar { display: flex; background: var(--surface); border-radius: 12px; padding: 4px; border: 1px solid var(--border); }
        .tab-btn {
            flex: 1; padding: 12px; background: none; border: none; color: var(--text-dim);
            font-family: 'Tajawal', sans-serif; font-weight: 700; font-size: 0.95rem; cursor: pointer;
            border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px;
        }
        .tab-btn.active { background: var(--primary); color: white; }

        .tab-section { display: none; flex-direction: column; gap: 12px; flex: 1; }
        .tab-section.active { display: flex; }

        .card { background: var(--surface); border-radius: 16px; border: 1px solid var(--border); padding: 16px; display: flex; flex-direction: column; gap: 12px; }

        .chat-feed {
            display: flex; flex-direction: column; gap: 14px; max-height: 55vh; overflow-y: auto; padding: 10px;
            background: var(--card); border-radius: 12px; border: 1px solid var(--border); scroll-behavior: smooth;
        }

        .chat-bubble {
            padding: 14px 16px; border-radius: 16px; font-size: 0.95rem; line-height: 1.8; max-width: 92%;
            display: flex; gap: 10px; align-items: flex-start; position: relative;
            animation: slideUp 0.3s ease-out forwards;
        }
        @keyframes slideUp { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }

        .user-bubble { background: var(--primary); color: white; align-self: flex-start; border-bottom-right-radius: 4px; }
        .ai-bubble { background: var(--ai-bubble-bg); color: var(--text-main); align-self: flex-end; border-bottom-left-radius: 4px; border: 1px solid var(--border); flex-direction: row-reverse; }
        
        /* تحسينات الـ Markdown */
        .ai-content { width: 100%; overflow-x: auto; }
        .ai-content h1, .ai-content h2, .ai-content h3 { margin-top: 5px; margin-bottom: 10px; color: var(--accent-purple); }
        .ai-content p { margin: 5px 0; }
        .ai-content strong { color: var(--accent-green); }
        
        .copy-btn {
            position: absolute; bottom: -10px; left: 10px; background: var(--surface); color: var(--text-dim);
            border: 1px solid var(--border); border-radius: 8px; padding: 4px 8px; font-size: 0.75rem;
            cursor: pointer; display: flex; align-items: center; gap: 4px; opacity: 0.8;
        }
        .copy-btn:hover { opacity: 1; color: var(--primary); }

        .bubble-icon { flex-shrink: 0; margin-top: 2px; }

        .input-group { display: flex; flex-direction: column; gap: 6px; }
        textarea {
            background: var(--card); color: var(--text-main); border: 1px solid var(--border);
            padding: 12px; border-radius: 10px; font-family: 'Tajawal', sans-serif; font-size: 0.95rem;
            outline: none; resize: vertical; min-height: 60px;
        }

        .image-preview-bar {
            display: none; align-items: center; justify-content: space-between; background: rgba(139, 92, 246, 0.15);
            border: 1px solid var(--accent-purple); padding: 8px 12px; border-radius: 10px; font-size: 0.85rem; color: var(--accent-purple);
        }

        .btn-controls { display: grid; grid-template-columns: 1fr auto auto auto; gap: 8px; }

        .btn {
            background: var(--primary); color: white; border: none; padding: 12px; border-radius: 10px;
            font-family: 'Tajawal', sans-serif; font-weight: 700; font-size: 0.95rem; cursor: pointer;
            display: flex; align-items: center; justify-content: center; gap: 8px; transition: transform 0.1s;
        }
        .btn:active { transform: scale(0.96); }
        .btn-purple { background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%); }
        .btn-green { background: var(--accent-green); color: #042f2e; }
        .btn-clear { background: var(--danger); }
        input[type="file"] { display: none; }

        .doc-item { background: var(--card); border-radius: 12px; padding: 12px; border: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }
        .doc-header { display: flex; justify-content: space-between; align-items: center; }
        .doc-title { font-weight: 700; font-size: 0.95rem; color: var(--accent-purple); display: flex; align-items: center; gap: 8px;}
        .doc-body { font-size: 0.85rem; color: var(--text-dim); line-height: 1.5; max-height: 100px; overflow-y: auto; background: var(--surface); padding: 8px; border-radius: 6px; white-space: pre-wrap; }

        .spin-icon { animation: spin 1.2s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        .status-msg { display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 0.9rem; margin-top: 10px; font-weight: bold;}
    </style>
</head>
<body>

    <header class="app-header">
        <div class="submarine-logo">
            ge_nius
            <div class="submarine-propeller"></div>
        </div>
        <div class="header-actions">
            <span style="font-size: 0.85rem; color: var(--accent-green); display: flex; align-items: center; gap: 5px;" id="docCountBadge">
                <i data-lucide="database"></i> 0 وثائق
            </span>
            <button class="theme-btn" id="themeToggleBtn" onclick="toggleTheme()">
                <i data-lucide="sun" id="themeIcon"></i>
            </button>
        </div>
    </header>

    <div class="tab-bar">
        <button class="tab-btn active" id="btnAskTab" onclick="switchTab('askTab', this)">
            <i data-lucide="message-circle-code"></i> المحادثة
        </button>
        <button class="tab-btn" id="btnDocsTab" onclick="switchTab('docsTab', this)">
            <i data-lucide="files"></i> وثائق الدروس
        </button>
    </div>

    <!-- TAB 1: Chat Feed -->
    <div class="tab-section active" id="askTab">
        <div class="chat-feed" id="chatFeed">
            <div id="welcomeMsg" style="color: var(--text-dim); font-style: italic; text-align: center; padding: 15px; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                <i data-lucide="sparkles" style="width: 28px; height: 28px; color: var(--accent-purple);"></i>
                مرحباً بك! ارفع وثائق دروسك، ثم صور أو اكتب سؤالك هنا ليجيبك النظام بدقة.
            </div>
        </div>

        <div class="card">
            <div class="image-preview-bar" id="questionImgPreview">
                <span style="display: flex; align-items: center; gap: 6px;"><i data-lucide="image-check" style="width: 16px; height: 16px;"></i> تم إرفاق الصورة</span>
                <span style="cursor: pointer; color: var(--danger); font-weight: bold; display: flex; align-items: center; gap: 4px;" onclick="removeQuestionImage()">
                    <i data-lucide="trash-2" style="width: 16px; height: 16px;"></i> إلغاء
                </span>
            </div>

            <div class="input-group">
                <textarea id="userQuery" placeholder="اكتب سؤالك هنا أو ارفق صورة التمرين..."></textarea>
            </div>
            
            <div class="btn-controls">
                <button class="btn btn-green" onclick="submitQuestion()">
                    <i data-lucide="send"></i> إرسال
                </button>
                <label for="qFileInputCamera" class="btn btn-purple" title="كاميرا">
                    <i data-lucide="camera"></i>
                </label>
                <input type="file" id="qFileInputCamera" accept="image/*" capture="environment">

                <label for="qFileInputGallery" class="btn btn-purple" title="معرض الصور">
                    <i data-lucide="image"></i>
                </label>
                <input type="file" id="qFileInputGallery" accept="image/*">
                
                <button class="btn btn-clear" onclick="clearChat()" title="مسح المحادثة">
                    <i data-lucide="trash"></i>
                </button>
            </div>
        </div>
    </div>

    <!-- TAB 2: Curriculum Documents Section -->
    <div class="tab-section" id="docsTab">
        <div class="card">
            <span style="font-weight: 700; font-size: 1rem; color: var(--accent-purple); display: flex; align-items: center; gap: 8px;">
                <i data-lucide="file-plus-2"></i> إضافة وثائق دراسية
            </span>
            <p style="font-size: 0.8rem; color: var(--text-dim); margin: 0;">اختر التصوير المباشر لصفحة الدرس أو ارفع عدة صور معاً:</p>
            
            <div style="display: flex; gap: 8px;">
                <label for="docFileInputCamera" class="btn btn-purple" style="flex: 1; text-align: center; margin:0;">
                    <i data-lucide="camera"></i> تصوير مباشر
                </label>
                <input type="file" id="docFileInputCamera" accept="image/*" capture="environment">

                <label for="docFileInputGallery" class="btn btn-purple" style="flex: 1; text-align: center; margin:0;">
                    <i data-lucide="images"></i> معرض الصور
                </label>
                <input type="file" id="docFileInputGallery" accept="image/*" multiple>
            </div>
            
            <div id="uploadStatus" class="status-msg"></div>
        </div>

        <div class="card">
            <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-dim); display: flex; align-items: center; gap: 8px;">
                <i data-lucide="folder-open"></i> الوثائق والأفكار المستخرجة الخاصة بك:
            </span>
            <div id="docsList" style="display: flex; flex-direction: column; gap: 10px;"></div>
        </div>
    </div>

    <script>
        // إعدادات الوضع الليلي / النهاري
        function toggleTheme() {
            const isLight = document.body.classList.toggle('light-mode');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            const themeIcon = document.getElementById('themeIcon');
            themeIcon.setAttribute('data-lucide', isLight ? 'moon' : 'sun');
            lucide.createIcons();
            playSound('tap');
        }
        if (localStorage.getItem('theme') === 'light') { document.body.classList.add('light-mode'); }
        lucide.createIcons(); // تفعيل الأيقونات في البداية
        if(document.body.classList.contains('light-mode')) { document.getElementById('themeIcon').setAttribute('data-lucide', 'moon'); lucide.createIcons(); }

        // نظام الصوت الذكي 
        function playSound(type) {
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain); gain.connect(ctx.destination);
                if (type === 'send') { osc.frequency.setValueAtTime(400, ctx.currentTime); osc.type = 'sine'; gain.gain.setValueAtTime(0.05, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1); osc.start(); osc.stop(ctx.currentTime + 0.1); }
                else if (type === 'receive') { osc.frequency.setValueAtTime(800, ctx.currentTime); osc.type = 'triangle'; gain.gain.setValueAtTime(0.05, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2); osc.start(); osc.stop(ctx.currentTime + 0.2); }
                else if (type === 'success') { osc.frequency.setValueAtTime(1200, ctx.currentTime); osc.type = 'sine'; gain.gain.setValueAtTime(0.05, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3); osc.start(); osc.stop(ctx.currentTime + 0.3); }
                else if (type === 'tap') { osc.frequency.setValueAtTime(300, ctx.currentTime); osc.type = 'square'; gain.gain.setValueAtTime(0.02, ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.05); osc.start(); osc.stop(ctx.currentTime + 0.05); }
            } catch(e) {}
        }

        // استرجاع المحادثة المحفوظة
        const chatFeed = document.getElementById('chatFeed');
        const savedChat = localStorage.getItem('genius_chat_history');
        if (savedChat && savedChat.trim() !== '') {
            chatFeed.innerHTML = savedChat;
            lucide.createIcons({root: chatFeed});
            if (window.MathJax) MathJax.typesetPromise([chatFeed]);
            chatFeed.scrollTop = chatFeed.scrollHeight;
        }
        function saveChatHistory() {
            // مسح رسالة التحميل قبل الحفظ
            const clones = chatFeed.cloneNode(true);
            const loaders = clones.querySelectorAll('.loading-bubble-temp');
            loaders.forEach(l => l.remove());
            localStorage.setItem('genius_chat_history', clones.innerHTML);
        }
        function clearChat() {
            playSound('tap');
            if(confirm('هل أنت متأكد من مسح محادثة اليوم؟')) {
                localStorage.removeItem('genius_chat_history');
                chatFeed.innerHTML = `<div id="welcomeMsg" style="color: var(--text-dim); font-style: italic; text-align: center; padding: 15px; display: flex; flex-direction: column; align-items: center; gap: 8px;"><i data-lucide="sparkles" style="width: 28px; height: 28px; color: var(--accent-purple);"></i>تم مسح المحادثة بنجاح.</div>`;
                lucide.createIcons();
            }
        }

        // نسخ النص
        window.copyText = function(btn, text) {
            navigator.clipboard.writeText(decodeURIComponent(text)).then(() => {
                const originalHtml = btn.innerHTML;
                btn.innerHTML = `<i data-lucide="check"></i> تم النسخ`;
                lucide.createIcons({root: btn});
                playSound('tap');
                setTimeout(() => { btn.innerHTML = originalHtml; lucide.createIcons({root: btn}); }, 2000);
            });
        };

        let curriculumDocs = [];
        let attachedQuestionBase64 = null;
        fetchDocs();

        function switchTab(tabId, btnElement) {
            playSound('tap');
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
            if(btnElement) btnElement.classList.add('active');
            const targetSection = document.getElementById(tabId);
            if(targetSection) targetSection.classList.add('active');
        }

        function fetchDocs() {
            fetch('/api/docs').then(res => res.json()).then(data => {
                curriculumDocs = data; renderDocs();
            }).catch(err => console.log(err));
        }

        function renderDocs() {
            const listDiv = document.getElementById('docsList');
            const countBadge = document.getElementById('docCountBadge');
            if(countBadge) { countBadge.innerHTML = `<i data-lucide="database" style="width: 14px; height: 14px;"></i> ${curriculumDocs.length} وثائق`; lucide.createIcons({root: countBadge}); }
            if (!listDiv) return;
            if (curriculumDocs.length === 0) {
                listDiv.innerHTML = '<div style="color: var(--text-dim); font-style: italic; text-align: center; padding: 10px;">لم تضف أي وثائق دروس بعد.</div>';
                return;
            }
            listDiv.innerHTML = curriculumDocs.map((item, index) => `
                <div class="doc-item">
                    <div class="doc-header">
                        <span class="doc-title"><i data-lucide="file-text"></i> وثيقة ${index + 1}</span>
                        <button class="btn btn-clear" style="padding: 4px 10px;" onclick="deleteDoc(${item.id})"><i data-lucide="trash-2" style="width: 14px; height: 14px;"></i> حذف</button>
                    </div>
                    <div class="doc-body">${item.concepts}</div>
                </div>
            `).join('');
            lucide.createIcons({root: listDiv});
        }

        function handleQuestionImageSelect(e) {
            playSound('tap');
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(evt) {
                attachedQuestionBase64 = evt.target.result;
                const preview = document.getElementById('questionImgPreview');
                if(preview) preview.style.display = 'flex';
            };
            reader.readAsDataURL(file);
            e.target.value = '';
        }
        document.getElementById('qFileInputCamera').addEventListener('change', handleQuestionImageSelect);
        document.getElementById('qFileInputGallery').addEventListener('change', handleQuestionImageSelect);

        function removeQuestionImage() { playSound('tap'); attachedQuestionBase64 = null; document.getElementById('questionImgPreview').style.display = 'none'; }

        async function handleDocImageSelect(e) {
            playSound('tap');
            const files = e.target.files;
            if (!files || files.length === 0) return;
            const statusDiv = document.getElementById('uploadStatus');
            for (let i = 0; i < files.length; i++) {
                if(statusDiv) { statusDiv.innerHTML = `<i data-lucide="loader" class="spin-icon"></i> جاري قراءة وتفريغ الوثيقة ${i + 1} من ${files.length}...`; statusDiv.style.color = 'var(--primary)'; lucide.createIcons({root: statusDiv}); }
                await new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = async function(evt) {
                        try {
                            const res = await fetch('/api/docs/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: evt.target.result }) });
                            const data = await res.json();
                            if (data.docs) curriculumDocs = data.docs;
                        } catch (err) {}
                        resolve();
                    };
                    reader.readAsDataURL(files[i]);
                });
            }
            renderDocs();
            if(statusDiv) { statusDiv.innerHTML = '<i data-lucide="check-circle-2"></i> تم الحفظ بنجاح!'; statusDiv.style.color = 'var(--accent-green)'; lucide.createIcons({root: statusDiv}); playSound('success'); }
            e.target.value = '';
        }
        document.getElementById('docFileInputCamera').addEventListener('change', handleDocImageSelect);
        document.getElementById('docFileInputGallery').addEventListener('change', handleDocImageSelect);

        function deleteDoc(id) { fetch('/api/docs/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) }).then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); }); }

        function submitQuestion() {
            const queryInput = document.getElementById('userQuery');
            const query = queryInput.value.trim();
            if (!query && !attachedQuestionBase64) { alert('يرجى كتابة سؤالك أو إرفاق صورة أولاً!'); return; }
            if (curriculumDocs.length === 0) { alert('يرجى رفع وثائق دروسك أولاً!'); return; }
            
            playSound('send');
            const welcome = document.getElementById('welcomeMsg'); if(welcome) welcome.remove();

            let userTextDisplay = query;
            if (attachedQuestionBase64) { userTextDisplay = (query ? query + '<br>' : '') + '<span style="color:#fbbf24; font-size:0.85em"><i data-lucide="image" style="width:14px;height:14px;"></i> تم إرفاق صورة</span>'; }

            const userBubble = document.createElement('div');
            userBubble.className = 'chat-bubble user-bubble';
            userBubble.innerHTML = `<i data-lucide="user" class="bubble-icon"></i> <div>${userTextDisplay}</div>`;
            chatFeed.appendChild(userBubble);
            lucide.createIcons({root: userBubble});

            const loadingBubble = document.createElement('div');
            loadingBubble.className = 'chat-bubble ai-bubble loading-bubble-temp';
            loadingBubble.innerHTML = `<i data-lucide="loader-circle" class="bubble-icon spin-icon"></i> <div class="thinking-text" style="color: var(--accent-purple); font-weight: bold;">أقرأ الوثائق... ⏳</div>`;
            chatFeed.appendChild(loadingBubble);
            lucide.createIcons({root: loadingBubble});
            
            // تأثير التفكير الحي
            const thinkPhrases = ["أقرأ الوثائق... ⏳", "أحلل سؤالك بدقة... 🧠", "أستخرج المفاهيم... 🔍", "أجهز لك الشرح السحري! ✨"];
            let phraseIdx = 0;
            const thinkInterval = setInterval(() => {
                phraseIdx = (phraseIdx + 1) % thinkPhrases.length;
                const txt = loadingBubble.querySelector('.thinking-text');
                if(txt) txt.textContent = thinkPhrases[phraseIdx];
            }, 2000);

            const payload = { query: query, image: attachedQuestionBase64 };
            queryInput.value = ''; removeQuestionImage(); chatFeed.scrollTop = chatFeed.scrollHeight;

            fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            .then(res => res.json())
            .then(data => {
                clearInterval(thinkInterval);
                chatFeed.removeChild(loadingBubble);
                playSound('receive');
                const aiBubble = document.createElement('div');

                if (data.status === 'out_of_scope') {
                    aiBubble.className = 'chat-bubble out-of-scope-bubble';
                    aiBubble.innerHTML = `<i data-lucide="alert-triangle"></i> عذراً، هذا غير مدرج في برنامجك الدراسي`;
                } else if (data.status === 'success') {
                    aiBubble.className = 'chat-bubble ai-bubble';
                    // تحويل الـ Markdown إلى HTML منسق وجميل
                    const formattedHtml = marked.parse(data.answer);
                    const encodedAnswer = encodeURIComponent(data.answer);
                    aiBubble.innerHTML = `
                        <i data-lucide="bot" class="bubble-icon" style="color: var(--accent-purple)"></i> 
                        <div class="ai-content">${formattedHtml}</div>
                        <button class="copy-btn" onclick="copyText(this, '${encodedAnswer}')"><i data-lucide="copy" style="width:14px;height:14px;"></i> نسخ</button>
                    `;
                    
                    if (window.MathJax && window.MathJax.typesetPromise) {
                        window.MathJax.typesetPromise([aiBubble]).catch(err => console.log(err));
                    }
                } else {
                    aiBubble.className = 'chat-bubble ai-bubble';
                    aiBubble.innerHTML = `<i data-lucide="alert-circle" class="bubble-icon" style="color: var(--danger)"></i> <div>حدث خطأ: ${data.error || 'تعذر الإجابة.'}</div>`;
                }
                
                chatFeed.appendChild(aiBubble); 
                lucide.createIcons({root: aiBubble});
                chatFeed.scrollTop = chatFeed.scrollHeight;
                saveChatHistory();
            }).catch(err => {
                clearInterval(thinkInterval);
                chatFeed.removeChild(loadingBubble);
                const errBubble = document.createElement('div');
                errBubble.className = 'chat-bubble ai-bubble';
                errBubble.innerHTML = `<i data-lucide="wifi-off" class="bubble-icon" style="color: var(--danger)"></i> <div>تعذر الاتصال بالسيرفر.</div>`;
                chatFeed.appendChild(errBubble); 
                lucide.createIcons({root: errBubble});
                chatFeed.scrollTop = chatFeed.scrollHeight;
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# سيرفر بايثون الموحد
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
                payload = {
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_base64}}]}],
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
            docs = load_curriculum(session_id)

            messages_content = []
            if question_image_base64:
                messages_content.append({"type": "image_url", "image_url": {"url": question_image_base64}})

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
                f"3. إذا كان ضمن الدروس والمحتوى المرفوع، قدم إجابة شاملة وشارحة خطوة بخطوة باللغة العربية.\n"
                f"\n--- تعليمات التنسيق والمعادلات (تطبيق إلزامي) ---\n"
                f"- لا تستخدم أبداً الأقواس المربعة \\[ أو \\] أو الأقواس الدائرية \\( أو \\) لتمثيل المعادلات.\n"
                f"- لكتابة المتغيرات الرياضية والرموز داخل النص: يجب استخدام رمز الدولار المفرد حصراً، مثال: $x=2$ أو $v$.\n"
                f"- لكتابة المعادلات الطويلة والمصفوفات والكسور: يجب كتابتها في سطر جديد ومستقل واستخدام رمز الدولار المزدوج حصراً، مثال:\n"
                f"$$ \\vec{{u}} = \\sqrt{{x^2 + y^2}} $$\n"
                f"- يمكنك استخدام Markdown لتنظيم العناوين الفرعية (بواسطة ###) والقوائم المقطعية (-)."
            )
            messages_content.append({"type": "text", "text": full_prompt})

            payload = {
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": messages_content}],
                "max_tokens": 4096
            }

            try:
                ai_reply = self.send_api_request(payload)
                if "OUT_OF_SCOPE" in ai_reply or ai_reply.startswith("OUT_OF_SCOPE"):
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
