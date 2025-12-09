import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta, datetime
from collections import defaultdict

# --- 基本設定 ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-secret-key')

# DATABASE_URL の処理（Railwayのpostgres://をpostgresql://に変換）
database_url = os.environ.get('DATABASE_URL', 'sqlite:///reviews.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# LINE Messaging API 設定
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')

db = SQLAlchemy(app)

# --- ★★★ 復習間隔をここで自由に設定 ★★★ ---
# 時間単位: 'h'をつける（1h=1時間後、3h=3時間後など）
# 日単位: 数字のみ
REVIEW_INTERVALS_HOURS = [1, 3, 6]  # 当日: 1時間後、3時間後、6時間後
REVIEW_INTERVALS_DAYS = [1, 3, 7, 16, 35, 60, 120]  # 翌日以降


# --- データベースのモデル定義 ---
class ReviewItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(100), nullable=False, default='一般')
    date_added = db.Column(db.Date, nullable=False, default=date.today)
    review_level = db.Column(db.Integer, nullable=False, default=0)
    next_review_date = db.Column(db.Date, nullable=False)

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
        review_level = 0
        interval_days = REVIEW_INTERVALS_DAYS[0]
        if initial_confidence == 'good' and len(REVIEW_INTERVALS_DAYS) > 1:
            review_level = 1
            interval_days = REVIEW_INTERVALS_DAYS[1]
        new_item = ReviewItem(
            topic=topic, url=url, category=category, review_level=review_level,
            next_review_date=date.today() + timedelta(days=interval_days)
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f"追加しました", "success")
        if 'bookmarklet' in request.args:
            return "<script>window.close();</script>"
        return redirect(url_for('index'))
    initial_topic = request.args.get('title', '')
    initial_url = request.args.get('url', '')
    return render_template('add_form.html', initial_topic=initial_topic, initial_url=initial_url)

