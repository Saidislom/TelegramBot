# -*- coding: utf-8 -*-

import importlib
import json
import logging
import sys
import time
import os

from datetime import datetime

import leancloud
import requests
import telegram
from flask import Flask
from flask import request, jsonify
from leancloud import LeanCloudError
from user_agents import parse

importlib.reload(sys)

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
app.config.from_pyfile('default_config.py')

Comment = leancloud.Object.extend('Comment')
TGChat = leancloud.Object.extend('Chat')

# init value
CHAT_ID = None
IS_USE_SYSTEM_VARIABLE = app.config['IS_USE_SYSTEM_VARIABLE']
if IS_USE_SYSTEM_VARIABLE is True:
    BOT_TOKEN = os.environ['DO_TELEGRAM_BOT_TOKEN']
    BOT_URL = os.environ['DO_TELEGRAM_BOT_URL']
    BOT_NAME = os.environ['DO_TELEGRAM_BOT_NAME']
    AUTHOR_ID = os.environ['DO_DS_ID']
    SHORT_NAME = os.environ['DO_DS_SHORT_NAME']
    DS_SECRET = os.environ['DO_DS_SECRET']
    HOST_NAME = os.environ['HOST_NAME']
else:
    BOT_TOKEN = app.config['DO_TELEGRAM_BOT_TOKEN']
    BOT_URL = app.config['DO_TELEGRAM_BOT_URL']
    BOT_NAME = app.config['DO_TELEGRAM_BOT_NAME']
    AUTHOR_ID = app.config['DO_DS_ID']
    SHORT_NAME = app.config['DO_DS_SHORT_NAME']
    DS_SECRET = app.config['DO_DS_SECRET']
    HOST_NAME = app.config['HOST_NAME']

global BOT
BOT = telegram.Bot(token=str(BOT_TOKEN))
flag = BOT.setWebhook(str(BOT_URL))
if flag is True:
    leancloud.logger.debug("Web Hook Setup Success!")
else:
    leancloud.logger.error("Web Hook Setup Fail!")


@app.route('/bot', methods=['POST', 'GET'])
def index():
    if request.method == "POST":
        update = telegram.Update.de_json(request.get_json(force=True), BOT)
        leancloud.logger.debug("bot start!")
        handle_message(update.message)
        return 'ok'
    else:
        print(request.headers)
        print(request.form)
        print(request.get_json())
        return '{"Doublemine":"i am not bot!"}'


@app.route('/ds', methods=['POST', 'GET'])
def received_duoshuo():
    if request.method == 'POST':
        print(request.form)
        msg = {
            "code": 200, "message": "success"}
        json = request.get_json()
        leancloud.logger.debug('接收到的参数为:' + str(json))
        if request.form['action'] == 'sync_log':
            del_comment()
            return jsonify(msg)
    else:
        return "get request send success!"


@app.route("/lean", methods=["POST", "GET"])
def lean():
    comment = Comment()
    comment.set('log_id', '你好么')
    comment.save()
    return "ok"


def del_comment():
    query_since_id = Comment.query
    query_since_id.not_equal_to('user_id', AUTHOR_ID)
    try:
        query_since_id_result = query_since_id.first()
    except LeanCloudError:
        leancloud.logger.error("发生LeanCloudError 执行赋空操作")
        query_since_id_result = None
    if query_since_id_result is None:
        since_id = '0'
    else:
        since_id = query_since_id_result.get("log_id")
    payload = {
        'short_name': SHORT_NAME,
        'secret': DS_SECRET,
        'limit': '1',
        'order': 'desc',
        'since_id': since_id

    }
    request_list = requests.get(
        "http://api.duoshuo.com/log/list.json", params=payload)
    if request_list.ok is True:
        # try:
        #     comment = request_list.json()
        # except ValueError:
        #     print("Json Syntax Error")
        #     return
        print(request_list.text)
        json_obj = json.loads(request_list.text)
        if json_obj.get("response") is not None:
            meta_obj = json_obj.get('response')
            leancloud.logger.debug('metaObj', meta_obj)
            if len(meta_obj) > 0:
                if meta_obj[0] is not None and len(meta_obj[0]) > 0:
                    meta_detail = meta_obj[0]
                    if meta_detail.get('action') is not None:
                        if meta_detail.get('action') == 'create':  # 新的评论
                            # todo:新的评论
                            leancloud.logger.debug("你有新的评论")
                            '''
                            保存数据到leancloud
                            '''
                            if query_since_id_result is not None:
                                query_since_id_result.set('log_id', meta_detail.get('log_id'))
                                query_since_id_result.set('site_id', str(meta_detail.get('site_id')))
                                if meta_detail.get('user_id') == AUTHOR_ID:
                                    query_since_id_result.save()
                                    return
                                else:
                                    query_since_id_result.set('user_id', meta_detail.get('user_id'))
                                    query_since_id_result.save()
                                    handle_detail_msg("新的评论", meta_detail.get('meta'), meta_detail)
                            else:
                                comment_obj = Comment()
                                comment_obj.set('log_id', meta_detail.get('log_id'))
                                comment_obj.set('site_id', str(meta_detail.get('site_id')))
                                if meta_detail.get('user_id') == AUTHOR_ID:
                                    comment_obj.save()
                                    return
                                else:
                                    comment_obj.set('user_id', meta_detail.get('user_id'))
                                    comment_obj.save()
                                    handle_detail_msg("新的评论", meta_detail.get('meta'), meta_detail)
                else:
                    leancloud.logger.error("内部严重错误！")
                    return
            else:
                leancloud.logger.info("response 长度为0，跳过发送执行")
    else:
        leancloud.logger.error("网络请求失败！")


