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
        .history-item-content { display: flex; align-items: center; gap
