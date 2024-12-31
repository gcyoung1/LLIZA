import os
import cryptocode
import json

from lliza.lliza import CarlBot
from lliza.models import User

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
logging_enabled = True

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