# --- 「復習完了」ボタンの処理 ---
@app.route('/review/<int:item_id>', methods=['POST'])
def review_item(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    confidence = request.form.get('confidence')
    if confidence == 'again':
        item.review_level = 0
        interval_days = REVIEW_INTERVALS_DAYS[0]
        item.next_review_date = date.today() + timedelta(days=interval_days)
        flash(f"もう1回", "info")
    else:
        if item.review_level < len(REVIEW_INTERVALS_DAYS) - 1:
             item.review_level += 1
        interval_days = REVIEW_INTERVALS_DAYS[item.review_level]
        item.next_review_date = date.today() + timedelta(days=interval_days)
        flash(f"覚えた", "success")
    db.session.commit()
    return redirect(url_for('index'))

# --- 復習日を直接更新する処理 ---
@app.route('/update_date/<int:item_id>', methods=['POST'])
def update_date(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    new_date_str = request.form.get('new_date')
    if new_date_str:
        try:
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            item.next_review_date = new_date
            db.session.commit()
            flash(f"「{item.topic}」の次回復習日を{new_date_str}に変更しました。", "success")
        except ValueError:
            flash("日付の形式が正しくありません。", "danger")
    return redirect(url_for('index'))

# --- 項目を削除する処理 ---
@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash(f"「{item.topic}」を削除しました。", "info")
    return redirect(url_for('index'))

# --- ★★★【新機能】項目を編集する処理 ★★★ ---
@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    if request.method == 'POST':
        # POSTリクエスト: フォームから送信されたデータで更新
        item.topic = request.form['topic']
        item.url = request.form['url']
        item.category = request.form.get('category', '一般').strip()
        if not item.category:
            item.category = '一般'

        db.session.commit()
        flash(f"「{item.topic}」を更新しました。", "success")
        return redirect(url_for('index'))

    # GETリクエスト: 編集ページを表示
    return render_template('edit_item.html', item=item)

# --- ブックマークレットの説明ページ ---
@app.route('/bookmarklet')
def bookmarklet():
    return render_template('bookmarklet.html')

# --- ★★★【API】復習待ちの項目数を取得 ★★★ ---
@app.route('/api/pending-reviews')
def api_pending_reviews():
    today = date.today()
    items = ReviewItem.query.filter(ReviewItem.next_review_date <= today).all()
    return jsonify({
        'count': len(items),
        'items': [{
            'id': item.id,
            'topic': item.topic,
            'category': item.category,
            'next_review_date': item.next_review_date.strftime('%Y-%m-%d'),
            'review_level': item.review_level
        } for item in items]
    })

# --- ★★★【API】項目を編集（インライン用） ★★★ ---
@app.route('/api/edit/<int:item_id>', methods=['POST'])
def api_edit_item(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    data = request.get_json()
    if data and data.get('topic'):
        item.topic = data['topic'].strip()
        if data.get('url') is not None:
            item.url = data['url']
        db.session.commit()
        return jsonify({'success': True, 'topic': item.topic})
    return jsonify({'error': '項目名は必須だよ。'}), 400

# --- ★★★【API】全項目を取得 ★★★ ---
@app.route('/api/items')
def api_items():
    items = ReviewItem.query.order_by(ReviewItem.next_review_date).all()
    return jsonify({
        'items': [{
            'id': item.id,
            'topic': item.topic,
            'url': item.url,
            'category': item.category,
            'date_added': item.date_added.strftime('%Y-%m-%d'),
            'next_review_date': item.next_review_date.strftime('%Y-%m-%d'),
            'review_level': item.review_level
        } for item in items]
    })

# --- ★★★【API】バックアップエクスポート ★★★ ---
@app.route('/api/export')
def api_export():
    items = ReviewItem.query.all()
    data = {
        'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'items': [{
            'topic': item.topic,
            'url': item.url,
            'category': item.category,
            'date_added': item.date_added.strftime('%Y-%m-%d'),
            'next_review_date': item.next_review_date.strftime('%Y-%m-%d'),
            'review_level': item.review_level
        } for item in items]
    }
    return jsonify(data)

# --- ★★★【API】バックアップインポート ★★★ ---
@app.route('/api/import', methods=['POST'])
def api_import():
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': '無効なデータ'}), 400
    
    imported = 0
    for item_data in data['items']:
        if not item_data.get('topic'):
            continue
        new_item = ReviewItem(
            topic=item_data['topic'],
            url=item_data.get('url', ''),
            category=item_data.get('category', '一般'),
            date_added=datetime.strptime(item_data.get('date_added', date.today().strftime('%Y-%m-%d')), '%Y-%m-%d').date(),
            next_review_date=datetime.strptime(item_data.get('next_review_date', date.today().strftime('%Y-%m-%d')), '%Y-%m-%d').date(),
            review_level=item_data.get('review_level', 0)
        )
        db.session.add(new_item)
        imported += 1
    
    db.session.commit()
    return jsonify({'success': True, 'imported': imported})

# --- ★★★【API】項目を追加（JSON対応） ★★★ ---
@app.route('/api/add', methods=['POST'])
def api_add_item():
    data = request.get_json()
    if not data or not data.get('topic'):
        return jsonify({'error': '項目名は必須だよ。'}), 400
    
    topic = data.get('topic')
    url = data.get('url', '')
    category = data.get('category', '一般').strip() or '一般'
    initial_confidence = data.get('initial_confidence', 'again')
    
    review_level = 0
    interval_days = REVIEW_INTERVALS_DAYS[0]
    if initial_confidence == 'good' and len(REVIEW_INTERVALS_DAYS) > 1:
        review_level = 1
        interval_days = REVIEW_INTERVALS_DAYS[1]
    
    new_item = ReviewItem(
        topic=topic, url=url, category=category, review_level=review_level,
        next_review_date=date.today() + timedelta(days=interval_days)
    )
    db.session.add(new_item)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'item': {
            'id': new_item.id,
            'topic': new_item.topic,
            'next_review_date': new_item.next_review_date.strftime('%Y-%m-%d'),
            'interval_days': interval_days
        }
    })

