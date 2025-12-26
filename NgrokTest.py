from flask import Flask, render_template_string, request, jsonify, make_response, session, redirect
import os
import base64
import json
from openai import OpenAI
from datetime import datetime
import threading

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Enable sessions for login persistence
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
from flask_session import Session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/tmp/flask_sessions'
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
Session(app)

# Define log file path - will be created automatically
LOG_FILE = '/tmp/login_logs.json'

# ============ NGROK FIX ============
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ============ HTML TEMPLATES ============
LOGIN_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Math OCR Analyzer - Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        body { background: #ffffff; min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
        .login-container { width: 100%; max-width: 400px; background: #ffffff; border-radius: 12px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08); padding: 40px; text-align: center; }
        .login-header { margin-bottom: 30px; }
        .login-header h1 { font-size: 24px; font-weight: 700; color: #1f2937; margin-bottom: 8px; }
        .login-header p { color: #6b7280; font-size: 14px; }
        .login-form { display: flex; flex-direction: column; gap: 16px; margin-bottom: 24px; }
        .input-group { position: relative; text-align: left; }
        .input-group label { display: block; margin-bottom: 6px; color: #374151; font-size: 14px; font-weight: 500; }
        .input-group input { width: 100%; padding: 12px 16px 12px 40px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; transition: border 0.2s; }
        .input-group input:focus { outline: none; border-color: #667eea; }
        .input-group i { position: absolute; left: 12px; top: 36px; color: #9ca3af; font-size: 16px; }
        .login-buttons { display: flex; flex-direction: column; gap: 12px; }
        .btn { padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .btn-google { background: #ffffff; color: #374151; border: 1px solid #d1d5db; }
        .btn-google:hover { background: #f9fafb; }
        .btn-apple { background: #000000; color: #ffffff; }
        .btn-apple:hover { background: #1f2937; }
        .login-submit { background: #667eea; color: white; margin-top: 10px; }
        .login-submit:hover { background: #5a6cd4; }
        .toggle-container { margin-top: 20px; text-align: center; }
        .toggle { display: inline-flex; align-items: center; gap: 8px; color: #6b7280; font-size: 14px; }
        .toggle-switch { width: 40px; height: 20px; background: #e5e7eb; border-radius: 10px; position: relative; cursor: pointer; transition: background 0.2s; }
        .toggle-switch.active { background: #10b981; }
        .toggle-switch::after { content: ''; width: 16px; height: 16px; background: #ffffff; border-radius: 50%; position: absolute; top: 2px; left: 2px; transition: transform 0.2s; }
        .toggle-switch.active::after { transform: translateX(20px); }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>📐 Math.AI Analyzer</h1>
            <p>Log in to analyze your math problems</p>
        </div>
        <form class="login-form" onsubmit="event.preventDefault(); loginWithCredentials();">
            <div class="input-group">
                <label for="email">Email</label>
                <i>👤</i>
                <input type="email" id="email" placeholder="student@example.com" required>
            </div>
            <div class="input-group">
                <label for="password">Password</label>
                <i>🔒</i>
                <input type="password" id="password" placeholder="••••••••" required>
            </div>
            <button type="submit" class="btn login-submit">Login</button>
        </form>
        <div style="margin: 15px 0; text-align: center; color: #6b7280; font-size: 14px;">OR</div>
        <div class="login-buttons">
            <button class="btn btn-google" onclick="handleSocialLogin('Google')">
                <span>G</span> Continue with Google
            </button>
            <button class="btn btn-apple" onclick="handleSocialLogin('Apple')" id="appleBtn" style="display: none;">
                <span>🍎</span> Continue with Apple
            </button>
        </div>
        <div class="toggle-container">
            <span class="toggle">
                Enable Apple Login
                <div class="toggle-switch" id="appleToggle"></div>
            </span>
        </div>
    </div>
    <script>
        const appleToggle = document.getElementById('appleToggle');
        const appleBtn = document.getElementById('appleBtn');
        appleToggle.addEventListener('click', () => {
            appleToggle.classList.toggle('active');
            appleBtn.style.display = appleToggle.classList.contains('active') ? 'flex' : 'none';
        });
        function loginWithCredentials() {
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            if (!email) { alert('Please enter an email'); return; }
            fetch('/api/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ username: email, password: password }) })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    localStorage.setItem('userEmailPrefix', email.split('@')[0]);
                    window.location.href = '/main';
                } else {
                    alert('Login failed: ' + data.message);
                }
            });
        }
        function handleSocialLogin(provider) {
            const email = document.getElementById('email').value || `${provider.toLowerCase()}_user@example.com`;
            fetch('/api/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: email, provider: provider.toLowerCase()}) })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    localStorage.setItem('userEmailPrefix', email.split('@')[0]);
                    window.location.href = '/main';
                }
            });
        }
    </script>
</body>
</html>'''

MAIN_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Math.AI Analyzer - CAS Educations</title>
    <script>
        window.MathJax = {
            tex: {
                inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
                processEscapes: true,
                processEnvironments: true
            },
            options: {
                skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
            },
            startup: {
                pageReady: () => { return MathJax.startup.defaultPageReady(); }
            }
        };
    </script>
    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --background: #fcfcfc;
            --foreground: #2e2e2e;
            --card: #ffffff;
            --card-foreground: #2e2e2e;
            --primary: #4f7cff;
            --primary-foreground: #ffffff;
            --secondary: #f5f5f7;
            --secondary-foreground: #404040;
            --muted: #f5f5f7;
            --muted-foreground: #808080;
            --accent: #f0f2ff;
            --accent-foreground: #404040;
            --destructive: #ef4444;
            --destructive-foreground: #ffffff;
            --border: #e5e5e8;
            --input: #e5e5e8;
            --ring: #4f7cff;
            --sidebar: #fafafa;
            --sidebar-foreground: #404040;
            --sidebar-accent: #f0f2ff;
            --sidebar-border: #ebebed;
            --radius: 0.75rem;
        }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif; background-color: var(--background); color: var(--foreground); line-height: 1.6; padding: 0; overflow: hidden; }
        .dashboard-container { display: flex; height: 100vh; width: 100%; overflow: hidden; }
        .dashboard-layout { display: flex; height: 100%; width: 100%; }
        .sidebar { width: 16rem; background-color: var(--sidebar); border-right: 1px solid var(--sidebar-border); display: flex; flex-direction: column; height: 100%; }
        .sidebar-header { padding: 1.5rem; border-bottom: 1px solid var(--sidebar-border); }
        .sidebar-logo { display: flex; align-items: center; gap: 0.75rem; cursor: pointer; }
        .sidebar-logo:hover { opacity: 0.8; }
        .sidebar-logo-icon { width: 2.5rem; height: 2.5rem; background-color: var(--primary); border-radius: 0.75rem; display: flex; align-items: center; justify-content: center; }
        .sidebar-logo-icon svg { width: 1.5rem; height: 1.5rem; color: var(--primary-foreground); }
        .sidebar-logo h1 { font-size: 1.25rem; font-weight: 700; }
        .sidebar-content { flex: 1; overflow-y: auto; padding: 1rem; }
        .sidebar-section-title { font-size: 0.75rem; font-weight: 600; color: rgba(64, 64, 64, 0.6); text-transform: uppercase; letter-spacing: 0.05em; padding: 0 0.75rem; margin-bottom: 0.75rem; }
        .sidebar-item { padding: 0.75rem; border-radius: calc(var(--radius) - 0.25rem); cursor: pointer; transition: background-color 0.2s; margin-bottom: 0.5rem; }
        .sidebar-item:hover { background-color: var(--sidebar-accent); }
        .sidebar-item-title { font-weight: 500; font-size: 0.875rem; margin-bottom: 0.125rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .sidebar-item-date { font-size: 0.75rem; color: rgba(64, 64, 64, 0.6); }
        .main-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
        .header { border-bottom: 1px solid var(--border); background-color: var(--card); padding: 1rem 1.5rem; display: flex; align-items: center; justify-content: space-between; width: 100%; }
        .header-left { display: flex; align-items: center; gap: 1rem; }
        .header-logo { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }
        .header-logo:hover { opacity: 0.8; }
        .header-logo-icon { width: 2rem; height: 2rem; background-color: var(--primary); border-radius: 0.5rem; display: flex; align-items: center; justify-content: center; }
        .header-logo-icon svg { width: 1.25rem; height: 1.25rem; color: var(--primary-foreground); }
        .header-brand { font-weight: 700; font-size: 1.125rem; }
        .header-right { display: flex; align-items: center; gap: 1rem; }
        .user-info { font-size: 0.875rem; font-weight: 500; }
        .user-name { color: var(--primary); }
        .btn-logout { background-color: transparent; color: var(--foreground); padding: 0.5rem 1rem; }
        .btn-logout:hover { background-color: var(--accent); }
        .content-area { flex: 1; overflow-y: auto; padding: 1.5rem; width: 100%; }
        .upload-section { max-width: 80rem; margin: 0 auto; width: 100%; }
        .section-header { margin-bottom: 2rem; }
        .section-header h1 { font-size: 2.25rem; font-weight: 700; margin-bottom: 0.5rem; }
        .section-header p { font-size: 1.125rem; color: var(--muted-foreground); }
        .upload-grid { display: flex; justify-content: center; gap: 1.5rem; margin-bottom: 2rem; flex-wrap: wrap; }
        .upload-card { background-color: var(--card); border: 2px dashed var(--border); border-radius: var(--radius); padding: 1.5rem; text-align: center; transition: border-color 0.2s; cursor: pointer; max-width: 20rem; width: 100%; }
        .upload-card:hover { border-color: rgba(79, 124, 255, 0.5); }
        .upload-icon { width: 4rem; height: 4rem; background-color: rgba(79, 124, 255, 0.1); border-radius: 1rem; display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem; }
        .upload-icon svg { width: 2rem; height: 2rem; color: var(--primary); }
        .upload-card h3 { font-weight: 600; margin-bottom: 0.5rem; }
        .upload-card p { font-size: 0.875rem; color: var(--muted-foreground); margin-bottom: 1rem; }
        .file-list { text-align: left; margin-top: 1rem; }
        .file-item { display: flex; align-items: center; gap: 0.5rem; font-size: 0.75rem; color: var(--muted-foreground); margin-bottom: 0.25rem; }
        .file-item svg { width: 0.75rem; height: 0.75rem; }
        .btn-start { background-color: var(--primary); color: var(--primary-foreground); padding: 0.75rem 3rem; font-size: 1rem; margin: 0 auto; display: flex; }
        .btn-start:disabled { opacity: 0.5; cursor: not-allowed; }
        .results-section { max-width: 80rem; margin: 0 auto; width: 100%; }
        .results-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem; }
        .results-header h1 { font-size: 1.875rem; font-weight: 700; }
        .results-header p { color: var(--muted-foreground); margin-top: 0.25rem; }
        .badge-group { display: flex; gap: 0.5rem; flex-wrap: wrap; }
        .badge { padding: 0.25rem 0.75rem; border-radius: calc(var(--radius) - 0.25rem); font-size: 0.875rem; background-color: var(--secondary); display: inline-flex; align-items: center; gap: 0.5rem; }
        .badge-dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; }
        .badge-dot.correct { background-color: #22c55e; }
        .badge-dot.partial { background-color: #eab308; }
        .badge-dot.incorrect { background-color: #ef4444; }
        .accordion { display: flex; flex-direction: column; gap: 1rem; }
        .accordion-item { background-color: var(--card); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
        .accordion-trigger { width: 100%; padding: 1.5rem; display: flex; align-items: flex-start; gap: 1rem; cursor: pointer; background: none; border: none; text-align: left; transition: background-color 0.2s; }
        .accordion-trigger:hover { background-color: var(--accent); }
        .question-number { width: 2.5rem; height: 2.5rem; border-radius: 0.75rem; display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; }
        .question-number.correct { background-color: rgba(34, 197, 94, 0.1); color: #16a34a; }
        .question-number.partial { background-color: rgba(234, 179, 8, 0.1); color: #ca8a04; }
        .question-number.incorrect { background-color: rgba(239, 68, 68, 0.1); color: #dc2626; }
        .question-info { flex: 1; padding-top: 0.25rem; }
        .question-info p:first-child { font-weight: 600; margin-bottom: 0.25rem; }
        .question-info p:last-child { font-size: 0.875rem; color: var(--muted-foreground); text-transform: capitalize; }
        .accordion-content { display: none; padding: 0 1.5rem 1.5rem; }
        .accordion-content.open { display: block; }
        .analysis-section { margin-bottom: 1.5rem; }
        .analysis-section h3 { font-weight: 600; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem; }
        .analysis-section h3 svg { width: 1.25rem; height: 1.25rem; }
        .solution-card { background-color: rgba(245, 245, 247, 0.3); border: 1px solid var(--border); border-radius: var(--radius); padding: 1rem; }
        .solution-card.error { background-color: rgba(239, 68, 68, 0.05); border-color: rgba(239, 68, 68, 0.3); }
        .solution-card.corrected { background-color: rgba(34, 197, 94, 0.05); border-color: rgba(34, 197, 94, 0.3); }
        .solution-steps { font-family: 'Courier New', monospace; font-size: 0.875rem; }
        .solution-steps div { margin-bottom: 0.5rem; }
        .practice-paper-card { background-color: var(--card); border: 2px solid rgba(79, 124, 255, 0.2); border-radius: var(--radius); padding: 1.5rem; margin-top: 1.5rem; }
        .practice-paper-card h3 { font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; }
        .practice-paper-card p { color: var(--muted-foreground); margin-bottom: 1rem; }
        .new-question-list { background-color: var(--background); border-radius: calc(var(--radius) - 0.25rem); padding: 1rem; margin-bottom: 1rem; }
        .new-question-item { display: flex; align-items: flex-start; gap: 0.75rem; margin-bottom: 0.75rem; }
        .new-question-item:last-child { margin-bottom: 0; }
        .new-question-number { width: 2rem; height: 2rem; border-radius: 0.5rem; display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; }
        .reanalysis-card { background-color: rgba(240, 242, 255, 0.5); border: 1px solid var(--border); border-radius: var(--radius); padding: 1rem; margin-top: 1rem; }
        .reanalysis-input-group { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
        .reanalysis-input-group input { flex: 1; }
        .ai-response { background-color: var(--background); border: 1px solid var(--border); border-radius: calc(var(--radius) - 0.25rem); padding: 1rem; display: flex; align-items: flex-start; gap: 0.75rem; }
        .ai-badge { background-color: var(--primary); color: var(--primary-foreground); padding: 0.125rem 0.5rem; border-radius: calc(var(--radius) - 0.5rem); font-size: 0.75rem; font-weight: 600; flex-shrink: 0; margin-top: 0.125rem; }
        .ai-response p { font-size: 0.875rem; line-height: 1.6; flex: 1; }
        .modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(0, 0, 0, 0.5); z-index: 50; align-items: center; justify-content: center; padding: 1rem; }
        .modal.open { display: flex; }
        .modal-content { background-color: var(--card); border-radius: var(--radius); max-width: 48rem; width: 100%; max-height: 90vh; overflow-y: auto; padding: 1.5rem; }
        .modal-header { margin-bottom: 1rem; }
        .modal-header h3 { font-size: 1.25rem; font-weight: 600; }
        .modal-image { position: relative; aspect-ratio: 3/4; background-color: var(--muted); border-radius: calc(var(--radius) - 0.25rem); overflow: hidden; margin-bottom: 1rem; }
        .modal-image img { width: 100%; height: 100%; object-fit: cover; }
        .error-highlight { position: absolute; border: 4px solid #ef4444; border-radius: 0.5rem; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .modal-caption { text-align: center; font-size: 0.875rem; color: var(--muted-foreground); }
        .mobile-menu-btn { display: none; }
        .mobile-overlay { display: none; }
        @media (max-width: 1024px) {
            .sidebar { display: none; }
            .mobile-menu-btn { display: flex; background: transparent; border: none; padding: 0.5rem; cursor: pointer; }
            .mobile-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 40; }
            .mobile-overlay.open { display: block; }
            .mobile-sidebar-backdrop { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(0, 0, 0, 0.5); }
            .mobile-sidebar { position: absolute; top: 0; left: 0; bottom: 0; width: 16rem; background-color: var(--sidebar); }
            .mobile-logout { position: absolute; bottom: 0; left: 0; right: 0; padding: 1rem; border-top: 1px solid var(--sidebar-border); }
            .mobile-logout button { width: 100%; justify-content: flex-start; background: transparent; color: var(--sidebar-foreground); padding: 0.75rem; }
            .btn-logout { display: none; }
            .header-brand { display: none; }
        }
        @media (max-width: 640px) {
            .user-info { display: none; }
            .upload-grid { flex-direction: column; align-items: center; }
            .results-header { flex-direction: column; align-items: flex-start; }
        }
        .hidden { display: none; }
        .btn, button { padding: 0.625rem 1.5rem; border-radius: calc(var(--radius) - 0.25rem); font-weight: 500; font-size: 0.875rem; cursor: pointer; transition: all 0.2s; border: none; display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; }
        .btn-primary { background-color: var(--primary); color: var(--primary-foreground); }
        .btn-primary:hover { opacity: 0.9; }
        .btn-outline { background-color: transparent; border: 1px solid var(--border); color: var(--foreground); }
        .btn-outline:hover { background-color: var(--accent); }
        .loading { display: inline-block; width: 20px; height: 20px; border: 3px solid #f3f4f6; border-top-color: #4f7cff; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        /* Practice paper for PDF */
        .practice-paper { padding: 30px; background: white; }
        .practice-header { margin-bottom: 30px; text-align: center; }
        .practice-title { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
        .practice-subtitle { font-size: 16px; color: #666; }
        .practice-question { margin-bottom: 30px; }
        .practice-question-number { font-size: 18px; font-weight: 700; color: var(--primary); margin-bottom: 10px; }
    </style>
</head>
<body>
    <div id="dashboardPage" class="dashboard-container">
        <div class="dashboard-layout">
            <!-- Sidebar (Desktop) -->
            <aside class="sidebar">
                <div class="sidebar-header">
                    <div class="sidebar-logo" onclick="resetToDashboard()">
                        <div class="sidebar-logo-icon">
                            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
                            </svg>
                        </div>
                        <h1>Math.AI Analyzer</h1>
                    </div>
                </div>
                <div class="sidebar-content">
                    <div class="sidebar-section-title">Analysis History</div>
                    <div id="historyList"></div>
                </div>
            </aside>
            <!-- Mobile Overlay -->
            <div id="mobileOverlay" class="mobile-overlay">
                <div class="mobile-sidebar-backdrop" onclick="closeMobileMenu()"></div>
                <aside class="mobile-sidebar">
                    <div class="sidebar-header">
                        <div class="sidebar-logo" onclick="resetToDashboard(); closeMobileMenu();">
                            <div class="sidebar-logo-icon">
                                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
                                </svg>
                            </div>
                            <h1>Math.AI Analyzer</h1>
                        </div>
                    </div>
                    <div class="sidebar-content">
                        <div class="sidebar-section-title">Analysis History</div>
                        <div id="mobileHistoryList"></div>
                    </div>
                    <div class="mobile-logout">
                        <button onclick="handleLogout()">
                            <svg style="width: 1rem; height: 1rem; margin-right: 0.5rem;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
                            </svg>
                            Logout
                        </button>
                    </div>
                </aside>
            </div>
            <!-- Main Content -->
            <div class="main-content">
                <header class="header">
                    <div class="header-left">
                        <button class="mobile-menu-btn" onclick="openMobileMenu()">
                            <svg style="width: 1.25rem; height: 1.25rem;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
                            </svg>
                        </button>
                        <div class="header-logo" onclick="resetToDashboard()">
                            <div class="header-logo-icon">
                                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
                                </svg>
                            </div>
                            <span class="header-brand">CAS Educations</span>
                        </div>
                    </div>
                    <div class="header-right">
                        <p class="user-info">Welcome, <span class="user-name" id="userName"></span></p>
                        <button class="btn-logout" onclick="handleLogout()">
                            <svg style="width: 1rem; height: 1rem;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
                            </svg>
                            Logout
                        </button>
                    </div>
                </header>
                <main class="content-area">
                    <!-- Upload Section -->
                    <div id="uploadSection" class="upload-section">
                        <div class="section-header">
                            <h1>Upload Answer Sheets for Analysis</h1>
                            <p>Upload question papers and student answer sheets to get AI-powered analysis</p>
                        </div>
                        <div class="upload-grid">
                            <div class="upload-card" onclick="document.getElementById('questionInput').click()">
                                <div class="upload-icon">
                                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                                    </svg>
                                </div>
                                <h3>Question Papers</h3>
                                <p>Upload the original question papers</p>
                                <input type="file" id="questionInput" multiple accept="image/*,.pdf" style="display:none;">
                                <button class="btn-outline">
                                    <svg style="width: 1rem; height: 1rem;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                                    </svg>
                                    Upload Files
                                </button>
                                <div id="questionFileList" class="file-list"></div>
                            </div>
                            <div class="upload-card" onclick="document.getElementById('answerInput').click()">
                                <div class="upload-icon">
                                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                                    </svg>
                                </div>
                                <h3>Student Answer Sheets</h3>
                                <p>Upload student's handwritten answers</p>
                                <input type="file" id="answerInput" multiple accept="image/*,.pdf" style="display:none;">
                                <button class="btn-outline">
                                    <svg style="width: 1rem; height: 1rem;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                                    </svg>
                                    Upload Files
                                </button>
                                <div id="answerFileList" class="file-list"></div>
                            </div>
                        </div>
                        <div style="display: flex; justify-content: center;">
                            <button id="startAnalysisBtn" class="btn-start" onclick="startAnalysis()" disabled>
                                <svg style="width: 1.25rem; height: 1.25rem;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                                </svg>
                                Start Analysis
                            </button>
                        </div>
                    </div>
                    <!-- Results Section -->
                    <div id="resultsSection" class="results-section hidden">
                        <div class="results-header">
                            <div>
                                <h1>Analysis Results</h1>
                                <p>AI-powered answer sheet analysis</p>
                            </div>
                            <div class="badge-group" id="badgeGroup"></div>
                        </div>
                        <div class="accordion" id="accordion"></div>
                        <!-- Practice Paper -->
                        <div class="practice-paper-card" id="practicePaperCard">
                            <h3>Generate Personalized Practice Paper</h3>
                            <p>Create a new question paper with modified questions for incorrect and partial answers</p>
                            <div id="practicePaperContent">
                                <button class="btn-start" onclick="generatePracticePaper()">
                                    <svg style="width: 1.25rem; height: 1.25rem;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                                    </svg>
                                    Generate New Question Paper
                                </button>
                            </div>
                        </div>
                    </div>
                </main>
            </div>
        </div>
    </div>
    <!-- Image Modal -->
    <div id="imageModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modalTitle">Answer Sheet - Question</h3>
            </div>
            <div class="modal-image">
                <img id="modalImage" src="" alt="Answer sheet">
                <div id="errorHighlight" class="error-highlight" style="display: none;"></div>
            </div>
            <p class="modal-caption" id="modalCaption"></p>
            <button class="btn-outline" style="width: 100%; margin-top: 1rem;" onclick="closeImageModal()">Close</button>
        </div>
    </div>
    <script>
        // State management
        let currentUser = localStorage.getItem('userEmailPrefix') || '';
        let questionFiles = [];
        let answerFiles = [];
        let allFiles = [];
        let analysisResult = null;
        let practiceResult = null;
        let history = [];
        let isAnalyzing = false;
        document.getElementById('userName').textContent = currentUser;

        function renderMath(element) {
            if (window.MathJax) {
                MathJax.typesetPromise([element]).catch(err => console.error('MathJax error:', err));
            }
        }

        // Mobile menu functions...
        function openMobileMenu() {
            document.getElementById('mobileOverlay').classList.add('open');
        }

        function closeMobileMenu() {
            document.getElementById('mobileOverlay').classList.remove('open');
        }

        function handleLogout() {
            localStorage.removeItem('userEmailPrefix');
            window.location.href = '/';
        }

        function resetToDashboard() {
            document.getElementById('uploadSection').classList.remove('hidden');
            document.getElementById('resultsSection').classList.add('hidden');
            closeMobileMenu();
        }

        // File handling (unchanged)...
        document.getElementById('questionInput').addEventListener('change', async e => {
            await handleFileUpload(e.target.files, questionFiles, 'questionFileList');
            checkStartButton();
        });

        document.getElementById('answerInput').addEventListener('change', async e => {
            await handleFileUpload(e.target.files, answerFiles, 'answerFileList');
            checkStartButton();
        });

        async function handleFileUpload(files, targetArray, listId) {
            for (let file of files) {
                if (!targetArray.find(f => f.name === file.name)) {
                    let dataURL = '';
                    if (file.type.startsWith('image/')) {
                        dataURL = await new Promise(resolve => {
                            const reader = new FileReader();
                            reader.onload = ev => resolve(ev.target.result);
                            reader.readAsDataURL(file);
                        });
                    }
                    targetArray.push({name: file.name, file: file, dataURL: dataURL});
                }
            }
            displayFiles(listId, targetArray);
        }

        function displayFiles(elementId, files) {
            const el = document.getElementById(elementId);
            el.innerHTML = files.map(f => `
                <div class="file-item">
                    <svg fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                    ${f.name}
                </div>
            `).join('');
        }

        function checkStartButton() {
            document.getElementById('startAnalysisBtn').disabled = questionFiles.length === 0 || answerFiles.length === 0;
        }

        async function startAnalysis() {
            if (isAnalyzing) return;
            isAnalyzing = true;
            const btn = document.getElementById('startAnalysisBtn');
            btn.innerHTML = '<div class="loading"></div> Analyzing...';
            btn.disabled = true;
            allFiles = [...questionFiles, ...answerFiles];
            const formData = new FormData();
            allFiles.forEach(f => formData.append('files', f.file));
            try {
                const res = await fetch('/analyze', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.error) alert(data.error);
                else {
                    analysisResult = data;
                    displayAnalysis(data);
                    addToHistory();
                    document.getElementById('uploadSection').classList.add('hidden');
                    document.getElementById('resultsSection').classList.remove('hidden');
                }
            } catch (e) {
                alert('Error: ' + e.message);
            } finally {
                isAnalyzing = false;
                btn.innerHTML = `<svg style="width: 1.25rem; height: 1.25rem;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg> Start Analysis`;
                btn.disabled = false;
            }
        }

        function processSteps(str) {
            if (!str) return '';
            // Split by <br> and create proper paragraph structure
            const steps = str.split('<br>').filter(step => step.trim() !== '');
            return steps.map(step => `<p style="margin-bottom: 0.75rem; line-height: 1.8;">${step.trim()}</p>`).join('');
        }

        function displayAnalysis(result) {
            const accordion = document.getElementById('accordion');
            accordion.innerHTML = '';
            let counts = {correct: 0, partial: 0, incorrect: 0};
            result.questions.forEach((q, i) => {
                counts[q.status]++;
                const item = document.createElement('div');
                item.className = 'accordion-item';
                item.innerHTML = `
                    <button class="accordion-trigger" onclick="toggleAccordion('q${i}')">
                        <div class="question-number ${q.status}">${q.number}</div>
                        <div class="question-info">
                            <p>${q.question}</p>
                            <p>Status: ${q.status}</p>
                        </div>
                    </button>
                    <div id="q${i}" class="accordion-content">
                        <div class="analysis-section">
                            <h3><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg> Student Solution</h3>
                            <div class="solution-card"><div class="solution-steps">${processSteps(q.student_original)}</div></div>
                        </div>
                        <div class="analysis-section">
                            <h3><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> Error Analysis</h3>
                            <div class="solution-card error"><p>${q.error}</p></div>
                        </div>
                        <div class="analysis-section">
                            <h3><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> LLM-Corrected Solution</h3>
                            <div class="solution-card corrected"><div class="solution-steps">${processSteps(q.correct_solution)}</div></div>
                        </div>
                        <button class="btn-outline" onclick="openImageModal(${i}, '${q.status}', '${q.image_file || ''}', ${JSON.stringify(q.error_bbox || {})})">
                            <svg style="width: 1rem; height: 1rem;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                            View Answer Image
                        </button>
                        <div class="reanalysis-card">
                            <h3 style="font-size: 1rem; font-weight: 600; margin-bottom: 0.75rem;">Re-analyze This Question</h3>
                            <div class="reanalysis-input-group">
                                <input type="text" id="reanalysisInput${i}" placeholder="Ask AI to re-analyze this question...">
                                <button class="btn-primary" style="width: auto;" onclick="reanalyzeQuestion(${i})">Send</button>
                            </div>
                            <div id="aiResponse${i}" style="display: none;" class="ai-response">
                                <div class="ai-badge">AI</div>
                                <p></p>
                            </div>
                        </div>
                    </div>`;
                accordion.appendChild(item);
                renderMath(item);
            });
            document.getElementById('badgeGroup').innerHTML = `
                <div class="badge"><div class="badge-dot correct"></div>${counts.correct} Correct</div>
                <div class="badge"><div class="badge-dot partial"></div>${counts.partial} Partial</div>
                <div class="badge"><div class="badge-dot incorrect"></div>${counts.incorrect} Incorrect</div>
            `;
        }

        function toggleAccordion(id) {
            document.getElementById(id).classList.toggle('open');
        }

        // reanalyzeQuestion, openImageModal, closeImageModal unchanged...
        async function generatePracticePaper() {
            if (!analysisResult) return;
            const content = document.getElementById('practicePaperContent');
            content.innerHTML = '<div class="loading"></div> Generating...';
            try {
                const res = await fetch('/generate_practice', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({analysis: analysisResult}) });
                const data = await res.json();
                if (data.error) {
                    content.innerHTML = `<p>Error: ${data.error}</p>`;
                } else if (data.practice_questions.length === 0) {
                    content.innerHTML = '<p>No mistakes found, no practice needed!</p>';
                } else {
                    practiceResult = data;
                    content.innerHTML = `
                        <div class="practice-paper" id="practice-paper">
                            <div class="practice-header">
                                <div class="practice-title">📝 Practice Paper</div>
                                <div class="practice-subtitle">Practice questions based on areas needing improvement</div>
                            </div>
                            <div class="practice-questions">
                                ${data.practice_questions.map(pq => `
                                    <div class="practice-question">
                                        <div class="practice-question-number">Question ${pq.number}</div>
                                        <div class="practice-question-text">${pq.question}</div>
                                    </div>
                                `).join('')}
                            </div>
                            <div style="text-align:center; margin-top:40px;">
                                <button class="btn-outline" onclick="downloadPracticePaper()"> 📥 Download as PDF </button>
                            </div>
                        </div>`;
                    // Render MathJax once after inserting the content
                    renderMath(document.getElementById('practice-paper'));
                }
            } catch (e) {
                content.innerHTML = `<p>Error: ${e.message}</p>`;
            }
        }

        async function downloadPracticePaper() {
    if (!practiceResult) return;
    const practicePaper = document.getElementById('practice-paper');
    if (!practicePaper) {
        alert('Practice paper not found!');
        return;
    }
    const loading = document.createElement('div');
    loading.innerHTML = '<div class="loading"></div> Generating PDF...';
    Object.assign(loading.style, {
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        background: 'rgba(255,255,255,0.9)',
        padding: '20px',
        borderRadius: '10px',
        zIndex: '9999'
    });
    document.body.appendChild(loading);
    try {
        // Wait a bit for any pending MathJax to complete
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const canvas = await html2canvas(practicePaper, {
            scale: 2,
            useCORS: true,
            backgroundColor: '#ffffff',
            logging: false,
            windowWidth: practicePaper.scrollWidth + 60,
            windowHeight: practicePaper.scrollHeight + 60,
            ignoreElements: function(element) {
                // Ignore MathJax processing elements
                return element.classList && (
                    element.classList.contains('MathJax_Processing') ||
                    element.classList.contains('MathJax_Processed')
                );
            }
        });
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF('p', 'mm', 'a4');
        const imgData = canvas.toDataURL('image/png');
        const imgWidth = pdf.internal.pageSize.getWidth();
        const imgHeight = (canvas.height * imgWidth) / canvas.width;
        pdf.addImage(imgData, 'PNG', 0, 0, imgWidth, imgHeight);
        pdf.save(`Math_Practice_Paper_${new Date().toISOString().slice(0,10)}.pdf`);
    } catch (error) {
        console.error('PDF generation failed:', error);
        alert('Failed to generate PDF. Please try again.');
    } finally {
        document.body.removeChild(loading);
    }
}

        // addToHistory and updateHistory unchanged...
        function addToHistory() {
            const title = `Analysis - ${new Date().toLocaleDateString()}`;
            history.push({title, date: new Date().toLocaleDateString()});
            updateHistory();
        }

        function updateHistory() {
            const html = history.map(h => `
                <div class="sidebar-item">
                    <div class="sidebar-item-title">${h.title}</div>
                    <div class="sidebar-item-date">${h.date}</div>
                </div>
            `).join('');
            document.getElementById('historyList').innerHTML = html;
            document.getElementById('mobileHistoryList').innerHTML = html;
        }
    </script>
</body>
</html>'''

# ============ ROUTES ============
@app.route('/')
def index():
    return render_template_string(LOGIN_HTML)

@app.route('/main')
def main():
    if not session.get('logged_in'):
        return redirect('/')
    return render_template_string(MAIN_HTML)

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # CHANGED LINE - using environment variable
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured.'}), 500

        files = request.files.getlist('files')
        if not files:
            return jsonify({'error': 'No files uploaded'}), 400

        client = OpenAI(api_key=api_key)
        file_contents = []
        file_names = []
        for i, file in enumerate(files):
            file.seek(0)
            if file.content_type.startswith('image/'):
                encoded = base64.b64encode(file.read()).decode('utf-8')
                file_contents.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "high"}
                })
            else:
                file_contents.append({
                    "type": "text",
                    "text": f"[PDF file: {file.filename}]"
                })
            file_names.append(file.filename)

        prompt = f""" 
        Analyze the math problems in these files: {', '.join(file_names)}
        For each question you find:
        1. Extract the question number (use what's in the image)
        2. Write the question with math formatted using $ for inline math like $x^2$ and $$ for display math
        3. Copy the student's work exactly as written (use $ for their math too)
        4. Check if it's "correct", "partial", or "incorrect". Be balanced: 'correct' if fully right, 'partial' if mostly right but minor errors, 'incorrect' if major mistakes.
        5. Explain any errors you see
        6. Provide the correct solution with clear steps (separate steps with <br>)
        7. Note which image file this is from
        Ensure each unique question number appears only once, even if in multiple files. Deduplicate by question number.
        Return ONLY a JSON array (no extra text): 
        [{{
            "number": "1",
            "question": "Solve $2x + 5 = 15$",
            "student_original": "Student wrote: $2x = 10$ <br> $x = 5$",
            "status": "correct",
            "error": "No errors found",
            "correct_solution": "Subtract 5 from both sides: $2x = 10$ <br> Divide by 2: $x = 5$ <br> Answer: $x = 5$",
            "image_file": "{file_names[0] if file_names else 'image.jpg'}",
            "error_bbox": null
        }}]
        """

        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[{
                "role": "user",
                "content": [{"type": "text", "text": prompt}] + file_contents
            }],
            max_completion_tokens=9000,
            temperature=0.3
        )

        result_text = response.choices[0].message.content.strip()
        # Clean up the response
        result_text = result_text.replace('```json', '').replace('```', '').strip()
        # Find JSON array
        start = result_text.find('[')
        end = result_text.rfind(']')
        if start != -1 and end != -1:
            result_text = result_text[start:end + 1]

        try:
            questions = json.loads(result_text)
            # Deduplicate questions by number
            seen = set()
            unique_questions = []
            for q in questions:
                if q['number'] not in seen:
                    seen.add(q['number'])
                    unique_questions.append(q)
            print(f"✅ Parsed {len(unique_questions)} unique questions")
            return jsonify({'questions': unique_questions})
        except json.JSONDecodeError as e:
            print(f"JSON Error: {str(e)}")
            print(f"Response preview: {result_text[:500]}")
            return jsonify({'error': 'Could not understand AI response. Please try again.'}), 500
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/reanalyze', methods=['POST'])
def reanalyze():
    try:
        # CHANGED LINE - using environment variable
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured.'}), 500

        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        client = OpenAI(api_key=api_key)

        prompt = f"""
        Re-analyze this question based on user query: "{data['user_query']}"
        Original: Question: {data['question']}
        Student: {data['student_original']}
        Previous error: {data['error']}
        Previous correct: {data['correct_solution']}
        Provide updated:
        - status: "correct|partial|incorrect"
        - error: updated description
        - correct_solution: updated steps <br> separated
        - response: brief response to user query
        Format ALL with LaTeX $
        Return JSON: {{"status": "", "error": "", "correct_solution": "", "response": ""}}
        """

        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=2000,
            temperature=0.3
        )

        result_text = response.choices[0].message.content.strip()
        result_text = result_text.replace('```json', '').replace('```', '').strip()

        try:
            updated = json.loads(result_text)
            return jsonify(updated)
        except json.JSONDecodeError:
            return jsonify({'error': 'Parse error'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def handle_login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        if not username:
            return jsonify({'success': False, 'message': 'Username required'}), 400

        session['user'] = username
        session['logged_in'] = True
        session['login_time'] = datetime.utcnow().isoformat()

        ip_address = request.remote_addr or 'Unknown'
        user_agent = request.headers.get('User-Agent', 'Unknown')[:100]
        current_time = datetime.utcnow().isoformat()

        def save_login():
            login_data = {
                'username': username,
                'timestamp': current_time,
                'ip': ip_address,
                'user_agent': user_agent
            }
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r') as f:
                    logins = json.load(f)
            else:
                logins = []
            logins.append(login_data)
            with open(LOG_FILE, 'w') as f:
                json.dump(logins, f, indent=2)

        threading.Thread(target=save_login, daemon=True).start()

        return jsonify({'success': True, 'message': 'Login successful', 'user': username})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/view-logs')
def view_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            logins = json.load(f)
        html = '''
        <!DOCTYPE html>
        <html>
        <head><title>Login Logs</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background-color: #667eea; color: white; }
            tr:nth-child(even) { background-color: #f2f2f2; }
        </style>
        </head>
        <body>
            <h1>🔐 Login Logs (Total: ''' + str(len(logins)) + ''')</h1>
            <table>
                <tr><th>#</th><th>Username</th><th>Timestamp</th><th>IP Address</th><th>User Agent</th></tr>
        '''
        for i, login in enumerate(reversed(logins), 1):
            html += f'''
                <tr>
                    <td>{i}</td>
                    <td><strong>{login['username']}</strong></td>
                    <td>{login['timestamp']}</td>
                    <td>{login['ip']}</td>
                    <td>{login['user_agent'][:50]}...</td>
                </tr>
            '''
        html += '''
            </table>
            <p style="margin-top: 20px;">
                <a href="/download-logs">📥 Download JSON</a> | <a href="/">🏠 Back to Login</a>
            </p>
        </body>
        </html>
        '''
        return html
    return "<h1>No logins yet</h1>"

@app.route('/download-logs')
def download_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            data = f.read()
        response = make_response(data)
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = 'attachment; filename=math_ocr_logins.json'
        return response
    return "No logins yet", 404

@app.route('/generate_practice', methods=['POST'])
def generate_practice():
    try:
        # CHANGED LINE - using environment variable
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured.'}), 500

        data = request.json
        if not data or 'analysis' not in data:
            return jsonify({'error': 'No analysis data provided.'}), 400

        analysis = data.get('analysis', {})
        questions = analysis.get('questions', [])
        if not questions:
            return jsonify({'error': 'No questions found in analysis data.'}), 400

        error_questions = [q for q in questions if q['status'] != 'correct']
        if not error_questions:
            return jsonify({'practice_questions': []})

        client = OpenAI(api_key=api_key)

        prompt = f"""
        Generate practice questions for these problems with mistakes: {json.dumps(error_questions, indent=2)}
        CRITICAL INSTRUCTIONS:
        1. Use the EXACT SAME question numbers as originals
        2. Create MODIFIED versions (similar concept, different values)
        3. Target the specific errors/concepts
        4. Format math with $LaTeX$
        5. Ensure each question number appears only once. No duplicates. If multiple for same number, combine into one.
        6. Ensure terms are not repeated in the question text; each mathematical term appears only once.
        Return JSON array: [{{"number": "number", "question": "modified with $LaTeX$"}}]
        """

        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=2000,
            temperature=0.7
        )

        result_text = response.choices[0].message.content.strip()
        result_text = result_text.replace('```json', '').replace('```', '').strip()

        try:
            practice_questions = json.loads(result_text)
            # Deduplicate practice questions by number
            seen = set()
            unique_practice = []
            for pq in practice_questions:
                if pq['number'] not in seen:
                    seen.add(pq['number'])
                    unique_practice.append(pq)
            return jsonify({'practice_questions': unique_practice})
        except json.JSONDecodeError as e:
            return jsonify({'error': f'Failed to parse: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
