#!/bin/bash

# ライブラリのインストール
pip install -r requirements.txt

# データベースのテーブルを作成
flask shell << EOF
from app import db
db.create_all()
EOF
