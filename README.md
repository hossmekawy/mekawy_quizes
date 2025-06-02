# Multi-Subject Quiz Application

A Flask-based quiz application that allows you to create and manage multiple quizzes for any subject. Features SQLite database storage, multiple question input methods, and an interactive quiz interface.

## Features

### 🎯 **Multi-Quiz Management**
- **Create Multiple Quizzes**: Create separate quizzes for different subjects
- **SQLite Database**: Persistent storage with proper database relationships
- **Quiz Dashboard**: Central hub to manage all your quizzes

### 📝 **Question Management**
- **Manual Entry**: Add questions one by one through a web form
- **File Upload**: Upload questions from CSV or Excel files
- **Text Parsing**: Paste questions in a specific text format and automatically parse them
- **Full CRUD Operations**: Create, Read, Update, and Delete questions
- **Inline Editing**: Edit questions directly from the management interface
- **Real-time Updates**: Changes are immediately reflected in the quiz

### 🎮 **Interactive Quiz Interface**
- **Question-by-Question Display**: Shows one question at a time
- **Immediate Feedback**: Shows correct answers when wrong answers are selected
- **Progress Tracking**: Visual progress bar and question counter
- **Score Calculation**: Final score with percentage
- **Mobile-First Design**: Optimized for mobile devices with responsive layout

### 🔐 **Authentication System**
- **Admin Login Required**: All quiz management features require authentication
- **Public Quiz Access**: Anyone can take quizzes without logging in
- **Secure Sessions**: Session-based authentication with password hashing
- **Default Admin Account**: Username: `admin`, Password: `admin123`

### 📄 **Premium PDF Generation**
- **Professional Answer Keys**: Generate beautiful, premium-looking PDF answer sheets
- **Complete Explanations**: Include detailed explanations for each question
- **Branded Design**: Professional layout with colors, tables, and typography
- **Public/Private Control**: Admin can control whether answers are publicly accessible
- **Instant Download**: One-click PDF download with proper formatting

### 📊 **Quiz Analytics & Tracking**
- **Automatic Attempt Tracking**: Records all quiz attempts with unique user IDs
- **User Name Collection**: Collects user names for better identification
- **Session Persistence**: Quiz progress is saved and restored on page refresh
- **No Authentication Required**: Users can take quizzes without signing up
- **Comprehensive Analytics**: View detailed statistics and performance data
- **Visual Charts**: Interactive graphs showing score distribution and trends
- **Admin Dashboard**: Centralized view of all quiz attempts across the system
- **Individual Quiz Analytics**: Detailed performance data for each quiz

### 💾 **Database Management**
- **Complete Database Export**: Create full backups of your entire quiz system
- **Database Import**: Restore from previously exported backup files
- **Automatic Backup**: Current database is backed up before importing
- **Data Validation**: Ensures imported files are valid quiz databases
- **Database Statistics**: View detailed information about your database
- **Safe Operations**: Built-in safeguards and confirmation prompts

## Installation

1. **Clone or download the project files**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Open your browser and go to**:
   - Public Dashboard: `http://localhost:5000/`
   - Admin Login: `http://localhost:5000/login`

## Usage

### For Quiz Takers (No Login Required)

1. **Go to the Public Dashboard** (`http://localhost:5000/`)
2. **Browse available quizzes** and click "Start Quiz"
3. **Take the quiz** with immediate feedback
4. **View your results** at the end

### For Administrators (Login Required)

1. **Login to Admin Panel**:
   - Go to `http://localhost:5000/login`
   - Username: `admin`
   - Password: `admin123`

2. **Create a new quiz**:
   - Enter a quiz name (e.g., "Operating Systems", "Math Quiz", "History Test")
   - Add an optional description
   - Click "Create Quiz"

3. **Access the quiz admin panel** by clicking "Manage Questions"

### Adding Questions

#### Method 1: Manual Entry
1. Go to the Quiz Admin Panel
2. Click on "Manual Entry" tab
3. Fill in the question, options, correct answer, and explanation
4. Click "Add Question"

#### Method 2: Upload CSV/Excel File
1. Go to the "Upload File" tab
2. Prepare a CSV or Excel file with columns:
   - `question`: The question text
   - `option_a`: Option A text
   - `option_b`: Option B text
   - `option_c`: Option C text
   - `option_d`: Option D text
   - `correct_answer`: The correct answer (A, B, C, or D)
   - `explanation`: Optional explanation text
3. Upload the file

#### Method 3: Parse Text Format
1. Go to the "Parse Text" tab
2. Paste your questions in this format:
   ```
   Question: 1
   Status: Answered
   Flag Question
   What is a key advantage of RTOS?

   Select only one

   A.High resource consumption
   B.Limited task switching
   C.Maximum utilization of devices
   D.Complex algorithms
   ```
3. The system will automatically parse and determine correct answers