def handle_detail_msg(comment_type, meta_obj, response_obj):
    '''
    :param meta_obj: meta信息
    :return: 返回提取之后的关键字
    '''
    global CHAT_ID
    if CHAT_ID is None:
        query = TGChat.query
        query.equal_to('telegram_flag', 'Doublemine')
        try:
            query_result = query.first()
        except LeanCloudError:
            leancloud.logger.info('服务器没有保存当前绑定的CHAT_ID,将不会发送推送消息')
            return
        if query_result is not None and query_result.get('chat_id') is not None:
            CHAT_ID = query_result.get('chat_id')
        else:
            leancloud.logger.info('服务器没有保存当前绑定的CHAT_ID,将不会发送推送消息')
            return

    if meta_obj is not None:  # detail info
        print(meta_obj)
        telegram_push_str = "\t\t收到一条%s\n\n" \
                            "用户昵称:\t %s\n\n" \
                            "设备类型:\t %s\n\n" \
                            "ip地址:\t %s\n\n" \
                            "评论时间:\t %s\n\n" \
                            "评论内容:\t %s\n\n" \
                            "点击前往:\t %s" % (comment_type,
                                            meta_obj.get('author_name'),
                                            str(parse(meta_obj.get("agent"))),
                                            meta_obj.get('ip'),
                                            time.strftime("%Y-%m-%d %H:%M:%S",
                                                          time.localtime(int(response_obj.get("date")))),
                                            meta_obj.get('message'),
                                            HOST_NAME +
                                            meta_obj.get('thread_key'))
        print(telegram_push_str)
        try:
            BOT.sendMessage(chat_id=CHAT_ID, text=telegram_push_str, parse_mode=telegram.ParseMode.HTML,
                            disable_web_page_preview=False
                            )
        except telegram.error.BadRequest:
            leancloud.logger.error("内容格式错误，无法解析为HTML5，直接以MD格式进行解析")
            try:
                BOT.sendMessage(chat_id=CHAT_ID, text=telegram_push_str, parse_mode=telegram.ParseMode.MARKDOWN,
                                disable_web_page_preview=False
                                )
            except telegram.error.BadRequest:
                leancloud.logger.error("内容格式错误，无法解析为MD，直接以TEXT发送")
                BOT.sendMessage(chat_id=CHAT_ID, text=telegram_push_str,
                                disable_web_page_preview=False
                                )


def handle_message(message):
    if message is None:
        print("the message is None")
        return
    text = message.text
    print("message content is:", text, "chat id =", message.chat.id)
    if '/echo' in text:
        echo(message)
    elif '/love' in text:
        love(message)
    elif '/help' in text:
        help(message)
    elif SHORT_NAME == text or '/bind' in text:
        send_telegram_chat_id(message)
    elif message.text == 'Bind@' + str(message.chat.id):
        bind_telegram_chat_id(message)
    logging.info(text)


def send_telegram_chat_id(message):
    bind_btn = telegram.KeyboardButton(text="Bind@" + str(message.chat.id))
    cancel_btn = telegram.KeyboardButton(text="Cancel Bind")
    custom_keyboard = [[cancel_btn, bind_btn]]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True, one_time_keyboard=True,
                                                selective=True)
    # reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    BOT.sendMessage(chat_id=message.chat.id, text="Bind current chat id to receive Duo Shuo push Message?\n\n"
                                                  "[Option 1]: Cancel Bind\n\n"
                                                  "[Option 2]: Bind@" + str(message.chat.id),
                    reply_markup=reply_markup)


def bind_telegram_chat_id(message):
    tg_chat = TGChat()
    tg_chat.set('telegram_flag', 'Doublemine')
    tg_chat.set('chat_id', str(message.chat.id))
    tg_chat.save()
    global CHAT_ID
    CHAT_ID = message.chat.id
    BOT.send_message(CHAT_ID, text='Okay! Bind Completed,Now,you can receive Duo Shuo Push Msg!')


def help(message):
    text = ('/love - Get Doublemine milestone\n'
            '/help - Get Some Help \n'
            '/bind - Bind Current Account ID to receive duo shuo push msg'
            )
    BOT.sendMessage(chat_id=message.chat.id, text=text)


def parse_cmd_text(text):
    # Telegram understands UTF-8, so encode text for unicode compatibility
    text = str(text)
    cmd = None
    if '/' in text:
        try:
            index = text.index(' ')
        except ValueError as e:
            return (text, None)
        cmd = text[:index]
        text = text[index + 1:]
    if cmd is not None and '@' in cmd:
        cmd = cmd.replace(BOT_NAME, '')
    return (cmd, text)


def echo(message):
    '''
    repeat the same message back (echo)
    '''
    cmd, text = parse_cmd_text(message.text)
    if text is None or len(text) == 0:
        pass
    else:
        chat_id = message.chat.id
        BOT.sendMessage(chat_id=chat_id, text=text)


def love(message):
    from_day = datetime(2014, 4, 24)
    now = datetime.now()
    text = 'Doublemine 和他家老婆大人已经相爱 %d 天啦 ヾ(*´▽‘*)ﾉ' % (now - from_day).days
    chat_id = message.chat.id
    BOT.sendMessage(chat_id=chat_id, text=text)


if __name__ == '__main__':
    app.debug = True
    app.run()
