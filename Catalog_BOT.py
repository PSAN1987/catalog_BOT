import os
import json
import time

import gspread
from flask import Flask, request, abort, render_template_string
from oauth2client.service_account import ServiceAccountCredentials

# line-bot-sdk v2 系
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
)

app = Flask(__name__)

# -----------------------
# 環境変数取得
# -----------------------
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
SERVICE_ACCOUNT_FILE = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")
SPREADSHEET_KEY = os.environ.get("SPREADSHEET_KEY", "")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# -----------------------
# Google Sheets 接続
# -----------------------
def get_gspread_client():
    """
    環境変数 SERVICE_ACCOUNT_FILE (JSONパス or JSON文字列) から認証情報を取り出し、
    gspread クライアントを返す
    """
    if not SERVICE_ACCOUNT_FILE:
        raise ValueError("環境変数 GCP_SERVICE_ACCOUNT_JSON が設定されていません。")

    service_account_dict = json.loads(SERVICE_ACCOUNT_FILE)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_dict, scope)
    return gspread.authorize(credentials)

def get_or_create_worksheet(sheet, title):
    """
    スプレッドシート内で該当titleのワークシートを取得。
    なければ新規作成し、ヘッダを書き込む。
    """
    try:
        ws = sheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=2000, cols=20)
        # 必要であればヘッダをセット
        if title == "CatalogRequests":
            ws.update('A1:H1', [[
                "氏名", "郵便番号", "住所", "電話番号", 
                "メールアドレス", "Insta/TikTok名", 
                "在籍予定の学校名と学年", "その他(質問・要望)"
            ]])
        elif title == "簡易見積":
            ws.update('A1:L1', [[
                "日時", "見積番号", "ユーザーID", 
                "使用日(割引区分)", "予算", "商品名", "枚数",
                "プリント位置", "色数", "背ネーム", 
                "合計金額", "単価"
            ]])
    return ws

def write_to_spreadsheet_for_catalog(form_data: dict):
    """
    カタログ請求フォーム送信のデータをスプレッドシートに1行追加する
    """
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_KEY)
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
# 簡易見積用データ構造
# -----------------------

# 下記のように、商品・割引区分・枚数レンジ・価格をまとめた辞書を作成します。
# （実際には非常に行数が多いので、一部例示とし、全量を入れるかどうかは運用次第です）
# ここではフルで入れてみますが、本番環境では外部CSVなどにして読み込むのがおすすめです。

