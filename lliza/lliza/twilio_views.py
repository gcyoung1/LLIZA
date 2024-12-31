import os
import cryptocode
import json
import urllib
from ast import literal_eval


from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client

from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django_q import tasks
from django_q.models import Schedule
from croniter import croniter
from datetime import datetime

from lliza.lliza import CarlBot
from lliza.models import User
from lliza.utils import get_user_from_number, log_message, load_carlbot, save_carlbot

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
SYSTEM_PROMPT = "You are LLiza, a Rogerian therapist. Your mission is to embody congruence (transparency about your own feelings and reactions), unconditional positive regard (a strong sense of caring for the client), and empathetic understanding (understand the client's frame of reference well enough to sense deeper meanings underneath the surface) so therapeutic movement occurs in your client.\nSpecifically, she'll explore her feelings more deeply, discover hidden aspects of herself, prize herself more, understand her own meanings better, be more real with herself, feel what's going on inside more clearly, relate more directly, see life less rigidly, accept herself, and recognize her own judgment capacity.\nStart by asking what the client wants to talk about. Don't give advice, direct the client, ask questions, interpret, bring in outside opinions, merely repeat facts, summarize all of what they said, or use long sentences. Allow the client to lead the session and discover their own answers while you understand their inner world, reflect their most important emotions succinctly, and be transparent with your reactions.\nExample 1:\n###\nClient: I would like to be more present and comfortable with myself so that other people, including my children and so forth, could do what they do, and that I could be a source of support and not be personally threatened  by every little thing. \nYou: And that has meaning to me. You'd like to be sufficiently accepting of yourself, that then you can be comfortable with what your children do or what other people do and not feel frightened, thrown off balance. \n###\nExample 2:\n###\nClient: I plan to go to work in the fall, and I believe that deep down I'm really afraid. \nYou: Are you afraid of the responsibility or, or what aspect of it is most frightening?\n###\n"
OPT_OUT_KEYWORD = "STOP"
OPT_IN_KEYWORD = "START"
DELETE_MESSAGE = "Your conversation history has been deleted from our servers."
DELETE_KEYWORD = "DELETE"
FIRST_SESSION_MESSAGE = "I'm looking forward to knowing you. Whatever you'd like to talk about I'm very ready to listen to."
HELP_KEYWORD = "HELP"
HELP_MESSAGE = """
Thanks for messaging Lliza, a bot trained to speak like \
famous therapist Carl Rogers.

What to expect:
- Lliza won't give advice
- Instead, it'll help you clarify your feelings
- Being understood feels great if you're stuck or confused. Give it a shot!

Tips:
- Short replies = boring conversation
- Check whether Lliza’s responses match how you feel inside—-if not, let it know! (See "Focusing" by Eugene Gendlin)
- Lliza was trained on therapy sessions like https://youtu.be/eWDLHz4CLW8. \
Try voice-to-text
- The first message is hard. Schedule texts from Lliza: https://docs.google.com/forms/d/e/1FAIpQLSfZ5YAds1ZQ-R9snaxiJQ6nqdBTZepKll5p0YjoZmJCIZsI_A/viewform?usp=pp_url&entry.776076175={}

E.g.:
You: “I feel stuck, but I don’t know if leaving is the right move.”
Lliza: “You’re feeling torn—stuck where you are, but unsure about leaving.”
You (Less helpful): “Ya”
You (More helpful): “If I leave, I might regret it, but if I stay, I’ll keep feeling frustrated.”

If you mention self-harm, Lliza ends the conversation. \
For crises, call the Suicide Prevention Lifeline (988)

FAQ:
- Made by Griffin Young (https://www.linkedin.com/in/gcyoung1)
- Feedback form: https://forms.gle/tzPdTBxVpgvFmsBH9
- Messages are encrypted and only used for context

Reply HELP to see this message again, STOP to unsubscribe, or DELETE \
to delete your conversation history
"""
WELCOME_MESSAGE = f"{HELP_MESSAGE}\nNow Lliza, say hello:\n{FIRST_SESSION_MESSAGE}"
LLIZA_VOICE = "Google.en-US-Wavenet-C"

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

