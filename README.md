# 🧠 復習タイマー - 絶対覚える暗記アプリ

忘却曲線に基づいた**しつこいリマインダー**で、絶対に覚える暗記アプリです。

## ✨ 特徴

### 🔔 しつこい通知システム
- **忘却曲線に基づくタイミング**: 20分後、1時間後、4時間後、8時間後に自動リマインド
- **確認するまで消えない**: `requireInteraction`で通知を見逃さない
- **繰り返しリマインド**: 復習するまで15分、30分、60分間隔でしつこく通知
- **静かな時間設定**: 23時〜7時は通知を控えめに

### 📱 PWA対応
- スマホのホーム画面に追加してアプリのように使用可能
- オフラインでも動作（キャッシュ済みページ）
- プッシュ通知対応

### 📊 復習間隔（忘却曲線）
デフォルトの復習スケジュール:
- 1日後 → 3日後 → 7日後 → 16日後 → 35日後 → 60日後 → 120日後

## 🚀 セットアップ

### 必要なもの
- Python 3.8+
- PostgreSQL（本番環境）

### ローカル開発

```bash
# リポジトリをクローン
git clone https://github.com/nishiko0124/fukusyu.git
cd fukusyu

# 仮想環境を作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# 環境変数を設定
export DATABASE_URL="sqlite:///reviews.db"  # 開発用SQLite
export SECRET_KEY="your-secret-key"

# データベースを初期化
python -c "from app import db; db.create_all()"

# 開発サーバーを起動
flask run
```

### 本番デプロイ（Railway/Render等）

1. リポジトリをGitHubにプッシュ
2. Railway/Render等でプロジェクトを作成
3. PostgreSQLアドオンを追加
4. 環境変数を設定:
   - `DATABASE_URL`: PostgreSQLの接続URL
   - `SECRET_KEY`: ランダムな文字列

## 📡 API エンドポイント

| エンドポイント | メソッド | 説明 |
|--------------|---------|------|
| `/api/pending-reviews` | GET | 今日復習すべき項目を取得 |
| `/api/items` | GET | 全項目を取得 |
| `/api/add` | POST | 新しい項目を追加（JSON） |
| `/api/review/<id>` | POST | 復習完了を記録 |

### 使用例

```bash
# 新しい項目を追加
curl -X POST https://your-app.com/api/add \
  -H "Content-Type: application/json" \
  -d '{"topic": "英単語: ephemeral", "category": "英語"}'

# 復習待ちを確認
curl https://your-app.com/api/pending-reviews
```

## 🔧 カスタマイズ

### 復習間隔の変更
`app.py`の`REVIEW_INTERVALS`を編集:

```python
REVIEW_INTERVALS = [1, 3, 7, 16, 35, 60, 120]  # 日数
```

### 通知設定
`notification.js`で以下を変更可能:
- `reminderIntervals`: リマインド間隔（分）
- `quietHoursStart/End`: 静かな時間
- `aggressiveMode`: しつこいモードのON/OFF

## 📁 ファイル構成

```
fukusyu/
├── app.py                 # Flaskアプリケーション
├── requirements.txt       # Python依存関係
├── static/
│   ├── manifest.json      # PWAマニフェスト
│   ├── sw.js             # Service Worker
│   ├── notification.js    # 通知管理
│   └── icon-*.svg        # アプリアイコン
├── templates/
│   ├── index.html        # メインページ
│   ├── add_form.html     # 項目追加フォーム
│   ├── edit_item.html    # 項目編集
│   └── bookmarklet.html  # ブックマークレット説明
└── .github/
    └── workflows/
        ├── deploy.yml    # CI/CDワークフロー
        └── reminder.yml  # 定期リマインダー
```

## 🤝 貢献

プルリクエスト歓迎です！

## 📜 ライセンス

MIT License
