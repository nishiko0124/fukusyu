import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta, datetime
from collections import defaultdict

# --- 基本設定 ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- ★★★ 復習間隔をここで自由に設定 ★★★ ---
REVIEW_INTERVALS = [1, 3, 7, 16, 35, 60, 120]


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
            flash("項目名は必須です。", "danger")
            return redirect(url_for('index'))
        if not category:
            category = '一般'
        review_level = 0
        interval_days = REVIEW_INTERVALS[0]
        if initial_confidence == 'good' and len(REVIEW_INTERVALS) > 1:
            review_level = 1
            interval_days = REVIEW_INTERVALS[1]
        new_item = ReviewItem(
            topic=topic, url=url, category=category, review_level=review_level,
            next_review_date=date.today() + timedelta(days=interval_days)
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f"「{topic}」を登録しました。次は{interval_days}日後です！", "success")
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
        interval_days = REVIEW_INTERVALS[0]
        item.next_review_date = date.today() + timedelta(days=interval_days)
        flash(f"「{item.topic}」を明日もう一度復習しましょう。", "info")
    else:
        if item.review_level < len(REVIEW_INTERVALS) - 1:
             item.review_level += 1
        interval_days = REVIEW_INTERVALS[item.review_level]
        item.next_review_date = date.today() + timedelta(days=interval_days)
        flash(f"「{item.topic}」を復習しました。次は{interval_days}日後です。", "success")
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