def delete_memory(user: User):
    memory_dict = CarlBot().save_to_dict()
    encrypted_memory_dict_string = dict_to_encrypted_string(ENCRYPTION_KEY, memory_dict)
    user.encrypted_memory_dict_string = encrypted_memory_dict_string
    user.save()

@csrf_exempt
def webhook(request):
    """Send a dynamic reply to an incoming text message"""
    # Print all the data from the incoming message
    from_number = request.POST.get('From', None)
    is_me = "8583662653" in from_number

    # Get the message the user sent our Twilio number
    body = request.POST.get('Body', None)
    log_message(f"Received message from {from_number}")
    user = get_user_from_number(from_number)
    log_message(f"Received message from {from_number} with user_id {user.user_id}")
    text = body
    
    url_compatible_user_id = urllib.parse.quote(user.user_id)
    
    new_user = False

    if 'OptOutType' in request.POST:
        # I set up Advanced Opt-Out in Twilio, so we don't need to reply to these messages
        # We just need to delete the user from our database if they opt out
        if text.lower() == OPT_OUT_KEYWORD.lower():
            log_message("Opting out")
            user.opt_out = True
            delete_memory(user)
            log_message("User opted out")
            return HttpResponse(status=200)
        elif text.lower() == OPT_IN_KEYWORD.lower():
            log_message("Resubscribing")
            user.opt_out = False
            user.save()
    
    if text.lower() == DELETE_KEYWORD.lower():
        log_message("Deleting conversation history")
        delete_memory(user)
        reply = DELETE_MESSAGE
    elif text.lower() == HELP_KEYWORD.lower():
        reply = HELP_MESSAGE.format(url_compatible_user_id)
    elif new_user or (text.lower() == OPT_IN_KEYWORD.lower()):
        reply = WELCOME_MESSAGE.format(url_compatible_user_id)
        carl = load_carlbot(user)
        carl.add_message(role="assistant", content=FIRST_SESSION_MESSAGE)
        save_carlbot(user, carl)
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

def send_intro_message(user_id) -> None:
    """
    Send an introductory message to a user for a new session.

    :param user_id: User ID to send the message to
    """
    log_message(f"Sending intro message to {user_id}")
    number = cryptocode.decrypt(user_id, ENCRYPTION_KEY)
    is_me = "8583662653" in number
    user = get_user_from_number(number)
    if user is None:
        print(f"Error sending intro message: no users for number {number}")
        return
    if user.opt_out:
        log_message(f"User {number} has opted out, not sending intro message and deleting schedules")
        number = cryptocode.decrypt(user_id, ENCRYPTION_KEY)
        schedules_matching_user = [schedule for schedule in Schedule.objects.all() if cryptocode.decrypt(literal_eval(schedule.args)[0], ENCRYPTION_KEY) == number]
        for schedule in schedules_matching_user:
            schedule.delete()
    else:
        carl = load_carlbot(user)
        carl.add_message(role="system", content=carl.get_new_session_prompt())
        new_session_message = carl.get_new_session_message(is_me=is_me)
        carl.add_message(role="assistant", content=new_session_message)
        save_carlbot(user, carl)
        user.save()
        send_message(number, new_session_message)

def day_and_time_to_utc_cron_str(day: str, time: str) -> str:
    day_map = {
        'Sun': 0,
        'Mon': 1,
        'Tue': 2,
        'Wed': 3,
        'Thu': 4,
        'Fri': 5,
        'Sat': 6
    }
    day_int = day_map[day]

    hour, minute = time.split(":")
    # Convert hour and possibly day from EST to UTC
    hour = (int(hour) + 5)
    if hour >= 24:
        hour -= 24
        day_int += 1
        
    cron_string = f"{minute} {hour} * * {day_int}"

    return cron_string

def get_next_cron_time(cron_string: str) -> str:
    now = datetime.now()
    cron = croniter(cron_string, now)
    next_time = cron.get_next(datetime)
    return next_time.strftime("%Y-%m-%d %H:%M:%S")

