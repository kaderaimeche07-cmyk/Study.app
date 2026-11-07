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
# استخدام مفتاح التفكير الفعال والناجح لديك لكافة وظائف التطبيق
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
        print(f"خطأ في قراءة قاعدة البيانات: {e}")
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
        print(f"خطأ في الإضافة لقاعدة البيانات: {e}")

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
        print(f"خطأ في الحذف من قاعدة البيانات: {e}")

# ==============================================================================
# الواجهة الرسومية (تتضمن أزرار الكاميرا المباشرة و MathJax)
# ==============================================================================
HTML_CODE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>مساعد المنهج الذكي (Qwen3)</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap" rel="stylesheet">
    <script>
      window.MathJax = {
        tex: {
          inlineMath: [['$', '$']],
          displayMath: [['$$', '$$']],
          processEscapes: true
        },
        options: {
          skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
        }
      };
    </script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" id="MathJax-script" async></script>

    <style>
        :root {
            --bg-dark: #0f172a; --surface-dark: #1e293b; --card-dark: #334155;
            --primary: #6366f1; --accent-purple: #8b5cf6; --accent-green: #10b981;
            --danger: #ef4444; --text-light: #f8fafc; --text-dim: #94a3b8;
            --border: rgba(255, 255, 255, 0.08);
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        body {
            font-family: 'Tajawal', sans-serif; background-color: var(--bg-dark);
            color: var(--text-light); margin: 0; padding: 12px;
            min-height: 100vh; display: flex; flex-direction: column; gap: 12px;
        }

        .app-header {
            background: var(--surface-dark); padding: 14px 18px; border-radius: 16px;
            border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;
        }
        .app-title { font-size: 1.1rem; font-weight: 800; margin: 0; color: #a5b4fc; }

        .tab-bar {
            display: flex; background: var(--surface-dark); border-radius: 12px; padding: 4px; border: 1px solid var(--border);
        }
        .tab-btn {
            flex: 1; padding: 12px; background: none; border: none;
            color: var(--text-dim); font-family: 'Tajawal', sans-serif;
            font-weight: 700; font-size: 0.95rem; cursor: pointer; border-radius: 8px;
            transition: all 0.2s; text-align: center;
        }
        .tab-btn.active { background: var(--primary); color: white; }

        .tab-section { display: none; flex-direction: column; gap: 12px; flex: 1; }
        .tab-section.active { display: flex; }

        .card {
            background: var(--surface-dark); border-radius: 16px;
            border: 1px solid var(--border); padding: 16px;
            display: flex; flex-direction: column; gap: 12px;
        }

        .chat-feed {
            display: flex; flex-direction: column; gap: 12px;
            max-height: 50vh; overflow-y: auto; padding: 8px;
            background: var(--card-dark); border-radius: 12px; border: 1px solid var(--border);
        }

        .chat-bubble {
            padding: 12px 16px; border-radius: 14px; font-size: 0.95rem; line-height: 1.8;
            max-width: 90%; white-space: pre-wrap; word-break: break-word;
        }
        .user-bubble {
            background: var(--primary); color: white; align-self: flex-start; border-bottom-right-radius: 4px;
        }
        .ai-bubble {
            background: #17223b; color: #e2e8f0; align-self: flex-end; border-bottom-left-radius: 4px; border: 1px solid var(--border);
        }
        .out-of-scope-bubble {
            background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger);
            color: #fca5a5; font-weight: 800; text-align: center; align-self: center; width: 100%; border-radius: 12px;
        }

        .input-group { display: flex; flex-direction: column; gap: 6px; }
        textarea {
            background: var(--card-dark); color: var(--text-light); border: 1px solid var(--border);
            padding: 12px; border-radius: 10px; font-family: 'Tajawal', sans-serif; font-size: 0.95rem;
            outline: none; resize: vertical; min-height: 60px;
        }

        .image-preview-bar {
            display: none; align-items: center; justify-content: space-between;
            background: rgba(139, 92, 246, 0.15); border: 1px solid var(--accent-purple);
            padding: 8px 12px; border-radius: 10px; font-size: 0.85rem; color: #c4b5fd;
        }

        .btn-controls { display: grid; grid-template-columns: 1fr auto auto; gap: 8px; }

        .btn {
            background: var(--primary); color: white; border: none; padding: 12px; border-radius: 10px;
            font-family: 'Tajawal', sans-serif; font-weight: 700; font-size: 0.95rem; cursor: pointer;
            display: flex; align-items: center; justify-content: center; gap: 8px; text-decoration: none;
        }
        .btn-purple { background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%); }
        .btn-green { background: var(--accent-green); color: #042f2e; }

        input[type="file"] { display: none; }

        .doc-item {
            background: var(--card-dark); border-radius: 12px; padding: 12px; border: 1px solid var(--border);
            display: flex; flex-direction: column; gap: 8px;
        }
        .doc-header { display: flex; justify-content: space-between; align-items: center; }
        .doc-title { font-weight: 700; font-size: 0.9rem; color: #a5b4fc; }
        .btn-del {
            background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3);
            padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; cursor: pointer;
        }
        .doc-body {
            font-size: 0.85rem; color: #cbd5e1; line-height: 1.5; max-height: 100px; overflow-y: auto;
            background: rgba(0,0,0,0.2); padding: 8px; border-radius: 6px; white-space: pre-wrap;
        }

        .spinner { text-align: center; color: #a5b4fc; font-weight: 700; padding: 10px; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    </style>
</head>
<body>

    <header class="app-header">
        <h1 class="app-title">🎓 المساعد الذكي (صور ونصوص)</h1>
        <span style="font-size: 0.8rem; color: var(--accent-green);" id="docCountBadge">0 وثائق محللة</span>
    </header>

    <div class="tab-bar">
        <button class="tab-btn active" id="btnAskTab" onclick="switchTab('askTab', this)">💬 المحادثة المستمرة</button>
        <button class="tab-btn" id="btnDocsTab" onclick="switchTab('docsTab', this)">📄 وثائق الدروس</button>
    </div>

    <!-- TAB 1: Chat Feed -->
    <div class="tab-section active" id="askTab">
        <div class="chat-feed" id="chatFeed">
            <div style="color: var(--text-dim); font-style: italic; text-align: center; padding: 15px;">
                مرحباً بك! ارفع وثائق دروسك، ثم صور أي تمرين أو اكتب سؤالك هنا ليجيبك النظام بدقة.
            </div>
        </div>

        <div class="card">
            <div class="image-preview-bar" id="questionImgPreview">
                <span>📷 تم إرفاق صورة مع السؤال</span>
                <span style="cursor: pointer; color: var(--danger); font-weight: bold;" onclick="removeQuestionImage()">✕ إلغاء</span>
            </div>

            <div class="input-group">
                <textarea id="userQuery" placeholder="اكتب سؤالك هنا أو ارفق صورة التمرين..."></textarea>
            </div>
            
            <div class="btn-controls">
                <button class="btn btn-green" onclick="submitQuestion()">🚀 إرسال</button>
                <label for="qFileInputCamera" class="btn btn-purple" style="padding: 12px 14px; margin: 0;" title="كاميرا مباشرة">
                    <span>📸</span>
                </label>
                <input type="file" id="qFileInputCamera" accept="image/*" capture="environment">

                <label for="qFileInputGallery" class="btn btn-purple" style="padding: 12px 14px; margin: 0;" title="رفع من المعرض">
                    <span>🖼️</span>
                </label>
                <input type="file" id="qFileInputGallery" accept="image/*">
            </div>
        </div>
    </div>

    <!-- TAB 2: Curriculum Documents Section -->
    <div class="tab-section" id="docsTab">
        <div class="card">
            <span style="font-weight: 700; font-size: 1rem; color: #a5b4fc;">➕ رفع وثيقة درس جديد</span>
            <p style="font-size: 0.8rem; color: var(--text-dim); margin: 0;">اختر التصوير المباشر لصفحة الدرس أو رفعها من المعرض:</p>
            
            <div style="display: flex; gap: 8px;">
                <label for="docFileInputCamera" class="btn btn-purple" style="flex: 1; text-align: center; margin:0;">
                    <span>📸 تصوير مباشر</span>
                </label>
                <input type="file" id="docFileInputCamera" accept="image/*" capture="environment">

                <label for="docFileInputGallery" class="btn btn-purple" style="flex: 1; text-align: center; margin:0;">
                    <span>🖼️ المعرض</span>
                </label>
                <input type="file" id="docFileInputGallery" accept="image/*">
            </div>
            
            <div id="uploadStatus" style="font-size: 0.85rem; text-align: center; min-height: 20px; margin-top: 10px;"></div>
        </div>

        <div class="card">
            <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-dim);">الوثائق والأفكار المستخرجة الخاصة بك:</span>
            <div id="docsList" style="display: flex; flex-direction: column; gap: 10px;"></div>
        </div>
    </div>

    <script>
        let curriculumDocs = [];
        let attachedQuestionBase64 = null;

        fetchDocs();

        function switchTab(tabId, btnElement) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
            if(btnElement) btnElement.classList.add('active');
            const targetSection = document.getElementById(tabId);
            if(targetSection) targetSection.classList.add('active');
        }

        function fetchDocs() {
            fetch('/api/docs').then(res => res.json()).then(data => {
                curriculumDocs = data; renderDocs();
            }).catch(err => console.error("تعذر جلب الوثائق:", err));
        }

        function renderDocs() {
            const listDiv = document.getElementById('docsList');
            const countBadge = document.getElementById('docCountBadge');
            if(countBadge) countBadge.textContent = curriculumDocs.length + ' وثائق محللة';
            if (!listDiv) return;

            if (curriculumDocs.length === 0) {
                listDiv.innerHTML = '<div style="color: var(--text-dim); font-style: italic; text-align: center; padding: 10px;">لم تضف أي وثائق دروس بعد. ارفع صورة درسك الأول!</div>';
                return;
            }

            listDiv.innerHTML = curriculumDocs.map((item, index) => `
                <div class="doc-item">
                    <div class="doc-header">
                        <span class="doc-title">📖 وثيقة درس رقم ${index + 1}</span>
                        <button class="btn-del" onclick="deleteDoc(${index})">حذف</button>
                    </div>
                    <div class="doc-body">${item.concepts}</div>
                </div>
            `).join('');
        }

        // دالة موحدة لقراءة صور الأسئلة
        function handleQuestionImageSelect(e) {
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

        function removeQuestionImage() {
            attachedQuestionBase64 = null;
            const preview = document.getElementById('questionImgPreview');
            if(preview) preview.style.display = 'none';
        }

        // دالة موحدة لقراءة صور الدروس
        function handleDocImageSelect(e) {
            const file = e.target.files[0];
            if (!file) return;
            const statusDiv = document.getElementById('uploadStatus');
            if(statusDiv) {
                statusDiv.textContent = '⚡ جاري قراءة وتفريغ صورة الدرس...';
                statusDiv.style.color = '#89b4fa';
            }
            const reader = new FileReader();
            reader.onload = function(evt) { uploadDocImage(evt.target.result); };
            reader.readAsDataURL(file);
            e.target.value = '';
        }

        document.getElementById('docFileInputCamera').addEventListener('change', handleDocImageSelect);
        document.getElementById('docFileInputGallery').addEventListener('change', handleDocImageSelect);

        function uploadDocImage(base64Data) {
            fetch('/api/docs/upload', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: base64Data })
            })
            .then(res => res.json())
            .then(data => {
                const statusDiv = document.getElementById('uploadStatus');
                if (data.error) {
                    if(statusDiv) { statusDiv.textContent = '❌ خطأ: ' + data.error; statusDiv.style.color = '#f38ba8'; }
                } else {
                    if(statusDiv) { statusDiv.textContent = '✓ تم قراءة الوثيقة وحفظها بنجاح!'; statusDiv.style.color = '#a6e3a1'; }
                    curriculumDocs = data.docs; renderDocs();
                }
            }).catch(err => {
                const statusDiv = document.getElementById('uploadStatus');
                if(statusDiv) statusDiv.textContent = '❌ تعذر الاتصال بالسيرفر.';
            });
        }

        function deleteDoc(index) {
            fetch('/api/docs/delete', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index: index })
            }).then(res => res.json()).then(data => { curriculumDocs = data; renderDocs(); });
        }

        function submitQuestion() {
            const queryInput = document.getElementById('userQuery');
            const query = queryInput.value.trim();
            const chatFeed = document.getElementById('chatFeed');

            if (!query && !attachedQuestionBase64) { alert('يرجى كتابة سؤالك أو إرفاق صورة أولاً!'); return; }
            if (curriculumDocs.length === 0) { alert('يرجى تصوير أو رفع وثائق دروسك أولاً!'); return; }

            let userTextDisplay = query;
            if (attachedQuestionBase64) { userTextDisplay = (query ? query + '\\n' : '') + '[📷 صورة مرفقة للسؤال]'; }

            const userBubble = document.createElement('div');
            userBubble.className = 'chat-bubble user-bubble';
            userBubble.textContent = '👤 ' + userTextDisplay;
            chatFeed.appendChild(userBubble);

            const loadingBubble = document.createElement('div');
            loadingBubble.className = 'chat-bubble ai-bubble spinner';
            loadingBubble.textContent = '🧠 جاري التفكير والتحليل عبر Qwen3...';
            chatFeed.appendChild(loadingBubble);

            const payload = { query: query, image: attachedQuestionBase64 };
            queryInput.value = ''; removeQuestionImage(); chatFeed.scrollTop = chatFeed.scrollHeight;

            fetch('/api/ask', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(data => {
                chatFeed.removeChild(loadingBubble);
                const aiBubble = document.createElement('div');

                if (data.status === 'out_of_scope') {
                    aiBubble.className = 'chat-bubble out-of-scope-bubble';
                    aiBubble.textContent = '⚠️ عذراً، هذا غير مدرج في برنامجك الدراسي';
                } else if (data.status === 'success') {
                    aiBubble.className = 'chat-bubble ai-bubble';
                    aiBubble.textContent = data.answer;
                    
                    if (window.MathJax && window.MathJax.typesetPromise) {
                        window.MathJax.typesetPromise([aiBubble]).catch((err) => console.log(err));
                    }
                } else {
                    aiBubble.className = 'chat-bubble ai-bubble';
                    aiBubble.textContent = 'حدث خطأ: ' + (data.error || 'تعذر الإجابة.');
                }
                chatFeed.appendChild(aiBubble); chatFeed.scrollTop = chatFeed.scrollHeight;
            }).catch(err => {
                chatFeed.removeChild(loadingBubble);
                const errBubble = document.createElement('div');
                errBubble.className = 'chat-bubble ai-bubble';
                errBubble.textContent = '❌ تعذر الاتصال بالسيرفر.';
                chatFeed.appendChild(errBubble); chatFeed.scrollTop = chatFeed.scrollHeight;
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
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
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
            docs = load_curriculum(session_id)
            index = req_json.get("index")
            if index is not None and 0 <= index < len(docs):
                doc_to_delete = docs[index]
                delete_document_from_db(session_id, doc_to_delete["id"])
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
                f"- لا تستخدم أبداً النجمات ** للخط العريض لأنها لن تظهر بشكل صحيح. رتب الخطوات باستخدام الأرقام والأسطر الجديدة.\n"
                f"- لا تستخدم أبداً الأقواس المربعة \\[ أو \\] أو الأقواس الدائرية \\( أو \\) لتمثيل المعادلات.\n"
                f"- لكتابة المتغيرات الرياضية والرموز داخل النص: يجب استخدام رمز الدولار المفرد حصراً، مثال: $x=2$ أو $v$.\n"
                f"- لكتابة المعادلات الطويلة والمصفوفات والكسور: يجب كتابتها في سطر جديد ومستقل واستخدام رمز الدولار المزدوج حصراً، مثال:\n"
                f"$$ \\vec{{u}} = \\sqrt{{x^2 + y^2}} $$"
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
