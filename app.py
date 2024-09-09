import time
import requests
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from threading import Thread
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://<user>:<password>@<host>/<dbname>'
db = SQLAlchemy(app)

# Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class Availability(db.Model):
    __tablename__ = 'availability'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    user = db.relationship('User')

class Break(db.Model):
    __tablename__ = 'breaks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    break_end = db.Column(db.DateTime, nullable=False)
    user = db.relationship('User')

class DoctorNote(db.Model):
    __tablename__ = 'doctor_notes'
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    user = db.relationship('User')

class QAAvailability(db.Model):
    __tablename__ = 'qa_availability'
    id = db.Column(db.Integer, primary_key=True)
    qa_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    user = db.relationship('User')

# Function to get current Indian time
def get_indian_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# Route for index
@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

# Route for login
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    user = User.query.filter_by(username=username).first()

    if user and user.password == password:  # Password comparison with stored hash
        session['username'] = username
        session['role'] = user.role
        return redirect(url_for('dashboard'))
    return 'Invalid credentials'

# Route for dashboard
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))

    current_time = get_indian_time()
    available_now = {}
    upcoming_scheduled = {}
    breaks = {}

    # Retrieve availability data from the database
    availabilities = Availability.query.all()
    for availability in availabilities:
        if availability.start_time <= current_time <= availability.end_time:
            available_now[availability.user.username] = availability.end_time.strftime('%Y-%m-%d %H:%M')
        elif availability.start_time > current_time:
            upcoming_scheduled[availability.user.username] = (
                availability.start_time.strftime('%Y-%m-%d %H:%M'), 
                availability.end_time.strftime('%Y-%m-%d %H:%M')
            )

    # Retrieve breaks data from the database
    breaks_data = Break.query.all()
    for break_info in breaks_data:
        if current_time <= break_info.break_end:
            breaks[break_info.user.username] = break_info.break_end.strftime('%Y-%m-%d %H:%M')

    if session['role'] == 'doctor':
        username = session['username']
        available_now = {username: available_now.get(username)}
        breaks = {username: breaks.get(username)}
        return render_template('dashboard.html', available_now=available_now, breaks=breaks, upcoming_scheduled={})

    if session['role'] == 'qa_radiographer':
        qa_availabilities = QAAvailability.query.all()
        qa_avail = {qa_availability.user.username: (qa_availability.start_time, qa_availability.end_time)
                    for qa_availability in qa_availabilities}
        return render_template('dashboard.html', available_now=available_now, breaks=breaks, qa_avail=qa_avail, upcoming_scheduled=upcoming_scheduled)

    return render_template('dashboard.html', available_now=available_now, breaks=breaks, upcoming_scheduled=upcoming_scheduled)

# Route for setting availability (QA and doctors)
@app.route('/set_availability', methods=['POST'])
def set_availability():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    user = User.query.filter_by(username=session['username']).first()
    start_date = request.form['start_date']
    start_time = request.form['start_time']
    end_date = request.form['end_date']
    end_time = request.form['end_time']
    
    availability_start = datetime.strptime(f'{start_date} {start_time}', '%Y-%m-%d %H:%M')
    availability_end = datetime.strptime(f'{end_date} {end_time}', '%Y-%m-%d %H:%M')

    if session['role'] == 'doctor':
        availability = Availability(user_id=user.id, start_time=availability_start, end_time=availability_end)
    else:
        availability = QAAvailability(qa_id=user.id, start_time=availability_start, end_time=availability_end)

    db.session.add(availability)
    db.session.commit()

    return redirect(url_for('dashboard'))

# Route for taking a break
@app.route('/take_break', methods=['POST'])
def take_break():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    user = User.query.filter_by(username=session['username']).first()
    break_duration = int(request.form['break_duration'])
    break_end_time = get_indian_time() + timedelta(minutes=break_duration)

    break_info = Break(user_id=user.id, break_end=break_end_time)
    db.session.add(break_info)
    db.session.commit()

    return redirect(url_for('dashboard'))

# Route for admin control
@app.route('/admin_control')
def admin_control():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    
    doctors = User.query.filter_by(role='doctor').all()
    return render_template('admin_control.html', users=doctors)

# Route for adding a note
@app.route('/add_note', methods=['POST'])
def add_note():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))

    doctor_id = request.form['doctor_id']
    note = request.form['note']

    doctor_note = DoctorNote(doctor_id=doctor_id, note=note)
    db.session.add(doctor_note)
    db.session.commit()

    return redirect(url_for('admin_control'))

# Route for logout
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
        time.sleep(15)

if __name__ == '__main__':
    ping_thread = Thread(target=ping_app)
    ping_thread.daemon = True
    ping_thread.start()

    app.run(debug=True)
