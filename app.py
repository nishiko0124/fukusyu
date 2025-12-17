import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta, datetime
from collections import defaultdict

# --- 基本設定 ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-secret-key')

# DATABASE_URL の処理
database_url = os.environ.get('DATABASE_URL', 'sqlite:///reviews.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# LINE Messaging API 設定
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')

db = SQLAlchemy(app)

# --- ★★★ 復習間隔の設定（ここを変更しました） ★★★ ---
# 1日後(Lv0) -> 3日後(Lv1) -> 7日後(Lv2) -> 14日後(Lv3) -> 30日後(Lv4) -> 完了
REVIEW_INTERVALS_DAYS = [1, 3, 7, 14, 30]

# 完了後、または上記リストを超えた後のループ間隔
COMPLETED_INTERVAL = 30


# --- データベースのモデル定義 ---
class ReviewItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(100), nullable=False, default='一般')
    date_added = db.Column(db.Date, nullable=False, default=date.today)
    review_level = db.Column(db.Integer, nullable=False, default=0)
    next_review_date = db.Column(db.Date, nullable=False)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f'<ReviewItem {self.topic}>'

# --- メインページ ---
@app.route('/')
def index():
    today = date.today()
    items_to_review_by_cat = defaultdict(list)
    all_items_by_cat = defaultdict(list)
    items_to_review = ReviewItem.query.filter(ReviewItem.next_review_date <= today).order_by(ReviewItem.category, ReviewItem.next_review_date).all()
    all_items = ReviewItem.query.order_by(ReviewItem.category, ReviewItem.next_review_date).all()
    for item in items_to_review:
        items_to_review_by_cat[item.category].append(item)
    for item in all_items:
        all_items_by_cat[item.category].append(item)
    return render_template(
        'index.html',
        items_by_cat=items_to_review_by_cat,
        all_items_by_cat=all_items_by_cat,
        today_str=today.strftime('%Y-%m-%d')
    )

# --- 新しい項目を追加する処理 ---
@app.route('/add', methods=['GET', 'POST'])
def add_item():
    if request.method == 'POST':
        topic = request.form.get('topic')
        url = request.form.get('url')
        category = request.form.get('category', '一般').strip()
        initial_confidence = request.form.get('initial_confidence', 'again')
        
        if not topic:
            flash("項目名は必須だよ。。", "danger")
            return redirect(url_for('index'))
        if not category:
            category = '一般'
            
        # 初期レベルの設定
        review_level = 0
        interval_days = REVIEW_INTERVALS_DAYS[0] # デフォルトは1日後
        
        # 「OK（Lv.1）」で登録した場合、次のステップ（3日後）からスタート
        if initial_confidence == 'good' and len(REVIEW_INTERVALS_DAYS) > 1:
            review_level = 1
            interval_days = REVIEW_INTERVALS_DAYS[1]
            
        new_item = ReviewItem(
            topic=topic, url=url, category=category, review_level=review_level,
            next_review_date=date.today() + timedelta(days=interval_days)
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f"追加しました（次は{interval_days}日後）", "success")
        return redirect(url_for('index'))
    return render_template('add_form.html') # 通常はindexから呼ばれるのでここはあまり使われない