PRICE_TABLE = [
    # 商品名, MinQty, MaxQty, DiscountType, UnitPrice, プリント位置追加, 色数追加, フルカラー追加, ネーム&背番号セット, ネーム(大), 番号(大)
    # ドライTシャツ
    {"item":"ドライTシャツ","min_qty":10,"max_qty":14,"discount_type":"早割","unit_price":1830,"pos_add":850,"color_add":850,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":10,"max_qty":14,"discount_type":"通常","unit_price":2030,"pos_add":850,"color_add":850,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":15,"max_qty":19,"discount_type":"早割","unit_price":1470,"pos_add":650,"color_add":650,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":15,"max_qty":19,"discount_type":"通常","unit_price":1670,"pos_add":650,"color_add":650,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":20,"max_qty":29,"discount_type":"早割","unit_price":1230,"pos_add":450,"color_add":450,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":20,"max_qty":29,"discount_type":"通常","unit_price":1430,"pos_add":450,"color_add":450,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":30,"max_qty":39,"discount_type":"早割","unit_price":1060,"pos_add":350,"color_add":350,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":30,"max_qty":39,"discount_type":"通常","unit_price":1260,"pos_add":350,"color_add":350,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":40,"max_qty":49,"discount_type":"早割","unit_price":980,"pos_add":350,"color_add":350,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":40,"max_qty":49,"discount_type":"通常","unit_price":1180,"pos_add":350,"color_add":350,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":50,"max_qty":99,"discount_type":"早割","unit_price":890,"pos_add":350,"color_add":350,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":50,"max_qty":99,"discount_type":"通常","unit_price":1090,"pos_add":350,"color_add":350,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":100,"max_qty":500,"discount_type":"早割","unit_price":770,"pos_add":300,"color_add":300,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ドライTシャツ","min_qty":100,"max_qty":500,"discount_type":"通常","unit_price":970,"pos_add":300,"color_add":300,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    # ヘビーウェイトTシャツ
    {"item":"ヘビーウェイトTシャツ","min_qty":10,"max_qty":14,"discount_type":"早割","unit_price":1970,"pos_add":850,"color_add":850,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ヘビーウェイトTシャツ","min_qty":10,"max_qty":14,"discount_type":"通常","unit_price":2170,"pos_add":850,"color_add":850,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ヘビーウェイトTシャツ","min_qty":15,"max_qty":19,"discount_type":"早割","unit_price":1610,"pos_add":650,"color_add":650,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    {"item":"ヘビーウェイトTシャツ","min_qty":15,"max_qty":19,"discount_type":"通常","unit_price":1810,"pos_add":650,"color_add":650,"fullcolor_add":550,"set_name_num":900,"big_name":550,"big_num":550},
    # ... （以下、同様に全商品・全枚数レンジの行を埋める）
    # ここでは省略のため、全商品分を貼り付けると非常に長くなるため、一部を例示。
    # 実際にはユーザ提供の全テーブルを同様の形式でPRICE_TABLEに入れてください。
]

# 追加料金の判定ロジック（色数）: ここでは「キー文字列 -> (色数追加の回数, フルカラー追加の回数)」で定義
COLOR_COST_MAP = {
    "前 or 背中 1色": (0, 0),
    "前 or 背中 2色": (1, 0),
    "前 or 背中 フルカラー": (0, 1),
    "前と背中 前1色 背中1色": (0, 0),
    "前と背中 前2色 背中1色": (1, 0),
    "前と背中 前1色 背中2色": (1, 0),
    "前と背中 前2色 背中2色": (2, 0),
    "前と背中 フルカラー": (0, 2),
}


# ユーザの見積フロー管理用
user_estimate_sessions = {}  # { user_id: {"step": n, "answers": {...}} }


def write_estimate_to_spreadsheet(user_id, estimate_data, total_price, unit_price):
    """
    計算が終わった見積情報をスプレッドシートの「簡易見積」に書き込む
    """
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_KEY)
    worksheet = get_or_create_worksheet(sh, "簡易見積")

    # 見積番号を生成（例: UNIX時間）
    quote_number = str(int(time.time()))

    # A列から順に: 日時, 見積番号, ユーザーID, 使用日(割引区分), 予算, 商品名, 枚数, プリント位置, 色数, 背ネーム, 合計金額, 単価
    new_row = [
        time.strftime("%Y/%m/%d %H:%M:%S"),    # 日時
        quote_number,                          # 見積番号
        user_id,                               # ユーザーID
        f"{estimate_data['usage_date']}({estimate_data['discount_type']})",  # 例 "14日前以上(早割)"
        estimate_data['budget'],
        estimate_data['item'],
        estimate_data['quantity'],
        estimate_data['print_position'],
        estimate_data['color_count'],
        estimate_data['back_name'],
        f"¥{total_price:,}",
        f"¥{unit_price:,}"
    ]
    worksheet.append_row(new_row, value_input_option="USER_ENTERED")

    return quote_number


def find_price_row(item_name, discount_type, quantity):
    """
    PRICE_TABLE から該当する行を探して返す。
    該当しない場合は None を返す
    """
    for row in PRICE_TABLE:
        if (row["item"] == item_name 
            and row["discount_type"] == discount_type
            and row["min_qty"] <= quantity <= row["max_qty"]):
            return row
    return None

def calculate_estimate(estimate_data):
    """
    estimate_data から見積を計算して (total_price, unit_price) を返す
    estimate_dataは以下のキーを持つ想定:
      - discount_type  ( '早割' or '通常' )
      - item          (商品名)
      - quantity      (int)
      - print_position
      - color_count
      - back_name
    """
    item_name = estimate_data['item']
    discount_type = estimate_data['discount_type']
    quantity = int(estimate_data['quantity'])
    print_position = estimate_data['print_position']
    color_choice = estimate_data['color_count']
    back_name = estimate_data['back_name']

    # 該当行の単価情報を取得
    row = find_price_row(item_name, discount_type, quantity)
    if row is None:
        # 該当なしの場合は計算不能
        return 0, 0

    base_price = row["unit_price"]

    # プリント位置追加
    if print_position in ["前のみ", "背中のみ"]:
        pos_add = 0
    else:
        pos_add = row["pos_add"]

    # 色数追加ロジック
    color_add_count, fullcolor_add_count = COLOR_COST_MAP[color_choice]
    color_fee = color_add_count * row["color_add"] + fullcolor_add_count * row["fullcolor_add"]

    # 背ネーム
    if back_name == "ネーム&背番号セット":
        back_name_fee = row["set_name_num"]
    elif back_name == "ネーム(大)":
        back_name_fee = row["big_name"]
    elif back_name == "番号(大)":
        back_name_fee = row["big_num"]
    else:
        back_name_fee = 0

    # 1枚あたりの価格
    unit_price = base_price + pos_add + color_fee + back_name_fee
    total_price = unit_price * quantity

    return total_price, unit_price


# -----------------------
# Flex Message作成ヘルパー
# -----------------------
def flex_usage_date():
    """
    使用日の質問（14日前以上 or 14日前以内）用のFlexメッセージ
    """
    flex_body = {
      "type": "bubble",
      "hero": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "text",
            "text": "【使用日】",
            "weight": "bold",
            "size": "lg"
          },
          {
            "type": "text",
            "text": "大会やイベントで使用する日程を教えてください\n(印刷開始14日前以上なら早割)",
            "size": "sm",
            "wrap": True
          }
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "14日前以上",
              "text": "14日前以上"
            }
          },
          {
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "14日前以内",
              "text": "14日前以内"
            }
          }
        ],
        "flex": 0
      }
    }
    return FlexSendMessage(alt_text="使用日を選択してください", contents=flex_body)

