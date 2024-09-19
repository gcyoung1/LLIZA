from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from django.core.cache import cache
from lliza.lliza import CarlBot

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

@csrf_exempt
def webhook(request):
    """Send a dynamic reply to an incoming text message"""
    # Print all the data from the incoming message
    from_number = request.POST.get('From', None)

    # Get the message the user sent our Twilio number
    body = request.POST.get('Body', None)
    
    psid = from_number
    text = body
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


    print(f"Received message: {body}")
    # Start our TwiML response
    resp = MessagingResponse()
    resp.message(reply)

    return HttpResponse(str(resp), content_type='application/xml')

@require_http_methods(["GET"])
def health(request):
    return HttpResponse("Healthy", status=200)

opt_in_message = "Thank you for messaging LLiza, a therapy bot. You are now opted in to receive replies from our service in the style of client-centered therapist Carl Rogers. Reply HELP for assistance, STOP to unsubscribe, or DELETE to remove your conversation history from our servers. Message/data rates may apply."
opt_out_message = "You have successfully been unsubscribed. You will not receive any more messages from this number. Reply START to resubscribe."
help_message = "Reply STOP to unsubscribe. Reply DELETE to remove your conversation history from our servers. Reply START to resubscribe. Msg&Data Rates May Apply."