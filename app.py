from flask import Flask, request, jsonify
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity, verify_jwt_in_request
import pyodbc
import regex as re
from datetime import timedelta
import secrets
import random

# Securely generate a secret key
SECRET_KEY = secrets.token_urlsafe(32)

# Connection details
DRIVER = "ODBC Driver 17 for SQL Server" #CHANGE WITH DRIVER NAME
SERVER = "Enter your server name"
DATABASE = "Enter your DATABASE name"
UID = "USERID"
PWD = "PASSWORD"

app = Flask(__name__)

# JWT configuration
app.config['SECRET_KEY'] = SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)
jwt = JWTManager(app)


# Regex patterns
gmail_regex = r"[a-zA-Z0-9]{4,}(?:\.[a-zA-Z0-9]+)?@[a-z]{2,}\.[a-z]{1,5}(?:\.[a-z]{1,5})?$"
name_regex = r"^[A-Za-z]{3,10} [A-Za-z]{3,10}$"
user_regex = r"^[A-Za-z0-9]{3,10}$"
pass_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])"

# Store OTPs for users
otp_store = {}

def db_conn():
    conn = pyodbc.connect(
        driver=DRIVER,
        server=SERVER,
        database=DATABASE,
        uid=UID,
        pwd=PWD,
        trustedconnection="Yes",
    )
    return conn

#demo function 
def fun(img_file):
    return "File recieved"

@app.route("/", methods=["GET"])
def welcome():
    return jsonify({"message": "Welcome"})

@app.route('/fetchImage', methods=["POST"])
def fetch_image():
    img_data = request.form.get('image')
    if not img_data:
        return jsonify({"message": "No image data provided"})
    return jsonify(fun(img_data))

@app.route("/data", methods=["GET"])
def get_data():
    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Emp")
    rows = cursor.fetchall()
    conn.close()
    data = []
    for row in rows:
        data.append(
            {
                "id": row[0],
                "name": row[1],
                "userName": row[2],
                "password": row[3],
                "email": row[4],
            }
        )
    return jsonify(data)

@app.route("/signUp", methods=["POST"])
def sign_up():
    conn = db_conn()
    cursor = conn.cursor()
    n_name = request.form.get("name")
    n_userName = request.form.get("userName")
    n_password = request.form.get("password")
    n_email = request.form.get("email")

    if not all([n_name, n_userName, n_password, n_email]):
        return jsonify({"message": "Please fill in all fields"})
    if not re.match(gmail_regex, n_email):
        return jsonify({"message": "Please enter a valid Gmail"})
    if not re.match(name_regex, n_name):
        return jsonify({"message": "Name should be in the form of FirstName LastName"})
    if not re.match(user_regex, n_userName):
        return jsonify({"message": "Username must be between 3 and 10 characters, and can include only letters and numbers"})
    if len(n_password) < 4:
        return jsonify({"message": "Password is too short"})
    if not re.match(pass_regex, n_password):
        return jsonify({"message": "Please use a strong password with upper, lower case letters, digits & special symbols"})

    cursor.execute("SELECT userName FROM Emp WHERE userName=?", (n_userName,))
    existing_username = cursor.fetchone()
    if existing_username:
        return jsonify({"message": "Username already exists"})

    sql = "INSERT INTO Emp (name, userName, pass, email) VALUES (?, ?, ?, ?)"
    cursor.execute(sql, (n_name, n_userName, n_password, n_email))
    conn.commit()
    conn.close()
    return jsonify({"message": "Signed up successfully"})

