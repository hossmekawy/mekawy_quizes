from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, make_response, send_file
import pandas as pd
import re
import os
import sqlite3
import json
import uuid
import shutil
import tempfile
from urllib.parse import quote
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO

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
            show_answers_public BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add show_answers_public column to existing quizzes table if it doesn't exist
    try:
        cursor.execute('ALTER TABLE quizzes ADD COLUMN show_answers_public BOOLEAN DEFAULT FALSE')
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Create quiz_attempts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            user_name TEXT,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            percentage REAL NOT NULL,
            time_taken INTEGER,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_answers TEXT,
            FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
        )
    ''')

    # Add user_name column to existing quiz_attempts table if it doesn't exist
    try:
        cursor.execute('ALTER TABLE quiz_attempts ADD COLUMN user_name TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

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

def update_quiz_settings(quiz_id, show_answers_public):
    conn = get_db_connection()
    conn.execute(
        'UPDATE quizzes SET show_answers_public = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (show_answers_public, quiz_id)
    )
    conn.commit()
    conn.close()

def update_question(question_db_id, question_data):
    conn = get_db_connection()
    conn.execute(
        '''UPDATE questions
           SET question_text = ?, option_a = ?, option_b = ?, option_c = ?, option_d = ?,
               correct_answer = ?, explanation = ?
           WHERE id = ?''',
        (question_data['question'], question_data['option_a'],
         question_data['option_b'], question_data['option_c'], question_data['option_d'],
         question_data['correct_answer'], question_data.get('explanation', ''), question_db_id)
    )
    conn.commit()
    conn.close()

def get_question_by_id(question_db_id):
    conn = get_db_connection()
    question = conn.execute('SELECT * FROM questions WHERE id = ?', (question_db_id,)).fetchone()
    conn.close()
    return dict(question) if question else None

def save_quiz_attempt(quiz_id, user_id, user_name, score, total_questions, percentage, time_taken, user_answers):
    conn = get_db_connection()
    conn.execute(
        '''INSERT INTO quiz_attempts
           (quiz_id, user_id, user_name, score, total_questions, percentage, time_taken, user_answers)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (quiz_id, user_id, user_name, score, total_questions, percentage, time_taken, json.dumps(user_answers))
    )
    conn.commit()
    conn.close()

def get_quiz_attempts(quiz_id):
    conn = get_db_connection()
    attempts = conn.execute(
        '''SELECT * FROM quiz_attempts
           WHERE quiz_id = ?
           ORDER BY completed_at DESC''',
        (quiz_id,)
    ).fetchall()
    conn.close()
    return [dict(attempt) for attempt in attempts]

def get_all_quiz_attempts():
    conn = get_db_connection()
    attempts = conn.execute(
        '''SELECT qa.*, q.name as quiz_name
           FROM quiz_attempts qa
           JOIN quizzes q ON qa.quiz_id = q.id
           ORDER BY qa.completed_at DESC'''
    ).fetchall()
    conn.close()
    return [dict(attempt) for attempt in attempts]

def get_quiz_statistics(quiz_id):
    conn = get_db_connection()

    # Get basic stats
    stats = conn.execute(
        '''SELECT
           COUNT(*) as total_attempts,
           AVG(percentage) as avg_percentage,
           MAX(percentage) as max_percentage,
           MIN(percentage) as min_percentage,
           AVG(time_taken) as avg_time
           FROM quiz_attempts
           WHERE quiz_id = ?''',
        (quiz_id,)
    ).fetchone()

    # Get score distribution
    distribution = conn.execute(
        '''SELECT
           CASE
               WHEN percentage >= 90 THEN 'A (90-100%)'
               WHEN percentage >= 80 THEN 'B (80-89%)'
               WHEN percentage >= 70 THEN 'C (70-79%)'
               WHEN percentage >= 60 THEN 'D (60-69%)'
               ELSE 'F (Below 60%)'
           END as grade,
           COUNT(*) as count
           FROM quiz_attempts
           WHERE quiz_id = ?
           GROUP BY
           CASE
               WHEN percentage >= 90 THEN 'A (90-100%)'
               WHEN percentage >= 80 THEN 'B (80-89%)'
               WHEN percentage >= 70 THEN 'C (70-79%)'
               WHEN percentage >= 60 THEN 'D (60-69%)'
               ELSE 'F (Below 60%)'
           END
           ORDER BY
           CASE
               WHEN percentage >= 90 THEN 1
               WHEN percentage >= 80 THEN 2
               WHEN percentage >= 70 THEN 3
               WHEN percentage >= 60 THEN 4
               ELSE 5
           END''',
        (quiz_id,)
    ).fetchall()

    conn.close()

    return {
        'basic': dict(stats) if stats else {},
        'distribution': [dict(row) for row in distribution]
    }

