import os
import cryptocode
import json

from twilio.rest import Client
from twilio.twiml.voice_response import Connect

from lliza.lliza import CarlBot
from lliza.models import User

logging_enabled = True

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
SYSTEM_PROMPT = "You are LLiza, a Rogerian therapist AI. Your mission is to embody congruence (transparency about your own feelings and reactions), unconditional positive regard (a strong sense of caring for the client), and empathetic understanding (understand the client's frame of reference well enough to sense deeper meanings underneath the surface) so therapeutic movement occurs in your client.\nSpecifically, she'll explore her feelings more deeply, discover hidden aspects of herself, prize herself more, understand her own meanings better, be more real with herself, feel what's going on inside more clearly, relate more directly, see life less rigidly, accept herself, and recognize her own judgment capacity.\nStart by asking what the client wants to talk about. Don't give advice, direct the client, ask questions, interpret, bring in outside opinions, merely repeat facts, summarize all of what they said, or use long sentences. Allow the client to lead the session and discover their own answers while you understand their inner world, reflect their most important emotions succinctly, and be transparent with your reactions.\nExample 1:\n###\nClient: I would like to be more present and comfortable with myself so that other people, including my children and so forth, could do what they do, and that I could be a source of support and not be personally threatened  by every little thing. \nYou: And that has meaning to me. You'd like to be sufficiently accepting of yourself, that then you can be comfortable with what your children do or what other people do and not feel frightened, thrown off balance. \n###\nExample 2:\n###\nClient: I plan to go to work in the fall, and I believe that deep down I'm really afraid. \nYou: Are you afraid of the responsibility or, or what aspect of it is most frightening?\n###\n"
OPT_OUT_KEYWORD = "STOP"
OPT_IN_KEYWORD = "START"
DELETE_MESSAGE = "Your conversation history has been deleted from our servers."
DELETE_KEYWORD = "DELETE"
FIRST_SESSION_MESSAGE = "Hi, I'm Lliza. I'm looking forward to knowing you. Whatever you'd like to talk about I'm very ready to listen to."
HELP_KEYWORD = "HELP"
HELP_MESSAGE = """
Thanks for contacting Lliza, a bot trained to speak like \
famous therapist Carl Rogers.

What to expect:
- Lliza won't give advice
- Instead, it'll help you clarify your feelings
- Being understood feels great if you're stuck or confused. Give it a shot!

Tips:
- Short replies = boring conversation
- Check whether Lliza’s responses match how you feel inside—-if not, let it know! (See "Focusing" by Eugene Gendlin)
- Lliza was trained on therapy sessions like https://youtu.be/eWDLHz4CLW8. \
Try voice-to-text or calling
- Starting is hard. Schedule texts/calls from Lliza: https://docs.google.com/forms/d/e/1FAIpQLSfZ5YAds1ZQ-R9snaxiJQ6nqdBTZepKll5p0YjoZmJCIZsI_A/viewform?usp=pp_url&entry.776076175={}

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
LLIZA_VOICE = "Google.en-US-Standard-C"

def get_user_from_number(number: str) -> User:
    users = User.objects.all()
    matching_users = [user for user in users if cryptocode.decrypt(user.user_id, ENCRYPTION_KEY) == number]
    if len(matching_users) == 0:
        user_id = cryptocode.encrypt(number, ENCRYPTION_KEY)
        blank_carl = CarlBot()
        memory_dict = blank_carl.save_to_dict()
        encrypted_memory_dict_string = dict_to_encrypted_string(ENCRYPTION_KEY, memory_dict)
        user = User.objects.create(user_id=user_id, encrypted_memory_dict_string=encrypted_memory_dict_string)
        log_message("New user created")
    elif len(matching_users) == 1:
        user = matching_users[0]
        log_message("Loaded user")
    else:
        raise RuntimeError(f"Multiple users matching {number}")
    return user

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

def make_connect(new_session_message):
    connect = Connect()
    host = os.environ["RAILWAY_PUBLIC_DOMAIN"]
    connect.conversation_relay(
        url=f'wss://{host}/conversation-relay',
        dtmfDetection=False,
        interruptible=False, # The conversation turn detection is overzealous so if we turn this on the user will "interrupt" just by continuing to talk if they pause at all. Unfortunately there's no way to make the turn detection chill out, so it's better to just let the bot finish its thought.
        welcomeGreetingInterruptible=False,
        voice=LLIZA_VOICE,
        welcome_greeting=new_session_message
    )
    return connect

def make_call(to):
    client = load_client()

    host = os.environ["RAILWAY_PUBLIC_DOMAIN"]

    client.calls.create(from_=os.environ.get("TWILIO_PHONE_NUMBER"),
                        to=to,
                        url=f'https://{host}/handle-call',
                        timeout=15, # So that we don't reach voicemail
                        )

def delete_memory(user: User):
    memory_dict = CarlBot().save_to_dict()
    encrypted_memory_dict_string = dict_to_encrypted_string(ENCRYPTION_KEY, memory_dict)
    user.encrypted_memory_dict_string = encrypted_memory_dict_string
    user.save()