### Taking the Quiz
1. **Enter Your Name**: When starting a quiz, you'll be prompted to enter your name
2. **Session Persistence**: Your progress is automatically saved - you can refresh the page and continue where you left off
3. **Answer Questions**: Navigate through questions one by one
4. **Immediate Feedback**: Get instant feedback on wrong answers with correct answer explanations
5. **Complete Quiz**: View your final score with your name and unique session ID

### Managing Questions
1. Go to the "Manage Questions" tab
2. View all questions with their correct answers highlighted
3. **Edit questions**: Click the edit icon (pencil) to modify any question
4. **Delete questions**: Click the delete icon (trash) to remove individual questions
5. **Clear all**: Use "Clear All Questions" to remove all questions at once

#### Editing Questions
- Click the blue edit icon next to any question
- Modify question text, options, correct answer, or explanation
- Changes are saved immediately and reflected in the quiz
- Modal interface provides easy form-based editing

### Viewing Analytics

#### Quiz-Specific Analytics
1. Go to any quiz admin panel
2. Click "📊 Analytics" in the navigation
3. View detailed statistics including:
   - Total attempts and average scores
   - Score distribution charts
   - Performance trends over time
   - Individual attempt details with user IDs

#### System-Wide Analytics
1. From the admin dashboard, click "📊 Analytics"
2. View overall system statistics:
   - Total quizzes and attempts across all quizzes
   - Average performance metrics
   - Recent activity across all quizzes
   - Quiz performance comparison charts

### Quiz Attempt Tracking
- **Automatic Tracking**: Every quiz completion is automatically recorded
- **Unique User IDs**: Each attempt gets a unique identifier (no login required)
- **Comprehensive Data**: Tracks score, percentage, time taken, and answers
- **Real-time Analytics**: Data is immediately available in admin dashboards
- **Visual Charts**: Interactive graphs powered by Chart.js

### Database Management

#### Exporting Database
1. Go to admin dashboard and click "💾 Database"
2. Click "Export Database" button
3. A timestamped .db file will be downloaded
4. This file contains your complete quiz system backup

#### Importing Database
1. Go to Database Management page
2. Select a previously exported .db file
3. Check the confirmation checkbox
4. Click "Import Database"
5. **Warning**: This replaces all current data

#### Database Statistics
- View total quizzes, questions, and attempts
- Monitor database file size
- See table counts and other metrics
- Refresh statistics in real-time

## Text Format for Parsing

The application can automatically parse questions in this format:

```
Question: [number]
Status: [status]
Flag Question
[Question text]

Select only one

A.[option text]
B.[option text]
C.[option text]
D.[option text]
```

The system uses AI-powered analysis to determine the correct answers based on Operating Systems knowledge.

## File Structure

```
├── app.py                 # Main Flask application
├── templates/
│   ├── admin.html        # Admin panel template
│   └── quiz.html         # Quiz interface template
├── uploads/              # Temporary file uploads (created automatically)
├── requirements.txt      # Python dependencies
├── sample_questions.csv  # Sample CSV file
└── README.md            # This file
```

## Sample CSV Format

```csv
question,option_a,option_b,option_c,option_d,correct_answer,explanation
"What is RTOS?","Real-time OS","Regular OS","Random OS","Rapid OS","A","Real-time Operating System"
```

## Technologies Used

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS (Tailwind CSS), JavaScript
- **File Processing**: pandas, openpyxl
- **Styling**: Tailwind CSS CDN

## Features in Detail

### Automatic Answer Detection
The text parsing feature includes intelligent answer detection for Operating Systems topics:
- RTOS concepts and characteristics
- Operating system functions and components
- Scheduling algorithms
- Memory management
- Process management
- Real-time systems
- And more...

### Responsive Design
- Mobile-friendly interface
- Adaptive layouts for different screen sizes
- Touch-friendly buttons and interactions

### Data Persistence
- Questions are stored in memory during the session
- For production use, consider implementing database storage

## Customization

### Adding New Answer Patterns
To improve automatic answer detection, edit the `answer_map` dictionary in `app.py`:

```python
answer_map = {
    'your_keyword_pattern': 'correct_answer_letter',
    # Add more patterns...
}
```

### Styling
The application uses Tailwind CSS. You can customize the appearance by modifying the CSS classes in the HTML templates.

## Troubleshooting

### Common Issues

1. **File upload fails**: Check file format (CSV/Excel) and column names
2. **Text parsing doesn't work**: Ensure the text follows the exact format shown above
3. **Questions don't appear**: Check that questions were added successfully in the admin panel

### Error Messages
The application provides clear error messages for common issues like:
- Invalid file formats
- Missing required columns
- Parsing errors
- Network connectivity issues

## Contributing

Feel free to contribute by:
- Adding more answer patterns for automatic detection
- Improving the UI/UX
- Adding new features like question categories
- Implementing database storage
- Adding user authentication

## License

This project is open source and available under the MIT License.