def export_database():
    """Create a backup of the current database"""
    try:
        # Create a temporary file for the backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'quiz_backup_{timestamp}.db'
        backup_path = os.path.join(tempfile.gettempdir(), backup_filename)

        # Copy the database file
        shutil.copy2(app.config['DATABASE'], backup_path)

        return backup_path, backup_filename
    except Exception as e:
        print(f"Error exporting database: {str(e)}")
        return None, None

def import_database(file_path):
    """Import a database backup"""
    try:
        # Validate the uploaded file is a valid SQLite database
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()

        # Check if it has the expected tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        expected_tables = ['users', 'quizzes', 'questions', 'quiz_attempts']

        if not all(table in tables for table in expected_tables):
            conn.close()
            return False, "Invalid database file: missing required tables"

        conn.close()

        # Create backup of current database
        current_backup_path = app.config['DATABASE'] + '.backup'
        shutil.copy2(app.config['DATABASE'], current_backup_path)

        # Replace current database with imported one
        shutil.copy2(file_path, app.config['DATABASE'])

        return True, "Database imported successfully"

    except Exception as e:
        return False, f"Error importing database: {str(e)}"

def get_database_stats():
    """Get statistics about the current database"""
    try:
        conn = get_db_connection()

        stats = {}

        # Count tables
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        stats['tables'] = len(tables)

        # Count records in each table
        for table in ['users', 'quizzes', 'questions', 'quiz_attempts']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            except:
                stats[table] = 0

        # Get database file size
        db_size = os.path.getsize(app.config['DATABASE'])
        stats['file_size'] = db_size
        stats['file_size_mb'] = round(db_size / (1024 * 1024), 2)

        conn.close()
        return stats

    except Exception as e:
        print(f"Error getting database stats: {str(e)}")
        return {}

# Initialize database on startup
init_db()

