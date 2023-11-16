import requests
import os
import urllib3
import openai
from typing import List, Dict

urllib3.disable_warnings()


class CarlBot:

    def __init__(self, base_system_prompt, max_n_dialogue_buffer_messages,
                 max_summary_buffer_points, max_user_message_chars=700):
        self.max_n_dialogue_buffer_messages = max_n_dialogue_buffer_messages
        self.min_n_dialogue_buffer_messages = 2
        self.max_summary_buffer_points = max_summary_buffer_points
        self.base_system_prompt = base_system_prompt
        self.max_user_message_chars = max_user_message_chars

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
        return "\n- ".join([""] + summary)

    @property
    def system_prompt_message(self):
        content = f"{self.base_system_prompt}\nPreviously Expressed Attitudes:\n{self.summary_buffer_str}"
        return {"role": "system", "content": content}

    @property
    def messages(self):
        return [self.system_prompt_message] + self.dialogue_buffer

    def summarize_attitudes_in_dialogue(self, dialogue: List[Dict[str, str]], n_bullets: int) -> List[str]:
        dialogue_str = self.stringify_dialogue(dialogue)
        suffix = "\n- I feel"
        response = openai.Completion.create(
            model="gpt-3.5-turbo-instruct",
            prompt=f"{dialogue_str}\nMake a bulletpoint list of the top {n_bullets} most important attitudes coming out in this interview:{suffix}",
            max_tokens=200,  # 100 left unfinished bullets
            temperature=0.0,
        )
        summary = suffix + response.choices[0].text
        return summary.split("\n- ")[1:] # All but first empty string
    
    def summarize_attitudes(self, summary_points: List[str], n_bullets:int) -> List[str]:
        summary_str = self.stringify_summary(summary_points)
        suffix = "\n- I feel"
        response = openai.Completion.create(
            model="gpt-3.5-turbo-instruct",
            prompt=f"{summary_str}\nCondense these attitudes to {n_bullets} bulletpoints:{suffix}",
            max_tokens=200,  # 100 left unfinished bullets
            temperature=0.0,
        )
        summary = suffix + response.choices[0].text
        return summary.split("\n- ")[1:] # All but first empty string

    def update_summary(self):
        n_bullets = min(self.max_summary_buffer_points, max(2, self.max_summary_buffer_points // 3))
        bullets = self.summarize_attitudes_in_dialogue(self.dialogue_buffer[:-self.min_n_dialogue_buffer_messages], n_bullets)
        self.all_summary_points.extend(bullets)
        self.summary_buffer.extend(bullets)
        if len(self.summary_buffer) > self.max_summary_buffer_points:
            self.summary_buffer = self.summarize_attitudes(
                self.summary_buffer, n_bullets)

    def is_crisis(self, content:str) -> bool:
        response = openai.Moderation.create(input=content, )
        moderation_categories = response["results"][0]["categories"]
        return any(moderation_categories[category] for category in
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
        return [content[:split_point]] + self.split_content(content[split_point + 1:])

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
        response = openai.ChatCompletion.create(
            model="ft:gpt-3.5-turbo-0613:personal:recipe-ner:7rdio4Q4",
            messages=self.messages)
        return response.choices[0].message.content

    def load(self, dialogue_buffer, summary_buffer, crisis_mode):
        self.dialogue_buffer = dialogue_buffer
        self.summary_buffer = summary_buffer
        self.crisis_mode = crisis_mode


if __name__ == "__main__":
    carl = CarlBot("You're AI Rogerian therapist LLIZA texting a client. Be accepting, empathetic, and genuine. Don't direct or advise.",
                   10, 10)

    while True:
        user_input = input("You: ")
        carl.add_message("user", user_input)
        response = carl.get_response()
        print(f"Carl: {response}")
        carl.add_message("assistant", response)
