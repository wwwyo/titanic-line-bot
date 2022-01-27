import os
import json
import boto3

from linebot import (
    LineBotApi, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, StickerSendMessage, PostbackEvent, PostbackAction, QuickReply, QuickReplyButton
)

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

channel_secret = os.environ['secret_token']
channel_access_token = os.environ['access_token']
dynamo_table = os.environ['dynamo_table']
region = 'us-east-1'

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)


def lambda_handler(event, context):
    signature = event["headers"]["x-line-signature"]
    body = event["body"]
    # parse webhook body
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        logger.error("Got exception from LINE Messaging API")

    dynamodb = boto3.resource('dynamodb', region_name=region)
    dynamotable = dynamodb.Table(dynamo_table)

    # if event is MessageEvent and message is TextMessage, then echo text #
    for event in events:
        logger.info(str(event))

        primary_key = {"userId": str(event.source.user_id)}
        if isinstance(event, PostbackEvent):

            res = dynamotable.get_item(Key=primary_key)
            if not res.get('Item'):
                response = dynamotable.put_item(
                    Item={
                        'userId': str(event.source.user_id),
                        'Question': '0'
                    }
                )
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text='ご利用の際は『予測』とお声がけください😁'))
                break
            
            question = str(res['Item']['Question'])
            logger.info(question)
            if question == "0":
                response = dynamotable.update_item(
                    Key=primary_key,
                    UpdateExpression="set Question = :Question, Pclass = :Pclass",
                    ExpressionAttributeValues={
                        ':Question': 1,
                        ':Pclass': event.postback.data
                    })
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="年齢はいくつですか？"))

            elif question == "4":
                response = dynamotable.update_item(
                    Key=primary_key,
                    UpdateExpression="set Question = :Question, Sex = :Sex",
                    ExpressionAttributeValues={
                        ':Question': 5,
                        ':Sex': event.postback.data
                    })

                ENDPOINT_NAME = os.environ['endpoint_name']
                client = boto3.client(
                    "sagemaker-runtime", region_name="us-east-1")

                input_data = [[res['Item']['Pclass'],
                                event.postback.data,
                                res['Item']['Age'],
                                res['Item']['SibSp'],
                                res['Item']['Parch'],
                                0,
                                1,
                                0]]
                # Pclass_1,2,3, Sex_0,1, Age, SibSp_0, Parch_0, EmbarkedS,Q,P
                request_body = '\n'.join(
                    [','.join([str(x) for x in rec]) for rec in input_data])
                content_type = "text/csv"
                accept_type = "application/json"

                try:
                    response = client.invoke_endpoint(
                        EndpointName=ENDPOINT_NAME,
                        Body=request_body,
                        ContentType=content_type,
                        Accept=accept_type
                    )
                    predictions = json.loads(
                    response['Body'].read().decode("utf-8"))
                    predict = round(predictions*100,1)
                except:
                    predict = -1

                if predict >= 80:
                    line_bot_api.reply_message(
                        event.reply_token,
                        [TextSendMessage(text=f'生存確率{predict}%！！'),
                        TextSendMessage(
                            text='安心してください。あなたは無事に帰ってこれるでしょう。'),
                            StickerSendMessage(
                            package_id='11537',
                            sticker_id='52002734')])
                elif predict >= 50:
                    line_bot_api.reply_message(
                        event.reply_token,
                        [TextSendMessage(text=f'生存確率{predict}%'),
                        TextSendMessage(
                            text='おそらく大丈夫。無事を信じています。'),
                            StickerSendMessage(
                            package_id='11538',
                            sticker_id='51626494')])
                elif predict == -1:
                    line_bot_api.reply_message(
                        event.reply_token,
                        [TextSendMessage(text=f'申し訳ございません予測ができませんでした。入力は全て数値orボタンでお願いします。'),
                        TextSendMessage(text='ご利用の際は『予測』とお声がけください😁'),
                            ])

                else:
                    line_bot_api.reply_message(
                        event.reply_token,
                        [TextSendMessage(text=f'...生存確率{predict}%'),
                        TextSendMessage(
                            text='あなたには困難な運命が待ち受けている...かもしれません...'),
                            StickerSendMessage(
                            package_id='11538',
                            sticker_id='51626497')])
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text='ご利用の際は『予測』とお声がけください😁'))


        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            if '予測' == event.message.text:
                response = dynamotable.put_item(
                    Item={
                        'userId': str(event.source.user_id),
                        'Question': '0'
                    }
                )
                line_bot_api.reply_message(
                    event.reply_token,
                    [TextSendMessage(text='ご利用ありがとうございます！いくつかご質問にお答えください。'),
                     TextSendMessage(
                        text='どのチケットを購入しますか？',
                        quick_reply=QuickReply(
                            items=[
                                QuickReplyButton(
                                    action=PostbackAction(
                                        label="1stクラス（500万円）", data="1", display_text="1stクラス（500万円）")
                                ),
                                QuickReplyButton(
                                    action=PostbackAction(
                                        label="2ndクラス（100万円）", data="2", display_text="2ndクラス（100万円）")
                                ),
                                QuickReplyButton(
                                    action=PostbackAction(
                                        label="3rdクラス（3万円）", data="3", display_text="3rdクラス（3万円）")
                                )
                            ]))])

            else:
                res = dynamotable.get_item(Key={'userId': str(event.source.user_id)})
                if not res.get('Item'):
                    response = dynamotable.put_item(
                        Item={
                            'userId': str(event.source.user_id),
                        }
                    )
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='ご利用の際は『予測』とお声がけください😁'))
                    break
                question = str(res['Item']['Question'])
                logger.info(question)
                if question == "1":
                    response = dynamotable.update_item(
                        Key=primary_key,
                        UpdateExpression="set Question = :Question, Age = :Age",
                        ExpressionAttributeValues={
                            ':Question': 2,
                            ':Age': event.message.text
                        })

                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='一緒に乗船する予定の兄弟・配偶者の人数を教えてください。'))

                elif question == "2":
                    response = dynamotable.update_item(
                        Key=primary_key,
                        UpdateExpression="set Question = :Question, SibSp = :SibSp",
                        ExpressionAttributeValues={
                            ':Question': 3,
                            ':SibSp': event.message.text
                        })

                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='一緒に乗船する予定の両親・子供の人数を教えてください。'))

                elif question == "3":
                    response = dynamotable.update_item(
                        Key=primary_key,
                        UpdateExpression="set Question = :Question, Parch = :Parch",
                        ExpressionAttributeValues={
                            ':Question': 4,
                            ':Parch': event.message.text
                        })

                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(
                            text='性別はどちらですか？',
                            quick_reply=QuickReply(
                                items=[
                                    QuickReplyButton(
                                        action=PostbackAction(
                                            label="男性", data="0", display_text="男性")
                                    ),
                                    QuickReplyButton(
                                        action=PostbackAction(
                                            label="女性", data="1", display_text="女性")
                                    )
                                ])))
                else:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='ご利用の際は『予測』とお声がけください😁'))

    return 'OK'
