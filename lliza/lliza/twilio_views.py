from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def webhook(request):
    """Send a dynamic reply to an incoming text message"""
    # Print all the data from the incoming message
    for key, value in request.POST.items():
        print(f"{key}: {value}")
    # Get the message the user sent our Twilio number
    body = request.POST.get('Body', None)
    

    print(f"Received message: {body}")
    # Start our TwiML response
    resp = MessagingResponse()

    # Determine the right reply for this message
    if body == 'hello':
        resp.message("Hi!")
    elif body == 'bye':
        resp.message("Goodbye")

    return HttpResponse(str(resp), content_type='application/xml')

@require_http_methods(["GET"])
def health(request):
    return HttpResponse("Healthy", status=200)

opt_in_message = "Thank you for messaging LLiza, a therapy bot. You are now opted in to receive replies from our service in the style of client-centered therapist Carl Rogers. Reply HELP for assistance, STOP to unsubscribe, or DELETE to remove your conversation history from our servers. Message/data rates may apply."
opt_out_message = "You have successfully been unsubscribed. You will not receive any more messages from this number. Reply START to resubscribe."
help_message = "Reply STOP to unsubscribe. Reply DELETE to remove your conversation history from our servers. Reply START to resubscribe. Msg&Data Rates May Apply."