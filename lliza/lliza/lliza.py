import urllib3
from openai import OpenAI

client = OpenAI()
from typing import List, Dict

urllib3.disable_warnings()

SYSTEM_PROMPT = "You are LLiza, a Rogerian therapist. Your mission is to embody congruence (transparency about your own feelings and reactions), unconditional positive regard (a strong sense of caring for the client), and empathetic understanding (understand the client's frame of reference well enough to sense deeper meanings underneath the surface) so therapeutic movement occurs in your client.\nSpecifically, she'll explore her feelings more deeply, discover hidden aspects of herself, prize herself more, understand her own meanings better, be more real with herself, feel what's going on inside more clearly, relate more directly, see life less rigidly, accept herself, and recognize her own judgment capacity.\nStart by asking what the client wants to talk about. Don't give advice, direct the client, ask questions, interpret, bring in outside opinions, merely repeat facts, summarize all of what they said, or use long sentences. Allow the client to lead the session and discover their own answers while you understand their inner world, reflect their most important emotions succinctly, and be transparent with your reactions.\nExample 1:\n###\nClient: I would like to be more present and comfortable with myself so that other people, including my children and so forth, could do what they do, and that I could be a source of support and not be personally threatened  by every little thing. \nYou: And that has meaning to me. You'd like to be sufficiently accepting of yourself, that then you can be comfortable with what your children do or what other people do and not feel frightened, thrown off balance. \n###\nExample 2:\n###\nClient: I plan to go to work in the fall, and I believe that deep down I'm really afraid. \nYou: Are you afraid of the responsibility or, or what aspect of it is most frightening?\n###\n"

