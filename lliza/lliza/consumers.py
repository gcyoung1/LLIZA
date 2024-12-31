from channels.generic.websocket import WebsocketConsumer
import json

from lliza.utils import get_user_from_number, log_message, load_carlbot, save_carlbot

from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client

from django.http import HttpResponse

class ConversationRelayConsumer(WebsocketConsumer):
    def connect(self):
        """Handle WebSocket connection."""
        log_message("Client connected to Conversation Relay.")
        self.accept()
        self.user = None
        self.carlbot = None

    def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if self.user is not None and self.carl is not None:
            save_carlbot(self.user, self.carlbot)
            self.user.save()
        log_message("Client disconnected.")

    def receive(self, text_data):
        """Handle incoming messages from Twilio."""
        try:
            log_message("Processing incoming message")
            data = json.loads(text_data)
            # pretty print the data
            log_message(json.dumps(data, indent=4))

            if data['type'] == 'setup':
                self.handle_setup(data)
            elif data['type'] == 'prompt':
                self.handle_prompt(data)
            elif data['type'] == 'interrupt':
                self.handle_interrupt(data)
            elif data['type'] == 'error':
                self.handle_error(data)

        except Exception as e:
            log_message(f"Error processing message: {e}")

    def handle_setup(self, data):
        """Handle setup message from Twilio."""
        try:
            if data['direction'] == 'inbound':
                number = data['from']
            else:
                number = data['to']
            self.user = get_user_from_number(number)
            self.carlbot = load_carlbot(self.user)
            log_message("Setup complete.")
        except Exception as e:
            log_message(f"Error processing setup message: {e}")

    def handle_prompt(self, data):
        """Handle messages from user"""
        try:
            raw_message = data['voicePrompt']
            unicode_decoded = raw_message.encode().decode('unicode-escape')
            self.carlbot.add_message(role="user", content=unicode_decoded)
            reply = self.carlbot.get_response(is_me=False)
            self.carlbot.add_message(role="assistant", content=reply)            
            self.user.num_messages += 1
            twilio_response = {
                "type": "text",
                "token": reply,
                "last": True
            }
            self.send(text_data=json.dumps(twilio_response))
        except Exception as e:
            log_message(f"Error processing prompt: {e}")

    def handle_interrupt(self, data):
        """Handle user interruptions"""
        try:
            amended_content = data["utteranceUntilInterrupt"] + "..."
            self.carlbot.dialogue_buffer[-1] = {"role": "assistant",
                                                "content": amended_content}
        except Exception as e:
            log_message(f"Error processing interrupt: {e}")

    def handle_error(self, data):
        try:
            print("Error: ", data)
        except Exception as e:
            log_message(f"Error processing error: {e}")