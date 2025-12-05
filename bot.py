# bot.py - ربات گزارش‌گیری منتورینگ
import os
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread
import atexit

# ==================== تنظیمات ====================
TOKEN = os.environ.get("TOKEN", "توکن_ربات_خودت_را_اینجا_قرار_ده")
POINTS_PER_REPORT = 1  # هر پیام = ۱ امتیاز
WEB_PORT = 8080

# ==================== دیتابیس ====================
def init_db():
    conn = sqlite3.connect('mentors.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS mentors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        name TEXT,
        score INTEGER DEFAULT 0,
        last_report_date TEXT,
        total_reports INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mentor_username TEXT,
        report_text TEXT,
        date TEXT,
        FOREIGN KEY (mentor_username) REFERENCES mentors(username)
    )''')
    
    conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

# ==================== توابع کمکی ====================
def get_user_info(user):
    """دریافت اطلاعات کاربر"""
    username = user.username or f"user{user.id}"
    name = user.first_name or "بی‌نام"
    if user.last_name:
        name += f" {user.last_name}"
    return username, name

def get_score(username):
    """دریافت امتیاز کاربر"""
    c.execute("SELECT score FROM mentors WHERE username = ?", (username,))
    result = c.fetchone()
    return result[0] if result else 0

def get_total_reports(username):
    """دریافت تعداد گزارش‌ها"""
    c.execute("SELECT total_reports FROM mentors WHERE username = ?", (username,))
    result = c.fetchone()
    return result[0] if result else 0

# ==================== ربات تلگرام ====================
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پیام‌های گروه"""
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    message = update.message.text or ""
    user = update.message.from_user
    username, name = get_user_info(user)
    
    # فقط پیام‌های حاوی هشتگ #گزارش_هفتگی
    if "#گزارش_هفتگی" in message:
        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        try:
            # ذخیره گزارش
            c.execute(
                "INSERT INTO reports (mentor_username, report_text, date) VALUES (?, ?, ?)",
                (username, message[:500], today)  # فقط ۵۰۰ کاراکتر اول
            )
            
            # بررسی وجود منتور
            c.execute("SELECT score, total_reports FROM mentors WHERE username = ?", (username,))
            result = c.fetchone()
            
            if result:
                # آپدیت امتیاز
                new_score = result[0] + POINTS_PER_REPORT
                new_total = result[1] + 1
                c.execute(
                    "UPDATE mentors SET score = ?, last_report_date = ?, total_reports = ? WHERE username = ?",
                    (new_score, today, new_total, username)
                )
            else:
                # منتور جدید
                c.execute(
                    "INSERT INTO mentors (username, name, score, last_report_date, total_reports) VALUES (?, ?, ?, ?, ?)",
                    (username, name, POINTS_PER_REPORT, today, 1)
                )
            
            conn.commit()
            
            # پاسخ
            await update.message.reply_text(
                f"✅ **گزارش ثبت شد**\n"
                f"👤 {name}\n"
                f"⭐ +{POINTS_PER_REPORT} امتیاز\n"
                f"📊 مجموع: {get_score(username)} امتیاز\n"
                f"📅 {today.split()[0]}\n\n"
                f"🏆 /scoreboard"
            )
            
        except Exception as e:
            print(f"خطا در ذخیره گزارش: {e}")
            await update.message.reply_text("❌ خطا در ثبت گزارش")

async def scoreboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش جدول امتیازات"""
    try:
        c.execute("""
            SELECT name, score, total_reports, last_report_date 
            FROM mentors 
            ORDER BY score DESC 
            LIMIT 15
        """)
        mentors = c.fetchall()
        
        if not mentors:
            await update.message.reply_text("📭 هنوز گزارشی ثبت نشده است!")
            return
        
        text = f"🏆 **جدول امتیازات** 🏆\n"
        text += f"🎯 هر گزارش = {POINTS_PER_REPORT} امتیاز\n\n"
        
        for i, (name, score, total_reports, last_date) in enumerate(mentors, 1):
            medal = ""
            if i == 1: medal = "🥇 "
            elif i == 2: medal = "🥈 "
            elif i == 3: medal = "🥉 "
            
            text += f"{medal}{i}. **{name}**\n"
            text += f"   ⭐ {score} امتیاز\n"
            text += f"   📊 {total_reports} گزارش\n"
            if last_date:
                text += f"   📅 {last_date.split()[0]}\n"
            text += "\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        print(f"خطا در نمایش امتیازات: {e}")
        await update.message.reply_text("❌ خطا در نمایش جدول")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور راهنما"""
    await update.message.reply_text(
        f"🤖 **ربات گزارش‌گیری منتورینگ**\n\n"
        f"📝 هر پیام با هشتگ #گزارش_هفتگی = {POINTS_PER_REPORT} امتیاز\n\n"
        f"📋 **دستورات:**\n"
        f"/scoreboard - نمایش جدول امتیازات\n"
        f"/help - این راهنما\n\n"
        f"🎯 **نحوه استفاده:**\n"
        f"در گروه پیام بفرستید:\n"
        f"#گزارش_هفتگی\n"
        f"[متن گزارش شما]"
    )

# ==================== وب سرور ====================
app = Flask(__name__)

@app.route('/')
def scoreboard_web():
    """صفحه وب نمایش امتیازات"""
    try:
        c.execute("""
            SELECT name, username, score, total_reports, last_report_date 
            FROM mentors 
            ORDER BY score DESC
        """)
        mentors = c.fetchall()
        
        html = f"""
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>🏆 جدول امتیازات منتورینگ</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                }}
                .container {{
                    max-width: 1000px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(to right, #4CAF50, #2196F3);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 2.5rem;
                }}
                .stats {{
                    display: flex;
                    justify-content: space-around;
                    background: #f8f9fa;
                    padding: 20px;
                    border-bottom: 1px solid #dee2e6;
                }}
                .stat-box {{
                    text-align: center;
                }}
                .stat-number {{
                    font-size: 2rem;
                    font-weight: bold;
                    color: #2196F3;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                th, td {{
                    padding: 15px;
                    text-align: center;
                    border-bottom: 1px solid #e9ecef;
                }}
                th {{
                    background: #f1f3f5;
                    font-weight: 600;
                }}
                tr:hover {{
                    background: #f8f9fa;
                }}
                .rank-1 {{ color: gold; font-weight: bold; }}
                .rank-2 {{ color: silver; font-weight: bold; }}
                .rank-3 {{ color: #cd7f32; font-weight: bold; }}
                .score {{ color: #28a745; font-weight: bold; font-size: 1.2em; }}
                .footer {{
                    text-align: center;
                    padding: 20px;
                    color: #6c757d;
                    border-top: 1px solid #dee2e6;
                }}
                @media (max-width: 768px) {{
                    .stats {{ flex-direction: column; gap: 15px; }}
                    th, td {{ padding: 10px; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏆 جدول امتیازات منتورینگ</h1>
                    <p>هر گزارش با #گزارش_هفتگی = {POINTS_PER_REPORT} امتیاز</p>
                </div>
                
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-number">{len(mentors)}</div>
                        <div>تعداد منتورها</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{sum(m[3] for m in mentors)}</div>
                        <div>تعداد گزارش‌ها</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{sum(m[2] for m in mentors)}</div>
                        <div>امتیاز کل</div>
                    </div>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th width="80">رتبه</th>
                            <th>نام منتور</th>
                            <th width="100">امتیاز</th>
                            <th width="100">تعداد گزارش</th>
                            <th width="120">آخرین گزارش</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for i, (name, username, score, total_reports, last_date) in enumerate(mentors, 1):
            rank_class = ""
            if i == 1: rank_class = "rank-1"
            elif i == 2: rank_class = "rank-2"
            elif i == 3: rank_class = "rank-3"
            
            html += f"""
                        <tr>
                            <td class="{rank_class}">{i}</td>
                            <td>
                                <strong>{name}</strong><br>
                                <small style="color: #666;">@{username}</small>
                            </td>
                            <td><span class="score">{score}</span></td>
                            <td>{total_reports}</td>
                            <td>{last_date.split()[0] if last_date else '---'}</td>
                        </tr>
            """
        
        html += f"""
                    </tbody>
                </table>
                
                <div class="footer">
                    <p>🔄 آخرین بروزرسانی: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                    <p>🤖 ربات اتوماتیک گزارش‌گیری | هر گزارش = {POINTS_PER_REPORT} امتیاز</p>
                </div>
            </div>
            
            <script>
                // بروزرسانی خودکار هر ۳۰ ثانیه
                setTimeout(() => location.reload(), 30000);
            </script>
        </body>
        </html>
        """
        return html
        
    except Exception as e:
        return f"<h1>خطا در بارگذاری داده‌ها</h1><p>{str(e)}</p>"

# ==================== اجرا ====================
def run_flask():
    """اجرای وب سرور"""
    print(f"🌐 وب سرور در پورت {WEB_PORT} شروع شد")
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False)

def run_telegram_bot():
    """اجرای ربات تلگرام"""
    print("🤖 در حال راه‌اندازی ربات تلگرام...")
    
    application = Application.builder().token(TOKEN).build()
    
    # اضافه کردن دستورات
    application.add_handler(CommandHandler("start", help_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("scoreboard", scoreboard_command))
    application.add_handler(CommandHandler("scores", scoreboard_command))
    
    # هندلر پیام‌های گروه
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.GROUP & ~filters.COMMAND,
        handle_group_message
    ))
    
    print("✅ ربات تلگرام آماده است!")
    print(f"⭐ هر گزارش = {POINTS_PER_REPORT} امتیاز")
    print("📝 منتظر گزارش‌ها با هشتگ #گزارش_هفتگی...")
    
    application.run_polling()

def cleanup():
    """پاکسازی هنگام خروج"""
    print("🧹 در حال بستن اتصالات...")
    conn.close()

# ثبت تابع پاکسازی
atexit.register(cleanup)

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 ربات گزارش‌گیری منتورینگ")
    print("=" * 50)
    
    # بررسی توکن
    if TOKEN == "توکن_ربات_خودت_را_اینجا_قرار_ده":
        print("❌ لطفا توکن ربات را تنظیم کنید!")
        print("1. توکن را از @BotFather بگیرید")
        print("2. در کد خط 12 توکن را قرار دهید")
        print("3. یا از متغیر محیطی TOKEN استفاده کنید")
        exit()
    
    # اجرای همزمان وب سرور و ربات
    from threading import Thread
    
    # اجرای وب سرور در پس‌زمینه
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # اجرای ربات تلگرام (اصلی)
    run_telegram_bot()
