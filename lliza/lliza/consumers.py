from channels.generic.websocket import WebsocketConsumer
import json
import cryptocode
import urllib
from lliza.utils import get_user_from_number, log_message, load_carlbot, save_carlbot, ENCRYPTION_KEY, HELP_MESSAGE, send_message

class ConversationRelayConsumer(WebsocketConsumer):
    def connect(self):
        """Handle WebSocket connection."""
        log_message("Client connected to Conversation Relay.")
        self.accept()
        self.user = None
        self.new_user = False
        self.carlbot = None
        self.is_me = False

    def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if self.user is not None and self.carlbot is not None:
            save_carlbot(self.user, self.carlbot)
            self.user.save() #superfluous bc save_carlbot already saves user
            if self.new_user:
                number = cryptocode.decrypt(self.user.user_id, ENCRYPTION_KEY)
                url_compatible_user_id = urllib.parse.quote(self.user.user_id)
                formatted_help = HELP_MESSAGE.format(url_compatible_user_id)
                send_message(number, formatted_help)
            
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
            self.is_me = "8583662653" in number
            self.user = get_user_from_number(number)
            if self.user.num_messages == 0:
                self.new_user = True
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
            reply = self.carlbot.get_response(is_me=self.is_me)
            self.carlbot.add_message(role="assistant", content=reply)            
            self.user.num_messages += 1
            twilio_response = {
                "type": "text",
                "token": reply,
                "last": True
            }
            log_message(f"Replying with: {reply}")
            self.send(text_data=json.dumps(twilio_response))
        except Exception as e:
            log_message(f"Error processing prompt: {e}")

    def handle_interrupt(self, data):
        """Handle user interruptions"""
        try:
            amended_content = data["utteranceUntilInterrupt"] + "..."
            log_message(f"Interrputed, amending {data['utteranceUntilInterrupt']} to {amended_content}")
            self.carlbot.dialogue_buffer[-1] = {"role": "assistant",
                                                "content": amended_content}
        except Exception as e:
            log_message(f"Error processing interrupt: {e}")

    def handle_error(self, data):
        try:
            print("Error: ", data)
        except Exception as e:
            log_message(f"Error processing error: {e}")