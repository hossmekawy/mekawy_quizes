from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import pandas as pd
import re
import os
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['DATABASE'] = 'quizzes.db'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database initialization
def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    # Create quizzes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            explanation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
        )
    ''')

    # Create users table for admin authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create default admin user if none exists
    existing_admin = cursor.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1').fetchone()[0]
    if existing_admin == 0:
        default_password_hash = generate_password_hash('admin123')
        cursor.execute(
            'INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)',
            ('admin', default_password_hash, True)
        )

    conn.commit()
    conn.close()

# Database helper functions
def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def get_all_quizzes():
    conn = get_db_connection()
    quizzes = conn.execute('SELECT * FROM quizzes ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(quiz) for quiz in quizzes]

def get_quiz_by_id(quiz_id):
    conn = get_db_connection()
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    conn.close()
    return dict(quiz) if quiz else None

def get_questions_by_quiz_id(quiz_id):
    conn = get_db_connection()
    questions = conn.execute('SELECT * FROM questions WHERE quiz_id = ? ORDER BY id', (quiz_id,)).fetchall()
    conn.close()

    # Format questions for frontend
    formatted_questions = []
    for i, q in enumerate(questions, 1):
        formatted_questions.append({
            'id': i,
            'db_id': q['id'],
            'question': q['question_text'],
            'options': [
                {'letter': 'A', 'text': q['option_a']},
                {'letter': 'B', 'text': q['option_b']},
                {'letter': 'C', 'text': q['option_c']},
                {'letter': 'D', 'text': q['option_d']}
            ],
            'correct_answer': q['correct_answer'],
            'explanation': q['explanation'] or ''
        })

    return formatted_questions

def create_quiz(name, description=''):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            'INSERT INTO quizzes (name, description) VALUES (?, ?)',
            (name, description)
        )
        quiz_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return quiz_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def add_question_to_quiz(quiz_id, question_data):
    conn = get_db_connection()
    conn.execute(
        '''INSERT INTO questions
           (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (quiz_id, question_data['question'], question_data['option_a'],
         question_data['option_b'], question_data['option_c'], question_data['option_d'],
         question_data['correct_answer'], question_data.get('explanation', ''))
    )
    conn.commit()
    conn.close()

