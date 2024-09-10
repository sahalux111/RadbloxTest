import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from threading import Thread

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database connection
def get_db_connection():
    conn = psycopg2.connect(
        dbname='radbloxdashboard',
        user='radblox',
        password='ntupYx7U3hhVtxt8Y4Iq2uQQ4WuWmkjR',
        host='dpg-creov63v2p9s73d1bm7g-a'
    )
    return conn

# Function to get a list of doctor names
def get_doctors():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE role = %s", ('doctor',))
    doctors = cur.fetchall()
    cur.close()
    conn.close()
    return [doctor[0] for doctor in doctors]

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
    cur = conn.cursor()
    cur.execute("SELECT password, role FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and user[0] == password:
        session['username'] = username
        session['role'] = user[1]
        return redirect(url_for('dashboard'))
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
    cur = conn.cursor()
    cur.execute("SELECT username, end_time FROM availability WHERE start_time <= %s AND end_time >= %s", (current_time, current_time))
    available_doctors = cur.fetchall()
    cur.execute("SELECT username, break_end FROM breaks WHERE break_end > %s", (current_time,))
    ongoing_breaks = cur.fetchall()
    cur.close()
    conn.close()

    for doctor, end_time in available_doctors:
        available_now[doctor] = end_time.strftime('%Y-%m-%d %H:%M')

    for doctor, break_end in ongoing_breaks:
        breaks[doctor] = break_end.strftime('%Y-%m-%d %H:%M')

    if session['role'] == 'doctor':
        username = session['username']
        available_now = {username: available_now.get(username)}
        breaks = {username: breaks.get(username)}
        return render_template('dashboard.html', available_now=available_now, breaks=breaks, upcoming_scheduled={})

    if session['role'] == 'qa_radiographer' or session['role'] == 'admin':
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, note FROM notes")
        doctor_notes = dict(cur.fetchall())
        cur.close()
        conn.close()
        return render_template('dashboard.html', available_now=available_now, breaks=breaks, upcoming_scheduled=upcoming_scheduled, doctor_notes=doctor_notes)

@app.route('/select_availability')
def select_availability():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    doctors = get_doctors()  # Retrieve doctor names
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
    cur = conn.cursor()
    cur.execute("INSERT INTO availability (username, start_time, end_time) VALUES (%s, %s, %s) ON CONFLICT (username, start_time) DO UPDATE SET end_time = %s", (doctor, availability_start, availability_end, availability_end))
    conn.commit()
    cur.close()
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
    cur = conn.cursor()
    cur.execute("INSERT INTO breaks (username, break_end) VALUES (%s, %s) ON CONFLICT (username) DO UPDATE SET break_end = %s", (doctor, break_end_time, break_end_time))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/admin_control')
def admin_control():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    
    doctors = get_doctors()  # Retrieve doctor names
    return render_template('admin_control.html', users=users, doctor_notes=doctor_notes, doctors=doctors)

@app.route('/add_note', methods=['POST'])
def add_note():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    
    doctor = request.form['doctor']
    note = request.form['note']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO notes (username, note) VALUES (%s, %s) ON CONFLICT (username) DO UPDATE SET note = %s", (doctor, note, note))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('admin_control'))

@app.route('/update_schedule', methods=['POST'])
def update_schedule():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))

    doctor = request.form['doctor']
    start_date = request.form['start_date']
    start_time = request.form['start_time']
    end_date = request.form['end_date']
    end_time = request.form['end_time']
    
    availability_start = datetime.strptime(f'{start_date} {start_time}', '%Y-%m-%d %H:%M')
    availability_end = datetime.strptime(f'{end_date} {end_time}', '%Y-%m-%d %H:%M')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO availability (username, start_time, end_time) VALUES (%s, %s, %s) ON CONFLICT (username, start_time) DO UPDATE SET end_time = %s", (doctor, availability_start, availability_end, availability_end))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('admin_control'))

@app.route('/update_break', methods=['POST'])
def update_break():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))

    doctor = request.form['doctor']
    break_start_date = request.form['break_start_date']
    break_start_time = request.form['break_start_time']
    break_duration = int(request.form['break_duration'])
    break_end_time = datetime.strptime(f'{break_start_date} {break_start_time}', '%Y-%m-%d %H:%M') + timedelta(minutes=break_duration)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO breaks (username, break_end) VALUES (%s, %s) ON CONFLICT (username) DO UPDATE SET break_end = %s", (doctor, break_end_time, break_end_time))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('admin_control'))

if __name__ == '__main__':
    app.run(debug=True)