@app.route("/login", methods=["POST"])
def login():
    conn = db_conn()
    cursor = conn.cursor()
    userName = request.form.get("userName")
    password = request.form.get("password")

    if not all([userName, password]):
        return jsonify({"message": "Please fill all the forms"})

    cursor.execute("SELECT * FROM Emp WHERE userName = ?", (userName,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        if password == user_data[3]:
            access_token = create_access_token(identity=user_data[2])
            return jsonify(
                {
                    "message": "Login successful",
                    "access_token": access_token,
                    "user": {
                        "id": user_data[0],
                        "name": user_data[1],
                        "userName": userName,
                        "password": password,
                    },
                }
            )
        else:
            return jsonify({"message": "Incorrect password."})
    else:
        return jsonify({"message": "User not found."})

@app.route("/uservalidate", methods=["GET", "POST"])
def user_validate():
    if request.method == "GET":
        try:
            verify_jwt_in_request()
            current_user = get_jwt_identity()
            return jsonify({"message": "User validated", "user": current_user})
        except Exception as e:
            return jsonify({"message": "Token is missing or invalid", "error": str(e)}), 401
    elif request.method == "POST":
        data = get_data().json
        usernames = [user["userName"] for user in data]
        passwords = [user["password"] for user in data]

        userName = request.form["userName"]
        password = request.form["password"]

        if userName in usernames and password in passwords:
            return jsonify({"message": "User exists"})
        if userName in usernames and password not in passwords:
            return jsonify({"message": "Password is incorrect"})
        else:
            return jsonify({"message": "User does not exist"})

@app.route("/deleteUser", methods=["GET", "POST"])
def delete_user():
    conn = db_conn()
    cursor = conn.cursor()

    if request.method == "GET":
        try:
            verify_jwt_in_request()
            current_user = get_jwt_identity()

            cursor.execute("SELECT * FROM Emp WHERE userName=?", (current_user,))
            user_to_delete = cursor.fetchone()

            if user_to_delete:
                cursor.execute("DELETE FROM Emp WHERE userName=?", (current_user,))
                conn.commit()
                conn.close()
                return jsonify({"message": f"User '{current_user}' deleted successfully."})
            else:
                conn.close()
                return jsonify({"message": f"User '{current_user}' does not exist."})
        except Exception as e:
            return jsonify({"message": "Token is missing or invalid", "error": str(e)}), 401

    elif request.method == "POST":
        username_to_delete = request.form.get("userName")
        user_password = request.form.get("password")

        if not all([username_to_delete, user_password]):
            return jsonify({"message": "Fill all the fields"})

        cursor.execute("SELECT * FROM Emp WHERE userName=?", (username_to_delete,))
        user_to_delete = cursor.fetchone()

        if user_to_delete:
            if user_password == user_to_delete[3]:
                cursor.execute("DELETE FROM Emp WHERE userName=?", (username_to_delete,))
                conn.commit()
                conn.close()
                return jsonify({"message": f"User '{username_to_delete}' deleted successfully."})
            else:
                conn.close()
                return jsonify({"message": "Incorrect password."})
        else:
            conn.close()
            return jsonify({"message": f"User '{username_to_delete}' does not exist."})

@app.route("/forgotPassword", methods=["POST"])
def forgot_password():
    userName = request.form.get("userName")

    if not userName:
        return jsonify({"message": "Please provide a username"})

    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Emp WHERE userName=?", (userName,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        otp = random.randint(1000, 9999)
        otp_store[userName] = otp
        return jsonify({"message": "OTP generated", "otp": otp})
    else:
        return jsonify({"message": "User not found"})

@app.route("/resetPassword", methods=["POST"])
def reset_password():
    userName = request.form.get("userName")
    otp = request.form.get("otp")
    new_password = request.form.get("newPassword")

    if not all([userName, otp, new_password]):
        return jsonify({"message": "Please provide username, otp, and new password"})

    if userName not in otp_store or otp_store[userName] != int(otp):
        return jsonify({"message": "Invalid or expired OTP"})

    if len(new_password) < 4:
        return jsonify({"message": "Password is too short"})
    if not re.match(pass_regex, new_password):
        return jsonify({"message": "Please use a strong password with upper, lower case letters, digits & special symbols"})

    conn = db_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE Emp SET pass=? WHERE userName=?", (new_password, userName))
    conn.commit()
    conn.close()

    del otp_store[userName]
    return jsonify({"message": "Password reset successfully"})

@app.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    current_user_id = get_jwt_identity()
    return jsonify(logged_in_as=current_user_id)

if __name__ == "__main__":
    app.run(debug=True)