def flex_budget():
    """
    1枚当たりの予算選択用
    """
    budgets = ["1,000円", "2,000円", "3,000円", "4,000円", "5,000円"]
    buttons = []
    for b in budgets:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "message",
                "label": b,
                "text": b
            }
        })

    flex_body = {
      "type": "bubble",
      "hero": {
        "type": "text",
        "text": "【1枚あたりの予算】",
        "weight": "bold",
        "size": "lg"
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {"type": "text", "text": "希望の1枚あたりの予算を選んでください", "wrap": True}
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": buttons,
        "flex": 0
      }
    }
    return FlexSendMessage(alt_text="予算を選択してください", contents=flex_body)

def flex_item_select():
    """
    商品名選択用(ここではcarouselで13種類を一覧表示)
    """
    items = [
        "ドライTシャツ","ヘビーウェイトTシャツ","ドライポロシャツ","ドライメッシュビブス",
        "ドライベースボールシャツ","ドライロングスリープTシャツ","ドライハーフパンツ",
        "ヘビーウェイトロングスリープTシャツ","クルーネックライトトレーナー",
        "フーデッドライトパーカー","スタンダードトレーナー","スタンダードWフードパーカー",
        "ジップアップライトパーカー"
    ]

    # 1バブル最大12ボタン制限があるため、ここではCarouselで分割
    # 分割ロジック例: 1バブル5種ずつ表示
    item_bubbles = []
    chunk_size = 5
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i+chunk_size]
        buttons = []
        for it in chunk:
            buttons.append({
                "type": "button",
                "style": "primary",
                "height": "sm",
                "action": {
                    "type": "message",
                    "label": it,
                    "text": it
                }
            })
        bubble = {
          "type": "bubble",
          "hero": {
            "type": "text",
            "text": "【商品名】",
            "weight": "bold",
            "size": "lg"
          },
          "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
              {"type": "text", "text": "ご希望の商品を選択してください", "wrap": True}
            ]
          },
          "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons
          }
        }
        item_bubbles.append(bubble)

    carousel = {
        "type": "carousel",
        "contents": item_bubbles
    }

    return FlexSendMessage(alt_text="商品名を選択してください", contents=carousel)

def flex_quantity():
    """
    必要枚数を10, 20, 30, 40, 50以上 から選択
    """
    quantities = ["10", "20", "30", "40", "50以上"]
    buttons = []
    for q in quantities:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "message",
                "label": q,
                "text": q
            }
        })
    flex_body = {
      "type": "bubble",
      "hero": {
        "type": "text",
        "text": "【枚数】",
        "weight": "bold",
        "size": "lg"
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {"type": "text", "text": "何枚ご入り用ですか？", "wrap": True}
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": buttons
      }
    }
    return FlexSendMessage(alt_text="必要枚数を選択してください", contents=flex_body)

