import requests
import urllib3
import openai
from typing import List

urllib3.disable_warnings()


class CarlBot:

    def __init__(self, base_system_prompt, max_n_dialogue_buffer_messages,
                 max_global_summary_points):
        self.max_n_dialogue_buffer_messages = max_n_dialogue_buffer_messages
        self.min_n_dialogue_buffer_messages = 2
        self.max_global_summary_points = max_global_summary_points
        self.base_system_prompt = base_system_prompt

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
        return "- " + "\n- ".join(summary)

    @property
    def system_prompt_message(self):
        content = f"{self.base_system_prompt}\nContext:\n{self.summary_buffer_str}"
        return {"role": "system", "content": content}

    @property
    def messages(self):
        return [self.system_prompt_message] + self.dialogue_buffer

    def summarize_chunk(self, chunk: str):
        response = openai.Completion.create(
            model="gpt-3.5-turbo-instruct",
            prompt=f"{chunk}\nTL;DR:\n- ",
            max_tokens=200,  # 100 left unfinished bullets
            temperature=0.0,
        )
        summary = "\n- " + response.choices[0].text
        return summary.split("\n- ")[1:]

    def update_summary(self):
        chunk = self.stringify_dialogue(
            self.dialogue_buffer[:-self.min_n_dialogue_buffer_messages])
        bullets = self.summarize_chunk(chunk)
        self.all_summary_points.extend(bullets)
        self.summary_buffer.extend(bullets)
        if len(self.summary_buffer) > self.max_global_summary_points:
            self.summary_buffer = self.summarize_chunk(
                self.stringify_summary(self.summary_buffer))

    def is_crisis(self, message):
        response = openai.Moderation.create(input=message, )
        moderation_categories = response["results"][0]["categories"]
        return any(moderation_categories[category] for category in
                   ["self-harm", "self-harm/intent", "self-harm/instructions"])

    def add_message(self, role, message):
        print("Adding message")
        if self.crisis_mode:
            return
        if role == "user" and self.is_crisis(message):
            self.crisis_mode = True
        message = {"role": role, "content": message}
        self.full_dialogue.append(message)
        self.dialogue_buffer.append(message)
        if len(self.dialogue_buffer) > self.max_n_dialogue_buffer_messages:
            print(self.stringify_dialogue(self.messages))
            self.update_summary()
            self.dialogue_buffer = self.dialogue_buffer[
                -self.min_n_dialogue_buffer_messages:]
        print("Added message")

    @property
    def summary_buffer_str(self):
        return self.stringify_summary(self.summary_buffer)

    def get_response(self):
        print("Getting response")
        if self.crisis_mode:
            return self.crisis_response
        response = openai.ChatCompletion.create(
            model="ft:gpt-3.5-turbo-0613:personal:recipe-ner:7rdio4Q4",
            messages=self.messages)
        print("Got response")
        return response.choices[0].message.content

    def load(self, dialogue_buffer, summary_buffer):
        self.dialogue_buffer = dialogue_buffer
        self.summary_buffer = summary_buffer


if __name__ == "__main__":
    carl = CarlBot("You are a chatbot therapist LLIZA trained by Carl Rogers.",
                   10, 10)

    while True:
        user_input = input("You: ")
        carl.add_message("user", user_input)
        response = carl.get_response()
        print(f"Carl: {response}")
        carl.add_message("assistant", response)