def delete_quiz(quiz_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM quizzes WHERE id = ?', (quiz_id,))
    conn.commit()
    conn.close()

def delete_question(question_db_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM questions WHERE id = ?', (question_db_id,))
    conn.commit()
    conn.close()

def clear_quiz_questions(quiz_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM questions WHERE quiz_id = ?', (quiz_id,))
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Authentication functions
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access admin features.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

def verify_password(username, password):
    user = get_user_by_username(username)
    if user and check_password_hash(user['password_hash'], password):
        return user
    return None

def parse_text_questions(text):
    """Parse questions from the provided text format"""
    questions = []

    # Split by "Question:" to get individual questions
    question_blocks = re.split(r'Question:\s*\d+', text)[1:]  # Skip first empty element

    for i, block in enumerate(question_blocks, 1):
        try:
            # Extract question text
            question_match = re.search(r'Flag Question\s*(.*?)\s*Select only one', block, re.DOTALL)
            if not question_match:
                continue

            question_text = question_match.group(1).strip()

            # Extract options
            options = []
            option_pattern = r'([A-D])\.([^A-D]*?)(?=[A-D]\.|$)'
            option_matches = re.findall(option_pattern, block, re.DOTALL)

            for letter, option_text in option_matches:
                # Clean up option text
                option_text = re.sub(r'^[a-d]\)\s*', '', option_text.strip())
                option_text = re.sub(r'^–\s*[A-D]\.\s*', '', option_text.strip())
                options.append({
                    'letter': letter,
                    'text': option_text
                })

            if len(options) == 4 and question_text:
                questions.append({
                    'id': i,
                    'question': question_text,
                    'options': options,
                    'correct_answer': None,  # Will be determined later
                    'explanation': ''
                })

        except Exception as e:
            print(f"Error parsing question {i}: {e}")
            continue

    return questions

def determine_correct_answers(questions):
    """Determine correct answers using general patterns (can be customized for specific subjects)"""
    # This is a simplified version - you can expand this for specific subjects
    for question in questions:
        question_text = question['question'].lower()

        # Simple heuristics - you can expand this based on your needs
        if 'real-time' in question_text and 'rtos' in question_text:
            # Look for options mentioning time constraints or real-time features
            for i, option in enumerate(question['options']):
                if 'time' in option['text'].lower() or 'constraint' in option['text'].lower():
                    question['correct_answer'] = option['letter']
                    break

        # If no specific pattern found, default to A (you can improve this logic)
        if not question['correct_answer']:
            question['correct_answer'] = 'A'

    return questions

# Routes
@app.route('/')
def index():
    quizzes = get_all_quizzes()
    return render_template('public_dashboard.html', quizzes=quizzes)

@app.route('/admin')
@login_required
def admin_dashboard():
    quizzes = get_all_quizzes()
    return render_template('dashboard.html', quizzes=quizzes)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = verify_password(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/quiz/<int:quiz_id>/admin')
@login_required
def quiz_admin(quiz_id):
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('index'))

    questions = get_questions_by_quiz_id(quiz_id)
    return render_template('admin.html', quiz=quiz, questions=questions)

@app.route('/quiz/<int:quiz_id>/take')
def take_quiz(quiz_id):
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('index'))

    questions = get_questions_by_quiz_id(quiz_id)
    if not questions:
        flash('No questions available in this quiz.', 'warning')
        return redirect(url_for('quiz_admin', quiz_id=quiz_id))

    return render_template('quiz.html', quiz=quiz, questions=questions)

@app.route('/api/quiz/<int:quiz_id>/questions')
def get_quiz_questions(quiz_id):
    questions = get_questions_by_quiz_id(quiz_id)
    return jsonify(questions)

@app.route('/create_quiz', methods=['POST'])
@login_required
def create_new_quiz():
    data = request.json
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()

    if not name:
        return jsonify({'success': False, 'message': 'Quiz name is required'})

    quiz_id = create_quiz(name, description)
    if quiz_id:
        return jsonify({'success': True, 'message': 'Quiz created successfully', 'quiz_id': quiz_id})
    else:
        return jsonify({'success': False, 'message': 'Quiz name already exists'})

@app.route('/delete_quiz/<int:quiz_id>', methods=['DELETE'])
@login_required
def delete_quiz_route(quiz_id):
    delete_quiz(quiz_id)
    return jsonify({'success': True, 'message': 'Quiz deleted successfully'})

@app.route('/quiz/<int:quiz_id>/add_question', methods=['POST'])
@login_required
def add_question(quiz_id):
    data = request.json

    # Verify quiz exists
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        return jsonify({'success': False, 'message': 'Quiz not found'})

    try:
        add_question_to_quiz(quiz_id, data)
        return jsonify({'success': True, 'message': 'Question added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error adding question: {str(e)}'})

@app.route('/quiz/<int:quiz_id>/upload_file', methods=['POST'])
@login_required
def upload_file(quiz_id):
    # Verify quiz exists
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        return jsonify({'success': False, 'message': 'Quiz not found'})

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(filepath)
            elif filename.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(filepath)
            else:
                return jsonify({'success': False, 'message': 'Unsupported file format'})

            # Expected columns: question, option_a, option_b, option_c, option_d, correct_answer, explanation
            required_columns = ['question', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']

            if not all(col in df.columns for col in required_columns):
                return jsonify({'success': False, 'message': f'Missing required columns: {required_columns}'})

            for _, row in df.iterrows():
                question_data = {
                    'question': str(row['question']),
                    'option_a': str(row['option_a']),
                    'option_b': str(row['option_b']),
                    'option_c': str(row['option_c']),
                    'option_d': str(row['option_d']),
                    'correct_answer': str(row['correct_answer']).upper(),
                    'explanation': str(row.get('explanation', ''))
                }
                add_question_to_quiz(quiz_id, question_data)

            os.remove(filepath)  # Clean up uploaded file
            return jsonify({'success': True, 'message': f'Successfully imported {len(df)} questions'})

        except Exception as e:
            return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'})

@app.route('/quiz/<int:quiz_id>/parse_text', methods=['POST'])
@login_required
def parse_text(quiz_id):
    # Verify quiz exists
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        return jsonify({'success': False, 'message': 'Quiz not found'})

    data = request.json
    text = data.get('text', '')

    if not text:
        return jsonify({'success': False, 'message': 'No text provided'})

    try:
        parsed_questions = parse_text_questions(text)

        if not parsed_questions:
            return jsonify({'success': False, 'message': 'No valid questions found in the text'})

        # Determine correct answers
        parsed_questions = determine_correct_answers(parsed_questions)

        # Add to database
        for question in parsed_questions:
            question_data = {
                'question': question['question'],
                'option_a': question['options'][0]['text'],
                'option_b': question['options'][1]['text'],
                'option_c': question['options'][2]['text'],
                'option_d': question['options'][3]['text'],
                'correct_answer': question['correct_answer'],
                'explanation': question['explanation']
            }
            add_question_to_quiz(quiz_id, question_data)

        return jsonify({'success': True, 'message': f'Successfully parsed and added {len(parsed_questions)} questions'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error parsing text: {str(e)}'})

@app.route('/quiz/<int:quiz_id>/clear_questions', methods=['POST'])
@login_required
def clear_questions(quiz_id):
    # Verify quiz exists
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        return jsonify({'success': False, 'message': 'Quiz not found'})

    clear_quiz_questions(quiz_id)
    return jsonify({'success': True, 'message': 'All questions cleared'})

@app.route('/delete_question/<int:question_db_id>', methods=['DELETE'])
@login_required
def delete_question_route(question_db_id):
    delete_question(question_db_id)
    return jsonify({'success': True, 'message': 'Question deleted'})

if __name__ == '__main__':
    app.run(debug=True)
