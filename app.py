import time
import requests
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from threading import Thread
import psycopg2
from psycopg2.extras import DictCursor

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# PostgreSQL connection details
def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="your_database_name",
        user="your_database_user",
        password="your_database_password"
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

    if user and check_password_hash(user['password'], password):
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
    upcoming_scheduled = {}
    breaks = {}

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    cursor.execute("SELECT * FROM availability WHERE availability_start <= %s AND availability_end >= %s", (current_time, current_time))
    available_doctors = cursor.fetchall()

    cursor.execute("SELECT * FROM breaks WHERE break_end >= %s", (current_time,))
    active_breaks = cursor.fetchall()

    for doctor in available_doctors:
        available_now[doctor['doctor_id']] = doctor['availability_end'].strftime('%Y-%m-%d %H:%M')

    for break_item in active_breaks:
        breaks[break_item['doctor_id']] = break_item['break_end'].strftime('%Y-%m-%d %H:%M')

    if session['role'] == 'doctor':
        username = session['username']
        available_now = {username: available_now.get(username)}
        breaks = {username: breaks.get(username)}
        return render_template('dashboard.html', available_now=available_now, breaks=breaks, upcoming_scheduled={})

    if session['role'] == 'qa_radiographer' or session['role'] == 'admin':
        cursor.execute("SELECT * FROM doctor_notes")
        doctor_notes = cursor.fetchall()
        return render_template('dashboard.html', available_now=available_now, breaks=breaks, upcoming_scheduled=upcoming_scheduled, doctor_notes=doctor_notes)

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
    
    doctor = session['username']
    start_date = request.form['start_date']
    start_time = request.form['start_time']
    end_date = request.form['end_date']
    end_time = request.form['end_time']
    
    availability_start = datetime.strptime(f'{start_date} {start_time}', '%Y-%m-%d %H:%M')
    availability_end = datetime.strptime(f'{end_date} {end_time}', '%Y-%m-%d %H:%M')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO availability (doctor_id, availability_start, availability_end)
        VALUES ((SELECT id FROM users WHERE username = %s), %s, %s)
    """, (doctor, availability_start, availability_end))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/take_break', methods=['POST'])
def take_break():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    doctor = session['username']
    break_duration = int(request.form['break_duration'])
    break_end_time = get_indian_time() + timedelta(minutes=break_duration)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO breaks (doctor_id, break_end)
        VALUES ((SELECT id FROM users WHERE username = %s), %s)
    """, (doctor, break_end_time))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/admin_control')
def admin_control():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    cursor.execute("SELECT * FROM doctor_notes")
    doctor_notes = cursor.fetchall()

    cursor.execute("SELECT username FROM users WHERE role = 'doctor'")
    doctors = [row['username'] for row in cursor.fetchall()]

    cursor.close()
    conn.close()
    
    return render_template('admin_control.html', users=users, doctor_notes=doctor_notes, doctors=doctors)

@app.route('/add_note', methods=['POST'])
def add_note():
    if 'username' not in session or session['role'] != 'admin':
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

    return redirect(url_for('admin_control'))

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



  
