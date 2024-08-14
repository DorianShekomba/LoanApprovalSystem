from flask import Flask, render_template, request, redirect, session, url_for, flash
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')  # Use environment variable for secret key

# In-memory storage for users
users = {}

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Load the Excel file
file_path = os.path.join(os.getcwd(), 'data', 'Final_data.xlsx')
try:
    excel_data = pd.read_excel(file_path)
except Exception as e:
    logging.error(f"Error loading Excel file: {e}")

# Convert 'NUMBER' column to string and handle missing values
excel_data['NUMBER'] = excel_data['NUMBER'].fillna('').astype(str)

# Ensure all numeric columns are displayed as integers
for col in ['FDY SCORING', 'TABVPM_SCORING', 'DVB_final']:
    if col in excel_data.columns:
        excel_data[col] = excel_data[col].fillna(0).astype(int)
    else:
        logging.warning(f"Column {col} not found in the data")

# Convert MODEL_NAME to strings and handle missing values
excel_data['MODEL_NAME'] = excel_data['MODEL_NAME'].fillna('').astype(str)

# Define the new scoring system based on the sum of FDY SCORING, TABVPM_SCORING, and DVB_final
def compute_score(row):
    try:
        total_score = row['FDY SCORING'] + row['TABVPM_SCORING'] + row['DVB_final']
        return total_score
    except KeyError as e:
        logging.error(f"KeyError while computing score: {e}")
        return 0

# Apply the scoring system to the dataset
excel_data['Final Score'] = excel_data.apply(compute_score, axis=1)

@app.route('/')
def home():
    if 'user' not in session:
        logging.debug("User not in session, redirecting to login")
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        account_type = request.form['account_type']
        hashed_password = generate_password_hash(password)  # Using default method

        logging.debug(f"Attempting to register user: {username}")

        if username in users:
            flash("Username already exists")
            logging.warning("Username already exists")
            return redirect(url_for('register'))

        users[username] = {
            'password': hashed_password,
            'account_type': account_type
        }

        logging.debug(f"User registered: {username} with account type: {account_type}")
        flash("Registration successful")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        logging.debug(f"Attempting to log in user: {username}")

        user = users.get(username)

        if user:
            logging.debug(f"Found user: {user}")
        else:
            logging.warning(f"User not found: {username}")

        if user and check_password_hash(user['password'], password):
            session['user'] = username
            session['account_type'] = user['account_type']
            logging.debug(f"Login successful for user: {username} with account type: {user['account_type']}")
            if user['account_type'] == 'admin':
                return redirect(url_for('home'))
            else:
                return redirect(url_for('enter_number'))
        else:
            flash("Invalid credentials")
            logging.warning("Invalid credentials provided")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    logging.debug("Logging out user")
    session.pop('user', None)
    session.pop('account_type', None)
    return redirect(url_for('login'))

@app.route('/enter_number', methods=['GET', 'POST'])
def enter_number():
    if 'user' not in session or session['account_type'] == 'admin':
        logging.debug("User not in session or is an admin, redirecting to login")
        return redirect(url_for('login'))

    if request.method == 'POST':
        number = request.form['number']
        session['number'] = number
        return redirect(url_for('user_credit_score'))

    return render_template('enter_number.html')

@app.route('/user_credit_score')
def user_credit_score():
    if 'user' not in session or 'number' not in session:
        logging.debug("User not in session or number not provided, redirecting to login")
        return redirect(url_for('login'))

    number = session['number']
    user_data = excel_data[excel_data['NUMBER'] == number].to_dict(orient='records')
    if not user_data:
        logging.warning(f"No data found for the given number: {number}")
        return "No data found for the given number", 404
    return render_template('user_score.html', data=user_data[0])

@app.route('/credit_score', methods=['GET', 'POST'])
def credit_score():
    if 'user' not in session:
        logging.debug("User not in session, redirecting to login")
        return redirect(url_for('login'))

    if session['account_type'] == 'admin':
        filtered_data = excel_data
        if request.method == 'POST':
            search_number = request.form.get('search_number')
            tabvpm_min = request.form.get('tabvpm_min')
            tabvpm_max = request.form.get('tabvpm_max')
            fdy_min = request.form.get('fdy_min')
            fdy_max = request.form.get('fdy_max')

            if search_number:
                filtered_data = filtered_data[filtered_data['NUMBER'].astype(str).str.contains(search_number)]
            if tabvpm_min:
                filtered_data = filtered_data[filtered_data['TABVPM'] >= int(tabvpm_min)]
            if tabvpm_max:
                filtered_data = filtered_data[filtered_data['TABVPM'] <= int(tabvpm_max)]
            if fdy_min:
                filtered_data = filtered_data[filtered_data['FDY IN MONTH'] >= int(fdy_min)]
            if fdy_max:
                filtered_data = filtered_data[filtered_data['FDY IN MONTH'] <= int(fdy_max)]
        filtered_data = filtered_data.sort_values(by='Final Score', ascending=False).to_dict(orient='records')
        return render_template('credit_score.html', data=filtered_data)
    else:
        return redirect(url_for('enter_number'))

@app.route('/data')
def data():
    if 'user' not in session or session['account_type'] != 'admin':
        logging.debug("User not in session or not admin, redirecting to login")
        return redirect(url_for('login'))
    data = excel_data.to_dict(orient='records')
    columns = excel_data.columns
    return render_template('data.html', data=data, columns=columns)

@app.route('/detail/<number>')
def detail(number):
    if 'user' not in session or session['account_type'] != 'admin':
        logging.debug("User not in session or not admin, redirecting to login")
        return redirect(url_for('login'))
    row = excel_data[excel_data['NUMBER'] == number].to_dict(orient='records')[0]
    return render_template('detail.html', row=row)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
