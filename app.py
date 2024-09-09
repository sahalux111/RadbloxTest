import time
import requests
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from threading import Thread
import psycopg2
from psycopg2.extras import DictCursor

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# PostgreSQL connection details
def get_db_connection():
    conn = psycopg2.connect(
        host="dpg-creov63v2p9s73d1bm7g-a",
        database="radbloxdashboard",
        user="radblox",
        password="ntupYx7U3hhVtxt8Y4Iq2uQQ4WuWmkjR"
    )
    return conn

# Adjust time zone to Indian Standard Time (UTC+5:30)
def get_indian_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    # Direct password comparison without hash
    if user and user['password'] == password:
        session['username'] = username
        session['role'] = user['role']
        return redirect(url_for('dashboard'))

    cursor.close()
    conn.close()
    return 'Invalid credentials'

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))

    current_time = get_indian_time()
    available_now = {}
    qa_availability = {}
    breaks = {}

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    # Fetch doctor availability
    cursor.execute("SELECT * FROM availability WHERE availability_start <= %s AND availability_end >= %s", (current_time, current_time))
    available_doctors = cursor.fetchall()

    # Fetch QA availability
    cursor.execute("SELECT * FROM qa_availability WHERE availability_start <= %s AND availability_end >= %s", (current_time, current_time))
    available_qas = cursor.fetchall()

    # Fetch doctor breaks
    cursor.execute("SELECT * FROM breaks WHERE break_end >= %s", (current_time,))
    active_breaks = cursor.fetchall()

    # Map doctors' availability and breaks
    for doctor in available_doctors:
        available_now[doctor['doctor_id']] = doctor['availability_end'].strftime('%Y-%m-%d %H:%M')

    for break_item in active_breaks:
        breaks[break_item['doctor_id']] = break_item['break_end'].strftime('%Y-%m-%d %H:%M')

    # Map QA availability
    for qa in available_qas:
        qa_availability[qa['qa_id']] = qa['availability_end'].strftime('%Y-%m-%d %H:%M')

    # Doctor-specific dashboard
    if session['role'] == 'doctor':
        username = session['username']
        available_now = {username: available_now.get(username)}
        breaks = {username: breaks.get(username)}
        return render_template('dashboard.html', available_now=available_now, breaks=breaks, upcoming_scheduled={})

    # QA Radiographer or Admin dashboard
    if session['role'] == 'qa_radiographer' or session['role'] == 'admin':
        cursor.execute("SELECT * FROM doctor_notes")
        doctor_notes = cursor.fetchall()
        return render_template('dashboard.html', available_now=available_now, qa_availability=qa_availability, breaks=breaks, upcoming_scheduled={}, doctor_notes=doctor_notes)

    cursor.close()
    conn.close()

@app.route('/select_availability')
def select_availability():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute("SELECT username FROM users WHERE role = 'doctor'")
    doctors = [row['username'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return render_template('select_availability.html', doctors=doctors)

@app.route('/set_availability', methods=['POST'])
def set_availability():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    user_role = session['role']
    start_date = request.form['start_date']
    start_time = request.form['start_time']
    end_date = request.form['end_date']
    end_time = request.form['end_time']
    cases_reported = request.form.get('cases_reported', 0)

    availability_start = datetime.strptime(f'{start_date} {start_time}', '%Y-%m-%d %H:%M')
    availability_end = datetime.strptime(f'{end_date} {end_time}', '%Y-%m-%d %H:%M')

    conn = get_db_connection()
    cursor = conn.cursor()

    if user_role == 'qa_radiographer':
        # Validate cases reported
        cursor.execute("SELECT cases_reported FROM qa_reports WHERE qa_id = (SELECT id FROM users WHERE username = %s) AND report_date = %s", (session['username'], get_indian_time().date()))
        reported_cases = cursor.fetchone()
        
        if not reported_cases or reported_cases['cases_reported'] != int(cases_reported):
            cursor.close()
            conn.close()
            return 'Number of cases reported does not match the previous day\'s report'

        cursor.execute("""
            INSERT INTO qa_availability (qa_id, availability_start, availability_end)
            VALUES ((SELECT id FROM users WHERE username = %s), %s, %s)
        """, (session['username'], availability_start, availability_end))
    elif user_role == 'doctor':
        cursor.execute("""
            INSERT INTO availability (doctor_id, availability_start, availability_end)
            VALUES ((SELECT id FROM users WHERE username = %s), %s, %s)
        """, (session['username'], availability_start, availability_end))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/add_note', methods=['POST'])
def add_note():
    if 'username' not in session or session['role'] not in ['admin', 'qa_radiographer']:
        return redirect(url_for('index'))
    
    doctor = request.form['doctor']
    note = request.form['note']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO doctor_notes (doctor_id, note)
        VALUES ((SELECT id FROM users WHERE username = %s), %s)
    """, (doctor, note))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/edit_note', methods=['POST'])
def edit_note():
    if 'username' not in session or session['role'] not in ['admin', 'qa_radiographer']:
        return redirect(url_for('index'))

    note_id = request.form['note_id']
    new_note = request.form['new_note']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE doctor_notes
        SET note = %s
        WHERE id = %s
    """, (new_note, note_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/report_cases', methods=['POST'])
def report_cases():
    if 'username' not in session or session['role'] != 'qa_radiographer':
        return redirect(url_for('index'))

    cases_reported = request.form['cases_reported']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO qa_reports (qa_id, report_date, cases_reported)
        VALUES ((SELECT id FROM users WHERE username = %s), %s, %s)
    """, (session['username'], get_indian_time().date(), cases_reported))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('index'))

def ping_app():
    while True:
        try:
            requests.get('https://your-app-url.com')
            print("Ping successful!")
        except Exception as e:
            print(f"Ping failed: {e}")
        time.sleep(15)  # Ping every 15 seconds

if __name__ == '__main__':
    # Start the pinging in a separate thread
    ping_thread = Thread(target=ping_app)
    ping_thread.daemon = True
    ping_thread.start()

    app.run(debug=True)
