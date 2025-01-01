import os
import cryptocode
import json
import urllib
from ast import literal_eval


from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse

from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django_q import tasks
from django_q.models import Schedule
from croniter import croniter
from datetime import datetime

from lliza.lliza import CarlBot
from lliza.models import User
from lliza.utils import get_user_from_number, log_message, load_carlbot, save_carlbot, load_client, send_message, DELETE_KEYWORD, DELETE_MESSAGE, HELP_KEYWORD, HELP_MESSAGE, OPT_OUT_KEYWORD, OPT_IN_KEYWORD, FIRST_SESSION_MESSAGE, WELCOME_MESSAGE, ENCRYPTION_KEY, make_connect, make_call, delete_memory

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

def start_session(user_id, call_or_text) -> None:
    """
    Send an introductory message to a user for a new session.

    :param user_id: User ID to send the message to
    """
    log_message(f"Sending intro message to {user_id}")
    number = cryptocode.decrypt(user_id, ENCRYPTION_KEY)
    is_me = "8583662653" in number
    user = get_user_from_number(number)
    if not user:
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
        new_session_message = carl.start_new_session(is_me=is_me)
        save_carlbot(user, carl)
        if call_or_text == "Call":
            send_message(number, new_session_message)
        elif call_or_text == "Text":
            connect = make_connect(new_session_message)
            make_call(number, connect)

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
    first_call_or_text = data.get("Text or call for the first session of the week?")
    if first_day != "None":
        first_cron_string = day_and_time_to_utc_cron_str(first_day, first_time)
        log_message(f"First day: {first_day}, first time: {first_time}")
        log_message(f"First cron string: {first_cron_string}")
        tasks.schedule(
            "lliza.twilio_views.start_session",
            user_id,
            first_call_or_text,
            schedule_type="C",
            cron=first_cron_string,
            next_run=get_next_cron_time(first_cron_string)
        )
        message_to_send_user += f"\nScheduled first repeating session for {first_day} at {first_time}"
    
    second_day = data.get("What day of the week for the second session?")
    second_time = data.get("What time (EST) for the second session of the week?")
    second_call_or_text = data.get("Text or call for the second session of the week?")
    if second_day is not None and second_day != "None": # Will be None if the first day is "None"
        log_message(f"Second day: {second_day}, second time: {second_time}")
        second_cron_string = day_and_time_to_utc_cron_str(second_day, second_time)
        log_message(f"Second cron string: {second_cron_string}")
        tasks.schedule(
            "lliza.twilio_views.start_session",
            user_id,
            second_call_or_text,
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
    new_session_message = carl.start_new_session(is_me=is_me)
    save_carlbot(user, carl)

    connect = make_connect(new_session_message)
    response.append(connect)
    return HttpResponse(str(response), content_type="application/xml")