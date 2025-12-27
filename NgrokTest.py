from flask import Flask, request, jsonify, session, redirect, make_response
from flask_cors import CORS  # <-- Make sure this line is present
import os
import base64
import json
from openai import OpenAI
from datetime import datetime
import threading

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Enable CORS for all routes and allow your Netlify domain
CORS(app, resources={r"/*": {"origins": ["https://math-ocr-frontend.netlify.app", "http://localhost:*"]}})

# Define log file path
LOG_FILE = '/tmp/login_logs.json'

# ============ API ROUTES ============
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

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
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
        start = result_text.find('[')
        end = result_text.rfind(']')
        if start != -1 and end != -1:
            result_text = result_text[start:end + 1]
        try:
            questions = json.loads(result_text)
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

@app.route('/generate_practice', methods=['POST'])
def generate_practice():
    try:
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
