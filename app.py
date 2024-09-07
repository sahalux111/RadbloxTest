import time
import requests
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from threading import Thread

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Simulated database
users = {
    'sunil': {'password': generate_password_hash('sunilrbx'), 'role': 'admin'},
    'arun': {'password': generate_password_hash('arunrbx'), 'role': 'admin'},
    'shrini': {'password': generate_password_hash('shrinirbx'), 'role': 'admin'},
    'sahal': {'password': generate_password_hash('sahalrbx'), 'role': 'admin'},
    'anto': {'password': generate_password_hash('antorbx'), 'role': 'admin'},
    'drmonika': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'dramit': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drshashank': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drronak': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'dranthony': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'droguntade': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drsmitha': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drnikita': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drkarim': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drfakhri': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'imugilteam': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drnamitha': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drsachin': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drvivek': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drraj': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'rdlteam': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'ishateam': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drdeepak': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drsurendar': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'ukteam': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'drsnehal': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'teslagroup': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'pranamika': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'hemanth': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'diana': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'muflih': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'titus': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'arumugham': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'srijesh': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'radstar': {'password': generate_password_hash('1234'), 'role': 'doctor'},
    'qa': {'password': generate_password_hash('qa'), 'role': 'qa_radiographer'}
}

available_doctors = {}
doctor_breaks = {}
doctor_notes = {}

# Function to get a list of doctor names
def get_doctors():
    return [user for user, details in users.items() if details['role'] == 'doctor']

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

    if username in users and check_password_hash(users[username]['password'], password):
        session['username'] = username
        session['role'] = users[username]['role']
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

    for doctor, break_end in doctor_breaks.items():
        if current_time >= break_end:
            start_time, end_time = available_doctors.get(doctor, (None, None))
            if start_time and end_time:
                start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M')
                end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M')
                if start_time <= current_time <= end_time:
                    available_now[doctor] = end_time.strftime('%Y-%m-%d %H:%M')
            del doctor_breaks[doctor]
        else:
            breaks[doctor] = break_end.strftime('%Y-%m-%d %H:%M')

    for doctor, (start_time, end_time) in available_doctors.items():
        start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M')
        end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M')

        if start_time <= current_time <= end_time and doctor not in doctor_breaks:
            available_now[doctor] = end_time.strftime('%Y-%m-%d %H:%M')
        elif start_time > current_time:
            upcoming_scheduled[doctor] = (start_time.strftime('%Y-%m-%d %H:%M'), end_time.strftime('%Y-%m-%d %H:%M'))

    if session['role'] == 'doctor':
        username = session['username']
        available_now = {username: available_now.get(username)}
        breaks = {username: breaks.get(username)}
        return render_template('dashboard.html', available_now=available_now, breaks=breaks, upcoming_scheduled={})

    if session['role'] == 'qa_radiographer' or session['role'] == 'admin':
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

    available_doctors[doctor] = (availability_start.strftime('%Y-%m-%d %H:%M'), availability_end.strftime('%Y-%m-%d %H:%M'))

    return redirect(url_for('dashboard'))

@app.route('/take_break', methods=['POST'])
def take_break():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    doctor = session['username']
    break_duration = int(request.form['break_duration'])
    break_end_time = get_indian_time() + timedelta(minutes=break_duration)

    doctor_breaks[doctor] = break_end_time

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

    doctor_notes[doctor] = note  # Save note for the doctor

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

    available_doctors[doctor] = (availability_start.strftime('%Y-%m-%d %H:%M'), availability_end.strftime('%Y-%m-%d %H:%M'))

    return redirect(url_for('admin_control'))

@app.route('/update_break', methods=['POST'])
def update_break():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))

    doctor = request.form['doctor']
    break_start_date = request.form['break_start_date']
    break_start_time = request.form['break_start_time']
    break_end_date = request.form['break_end_date']
    break_end_time = request.form['break_end_time']
    
    break_start = datetime.strptime(f'{break_start_date} {break_start_time}', '%Y-%m-%d %H:%M')
    break_end = datetime.strptime(f'{break_end_date} {break_end_time}', '%Y-%m-%d %H:%M')

    doctor_breaks[doctor] = break_end

    return redirect(url_for('admin_control'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('index'))

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




  