# --- ★★★【API】復習完了 ★★★ ---
@app.route('/api/review/<int:item_id>', methods=['POST'])
def api_review_item(item_id):
    item = ReviewItem.query.get_or_404(item_id)
    data = request.get_json() or {}
    confidence = data.get('confidence', 'good')
    
    if confidence == 'again':
        item.review_level = 0
        interval_days = REVIEW_INTERVALS_DAYS[0]
    else:
        if item.review_level < len(REVIEW_INTERVALS_DAYS) - 1:
            item.review_level += 1
        interval_days = REVIEW_INTERVALS_DAYS[item.review_level]
    
    item.next_review_date = date.today() + timedelta(days=interval_days)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'item': {
            'id': item.id,
            'topic': item.topic,
            'next_review_date': item.next_review_date.strftime('%Y-%m-%d'),
            'review_level': item.review_level,
            'interval_days': interval_days
        }
    })

# --- ★★★【LINE Messaging API】★★★ ---
def send_line_message(message):
    """LINE Messaging APIでプッシュ通知を送信"""
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        return False, "環境変数が設定されていません"
    
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    data = {
        'to': LINE_USER_ID,
        'messages': [{
            'type': 'text',
            'text': message
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return True, "送信成功"
        else:
            return False, f"エラー: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"例外: {str(e)}"

# デバッグ用: 環境変数の確認
@app.route('/api/debug-line')
def debug_line():
    return jsonify({
        'token_set': bool(LINE_CHANNEL_ACCESS_TOKEN),
        'token_preview': LINE_CHANNEL_ACCESS_TOKEN[:20] + '...' if LINE_CHANNEL_ACCESS_TOKEN else None,
        'user_id_set': bool(LINE_USER_ID),
        'user_id': LINE_USER_ID
    })

@app.route('/api/send-reminder', methods=['POST'])
def api_send_reminder():
    """今日の復習項目をLINEで通知（カテゴリ別）"""
    today = date.today()
    items = ReviewItem.query.filter(ReviewItem.next_review_date <= today).order_by(ReviewItem.category).all()
    
    if not items:
        success, detail = send_line_message("[復習] 今日の復習はありません")
        return jsonify({
            'success': success,
            'message': '通知を送信しました' if success else f'エラー: {detail}',
            'detail': detail
        })
    
    # カテゴリ別に整理
    by_cat = defaultdict(list)
    for item in items:
        by_cat[item.category].append(item)
    
    message = f"[復習] {len(items)}件\n"
    
    for cat, cat_items in by_cat.items():
        message += f"\n[{cat}]\n"
        for item in cat_items:
            # Lvも表示
            message += f"- {item.topic} (Lv.{item.review_level})\n"
    
    message += f"\nhttps://fukusyu-production.up.railway.app/"
    
    success, detail = send_line_message(message)
    
    return jsonify({
        'success': success,
        'count': len(items),
        'message': 'LINE通知を送信しました' if success else f'LINE通知エラー: {detail}'
    })

@app.route('/api/cron-reminder')
def cron_reminder():
    """外部cronサービスから呼び出し用（GETでもOK）"""
    today = date.today()
    items = ReviewItem.query.filter(ReviewItem.next_review_date <= today).order_by(ReviewItem.category).all()
    
    if not items:
        return jsonify({'success': True, 'message': '今日の復習はありません', 'count': 0})
    
    # カテゴリ別に整理
    by_cat = defaultdict(list)
    for item in items:
        by_cat[item.category].append(item)
    
    message = f"[復習] {len(items)}件\n"
    
    for cat, cat_items in by_cat.items():
        message += f"\n[{cat}]\n"
        for item in cat_items:
            message += f"- {item.topic}\n"
    
    message += f"\nhttps://fukusyu-production.up.railway.app/"
    
    success, detail = send_line_message(message)
    
    return jsonify({
        'success': success,
        'count': len(items),
        'detail': detail
    })

# --- データベース初期化 ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
