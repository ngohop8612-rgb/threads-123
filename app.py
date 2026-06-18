from flask import Flask, redirect, request, session, render_template, url_for
import requests, os, json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")

# Lấy từ Meta Developer App
APP_ID = os.environ.get("THREADS_APP_ID", "")
APP_SECRET = os.environ.get("THREADS_APP_SECRET", "")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000/callback")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Lưu token vào file JSON đơn giản
DB_FILE = "tokens.json"

def load_tokens():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_tokens(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ─── TRANG GỬI CHO KHÁCH HÀNG ─────────────────────────────────────
@app.route("/connect/<customer_name>")
def connect(customer_name):
    """Gửi link này cho khách hàng: /connect/ten-khach-hang"""
    session["customer_name"] = customer_name
    auth_url = (
        f"https://threads.net/oauth/authorize"
        f"?client_id={APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=threads_basic,threads_content_publish"
        f"&response_type=code"
        f"&state={customer_name}"
    )
    return render_template("connect.html", customer_name=customer_name, auth_url=auth_url)

# ─── CALLBACK SAU KHI KHÁCH ĐĂNG NHẬP ────────────────────────────
@app.route("/callback")
def callback():
    code = request.args.get("code")
    customer_name = request.args.get("state", "unknown")

    if not code:
        return "Lỗi: Không nhận được code từ Meta", 400

    # Đổi code lấy short-lived token
    res = requests.post("https://graph.threads.net/oauth/access_token", data={
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
        "grant_type": "authorization_code"
    })
    token_data = res.json()
    short_token = token_data.get("access_token")

    if not short_token:
        return f"Lỗi lấy token: {token_data}", 400

    # Đổi sang long-lived token (60 ngày)
    res2 = requests.get("https://graph.threads.net/access_token", params={
        "grant_type": "th_exchange_token",
        "client_secret": APP_SECRET,
        "access_token": short_token
    })
    long_token_data = res2.json()
    long_token = long_token_data.get("access_token", short_token)

    # Lấy thông tin tài khoản
    res3 = requests.get("https://graph.threads.net/v1.0/me", params={
        "fields": "id,username",
        "access_token": long_token
    })
    user_info = res3.json()

    # Lưu vào database
    tokens = load_tokens()
    tokens[customer_name] = {
        "username": user_info.get("username", "unknown"),
        "threads_id": user_info.get("id", ""),
        "token": long_token,
        "connected_at": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    save_tokens(tokens)

    return render_template("success.html", 
                         customer_name=customer_name,
                         username=user_info.get("username", ""))

# ─── DASHBOARD ADMIN ──────────────────────────────────────────────
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
        else:
            return render_template("admin_login.html", error="Sai mật khẩu!")

    if not session.get("admin"):
        return render_template("admin_login.html", error=None)

    tokens = load_tokens()
    return render_template("dashboard.html", accounts=tokens)

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
