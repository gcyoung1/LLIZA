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
FB_VERIFY_TOKEN = os.environ["FB_VERIFY_TOKEN"]
FB_APP_SECRET = os.environ["FB_APP_SECRET"]
PAGE_ACCESS_TOKEN = os.environ["PAGE_ACCESS_TOKEN"]

logging_enabled = True


def log_message(message):
    global logging_enabled
    if logging_enabled:
        print(message)


def load_carlbot(psid: str):
    carl = CarlBot(
        "You're AI Rogerian therapist LLIZA texting a client. Be accepting, empathetic, and genuine. Don't direct or advise.",
        10, 10)
    if cache.get(psid) is not None:
        dialogue_buffer, summary_buffer, crisis_mode = cache.get(psid)
        carl.load(dialogue_buffer, summary_buffer, crisis_mode)
    return carl


def save_carlbot(psid: str, carl: CarlBot):
    cache.set(psid,
              (carl.dialogue_buffer, carl.summary_buffer, carl.crisis_mode))

def get_hmac_string(secret, message):
    return hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    # Webhook verification
    if request.method == 'GET':
        if request.GET.get("hub.mode") == "subscribe" and request.GET.get(
                "hub.challenge"):
            if not request.GET.get("hub.verify_token") == FB_VERIFY_TOKEN:
                return HttpResponse("Verification token mismatch", status=403)
            log_message("WEBHOOK_VERIFIED")
            return HttpResponse(request.GET["hub.challenge"], status=200)

    elif request.method == 'POST':
        # Validate payload
        print(f"Received headers: {request.headers}")
        received_signature = request.headers["X-Hub-Signature-256"].split('=')[1]
        payload = request.body
        expected_signature = get_hmac_string(FB_APP_SECRET, payload)

        if not hmac.compare_digest(expected_signature, received_signature):
            log_message("Signature hash does not match")
            return HttpResponse('INVALID SIGNATURE HASH', status=403)

        log_message("Signature hash matches")
        body = json.loads(payload.decode('utf-8'))
        log_message(f"Received body: {body}")

        if 'object' in body and body['object'] == 'page':
            entries = body['entry']
            log_message(f"Received entries: {entries}")
            # Iterate through each entry as multiple entries can sometimes be batched
            for entry in entries:
                if "messaging" not in entry:
                    log_message("No messaging in entry")
                    continue
                messaging = entry['messaging']
                if len(messaging) > 1:
                    raise NotImplementedError(
                        "This example only supports a single message per request"
                    )
                psid = messaging[0]['sender']['id']
                message = messaging[0]['message']
                log_message(f"Received message: {message}")
                if 'quick_reply' in message:
                    log_message("Processing quick reply")
                    if message['quick_reply']['payload'] == "DELETE_DATA":
                        cache.delete(psid)
                        reply = "Session history deleted."
                else:
                    text = message['text']
                    log_message("Received message: " + text)
                    if len(text) > 2100:
                        log_message("Message too long")
                        reply = "[Message too long, not processed. Please send a shorter message.]"
                    else:
                        log_message("Processing message")
                        log_message("Loading CarlBot")
                        carl = load_carlbot(psid)
                        log_message("Adding message to CarlBot")
                        carl.add_message(role="user", content=text)
                        log_message("Getting CarlBot response")
                        reply = carl.get_response()
                        log_message("Registering CarlBot response")
                        carl.add_message(role="assistant", content=reply)
                        log_message("Saving CarlBot")
                        save_carlbot(psid, carl)

                log_message("Sending reply")
                send_reply(psid, reply)
            return HttpResponse('WEBHOOK EVENT HANDLED', status=200)
        return HttpResponse('INVALID WEBHOOK EVENT', status=403)


def post_payload(payload):
    url = f"https://graph.facebook.com/me/messages?access_token={PAGE_ACCESS_TOKEN}"  # Replace with actual API version and Page ID
    log_message(f"Posting payload to {url}")
    requests.post(url, json=payload)


def send_reply(psid, reply):
    log_message("Sending reply: " + reply)
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
    log_message(f"Sending payload {payload}")
    post_payload(payload)

@require_http_methods(["GET"])
def health(request):
    return HttpResponse("Healthy", status=200)