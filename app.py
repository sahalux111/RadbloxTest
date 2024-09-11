import time
import requests
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session, abort
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
    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}")
        abort(500)  # Internal Server Error

# Get the current time in Indian Standard Time (UTC+5:30)
def get_indian_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# Retrieve all users from the database
def get_users():
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT username, password, role FROM users")
        users = {row[0]: {'password': row[1], 'role': row[2]} for row in cursor.fetchall()}
        cursor.close()
        conn.close()
        return users
    except Exception as e:
        print(f"Error fetching users: {e}")
        abort(500)

# Retrieve availability for a user
def get_user_availability(username):
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT start_time, end_time FROM availability WHERE username = %s", (username,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Error fetching availability: {e}")
        abort(500)

# Save availability for a user
def set_user_availability(username, start_time, end_time):
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO availability (username, start_time, end_time) VALUES (%s, %s, %s) "
                       "ON CONFLICT (username) DO UPDATE SET start_time = %s, end_time = %s", 
                       (username, start_time, end_time, start_time, end_time))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error saving availability: {e}")
        abort(500)

# Get notes for a user
def get_user_notes(username):
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT note FROM notes WHERE username = %s", (username,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error fetching notes: {e}")
        abort(500)

# Save a note for a user
def set_user_notes(username, note):
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notes (username, note) VALUES (%s, %s) "
                       "ON CONFLICT (username) DO UPDATE SET note = %s", 
                       (username, note, note))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error saving notes: {e}")
        abort(500)

# Function to get a list of doctor names
def get_doctors():
    try:
        users = get_users()
        return [user for user, details in users.items() if details['role'] == 'doctor']
    except Exception as e:
        print(f"Error fetching doctors: {e}")
        abort(500)

# Function to get a list of QA users
def get_qa_users():
    try:
        users = get_users()
        return [user for user, details in users.items() if details['role'] == 'qa_radiographer']
    except Exception as e:
        print(f"Error fetching QA users: {e}")
        abort(500)

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    try:
        users = get_users()
        if username in users and users[username]['password'] == password:
            session['username'] = username
            session['role'] = users[username]['role']
            return redirect(url_for('dashboard'))
        return 'Invalid credentials'
    except Exception as e:
        print(f"Error during login: {e}")
        abort(500)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))

    current_time = get_indian_time()
    users = get_users()
    username = session['username']
    role = session['role']

    # Fetch user's availability and notes
    availability = get_user_availability(username)
    start_time, end_time = availability if availability else (None, None)

    if start_time and end_time:
        start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')

    if role == 'qa_radiographer':
        note = get_user_notes(username)
        return render_template('qa_dashboard.html', start_time=start_time, end_time=end_time, note=note)

    if role == 'doctor':
        available_now = {}
        if start_time and end_time and start_time <= current_time <= end_time:
            available_now[username] = end_time.strftime('%Y-%m-%d %H:%M')

        return render_template('doctor_dashboard.html', available_now=available_now)

    if role == 'admin':
        all_availability = {}
        for user in users:
            if users[user]['role'] == 'doctor':
                availability = get_user_availability(user)
                if availability:
                    all_availability[user] = availability
        return render_template('admin_dashboard.html', all_availability=all_availability)

@app.route('/select_availability')
def select_availability():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    doctors = get_doctors()  # Retrieve doctor names
    qa_users = get_qa_users()  # Retrieve QA user names
    return render_template('select_availability.html', doctors=doctors, qa_users=qa_users)

@app.route('/set_availability', methods=['POST'])
def set_availability():
    if 'username' not in session:
        return redirect(url_for('index'))

    user = session['username']
    start_date = request.form['start_date']
    start_time = request.form['start_time']
    end_date = request.form['end_date']
    end_time = request.form['end_time']
    
    availability_start = datetime.strptime(f'{start_date} {start_time}', '%Y-%m-%d %H:%M')
    availability_end = datetime.strptime(f'{end_date} {end_time}', '%Y-%m-%d %H:%M')

    set_user_availability(user, availability_start, availability_end)

    return redirect(url_for('dashboard'))

@app.route('/set_availability_now', methods=['POST'])
def set_availability_now():
    if 'username' not in session:
        return redirect(url_for('index'))

    user = session['username']
    current_time = get_indian_time()

    availability = get_user_availability(user)
    start_time, end_time = availability if availability else (None, None)

    if 'start_now' in request.form:
        set_user_availability(user, current_time, end_time)
    
    if 'end_now' in request.form:
        set_user_availability(user, start_time, current_time)

    return redirect(url_for('dashboard'))

@app.route('/qa_notes', methods=['GET', 'POST'])
def qa_notes():
    if 'username' not in session or session['role'] != 'qa_radiographer':
        return redirect(url_for('index'))
    
    user = session['username']
    if request.method == 'POST':
        note = request.form['note']
        set_user_notes(user, note)

    note = get_user_notes(user)
    return render_template('qa_notes.html', user=user, note=note)

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('index'))

def ping_app():
    while True:
        try:
            requests.get('https://radbloxtest-1.onrender.com')  # Replace with your app's URL
            print("Ping successfull")
        except Exception as e:
            print(f"Ping failed: {e}")
        time.sleep(15)  # Ping every 15 seconds

if __name__ == '__main__':
    # Start the pinging in a separate thread
    ping_thread = Thread(target=ping_app)
    ping_thread.daemon = True
    ping_thread.start()

    app.run(debug=True)

