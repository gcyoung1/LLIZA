from channels.generic.websocket import SyncWebsocketConsumer
import json
from django.contrib.auth.models import User  # Adjust based on your user model

from lliza.utils import get_user_from_number, log_message, load_carlbot, save_carlbot

from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client

from django.http import HttpResponse

class ConversationRelayConsumer(SyncWebsocketConsumer):
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
        log_message("Client disconnected.")

    def receive(self, text_data):
        """Handle incoming messages from Twilio."""
        try:
            log_message("Processing incoming message")
            data = json.loads(text_data)
            # pretty print the data
            log_message(json.dumps(data, indent=4))
            response = VoiceResponse()
            response.say("Hello, this is Carl. How can I help you today?")
            return HttpResponse(str(response), content_type="application/xml")


            # if data['event'] == 'text':
            #     # Extract user and message
            #     user_id = data.get('user_id')  # Ensure Twilio sends a user identifier
            #     user = self.load_user(user_id)
            #     text = data['message']['content']
            #     log_message(f"Received user message: {text}")

            #     # Process message with CarlBot
            #     log_message("Loading CarlBot")
            #     carl = load_carlbot(user)
            #     log_message("Adding message to CarlBot")
            #     carl.add_message(role="user", content=text)

            #     log_message("Getting CarlBot response")
            #     reply = carl.get_response(is_me=False)

            #     log_message("Registering CarlBot response")
            #     carl.add_message(role="assistant", content=reply)

            #     log_message("Saving CarlBot")
            #     save_carlbot(user, carl)

            #     user.num_messages += 1
            #     user.save()

            #     # Send response back to Twilio
            #     twilio_response = {
            #         "event": "text",
            #         "message": {
            #             "content": reply
            #         }
            #     }
            #     self.send(text_data=json.dumps(twilio_response))

        except Exception as e:
            log_message(f"Error processing message: {e}")
