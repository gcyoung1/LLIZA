from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from django.core.cache import cache
from lliza.lliza import CarlBot
from lliza.models import User

logging_enabled = True

OPT_OUT_KEYWORD = "STOP"
DELETE_MESSAGE = "Your conversation history has been deleted from our servers."
DELETE_KEYWORD = "DELETE"

def log_message(message):
    global logging_enabled
    if logging_enabled:
        print(message)

def load_carlbot(psid: str):
    carl = CarlBot(
        "You're AI Rogerian therapist LLIZA texting a client. Be accepting, empathetic, and genuine. Don't direct or advise.",
        10, 10)
    user_queryset = User.objects.filter(user_id__exact=psid)
    if user_queryset.exists():
        memory_dict = user_queryset.first().memory_dict
        carl.load_from_dict(memory_dict)
    return carl

def save_carlbot(psid: str, carl: CarlBot):
    user_queryset = User.objects.filter(user_id__exact=psid)
    if user_queryset.exists():
        user = user_queryset.first()
        user.memory_dict = carl.save_to_dict()
        user.save()
    else:
        User.objects.create(user_id=psid, memory_dict=carl.save_to_dict())

@csrf_exempt
def webhook(request):
    """Send a dynamic reply to an incoming text message"""
    # Print all the data from the incoming message
    from_number = request.POST.get('From', None)

    # Get the message the user sent our Twilio number
    body = request.POST.get('Body', None)
    psid = from_number
    text = body


    if 'OptOutType' in request.POST:
        # I set up Advanced Opt-Out in Twilio, so we don't need to reply to these messages
        # We just need to delete the user from our database if they opt out
        if text.lower() == OPT_OUT_KEYWORD.lower():
            log_message("Opting out")
            User.objects.filter(user_id__exact=psid).delete()
        return HttpResponse(status=200)
    

    if len(text) > 2100:
        log_message("Message too long")
        reply = "[Message too long, not processed. Please send a shorter message.]"
    elif text.lower() == DELETE_KEYWORD.lower():
        log_message("Deleting conversation history")
        if User.objects.filter(user_id__exact=psid).exists():
            User.objects.filter(user_id__exact=psid).delete()
        reply = DELETE_MESSAGE
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


    log_message(f"Received message: {body}")
    log_message(f"Sending reply: {reply}")
    # Start our TwiML response
    resp = MessagingResponse()
    resp.message(reply)

    return HttpResponse(str(resp), content_type='application/xml')

@require_http_methods(["GET"])
def health(request):
    return HttpResponse("Healthy", status=200)