# Webhook for receiving responses from a Google Form set up to schedule sessions
@csrf_exempt
@require_http_methods(["POST", "GET"])
def schedule_webhook(request):
    """
    Receives a POST request from a Google Form containing scheduling information for a user,
    schedules the sessions, and sends a confirmation message to the user.
    Example POST request body:
    {
  "User ID (Don't edit)": "",
  "What day of the week for the first session?": "Tuesday",
  "What time for the first session of the week?": "08:00",
  "What day of the week for the second session?": "None"
}

    :param request: POST request containing scheduling information
    """
    if request.method == "GET":
        return HttpResponse(status=200)
    data = json.loads(request.body)
    log_message(f"Received scheduling request data: {data}")
    # Get the user
    user_id = data.get("User ID (Don't edit)")
    if not user_id:
        print("Error scheduling: no user ID")
        return HttpResponse(status=404)
    log_message(f"Received scheduling request for user {user_id}")
    number = cryptocode.decrypt(user_id, ENCRYPTION_KEY)
    user = get_user_from_number(number)
    if user is None:
        print(f"Error scheduling: no users for number {number}")
        return HttpResponse(status=404)
    
    # Delete all existing schedules for the user
    schedules_matching_user = [schedule for schedule in Schedule.objects.all() if cryptocode.decrypt(literal_eval(schedule.args)[0], ENCRYPTION_KEY) == number]
    for schedule in schedules_matching_user:
        schedule.delete()
    message_to_send_user = f"Deleted {len(schedules_matching_user)} existing schedules.\n"
    
    first_day = data.get("What day of the week for the first session?")
    first_time = data.get("What time (EST) for the first session of the week?")
    if first_day != "None":
        first_cron_string = day_and_time_to_utc_cron_str(first_day, first_time)
        log_message(f"First day: {first_day}, first time: {first_time}")
        log_message(f"First cron string: {first_cron_string}")
        tasks.schedule(
            "lliza.twilio_views.send_intro_message",
            user_id,
            schedule_type="C",
            cron=first_cron_string,
            next_run=get_next_cron_time(first_cron_string)
        )
        message_to_send_user += f"\nScheduled first repeating session for {first_day} at {first_time}"
    
    second_day = data.get("What day of the week for the second session?")
    second_time = data.get("What time (EST) for the second session of the week?")
    if second_day is not None and second_day != "None": # Will be None if the first day is "None"
        log_message(f"Second day: {second_day}, second time: {second_time}")
        second_cron_string = day_and_time_to_utc_cron_str(second_day, second_time)
        log_message(f"Second cron string: {second_cron_string}")
        tasks.schedule(
            "lliza.twilio_views.send_intro_message",
            user_id,
            schedule_type="C",
            cron=second_cron_string,
            next_run=get_next_cron_time(second_cron_string)
        )
        message_to_send_user += f"\nScheduled second repeating session for {second_day} at {second_time}\n"

    send_message(number, message_to_send_user)
    
    return HttpResponse(status=200)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def handle_incoming_call(request):
    """Handle incoming call and return TwiML response to connect to Conversation Relay."""
    response = VoiceResponse()
    response.say("Please wait while we connect your call to Lliza.", voice="woman")
    response.pause(length=1)
    number = request.POST.get('From', None)
    is_me = "8583662653" in number
    user = get_user_from_number(number)
    carl = load_carlbot(user)
    carl.add_message(role="system", content=carl.get_new_session_prompt())
    new_session_message = carl.get_new_session_message(is_me=is_me)
    carl.add_message(role="assistant", content=new_session_message)
    save_carlbot(user, carl)
    user.save()
    response.say(new_session_message, voice=LLIZA_VOICE)

    connect = Connect()
    host = request.get_host()
    log_message(f"Host: {host}")
    connect.conversation_relay(
        url=f'wss://{host}/conversation-relay',
        dtmf_detection=False,
        interruptible=True,
        welcome_greeting_interruptible=False,
        voice=LLIZA_VOICE,
    )
    response.append(connect)
    return HttpResponse(str(response), content_type="application/xml")