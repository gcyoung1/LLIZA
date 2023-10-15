import json
import hmac
import hashlib
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
import requests
import os

from lliza.lliza import CarlBot

LATEST_API_VERSION = "v18.0"
TOKEN = os.environ["TOKEN"]
PAGE_ACCESS_TOKEN = os.environ["PAGE_ACCESS_TOKEN"]

def load_carlbot(psid: str):
    carl = CarlBot("You are Carl Rogers texting a client.", 10, 10)
    print("Trying to load memory...")
    if cache.get(psid) is not None:
        dialogue_buffer, summary_buffer = cache.get(psid)
        carl.load(dialogue_buffer, summary_buffer)
        print("Memory found!")
    return carl


def save_carlbot(psid: str, carl: CarlBot):
    cache.set(psid, (carl.dialogue_buffer, carl.summary_buffer))
    print("Memory saved!")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    # Webhook verification
    if request.method == 'GET':
        if request.GET.get("hub.mode") == "subscribe" and request.GET.get(
                "hub.challenge"):
            if not request.GET.get("hub.verify_token") == TOKEN:
                return HttpResponse("Verification token mismatch", status=403)
            print("WEBHOOK_VERIFIED")
            return HttpResponse(request.GET["hub.challenge"], status=200)

    elif request.method == 'POST':
        # Validate payload
        signature = request.headers["X-Hub-Signature-256"].split('=')[1]
        payload = request.body
        expected_signature = hmac.new(TOKEN.encode('utf-8'), payload,
                                      hashlib.sha256).hexdigest()

        if signature != expected_signature:
            print("Signature hash does not match")
            #return HttpResponse('INVALID SIGNATURE HASH', status=403)

        body = json.loads(payload.decode('utf-8'))

        if 'object' in body and body['object'] == 'page':
            entries = body['entry']
            # Iterate through each entry as multiple entries can sometimes be batched
            for entry in entries:
                if "messaging" not in entry:
                    continue
                messaging = entry['messaging']
                if len(messaging) > 1:
                    raise NotImplementedError(
                        "This example only supports a single message per request"
                    )
                psid = messaging[0]['sender']['id']
                message = messaging[0]['message']
                if 'quick_reply' in message:
                    if message['quick_reply']['payload'] == "DELETE_DATA":
                        cache.delete(psid)
                        send_reply(psid, "Session history deleted.")
                        return HttpResponse('WEBHOOK EVENT HANDLED',
                                            status=200)

                text = message['text']
                print("Received message: " + text)

                carl = load_carlbot(psid)

                carl.add_message(role="user", message=text)
                reply = carl.get_response()
                carl.add_message(role="assistant", message=reply)
                send_reply(psid, reply)
                save_carlbot(psid, carl)

            return HttpResponse('WEBHOOK EVENT HANDLED', status=200)
        return HttpResponse('INVALID WEBHOOK EVENT', status=403)


def post_payload(payload):
    url = f"https://graph.facebook.com/me/messages?access_token={PAGE_ACCESS_TOKEN}"  # Replace with actual API version and Page ID
    requests.post(url, json=payload)


def send_reply(psid, reply):
    print("Sending reply: " + reply)
    print("(With quick replies)")
    payload = {
        'recipient': {
            'id': psid
        },
        'message': {
            'text':
            reply,
            "quick_replies": [{
                "content_type": "text",
                "title": "Delete history",
                "payload": "DELETE_DATA",
            }]
        },
        'messaging_type': 'RESPONSE',
    }
    post_payload(payload)
