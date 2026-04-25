from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'smart_parking_secret'

import os

app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', 'piyush')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'smart_parking')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            role = 'admin' if username.lower() == 'admin' else 'user'
            cur.execute("INSERT INTO users(username, email, password, role) VALUES(%s, %s, %s, %s)", (username, email, hashed_password, role))
            mysql.connection.commit()
            flash('Registered successfully', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Username or email already exists.', 'danger')
        finally:
            cur.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_candidate = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, password, role FROM users WHERE username = %s", [username])
        user = cur.fetchone()
        cur.close()
        
        if user and check_password_hash(user['password'], password_candidate):
            session['user_id'] = user['id']
            session['username'] = username
            session['role'] = user['role']
            flash('Logged in efficiently', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid login credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM parking_slots")
    slots = cur.fetchall()
    cur.close()
    return render_template('dashboard.html', slots=slots)

@app.route('/book/<int:slot_id>', methods=['GET', 'POST'])
@login_required
def book(slot_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM parking_slots WHERE id = %s", [slot_id])
    slot = cur.fetchone()
    
    cur.execute("SELECT default_vehicle FROM users WHERE id = %s", [session['user_id']])
    user = cur.fetchone()
    default_veh = user['default_vehicle'] if user and user['default_vehicle'] else ""
    
    if not slot or slot['status'] == 'Occupied':
        cur.close()
        flash('Invalid or occupied slot.', 'danger')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        vehicle_number = request.form['vehicle_number']
        try:
            cur.execute("INSERT INTO bookings(user_id, slot_id, vehicle_number) VALUES(%s, %s, %s)", (session['user_id'], slot_id, vehicle_number))
            cur.execute("UPDATE parking_slots SET status = %s WHERE id = %s", ('Occupied', slot_id))
            mysql.connection.commit()
            flash('Slot booked successfully!', 'success')
            return redirect(url_for('my_bookings'))
        except Exception as e:
            mysql.connection.rollback()
            flash('Error booking.', 'danger')
        finally:
            cur.close()
    return render_template('book.html', slot=slot, default_veh=default_veh)

@app.route('/my_bookings')
@login_required
def my_bookings():
    cur = mysql.connection.cursor()
    query = """
    SELECT b.id, ps.slot_number, b.vehicle_number, b.status, b.booking_time
    FROM bookings b JOIN parking_slots ps ON b.slot_id = ps.id 
    WHERE b.user_id = %s ORDER BY b.booking_time DESC
    """
    cur.execute(query, [session['user_id']])
    bookings = cur.fetchall()
    
    from datetime import datetime, timezone
    for b in bookings:
        if b['booking_time']:
            b['booking_time_iso'] = b['booking_time'].isoformat()
            
            # Pure mathematical offset calculation (Server UTC - Database UTC)
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            elapsed = (now_utc - b['booking_time']).total_seconds()
            b['elapsed'] = int(elapsed) if elapsed > 0 else 0
            
    cur.close()
    return render_template('my_bookings.html', bookings=bookings)

@app.route('/checkout/<int:booking_id>')
@login_required
def checkout(booking_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT b.*, ps.slot_number FROM bookings b JOIN parking_slots ps ON b.slot_id = ps.id WHERE b.id = %s AND b.user_id = %s AND b.status = 'Active'", (booking_id, session['user_id']))
    booking = cur.fetchone()
    cur.close()
    
    if not booking:
        flash('Booking not found or inactive.', 'danger')
        return redirect(url_for('my_bookings'))
        
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    duration = (now_utc - booking['booking_time']).total_seconds() / 3600
    hours = max(1, int(duration + 0.99)) # Round up to nearest hour
    cost = hours * 50 # 50 rupees an hour
    
    return render_template('checkout.html', booking=booking, hours=hours, cost=cost)

@app.route('/pay/<int:booking_id>', methods=['POST'])
@login_required
def pay(booking_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, slot_id, booking_time FROM bookings WHERE id = %s AND user_id = %s AND status = 'Active'", (booking_id, session['user_id']))
    booking = cur.fetchone()
    
    if booking:
        try:
            from datetime import datetime, timezone
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            duration = (now_utc - booking['booking_time']).total_seconds() / 3600
            hours = max(1, int(duration + 0.99))
            final_cost = hours * 50
            
            cur.execute("UPDATE bookings SET status = 'Completed', payment_status = 'Paid', exit_time = CURRENT_TIMESTAMP, total_cost = %s WHERE id = %s", [final_cost, booking_id])
            cur.execute("UPDATE parking_slots SET status = 'Available' WHERE id = %s", [booking['slot_id']])
            mysql.connection.commit()
            flash('Payment successful. Booking ended!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash('Error checking out.', 'danger')
    return redirect(url_for('my_bookings'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        default_vehicle = request.form['default_vehicle']
        try:
            cur.execute("UPDATE users SET default_vehicle = %s WHERE id = %s", (default_vehicle, session['user_id']))
            mysql.connection.commit()
            flash('Profile updated.', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash('Error updating.', 'danger')
            
    cur.execute("SELECT username, email, default_vehicle FROM users WHERE id = %s", [session['user_id']])
    user = cur.fetchone()
    cur.close()
    return render_template('profile.html', user=user)

@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM parking_slots")
    slots = cur.fetchall()
    
    cur.execute("SELECT b.id, u.username, ps.slot_number, b.vehicle_number, b.status FROM bookings b JOIN users u ON b.user_id = u.id JOIN parking_slots ps ON b.slot_id = ps.id ORDER BY b.booking_time DESC")
    bookings = cur.fetchall()
    
    # --- New Analytics Queries ---
    cur.execute("SELECT SUM(total_cost) AS total_revenue FROM bookings WHERE status = 'Completed'")
    revenue_data = cur.fetchone()
    total_revenue = revenue_data['total_revenue'] if revenue_data and revenue_data['total_revenue'] else 0.0
    
    cur.execute("SELECT ps.vehicle_type, SUM(b.total_cost) AS rev FROM bookings b JOIN parking_slots ps ON b.slot_id = ps.id WHERE b.status = 'Completed' GROUP BY ps.vehicle_type")
    rev_by_type = cur.fetchall()
    # Safely handle Decimal extraction
    car_revenue = 0.0
    bike_revenue = 0.0
    for item in rev_by_type:
        if item['vehicle_type'] == 'Car':
            car_revenue = float(item['rev'] or 0)
        elif item['vehicle_type'] == 'Bike':
            bike_revenue = float(item['rev'] or 0)
            
    cur.close()
    return render_template('admin_dashboard.html', slots=slots, bookings=bookings, total_revenue=total_revenue, car_revenue=car_revenue, bike_revenue=bike_revenue)

@app.route('/admin_clear/<int:slot_id>', methods=['POST'])
@admin_required
def admin_clear(slot_id):
    cur = mysql.connection.cursor()
    try:
        cur.execute("UPDATE parking_slots SET status = 'Available' WHERE id = %s", [slot_id])
        cur.execute("UPDATE bookings SET status = 'Completed', exit_time = CURRENT_TIMESTAMP WHERE slot_id = %s AND status = 'Active'", [slot_id])
        mysql.connection.commit()
        flash('Slot forcefully cleared.', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash('Error clearing slot.', 'danger')
    finally:
        cur.close()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
