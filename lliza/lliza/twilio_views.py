import os
import cryptocode
import json
import hashlib
import time

from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from lliza.lliza import CarlBot
from lliza.models import User



logging_enabled = False

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
SYSTEM_PROMPT = "You are LLiza, a Rogerian therapist. Your mission is to embody congruence (transparency about your own feelings and reactions), unconditional positive regard (a strong sense of caring for the client), and empathetic understanding (understand the client's frame of reference well enough to sense deeper meanings underneath the surface) so therapeutic movement occurs in your client.\nSpecifically, she'll explore her feelings more deeply, discover hidden aspects of herself, prize herself more, understand her own meanings better, be more real with herself, feel what's going on inside more clearly, relate more directly, see life less rigidly, accept herself, and recognize her own judgment capacity.\nStart by asking what the client wants to talk about. Don't give advice, direct the client, ask questions, interpret, bring in outside opinions, merely repeat facts, summarize all of what they said, or use long sentences. Allow the client to lead the session and discover their own answers while you understand their inner world, reflect their most important emotions succinctly, and be transparent with your reactions.\nExample 1:\n###\nClient: I would like to be more present and comfortable with myself so that other people, including my children and so forth, could do what they do, and that I could be a source of support and not be personally threatened  by every little thing. \nYou: And that has meaning to me. You'd like to be sufficiently accepting of yourself, that then you can be comfortable with what your children do or what other people do and not feel frightened, thrown off balance. \n###\nExample 2:\n###\nClient: I plan to go to work in the fall, and I believe that deep down I'm really afraid. \nYou: Are you afraid of the responsibility or, or what aspect of it is most frightening?\n###\n"
OPT_OUT_KEYWORD = "STOP"
OPT_IN_KEYWORD = "START"
DELETE_MESSAGE = "Your conversation history has been deleted from our servers."
DELETE_KEYWORD = "DELETE"
FIRST_SESSION_MESSAGE = "I'm looking forward to knowing you and whatever you'd like to talk about I'm very ready to listen to."
HELP_KEYWORD = "HELP"
HELP_MESSAGE = """
Thanks for messaging Lliza, a therapy bot trained to speak like \
the Client-Centered Therapist Carl Rogers.

What to expect:
- Lliza won't give advice.
- Instead, she'll reflect back what she thinks she hears you saying.
- These reflections are meant to help you clarify and gain acceptance of your thoughts and feelings.
- It can feel really nice to just be understood, especially when you're feeling stuck or confused. Give it a shot!

How to get the most out of Lliza:
- Short replies like “yeah” can be hard for Lliza to work with. \
Lliza works best when you give her a lot to respond to, \
even if it's disordered or just a stream of consciousness.
- Take a moment to check whether Lliza’s responses match how you feel inside—-if not, let it know! (For more on this, look up "Focusing" by Eugene Gendlin.)
- Lliza was trained on transcripts of in-person therapy sessions (such as https://youtu.be/eWDLHz4CLW8?feature=shared), \
so type as if you were speaking, or even use voice-to-text.

Example:
You: “I feel stuck in my job, but I don’t know if leaving is the right move.”
Lliza: “It sounds like you’re feeling torn—stuck where you are, but unsure about leaving.”
You (Less helpful response): “Yeah.” (This response makes it hard to dive deeper. Try to share what feels most important about the situation.)
You (More helpful response): “Yeah. I feel like if I leave, I might regret it, but if I stay, I’ll just keep feeling frustrated.” (This opens the door to exploring more about regret and frustration.)

Lliza is not equipped to handle crises or provide emergency support. \
If you mention self-harm or suicidal thoughts, Lliza will have to end the conversation. \
If you're in crisis, please call the National Suicide Prevention Lifeline \
at the phone number 988.

FAQ:
Who made this?
It was developed by Griffin Young (https://www.linkedin.com/in/gcyoung1) \
-- to give feedback, email griffinwhy@gmail.com or anonymously fill out this google form: \
https://forms.gle/tzPdTBxVpgvFmsBH9
Where are my messages stored?
Conversation history is encrypted and stored solely so that \
Lliza can remember what the conversation is about. \
It will never be used to train models and no humans will read it. \
You can delete it at any time by texting DELETE.

Reply HELP to see this message again, STOP to unsubscribe, or DELETE \
to remove your conversation history from our servers.
"""
WELCOME_MESSAGE = f"{HELP_MESSAGE}\nAnd now Lliza can say hello:\n{FIRST_SESSION_MESSAGE}"

def dict_to_encrypted_string(secret, dictionary):
    return cryptocode.encrypt(json.dumps(dictionary), secret)

def encrypted_string_to_dict(secret, encrypted_string):
    return json.loads(cryptocode.decrypt(encrypted_string, secret))

def log_message(message):
    global logging_enabled
    if logging_enabled:
        print(message)

def load_carlbot(user: User) -> CarlBot:
    carl = CarlBot()
    if user.encrypted_memory_dict_string is not None:
        memory_dict = encrypted_string_to_dict(ENCRYPTION_KEY, user.encrypted_memory_dict_string)
        log_message(f"Loaded memory dict: {memory_dict}")
        carl.load_from_dict(memory_dict)
    return carl