# PDF Generation Functions
def generate_quiz_answers_pdf(quiz, questions):
    """Generate a premium-looking PDF with quiz questions and answers"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)

    # Container for the 'Flowable' objects
    elements = []

    # Define styles
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2563eb')
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#64748b')
    )

    question_style = ParagraphStyle(
        'QuestionStyle',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.HexColor('#1e293b')
    )

    option_style = ParagraphStyle(
        'OptionStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        leftIndent=20,
        textColor=colors.HexColor('#475569')
    )

    correct_option_style = ParagraphStyle(
        'CorrectOptionStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        leftIndent=20,
        textColor=colors.HexColor('#059669'),
        backColor=colors.HexColor('#ecfdf5')
    )

    explanation_style = ParagraphStyle(
        'ExplanationStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=15,
        leftIndent=20,
        textColor=colors.HexColor('#6b7280'),
        fontName='Helvetica-Oblique'
    )

    # Header
    elements.append(Paragraph(quiz['name'], title_style))
    elements.append(Paragraph('Answer Key & Explanations', subtitle_style))

    if quiz['description']:
        elements.append(Paragraph(quiz['description'], styles['Normal']))

    elements.append(Spacer(1, 20))

    # Quiz info table
    quiz_info = [
        ['Quiz Name:', quiz['name']],
        ['Total Questions:', str(len(questions))],
        ['Generated:', datetime.now().strftime('%B %d, %Y at %I:%M %p')]
    ]

    info_table = Table(quiz_info, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1e293b')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))

    elements.append(info_table)
    elements.append(Spacer(1, 30))

    # Questions and answers
    for i, question in enumerate(questions, 1):
        # Question
        elements.append(Paragraph(f"Question {i}: {question['question']}", question_style))

        # Options
        for option in question['options']:
            if option['letter'] == question['correct_answer']:
                elements.append(Paragraph(f"✓ {option['letter']}. {option['text']} (Correct Answer)", correct_option_style))
            else:
                elements.append(Paragraph(f"{option['letter']}. {option['text']}", option_style))

        # Explanation
        if question['explanation']:
            elements.append(Paragraph(f"Explanation: {question['explanation']}", explanation_style))

        # Add some space between questions
        if i < len(questions):
            elements.append(Spacer(1, 15))

    # Footer
    elements.append(PageBreak())
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#9ca3af')
    )
    elements.append(Spacer(1, 50))
    elements.append(Paragraph('Generated by Quiz Hub - Premium Quiz Management System', footer_style))
    elements.append(Paragraph(f'© {datetime.now().year} Quiz Hub. All rights reserved.', footer_style))

    # Build PDF
    doc.build(elements)

    # Get the value of the BytesIO buffer and return it
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

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

@app.route('/question/<int:question_db_id>', methods=['GET'])
@login_required
def get_question_route(question_db_id):
    question = get_question_by_id(question_db_id)
    if not question:
        return jsonify({'success': False, 'message': 'Question not found'})

    # Format question for frontend
    formatted_question = {
        'id': question['id'],
        'question': question['question_text'],
        'option_a': question['option_a'],
        'option_b': question['option_b'],
        'option_c': question['option_c'],
        'option_d': question['option_d'],
        'correct_answer': question['correct_answer'],
        'explanation': question['explanation'] or ''
    }

    return jsonify({'success': True, 'question': formatted_question})

@app.route('/question/<int:question_db_id>', methods=['PUT'])
@login_required
def update_question_route(question_db_id):
    data = request.json

    # Verify question exists
    question = get_question_by_id(question_db_id)
    if not question:
        return jsonify({'success': False, 'message': 'Question not found'})

    try:
        update_question(question_db_id, data)
        return jsonify({'success': True, 'message': 'Question updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error updating question: {str(e)}'})

@app.route('/quiz/<int:quiz_id>/start', methods=['POST'])
def start_quiz(quiz_id):
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()

        user_name = data.get('user_name', '').strip()

        if not user_name:
            return jsonify({'success': False, 'message': 'Name is required'})

        # Verify quiz exists
        quiz = get_quiz_by_id(quiz_id)
        if not quiz:
            return jsonify({'success': False, 'message': 'Quiz not found'})

        # Generate session ID
        session_id = f"quiz_{quiz_id}_{int(datetime.now().timestamp())}_{abs(hash(user_name)) % 10000}"

        # Store quiz session in Flask session
        session[f'quiz_session_{quiz_id}'] = {
            'session_id': session_id,
            'user_name': user_name,
            'current_question': 1,
            'answers': {},
            'start_time': datetime.now().isoformat(),
            'quiz_id': quiz_id
        }

        # Mark session as modified to ensure it's saved
        session.modified = True

        return jsonify({
            'success': True,
            'session_id': session_id,
            'user_name': user_name
        })

    except Exception as e:
        print(f"Error starting quiz: {str(e)}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})

@app.route('/quiz/<int:quiz_id>/session', methods=['GET'])
def get_quiz_session(quiz_id):
    try:
        session_key = f'quiz_session_{quiz_id}'
        if session_key in session:
            return jsonify({
                'success': True,
                'session': session[session_key]
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No active session found'
            })
    except Exception as e:
        print(f"Error getting session: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Session error'
        })

@app.route('/quiz/<int:quiz_id>/session', methods=['POST'])
def update_quiz_session(quiz_id):
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()

        session_key = f'quiz_session_{quiz_id}'

        if session_key in session:
            # Update session data
            session[session_key]['current_question'] = data.get('current_question', session[session_key]['current_question'])
            session[session_key]['answers'] = data.get('answers', session[session_key]['answers'])
            session.modified = True

            print(f"Session updated for quiz {quiz_id}: question {data.get('current_question')}, answers: {len(data.get('answers', {}))}")

            return jsonify({'success': True})
        else:
            print(f"No active session found for quiz {quiz_id}")
            return jsonify({'success': False, 'message': 'No active session found'})

    except Exception as e:
        print(f"Error updating session: {str(e)}")
        return jsonify({'success': False, 'message': f'Session update error: {str(e)}'})

@app.route('/quiz/<int:quiz_id>/submit', methods=['POST'])
def submit_quiz(quiz_id):
    data = request.json

    # Verify quiz exists
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        return jsonify({'success': False, 'message': 'Quiz not found'})

    # Get quiz questions for validation
    questions = get_questions_by_quiz_id(quiz_id)
    if not questions:
        return jsonify({'success': False, 'message': 'No questions found'})

    # Get session data
    session_key = f'quiz_session_{quiz_id}'
    quiz_session = session.get(session_key, {})

    # Calculate score
    user_answers = data.get('answers', {})
    score = 0
    total_questions = len(questions)

    for question in questions:
        user_answer = user_answers.get(str(question['id']))
        if user_answer == question['correct_answer']:
            score += 1

    percentage = (score / total_questions) * 100 if total_questions > 0 else 0
    time_taken = data.get('time_taken', 0)  # in seconds
    user_id = quiz_session.get('session_id', f'anonymous_{int(datetime.now().timestamp())}')
    user_name = quiz_session.get('user_name', 'Anonymous')

    # Save attempt to database
    save_quiz_attempt(quiz_id, user_id, user_name, score, total_questions, percentage, time_taken, user_answers)

    # Clear session after submission
    if session_key in session:
        del session[session_key]

    return jsonify({
        'success': True,
        'score': score,
        'total': total_questions,
        'percentage': round(percentage, 1),
        'user_id': user_id,
        'user_name': user_name
    })

@app.route('/quiz/<int:quiz_id>/analytics')
@login_required
def quiz_analytics(quiz_id):
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('admin_dashboard'))

    attempts = get_quiz_attempts(quiz_id)
    statistics = get_quiz_statistics(quiz_id)

    return render_template('quiz_analytics.html',
                         quiz=quiz,
                         attempts=attempts,
                         statistics=statistics)

@app.route('/admin/analytics')
@login_required
def admin_analytics():
    all_attempts = get_all_quiz_attempts()
    quizzes = get_all_quizzes()

    # Calculate overall statistics
    total_attempts = len(all_attempts)
    avg_score = sum(attempt['percentage'] for attempt in all_attempts) / total_attempts if total_attempts > 0 else 0

    return render_template('admin_analytics.html',
                         attempts=all_attempts,
                         quizzes=quizzes,
                         total_attempts=total_attempts,
                         avg_score=round(avg_score, 1))

@app.route('/admin/database')
@login_required
def database_management():
    stats = get_database_stats()
    return render_template('database_management.html', stats=stats)

@app.route('/admin/database/export')
@login_required
def export_database_route():
    backup_path, backup_filename = export_database()

    if backup_path:
        try:
            return send_file(
                backup_path,
                as_attachment=True,
                download_name=backup_filename,
                mimetype='application/octet-stream'
            )
        except Exception as e:
            flash(f'Error downloading backup: {str(e)}', 'error')
            return redirect(url_for('database_management'))
    else:
        flash('Error creating database backup', 'error')
        return redirect(url_for('database_management'))

@app.route('/admin/database/import', methods=['POST'])
@login_required
def import_database_route():
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('database_management'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('database_management'))

    if file and file.filename.endswith('.db'):
        try:
            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            file.save(temp_path)

            # Import the database
            success, message = import_database(temp_path)

            # Clean up temporary file
            os.remove(temp_path)

            if success:
                flash(message, 'success')
            else:
                flash(message, 'error')

        except Exception as e:
            flash(f'Error importing database: {str(e)}', 'error')
    else:
        flash('Please upload a valid .db file', 'error')

    return redirect(url_for('database_management'))

@app.route('/admin/database/stats')
@login_required
def database_stats_api():
    stats = get_database_stats()
    return jsonify(stats)

@app.route('/quiz/<int:quiz_id>/settings', methods=['POST'])
@login_required
def update_quiz_settings_route(quiz_id):
    data = request.json
    show_answers_public = data.get('show_answers_public', False)

    # Verify quiz exists
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        return jsonify({'success': False, 'message': 'Quiz not found'})

    update_quiz_settings(quiz_id, show_answers_public)
    return jsonify({'success': True, 'message': 'Quiz settings updated successfully'})

@app.route('/quiz/<int:quiz_id>/answers')
def view_quiz_answers(quiz_id):
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        flash('Quiz not found.', 'error')
        return redirect(url_for('index'))

    # Check if answers are public or user is admin
    if not quiz['show_answers_public'] and 'user_id' not in session:
        flash('Quiz answers are not publicly available.', 'error')
        return redirect(url_for('index'))

    questions = get_questions_by_quiz_id(quiz_id)
    return render_template('quiz_answers.html', quiz=quiz, questions=questions)

@app.route('/quiz/<int:quiz_id>/download-answers')
def download_quiz_answers(quiz_id):
    quiz = get_quiz_by_id(quiz_id)
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404

    # Check if answers are public or user is admin
    if not quiz['show_answers_public'] and 'user_id' not in session:
        return jsonify({'error': 'Quiz answers are not publicly available'}), 403

    questions = get_questions_by_quiz_id(quiz_id)
    if not questions:
        return jsonify({'error': 'No questions found'}), 404

    # Generate PDF
    pdf_data = generate_quiz_answers_pdf(quiz, questions)

    # Create a safe filename by removing/replacing problematic characters
    safe_filename = re.sub(r'[^\w\s-]', '', quiz['name']).strip()
    safe_filename = re.sub(r'[-\s]+', '-', safe_filename)
    if not safe_filename:  # If name becomes empty after cleaning
        safe_filename = f'quiz_{quiz_id}'

    # Create response with proper encoding handling
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'

    # Use RFC 5987 encoding for non-ASCII filenames
    filename = f'{safe_filename}_answers.pdf'
    try:
        # Try ASCII encoding first
        filename.encode('ascii')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    except UnicodeEncodeError:
        # Use RFC 5987 encoding for non-ASCII characters
        encoded_filename = quote(filename, safe='')
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"

    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
