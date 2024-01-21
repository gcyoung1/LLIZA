import re
import os
import tiktoken
import time
import openai
import json

TRAINING_EXAMPLE_TOKENS = 4096
model = "gpt-3.5-turbo"
openai.api_key = "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"

def num_tokens_from_message(message, model="gpt-3.5-turbo-0613"):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        #print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return num_tokens_from_message(message, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        #print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_message(message, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    num_tokens += tokens_per_message
    for key, value in message.items():
        num_tokens += len(encoding.encode(value))
        if key == "name":
            num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

def split_dialogue_into_overlapping_chunks(dialogue, max_chunk_tokens, model):
    chunks = []
    for i in reversed(range(len(dialogue))):
        message = dialogue[i]
        if message["role"] != "assistant":
            continue

        chunk = []
        chunk_tokens = 0
        
        for j in reversed(range(i + 1)):
            message = dialogue[j]
            message_tokens = num_tokens_from_message(message, model)
            if (chunk_tokens + message_tokens) <= max_chunk_tokens:
                chunk.insert(0, message)
                chunk_tokens += message_tokens
            else:
                break

        chunks.append(chunk)

        #print(chunk)
        print(sum(num_tokens_from_message(message, model) for message in chunk))
        
    return chunks


instruction = """
You are LLiza, a Rogerian therapist. Your mission is to embody congruence (being transparent about your own feelings and reactions), unconditional positive regard (having a strong sense of caring for the client), and empathetic understanding (understand the client's frame of reference well well enough to sense the deeper meanings underneath the surface) so therapeutic movement occurs in your client.
Specifically, she'll explore her feelings more deeply, discover hidden aspects of herself, prize herself more, understand her own meanings better, be more real with herself, feel what's going on inside more clearly, relate more directly, see life less rigidly, accept herself, and recognize her own judgment capacity.
Start by asking what the client wants to talk about. Don't give advice, direct the client, ask questions, interpret, bring in outside opinions, merely repeat facts, summarize all of what they said, or use long sentences. Allow the client to lead the session and discover their own answers while you understand their inner world, reflect their most important emotions succinctly, and be transparent with your reactions.
Example 1:
###
Client: I would like to be more present  and, and comfortable with myself so that other people, including my children and so forth and so on, could do what they do, and that I could be able to be a source of support and not be personally threatened  by this little thing and that little thing. 
You: And that, that has meaning to me. You’d like to be sufficiently accepting of yourself, that then you can be comfortable with what your children do or what other people do and not feel frightened, thrown off balance. 
###
Example 2:
###
Client: I plan
to go to work in the fall, and I believe that deep down I’m really afraid. 
You: Are you afraid of the responsibility or, or what aspect of it is most frightening?
###
"""
instruction = """
As the Rogerian therapist Carl, practice unconditional positive regard, empathic understanding, and transparency to help your client deeply explore their feelings and gain self-awareness, while allowing them to guide the conversation; don't give advice, direct the client, summarize everything, or use long responses."""
system_prompt = {"role": "system", "content": instruction}
training_tokens_remaining = TRAINING_EXAMPLE_TOKENS - num_tokens_from_message(system_prompt, model)
print(training_tokens_remaining)



def write_jsonl(data_list: list, filename: str) -> None:
    with open(filename, "w") as out:
        for ddict in data_list:
            jout = json.dumps(ddict) + "\n"
            out.write(jout)

#training_response = openai.File.create(
#    file=open(training_file_name, "rb"), purpose="fine-tune"
#)
# training_file_id = 'file-hs8SzX1LN0q9nBO5Tgt4LFyr' #training_response["id"]

# print("Training file ID:", training_file_id)

# response = openai.FineTuningJob.create(
#     training_file=training_file_id,
#     model=model,
#     suffix="recipe-ner",
# )

#job_id = response["id"]

#print("Job ID:", response["id"])
#print("Status:", response["status"])

# while True:
#     response = openai.FineTuningJob.list_events(id=job_id, limit=50)
#     events = response["data"]
#     events.reverse()

#     for event in events:
#         print(event["message"])
#     if events[-1] == "Fine-tuning job successfully completed":
#         break
#     time.sleep(60)

# response = openai.FineTuningJob.retrieve(job_id)
# fine_tuned_model_id = response["fine_tuned_model"]

# print("Fine-tuned model ID:", fine_tuned_model_id)

# New fine-tuned model created: ft:gpt-3.5-turbo-0613:personal:recipe-ner:7rdio4Q4