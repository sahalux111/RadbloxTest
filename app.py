from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure PostgreSQL Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://radblox_user:5sKqQMJVDrRLeqwggLDrkxyuRrAF6pHg@dpg-crc56ujtq21c738ppm6g-a.oregon-postgres.render.com/radblox'
db = SQLAlchemy(app)

# Define your database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_username = db.Column(db.String(80), db.ForeignKey('user.username'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)

class Break(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_username = db.Column(db.String(80), db.ForeignKey('user.username'), nullable=False)
    break_end_time = db.Column(db.DateTime, nullable=False)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_username = db.Column(db.String(80), db.ForeignKey('user.username'), nullable=False)
    note_content = db.Column(db.Text, nullable=False)

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        session['username'] = username
        session['role'] = user.role
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

    # Fetch data from the database
    doctor_availabilities = Availability.query.all()
    doctor_breaks = Break.query.all()

    for break_record in doctor_breaks:
        if current_time >= break_record.break_end_time:
            # Break is over, move the doctor back to available
            for availability in doctor_availabilities:
                if availability.doctor_username == break_record.doctor_username:
                    if availability.start_time <= current_time <= availability.end_time:
                        available_now[break_record.doctor_username] = availability.end_time.strftime('%Y-%m-%d %H:%M')
            db.session.delete(break_record)
            db.session.commit()
        else:
            # Break is ongoing
            breaks[break_record.doctor_username] = break_record.break_end_time.strftime('%Y-%m-%d %H:%M')

    for availability in doctor_availabilities:
        if availability.start_time <= current_time <= availability.end_time and availability.doctor_username not in breaks:
            available_now[availability.doctor_username] = availability.end_time.strftime('%Y-%m-%d %H:%M')
        elif availability.start_time > current_time:
            upcoming_scheduled[availability.doctor_username] = (availability.start_time.strftime('%Y-%m-%d %H:%M'), availability.end_time.strftime('%Y-%m-%d %H:%M'))

    if session['role'] == 'doctor':
        username = session['username']
        available_now = {username: available_now.get(username)}
        breaks = {username: breaks.get(username)}
        return render_template('dashboard.html', available_now=available_now, breaks=breaks, upcoming_scheduled={})

    if session['role'] in ['qa_radiographer', 'admin']:
        notes = Note.query.all()
        doctor_notes = {note.doctor_username: note.note_content for note in notes}
        return render_template('dashboard.html', available_now=available_now, breaks=breaks, upcoming_scheduled=upcoming_scheduled, doctor_notes=doctor_notes)

@app.route('/select_availability')
def select_availability():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    doctors = [user.username for user in User.query.filter_by(role='doctor').all()]
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

    new_availability = Availability(doctor_username=doctor, start_time=availability_start, end_time=availability_end)
    db.session.add(new_availability)
    db.session.commit()

    return redirect(url_for('dashboard'))

@app.route('/take_break', methods=['POST'])
def take_break():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    doctor = session['username']
    break_duration = int(request.form['break_duration'])
    break_end_time = get_indian_time() + timedelta(minutes=break_duration)

    new_break = Break(doctor_username=doctor, break_end_time=break_end_time)
    db.session.add(new_break)
    db.session.commit()

    return redirect(url_for('dashboard'))

@app.route('/admin_control')
def admin_control():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    
    doctors = [user.username for user in User.query.filter_by(role='doctor').all()]
    notes = Note.query.all()
    doctor_notes = {note.doctor_username: note.note_content for note in notes}
    return render_template('admin_control.html', users=User.query.all(), doctor_notes=doctor_notes, doctors=doctors)

@app.route('/add_note', methods=['POST'])
def add_note():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    
    doctor = request.form['doctor']
    note = request.form['note']

    new_note = Note(doctor_username=doctor, note_content=note)
    db.session.add(new_note)
    db.session.commit()

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

    existing_availability = Availability.query.filter_by(doctor_username=doctor).first()
    if existing_availability:
        existing_availability.start_time = availability_start
        existing_availability.end_time = availability_end
    else:
        new_availability = Availability(doctor_username=doctor, start_time=availability_start, end_time=availability_end)
        db.session.add(new_availability)

    db.session.commit()

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

    existing_break = Break.query.filter_by(doctor_username=doctor).first()
    if existing_break:
        existing_break.break_end_time = break_end
    else:
        new_break = Break(doctor_username=doctor, break_end_time=break_end)
        db.session.add(new_break)

    db.session.commit()

    return redirect(url_for('admin_control'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)