def flex_print_position():
    """
    プリント位置 (前のみ / 背中のみ / 前と背中)
    """
    positions = ["前のみ", "背中のみ", "前と背中"]
    buttons = []
    for pos in positions:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "message",
                "label": pos,
                "text": pos
            }
        })
    flex_body = {
      "type": "bubble",
      "hero": {
        "type": "text",
        "text": "【プリント位置】",
        "weight": "bold",
        "size": "lg"
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": buttons
      }
    }
    return FlexSendMessage(alt_text="プリント位置を選択してください", contents=flex_body)

def flex_color_count():
    """
    色数 (8パターン) の選択
    """
    color_list = [
        "前 or 背中 1色",
        "前 or 背中 2色",
        "前 or 背中 フルカラー",
        "前と背中 前1色 背中1色",
        "前と背中 前2色 背中1色",
        "前と背中 前1色 背中2色",
        "前と背中 前2色 背中2色",
        "前と背中 フルカラー",
    ]
    # 分割などしてCarouselにする
    color_bubbles = []
    chunk_size = 4
    for i in range(0, len(color_list), chunk_size):
        chunk = color_list[i:i+chunk_size]
        buttons = []
        for c in chunk:
            buttons.append({
                "type": "button",
                "style": "primary",
                "height": "sm",
                "action": {
                    "type": "message",
                    "label": c[:12],  # ラベルが長くなるので適宜短縮
                    "text": c
                }
            })
        bubble = {
          "type": "bubble",
          "hero": {
            "type": "text",
            "text": "【色数】",
            "weight": "bold",
            "size": "md"
          },
          "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons
          }
        }
        color_bubbles.append(bubble)

    carousel = {
        "type": "carousel",
        "contents": color_bubbles
    }
    return FlexSendMessage(alt_text="色数を選択してください", contents=carousel)

def flex_back_name():
    """
    背ネーム (ネーム&背番号セット / ネーム(大) / 番号(大))
    """
    names = ["ネーム&背番号セット", "ネーム(大)", "番号(大)"]
    buttons = []
    for nm in names:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "message",
                "label": nm,
                "text": nm
            }
        })
    flex_body = {
      "type": "bubble",
      "hero": {
        "type": "text",
        "text": "【背ネーム】",
        "weight": "bold",
        "size": "lg"
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": buttons
      }
    }
    return FlexSendMessage(alt_text="背ネームを選択してください", contents=flex_body)

# -----------------------
# 1) LINE Messaging API 受信 (Webhook)
# -----------------------
@app.route("/line/callback", methods=["POST"])
def line_callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400, "Invalid signature. Please check your channel access token/channel secret.")

    return "OK", 200

# -----------------------
# 2) LINE上でメッセージ受信時
# -----------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # まずは「見積り」フロー中かどうか確認
    if user_id in user_estimate_sessions and user_estimate_sessions[user_id]["step"] > 0:
        # すでに見積りフロー中
        process_estimate_flow(event, user_message)
        return

    # 見積りフローを開始するかチェック
    if user_message == "見積り":
        start_estimate_flow(event)
        return

    # カタログ案内
    if "カタログ" in user_message or "catalog" in user_message.lower():
        send_catalog_info(event)
        return

    # それ以外
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="メッセージありがとうございます。\n『カタログ』または『見積り』と入力すると詳細をお送りします。")
    )


def send_catalog_info(event: MessageEvent):
    """
    「カタログ」キーワードへの応答
    """
    form_url = "https://catalog-bot-1.onrender.com/catalog_form"
    reply_text = (
        "【カタログ送付に関するご案内】\n\n"
        "1. 無料請求応募方法について\n"
        "InstagramまたはTikTokアカウントをフォローしてください。\n"
        "Instagram: https://www.instagram.com/printmedia19\n"
        "TikTok: https://www.tiktok.com/@printmedia_19\n"
        "※カタログ送付数には限りがありますのでサブアカウントなど\n"
        "　使用しての重複申し込みはご遠慮下さい。\n\n"
        "2. カタログ送付時期\n"
        "2025年4月6日〜4月8日に郵送でお送りします。\n\n"
        "3. 配布数について\n"
        "現在：1000名様分を予定。超過した場合は\n"
        "配布数増加または抽選となる可能性があります。\n\n"
        "4. カタログ申し込みフォーム\n"
        f"{form_url}"
    )
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# -----------------------
# 見積りフロー管理
# -----------------------
def start_estimate_flow(event: MessageEvent):
    """
    見積りフローの最初のステップを開始
    """
    user_id = event.source.user_id
    user_estimate_sessions[user_id] = {
        "step": 1,
        "answers": {}
    }
    # 最初の質問: 使用日
    line_bot_api.reply_message(
        event.reply_token,
        flex_usage_date()
    )