# --- 「復習完了」ボタンの処理 ---
@app.route('/review/<int:item_id>', methods=['POST'])
def review_item(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    confidence = request.form.get('confidence')
    
    if confidence == 'again':
        # 忘れた場合: Lv.0（1日後）に戻る
        item.review_level = 0
        item.is_completed = False
        interval_days = REVIEW_INTERVALS_DAYS[0]
        item.next_review_date = date.today() + timedelta(days=interval_days)
        flash(f"リセットしました（次は明日）", "info")
    else:
        # 覚えた場合
        if item.is_completed:
            # 完了済みのループ: 30日後
            item.next_review_date = date.today() + timedelta(days=COMPLETED_INTERVAL)
            flash(f"完了維持（次は{COMPLETED_INTERVAL}日後）", "success")
        elif item.review_level >= len(REVIEW_INTERVALS_DAYS) - 1:
            # 最終レベル到達: 完了モードへ
            item.is_completed = True
            item.next_review_date = date.today() + timedelta(days=COMPLETED_INTERVAL)
            flash(f"全課程終了！次は{COMPLETED_INTERVAL}日後", "success")
        else:
            # 次のレベルへ昇格
            item.review_level += 1
            interval_days = REVIEW_INTERVALS_DAYS[item.review_level]
            item.next_review_date = date.today() + timedelta(days=interval_days)
            flash(f"レベルアップ！次は{interval_days}日後", "success")
            
    db.session.commit()
    return redirect(url_for('index'))

# --- 復習日を直接更新 ---
@app.route('/update_date/<int:item_id>', methods=['POST'])
def update_date(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    new_date_str = request.form.get('new_date')
    if new_date_str:
        try:
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            item.next_review_date = new_date
            db.session.commit()
        except ValueError:
            pass
    return redirect(url_for('index'))

# --- 項目削除 ---
@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('index'))

# --- 項目編集（HTMLフォーム用/旧互換） ---
@app.route('/edit/<int:item_id>', methods=['POST'])
def edit_item(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    if request.method == 'POST':
        item.topic = request.form.get('topic', item.topic)
        item.url = request.form.get('url', item.url)
        item.category = request.form.get('category', '一般').strip() or '一般'
        db.session.commit()
    return redirect(url_for('index'))

# --- API: 編集（インライン用） ---
@app.route('/api/edit/<int:item_id>', methods=['POST'])
def api_edit_item(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    data = request.get_json()
    if data and data.get('topic'):
        item.topic = data['topic'].strip()
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Error'}), 400

# --- API: 通知送信 ---
@app.route('/api/send-reminder', methods=['GET', 'POST'])
def api_send_reminder():
    today = date.today()
    items = ReviewItem.query.filter(ReviewItem.next_review_date <= today).order_by(ReviewItem.category).all()
    
    if not items:
        send_line_message("今日の復習はありません🎉")
        return jsonify({'success': True, 'message': '復習なし'})
    
    # カテゴリ別に整理
    by_cat = defaultdict(list)
    for item in items:
        by_cat[item.category].append(item)
    
    msg = f"復習 {len(items)}件あります！\n"
    for cat, cat_items in by_cat.items():
        msg += f"\n【{cat}】\n"
        for item in cat_items:
            msg += f"・{item.topic}\n"
    
    msg += "\nhttps://fukusyu-production.up.railway.app/"
    
    res, detail = send_line_message(msg)
    return jsonify({'success': res, 'message': detail})

# --- LINE送信関数 ---
def send_line_message(message):
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        return False, "LINE設定がありません"
    
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    data = {
        'to': LINE_USER_ID,
        'messages': [{'type': 'text', 'text': message}]
    }
    try:
        r = requests.post(url, headers=headers, json=data)
        return r.status_code == 200, r.text
    except Exception as e:
        return False, str(e)

# --- バックアップ機能 ---
@app.route('/api/export')
def api_export():
    items = ReviewItem.query.all()
    data = {'items': [{
        'topic': i.topic, 'url': i.url, 'category': i.category,
        'date_added': i.date_added.strftime('%Y-%m-%d'),
        'next_review_date': i.next_review_date.strftime('%Y-%m-%d'),
        'review_level': i.review_level
    } for i in items]}
    return jsonify(data)

@app.route('/api/import', methods=['POST'])
def api_import():
    data = request.get_json()
    if not data or 'items' not in data: return jsonify({'error': 'No data'}), 400
    for d in data['items']:
        if not d.get('topic'): continue
        db.session.add(ReviewItem(
            topic=d['topic'], url=d.get('url',''), category=d.get('category','一般'),
            date_added=datetime.strptime(d.get('date_added', date.today().strftime('%Y-%m-%d')), '%Y-%m-%d').date(),
            next_review_date=datetime.strptime(d.get('next_review_date', date.today().strftime('%Y-%m-%d')), '%Y-%m-%d').date(),
            review_level=d.get('review_level', 0)
        ))
    db.session.commit()
    return jsonify({'success': True})

# --- DB初期化 ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)