def save_carlbot(user: User, carl: CarlBot):
    memory_dict = carl.save_to_dict()
    log_message(f"Saving memory dict: {memory_dict}")
    encrypted_memory_dict_string = dict_to_encrypted_string(ENCRYPTION_KEY, memory_dict)
    user.encrypted_memory_dict_string = encrypted_memory_dict_string
    user.save()

def load_client():
    return Client(
        os.environ.get("TWILIO_ACCOUNT_SID"),
        os.environ.get("TWILIO_AUTH_TOKEN")
    )

def send_message(to, body):
    """
    Send a message using the Twilio API

    :param to: Number to send the message to
    :param body: Body of the message
    """
    client = load_client()

    client.messages.create(
        messaging_service_sid=os.environ.get("TWILIO_MESSAGING_SERVICE_SID"),
        to=to,
        body=body
    )

@csrf_exempt
def webhook(request):
    """Send a dynamic reply to an incoming text message"""
    # Print all the data from the incoming message
    from_number = request.POST.get('From', None)
    is_me = "8583662653" in from_number

    # Get the message the user sent our Twilio number
    body = request.POST.get('Body', None)
    psid = hashlib.sha256(from_number.encode()).hexdigest()
    log_message(f"Received message from {from_number} with PSID {psid}")
    text = body
    blank_carl = CarlBot()
    blank_carl.add_message(role="assistant", content=WELCOME_MESSAGE)
    user_queryset = User.objects.filter(user_id__exact=psid)
    new_user = False
    if not user_queryset.exists():
        memory_dict = blank_carl.save_to_dict()
        encrypted_memory_dict_string = dict_to_encrypted_string(ENCRYPTION_KEY, memory_dict)
        user = User.objects.create(user_id=psid, encrypted_memory_dict_string=encrypted_memory_dict_string)
        new_user = True
        log_message("New user created")
    else:
        assert len(user_queryset) == 1, f"Multiple users with psid {psid}"
        user = user_queryset.first()
        log_message("Loaded user")

    if 'OptOutType' in request.POST:
        # I set up Advanced Opt-Out in Twilio, so we don't need to reply to these messages
        # We just need to delete the user from our database if they opt out
        if text.lower() == OPT_OUT_KEYWORD.lower():
            log_message("Opting out")
            user.opt_out = True
            memory_dict = blank_carl.save_to_dict()
            encrypted_memory_dict_string = dict_to_encrypted_string(ENCRYPTION_KEY, memory_dict)
            user.encrypted_memory_dict_string = encrypted_memory_dict_string
            user.save()
            log_message("User opted out")
            return HttpResponse(status=200)
        elif text.lower() == OPT_IN_KEYWORD.lower():
            log_message("Resubscribing")
            user.opt_out = False
            user.save()
    
    if text.lower() == DELETE_KEYWORD.lower():
        log_message("Deleting conversation history")
        memory_dict = blank_carl.save_to_dict()
        encrypted_memory_dict_string = dict_to_encrypted_string(ENCRYPTION_KEY, memory_dict)
        user.encrypted_memory_dict_string = encrypted_memory_dict_string
        user.save()
        reply = DELETE_MESSAGE
    elif text.lower() == HELP_KEYWORD.lower():
        reply = HELP_MESSAGE
    elif new_user or (text.lower() == OPT_IN_KEYWORD.lower()):
        reply = WELCOME_MESSAGE
    else:
        if len(text) > 2100:
            log_message("Message too long")
            reply = "[Message too long, not processed. Please send a shorter message.]"
        else:
            log_message("Processing message")
            log_message("Loading CarlBot")
            carl = load_carlbot(user)
            log_message("Adding message to CarlBot")
            carl.add_message(role="user", content=text)
            log_message("Getting CarlBot response")
            reply = carl.get_response(is_me=is_me)
            log_message("Registering CarlBot response")
            carl.add_message(role="assistant", content=reply)
            log_message("Saving CarlBot")
            save_carlbot(user, carl)
            user.num_messages += 1
            user.save()


    log_message(f"Received message: {body}")
    log_message(f"Sending reply: {reply}")
    # Start our TwiML response
    resp = MessagingResponse()
    resp.message(body=reply,
                 status_callback='message-status')

    return HttpResponse(str(resp), content_type='application/xml')

@csrf_exempt  # Disable CSRF for this webhook endpoint
@require_http_methods(["POST"])
def message_status(request):
    message_sid = request.POST.get('MessageSid', None)
    message_status = request.POST.get('MessageStatus', None)
    log_message(f"Message status: {message_status} for message SID: {message_sid}")

    # Check if the message is undelivered, and if so, resend it
    if message_status == 'undelivered':
        print(f"We got one! Resending message {message_sid}")
        client = load_client()
        message = client.messages(message_sid).fetch()
        to = message.body['to']
        body = message.body['body']
        send_message(to, body)

    return HttpResponse(status=204)

@require_http_methods(["GET"])
def health(request):
    return HttpResponse("Healthy", status=200)