class CarlBot:

    def __init__(self,
                 base_system_prompt,
                 max_n_dialogue_buffer_messages,
                 max_summary_buffer_points,
                 max_user_message_chars=700):
        self.max_n_dialogue_buffer_messages = max_n_dialogue_buffer_messages
        self.min_n_dialogue_buffer_messages = 7
        self.max_summary_buffer_points = max_summary_buffer_points
        self.base_system_prompt = base_system_prompt
        self.max_user_message_chars = max_user_message_chars
        self.summarizer_model = "gpt-4o-mini-2024-07-18"
        self.chat_model = "ft:gpt-4o-mini-2024-07-18:personal:148-dialogues-6000:AH208Lhz"

        # Initialize memory
        self.all_summary_points = [
        ]  # This contains all summary bullets which were made in response to raw dialogue
        self.summary_buffer = [
        ]  # This contains our current summary bullets. Could be a summarized version of a previous summary buffer, which was originally made of points from all_summary_points

        # Initialize dialogue
        self.full_dialogue = []
        self.dialogue_buffer = []

        # Initialize crisis mode
        self.crisis_mode = False
        self.crisis_response = "It sounds like you are going through a very difficult time right now. I'm concerned about your safety and well-being based on what you've told me. I think this chat needs to come to an end, as I'm just an AI assistant without the proper training to provide any counseling or emergency support. But I want you to know there are compassionate people available to talk to you. Please reach out right away to the National Suicide Prevention Lifeline at the phone number 988 or chat with them online at https://988lifeline.org/chat. They have people there 24/7 ready to listen, care and assist you during this crisis. Your life matters and help is available."

    @staticmethod
    def stringify_dialogue(dialogue: List[dict]):
        return "\n".join([
            f"{message['role']}: {message['content']}" for message in dialogue
        ])

    @staticmethod
    def stringify_summary(summary: List[str]):
        return "\n- ".join([""] + summary)[1:]

    @property
    def system_prompt_message(self):
        content = f"{self.base_system_prompt}\nPreviously Expressed Attitudes:\n{self.summary_buffer_str}"
        return {"role": "system", "content": content}

    @property
    def messages(self):
        return [self.system_prompt_message] + self.dialogue_buffer

    def summarize_attitudes_in_dialogue(self, dialogue: List[Dict[str, str]],
                                        n_bullets: int) -> List[str]:
        dialogue_str = self.stringify_dialogue(dialogue)
        completion = client.chat.completions.create(
            model=self.summarizer_model,
            messages=[{"role": "user", "content": f"{dialogue_str}\n###\nMake a bulletpoint list of the top {n_bullets} most important attitudes coming out in this interview. Do not say anything first, just reply with the bullet points. Use first person."}],
            max_tokens=200,  # 100 left unfinished bullets
            temperature=0.0)
        summary = "\n" + completion.choices[0].message.content
        bullets = summary.split("\n- ")[1:] # All but first empty string
        return bullets
    
    def summarize_attitudes(self, summary_points: List[str],
                            n_bullets: int) -> List[str]:
        summary_str = self.stringify_summary(summary_points)
        completion = client.chat.completions.create(
            model=self.summarizer_model,
            messages=[{"role": "user", "content": f"{summary_str}\n###\nCondense these attitudes to {n_bullets} bulletpoints. Do not say anything first, just reply with the bullet points. Use first person."}],            
            max_tokens=200,  # 100 left unfinished bullets
            temperature=0.0)
        summary = "\n" + completion.choices[0].message.content
        bullets = summary.split("\n- ")[1:] # All but first empty string
        return bullets

    def update_summary(self):
        n_bullets = min(self.max_summary_buffer_points,
                        max(2, self.max_summary_buffer_points // 3))
        bullets = self.summarize_attitudes_in_dialogue(
            self.dialogue_buffer[:-self.min_n_dialogue_buffer_messages],
            n_bullets)
        self.all_summary_points.extend(bullets)
        self.summary_buffer.extend(bullets)
        if len(self.summary_buffer) > self.max_summary_buffer_points:
            self.summary_buffer = self.summarize_attitudes(
                self.summary_buffer, n_bullets)

    def is_crisis(self, content: str) -> bool:
        response = client.moderations.create(input=content)
        moderation_categories = response.results[0].categories
        return any(
            getattr(moderation_categories, category) for category in
            ["self-harm", "self-harm/intent", "self-harm/instructions"])

    def _add_message(self, role: str, content: str):
        if role == "user" and self.is_crisis(content):
            self.crisis_mode = True
        message = {"role": role, "content": content}
        self.full_dialogue.append(message)
        self.dialogue_buffer.append(message)
        if len(self.dialogue_buffer) > self.max_n_dialogue_buffer_messages:
            self.update_summary()
            self.dialogue_buffer = self.dialogue_buffer[
                -self.min_n_dialogue_buffer_messages:]

    def split_content(self, content: str) -> List[str]:
        if len(content) <= self.max_user_message_chars:
            return [content]
        split_point = content[:self.max_user_message_chars].rfind(" ")
        return [content[:split_point]] + self.split_content(
            content[split_point + 1:])

    def add_message(self, role: str, content: str):
        # Split content into multiple messages if it's too long
        for split_content in self.split_content(content):
            self._add_message(role, split_content)

    @property
    def summary_buffer_str(self):
        return self.stringify_summary(self.summary_buffer)

    def get_response(self):
        if self.crisis_mode:
            return self.crisis_response
        response = client.chat.completions.create(
            model=self.chat_model,
            messages=self.messages)
        return response.choices[0].message.content

    def load(self, dialogue_buffer, summary_buffer, crisis_mode):
        self.dialogue_buffer = dialogue_buffer
        self.summary_buffer = summary_buffer
        self.crisis_mode = crisis_mode

    def load_from_dict(self, memory_dict):
        self.load(memory_dict['dialogue_buffer'], memory_dict['summary_buffer'],
                  memory_dict['crisis_mode'])
    
    def save_to_dict(self):
        return {
            "dialogue_buffer": self.dialogue_buffer,
            "summary_buffer": self.summary_buffer,
            "crisis_mode": self.crisis_mode
        }


if __name__ == "__main__":
    carl = CarlBot(
        SYSTEM_PROMPT,
        10, 10)

    while True:
        user_input = input("You: ")
        carl.add_message("user", user_input)
        response = carl.get_response()
        print(f"Carl: {response}")
        carl.add_message("assistant", response)
