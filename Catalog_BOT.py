﻿import os
import json
import gspread

from flask import Flask, request, abort, render_template_string
from oauth2client.service_account import ServiceAccountCredentials

# line-bot-sdk v2 系
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# -----------------------
# Flaskアプリ
# -----------------------
app = Flask(__name__)

# -----------------------
# 環境変数取得
# -----------------------
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
SERVICE_ACCOUNT_FILE = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")
SPREADSHEET_KEY = os.environ.get("SPREADSHEET_KEY", "")

# -----------------------
# LINE Bot インスタンス
# -----------------------
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# -----------------------
# Google Sheets クライアントの初期化
# -----------------------
def get_gspread_client():
    """
    Secret Filesによるサービスアカウントファイルを読み込み、
    Googleスプレッドシートにアクセス可能なクライアントを返す
    """
    if not SERVICE_ACCOUNT_FILE:
        raise ValueError("環境変数 GCP_SERVICE_ACCOUNT_JSON が設定されていません。")

    with open(SERVICE_ACCOUNT_FILE, "r", encoding="utf-8") as f:
        service_account_dict = json.load(f)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_dict, scope)
    gc = gspread.authorize(credentials)
    return gc

def get_or_create_worksheet(sheet, title):
    """
    スプレッドシート内で該当titleのワークシートを取得。
    なければ新規作成し、ヘッダを書き込む。
    """
    try:
        ws = sheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=1000, cols=20)
        # A1セル等にヘッダ等の初期設定を施したい場合はここで
        ws.update('A1:H1', [[
            "氏名", "郵便番号", "住所", "電話番号", 
            "メールアドレス", "Insta/TikTok名", 
            "在籍予定の学校名と学年", "その他(質問・要望)"
        ]])
    return ws

def write_to_spreadsheet(form_data: dict):
    """
    フォーム送信のデータをスプレッドシートに1行追加する
    """
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_KEY)

    # 今回はシート名を"CatalogRequests"等に固定するとする
    worksheet = get_or_create_worksheet(sh, "CatalogRequests")

    new_row = [
        form_data.get("name", ""),
        form_data.get("postal_code", ""),
        form_data.get("address", ""),
        form_data.get("phone", ""),
        form_data.get("email", ""),
        form_data.get("sns_account", ""),
        form_data.get("school_grade", ""),
        form_data.get("other", ""),
    ]
    worksheet.append_row(new_row, value_input_option="USER_ENTERED")


# -----------------------
# 1) LINE Messaging API 受信 (Webhook)
# -----------------------
@app.route("/line/callback", methods=["POST"])
def line_callback():
    # X-Line-Signature ヘッダの取得
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    # 署名チェック
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400, "Invalid signature. Please check your channel access token/channel secret.")

    return "OK", 200


# -----------------------
# 2) LINE上でメッセージ受信したときのハンドラ
# -----------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent):
    user_message = event.message.text.strip().lower()
    
    # ユーザーが「カタログ」等のキーワードを送信したら案内を返す例
    if "カタログ" in user_message or "catalog" in user_message:
        # 1～4の案内文 + フォームURL
        # ここではフォームページを /catalog_form で用意している想定
        form_url = "https://catalog-bot-1.onrender.com/catalog_form"

        reply_text = (
            "【カタログ送付に関するご案内】\n\n"
            "1. 無料請求応募方法について\n"
            "PrintMediaのInstagramもしくはTikTokアカウントをフォローしてください。\n"
            "Instagram: @printmedia19\n"
            "TikTok: printmedia_19\n"
            "※カタログ送付数には限りがありますのでサブアカウントなど使用しての重複申し込みはご遠慮下さい。\n\n"
            "2. カタログ送付時期\n"
            "2025年4月6日〜4月8日に郵送でお送りします。\n\n"
            "3. 配布数について\n"
            "現在：1000名様分を予定。超過した場合は配布数増加または抽選となる可能性があります。\n\n"
            "4. カタログ申し込みフォーム\n"
            "下記フォームリンクからお申し込みください。\n"
            f"{form_url}"
        )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
    else:
        # それ以外のメッセージには適当に返答（必要に応じて）
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="メッセージありがとうございます。『カタログ』と入力すると詳細をお送りします。")
        )


# -----------------------
# 3) カタログ申し込みフォームを表示するエンドポイント (GET)
# -----------------------
@app.route("/catalog_form", methods=["GET"])
def show_catalog_form():
    """
    シンプルにHTMLを返すだけの例。
    実運用ではテンプレートファイルを Jinja2 で利用してもOK。
    """
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>カタログ申し込みフォーム</title>
</head>
<body>
    <h1>カタログ申し込みフォーム</h1>
    <p>以下の項目をご記入の上、送信してください。</p>
    <form action="/submit_form" method="post">
        <label>氏名（必須）:<br>
            <input type="text" name="name" required>
        </label>
        <br><br>

        <label>郵便番号（必須）:<br>
            <input type="text" name="postal_code" required>
        </label>
        <br><br>

        <label>住所（必須）:<br>
            <input type="text" name="address" required>
        </label>
        <br><br>

        <label>電話番号（必須）:<br>
            <input type="text" name="phone" required>
        </label>
        <br><br>

        <label>メールアドレス（必須）:<br>
            <input type="email" name="email" required>
        </label>
        <br><br>

        <label>Insta・TikTok名（必須）:<br>
            <input type="text" name="sns_account" required>
        </label>
        <br><br>

        <label>2025年度に在籍予定の学校名と学年（未記入可）:<br>
            <input type="text" name="school_grade">
        </label>
        <br><br>

        <label>その他（質問やご要望など）:<br>
            <textarea name="other" rows="4"></textarea>
        </label>
        <br><br>

        <input type="submit" value="送信">
    </form>
</body>
</html>
"""
    return render_template_string(html_content)


# -----------------------
# 4) カタログ申し込みフォームの送信を受け取ってスプレッドシートに保存
# -----------------------
@app.route("/submit_form", methods=["POST"])
def submit_catalog_form():
    # フォームからのデータを取得
    form_data = {
        "name": request.form.get("name", "").strip(),
        "postal_code": request.form.get("postal_code", "").strip(),
        "address": request.form.get("address", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "email": request.form.get("email", "").strip(),
        "sns_account": request.form.get("sns_account", "").strip(),
        "school_grade": request.form.get("school_grade", "").strip(),
        "other": request.form.get("other", "").strip(),
    }

    # Googleスプレッドシートに書き込み
    try:
        write_to_spreadsheet(form_data)
    except Exception as e:
        return f"エラーが発生しました: {e}", 500

    return "フォーム送信ありがとうございました！ カタログ送付をお待ちください。", 200


# -----------------------
# 動作確認用ルート
# -----------------------
@app.route("/", methods=["GET"])
def health_check():
    return "LINE Bot is running.", 200


# -----------------------
# アプリ起動(ローカル開発時)
# -----------------------
if __name__ == "__main__":
    # ポート番号は必要に応じて変更
    app.run(host="0.0.0.0", port=5000, debug=True)

