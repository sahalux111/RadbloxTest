import time
import requests
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from threading import Thread

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database connection
def get_db_connection():
    conn = psycopg2.connect(
        host='dpg-creov63v2p9s73d1bm7g-a',
        database='radbloxdashboard',
        user='radblox',
        password='ntupYx7U3hhVtxt8Y4Iq2uQQ4WuWmkjR'
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
    password = request.form['password']  # Direct password comparison

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT password, role FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and user[0] == password:  # No password hashing
        session['username'] = username
        session['role'] = user[1]
        return redirect(url_for('dashboard'))

    return 'Invalid credentials'

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))

    current_time = get_indian_time()

    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch doctor availability
    cur.execute("SELECT doctor, start_time, end_time, notes FROM doctor_availability")
    availabilities = cur.fetchall()

    # Fetch QA availability
    cur.execute("SELECT qa_username, start_time, end_time, notes FROM qa_availability")
    qa_availabilities = cur.fetchall()

    cur.close()
    conn.close()

    available_doctors = {}
    available_qas = {}

    for doctor, start_time, end_time, notes in availabilities:
        if start_time <= current_time and (end_time is None or current_time <= end_time):
            available_doctors[doctor] = {'end_time': end_time, 'notes': notes}

    for qa_username, start_time, end_time, notes in qa_availabilities:
        if start_time <= current_time and (end_time is None or current_time <= end_time):
            available_qas[qa_username] = {'end_time': end_time, 'notes': notes}

    if session['role'] == 'doctor':
        username = session['username']
        doctor_availability = available_doctors.get(username, None)
        return render_template('dashboard.html', doctor_availability=doctor_availability)

    if session['role'] == 'qa_radiographer':
        username = session['username']
        qa_availability = available_qas.get(username, None)
        return render_template('dashboard.html', qa_availability=qa_availability)

    if session['role'] == 'admin':
        return render_template('admin_dashboard.html', available_doctors=available_doctors, available_qas=available_qas)

@app.route('/set_availability_status', methods=['POST'])
def set_availability_status():
    if 'username' not in session:
        return redirect(url_for('index'))

    role = session['role']
    username = session['username']
    action = request.form['action']  # Can be 'available' or 'unavailable'

    conn = get_db_connection()
    cur = conn.cursor()

    if role == 'doctor':
        # Handle availability for doctor
        if action == 'available':
            start_time = get_indian_time()
            end_time = None  # End time is open-ended until "Unavailable" is clicked
            cur.execute("""
                INSERT INTO doctor_availability (doctor, start_time, end_time)
                VALUES (%s, %s, %s)
                ON CONFLICT (doctor) DO UPDATE SET start_time = %s, end_time = NULL
            """, (username, start_time, end_time, start_time))
        elif action == 'unavailable':
            end_time = get_indian_time()
            cur.execute("""
                UPDATE doctor_availability
                SET end_time = %s
                WHERE doctor = %s AND end_time IS NULL
            """, (end_time, username))

    elif role == 'qa_radiographer':
        # Handle availability for QA users
        if action == 'available':
            start_time = get_indian_time()
            end_time = None  # Same logic as doctors
            cur.execute("""
                INSERT INTO qa_availability (qa_username, start_time, end_time)
                VALUES (%s, %s, %s)
                ON CONFLICT (qa_username) DO UPDATE SET start_time = %s, end_time = NULL
            """, (username, start_time, end_time, start_time))
        elif action == 'unavailable':
            end_time = get_indian_time()
            cur.execute("""
                UPDATE qa_availability
                SET end_time = %s
                WHERE qa_username = %s AND end_time IS NULL
            """, (end_time, username))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/set_notes', methods=['POST'])
def set_notes():
    if 'username' not in session:
        return redirect(url_for('index'))

    role = session['role']
    username = session['username']
    notes = request.form['notes']

    conn = get_db_connection()
    cur = conn.cursor()

    if role == 'doctor':
        cur.execute("""
            UPDATE doctor_availability
            SET notes = %s
            WHERE doctor = %s AND end_time IS NULL
        """, (notes, username))

    elif role == 'qa_radiographer':
        cur.execute("""
            UPDATE qa_availability
            SET notes = %s
            WHERE qa_username = %s AND end_time IS NULL
        """, (notes, username))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('index'))

# Function to ping the app regularly to keep it alive
def ping_app():
    while True:
        try:
            # Replace with your deployed app's URL
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