def process_estimate_flow(event: MessageEvent, user_message: str):
    """
    見積りフロー中のユーザの回答を処理して、次のステップを送る
    """
    user_id = event.source.user_id
    session_data = user_estimate_sessions[user_id]
    step = session_data["step"]

    if step == 1:
        # 回答: 使用日
        # "14日前以上" / "14日前以内"
        if user_message in ["14日前以上", "14日前以内"]:
            session_data["answers"]["usage_date"] = user_message
            # 割引区分設定
            if user_message == "14日前以上":
                session_data["answers"]["discount_type"] = "早割"
            else:
                session_data["answers"]["discount_type"] = "通常"
            session_data["step"] = 2

            # 次の質問: 予算
            line_bot_api.reply_message(
                event.reply_token,
                flex_budget()
            )
        else:
            # 不正入力の場合は聞き直し
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="「14日前以上」または「14日前以内」を選択してください。")
            )

    elif step == 2:
        # 回答: 予算
        budgets = ["1,000円", "2,000円", "3,000円", "4,000円", "5,000円"]
        if user_message in budgets:
            session_data["answers"]["budget"] = user_message
            session_data["step"] = 3
            # 次の質問: 商品名
            line_bot_api.reply_message(
                event.reply_token,
                flex_item_select()
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="1枚あたりの予算をボタンから選択してください。")
            )

    elif step == 3:
        # 回答: 商品名
        items = [
            "ドライTシャツ","ヘビーウェイトTシャツ","ドライポロシャツ","ドライメッシュビブス",
            "ドライベースボールシャツ","ドライロングスリープTシャツ","ドライハーフパンツ",
            "ヘビーウェイトロングスリープTシャツ","クルーネックライトトレーナー",
            "フーデッドライトパーカー","スタンダードトレーナー","スタンダードWフードパーカー",
            "ジップアップライトパーカー"
        ]
        if user_message in items:
            session_data["answers"]["item"] = user_message
            session_data["step"] = 4
            # 次: 枚数
            line_bot_api.reply_message(
                event.reply_token,
                flex_quantity()
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="該当商品のボタンを選択してください。")
            )

    elif step == 4:
        # 枚数
        valid_choices = ["10","20","30","40","50以上"]
        if user_message in valid_choices:
            # 実際の数量
            if user_message == "50以上":
                # ここでは仮に100とする (あるいは実際のやり取りでユーザに入力してもらってもよい)
                session_data["answers"]["quantity"] = "100"
            else:
                session_data["answers"]["quantity"] = user_message
            session_data["step"] = 5

            # 次: プリント位置
            line_bot_api.reply_message(
                event.reply_token,
                flex_print_position()
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="枚数をボタンから選択してください。")
            )

    elif step == 5:
        # プリント位置
        valid_positions = ["前のみ", "背中のみ", "前と背中"]
        if user_message in valid_positions:
            session_data["answers"]["print_position"] = user_message
            session_data["step"] = 6
            # 次: 色数
            line_bot_api.reply_message(
                event.reply_token,
                flex_color_count()
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="プリント位置を選択してください。")
            )

    elif step == 6:
        # 色数
        color_list = list(COLOR_COST_MAP.keys())
        if user_message in color_list:
            session_data["answers"]["color_count"] = user_message
            session_data["step"] = 7
            # 次: 背ネーム
            line_bot_api.reply_message(
                event.reply_token,
                flex_back_name()
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="色数を選択してください。")
            )

    elif step == 7:
        # 背ネーム
        valid_back_names = ["ネーム&背番号セット", "ネーム(大)", "番号(大)"]
        if user_message in valid_back_names:
            session_data["answers"]["back_name"] = user_message
            # これで回答が出揃った
            session_data["step"] = 8

            # 見積計算
            est_data = session_data["answers"]
            quantity = int(est_data["quantity"])
            total_price, unit_price = calculate_estimate(est_data)

            # スプレッドシート書き込み
            quote_number = write_estimate_to_spreadsheet(
                user_id, est_data, total_price, unit_price
            )

            # ユーザへ結果返信
            reply_text = (
                f"お見積りが完了しました。\n\n"
                f"見積番号: {quote_number}\n"
                f"使用日: {est_data['usage_date']}（{est_data['discount_type']}）\n"
                f"予算: {est_data['budget']}\n"
                f"商品: {est_data['item']}\n"
                f"枚数: {quantity}枚\n"
                f"プリント位置: {est_data['print_position']}\n"
                f"色数: {est_data['color_count']}\n"
                f"背ネーム: {est_data['back_name']}\n\n"
                f"【合計金額】¥{total_price:,}\n"
                f"【1枚あたり】¥{unit_price:,}\n"
            )
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
            # フロー終了（セッション削除）
            del user_estimate_sessions[user_id]
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="背ネームを選択してください。")
            )

    else:
        # 想定外
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="見積の回答処理でエラーが発生しました。最初からやり直してください。")
        )
        # セッションリセット
        if user_id in user_estimate_sessions:
            del user_estimate_sessions[user_id]


# -----------------------
# 3) カタログ申し込みフォーム表示 (GET)
# -----------------------
@app.route("/catalog_form", methods=["GET"])
def show_catalog_form():
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>カタログ申し込みフォーム</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: sans-serif;
        }
        .container {
            max-width: 600px; 
            margin: 0 auto;
            padding: 1em;
        }
        label {
            display: block;
            margin-bottom: 0.5em;
        }
        input[type=text], input[type=email], textarea {
            width: 100%;
            padding: 0.5em;
            margin-top: 0.3em;
            box-sizing: border-box;
        }
        input[type=submit] {
            padding: 0.7em 1em;
            font-size: 1em;
            margin-top: 1em;
        }
    </style>
    <script>
    async function fetchAddress() {
        let pcRaw = document.getElementById('postal_code').value.trim();
        pcRaw = pcRaw.replace('-', '');
        if (pcRaw.length < 7) {
            return;
        }
        try {
            const response = await fetch(`https://api.zipaddress.net/?zipcode=${pcRaw}`);
            const data = await response.json();
            if (data.code === 200) {
                document.getElementById('address').value = data.data.fullAddress;
            }
        } catch (error) {
            console.log("住所検索失敗:", error);
        }
    }
    </script>
</head>
<body>
    <div class="container">
      <h1>カタログ申し込みフォーム</h1>
      <p>以下の項目をご記入の上、送信してください。</p>
      <form action="/submit_form" method="post">
          <label>氏名（必須）:
              <input type="text" name="name" required>
          </label>

          <label>郵便番号（必須）:<br>
              <small>※ハイフン無し7桁で入力すると自動で住所補完します</small><br>
              <input type="text" name="postal_code" id="postal_code" onkeyup="fetchAddress()" required>
          </label>

          <label>住所（必須）:
              <input type="text" name="address" id="address" required>
          </label>

          <label>電話番号（必須）:
              <input type="text" name="phone" required>
          </label>

          <label>メールアドレス（必須）:
              <input type="email" name="email" required>
          </label>

          <label>Insta・TikTok名（必須）:
              <input type="text" name="sns_account" required>
          </label>

          <label>2025年度に在籍予定の学校名と学年（未記入可）:
              <input type="text" name="school_grade">
          </label>

          <label>その他（質問やご要望など）:
              <textarea name="other" rows="4"></textarea>
          </label>

          <input type="submit" value="送信">
      </form>
    </div>
</body>
</html>
"""
    return render_template_string(html_content)

# -----------------------
# 4) カタログ申し込みフォームの送信処理
# -----------------------
@app.route("/submit_form", methods=["POST"])
def submit_catalog_form():
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

    try:
        write_to_spreadsheet_for_catalog(form_data)
    except Exception as e:
        return f"エラーが発生しました: {e}", 500

    return "フォーム送信ありがとうございました！ カタログ送付をお待ちください。", 200

# -----------------------
# 動作確認用
# -----------------------
@app.route("/", methods=["GET"])
def health_check():
    return "LINE Bot is running.", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
