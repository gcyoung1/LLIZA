import os
import re
import util
import argparse

def extract_dialogue(transcript, client_tag, therapist_tag):
    message_regex = rf'({client_tag}) ?(\d+):?((?:.|\n)*?)(?={therapist_tag} ?\d+)|({therapist_tag}) ?(\d+):?((?:.|\n)*?)(?={client_tag} ?\d+)'
    messages = re.findall(message_regex, transcript)
    dialogue = []

    for client_identifier, client_counter, client_text, therapist_identifier, therapist_counter, therapist_text in messages:
        if therapist_identifier:
            role = "assistant"
            content = therapist_text
            last_counter = therapist_counter
        else:
            role = "user"
            content = client_text
            last_counter = client_counter

        # Remove parentheticals
        content = re.sub(r'\([^)]*\)', '', content)
        # Remove commentary
        content = re.sub(r'\[[^]]*\]', '', content)
        # Remove ^L
        content = re.sub(r'\^L', '', content)
        # Remove newlines
        content = re.sub(r'\n', ' ', content)
        # Remove ^
        content = re.sub(r'\^', '', content)

        dialogue.append({"role": role, "content": content})

        #print(role)
        #print(content)
        #print("\n")
    return dialogue


def extract_message(line):
    # The issue here is that some dialogues have e.g. 'C24 (continued):' and others have 'C4 I feel so bad (T: Mm-hmm).'
    # So you can't just split on the first colon
    # But you also can't just grab the speaker because then (continued) will be included in the content
    other_speakers = ['Participant', 'Man', 'Woman', 'new']
    speaker_pattern = r'(\d+)\s*([CTS])|([CTS])\s*(\d+[A-Za-z]{0,3})' # Groups are (counter, speaker) or (speaker, counter)
    # Can't just match e.g. C24 because of lines like "C238 is a particularly good clarification"
    # match = re.match(r'^(?:\s*(?:[^ ]*:|.*:)|([^ ]* ?[^ ]*)\s*\:(.*))', line) 
    if ':' in line: 
        tag, content = line.split(':', 1)
        tag, content = tag.strip(), content.strip()

        if tag in other_speakers:
            return tag, None, content

        match = re.match(f"^{speaker_pattern}$", tag)
        if match is not None:
            if match.group(1) is not None:
                counter, speaker = match.group(1), match.group(2)
            elif match.group(3) is not None:
                speaker, counter = match.group(3), match.group(4)    
        else:
            speaker, counter = tag, None
            if len(speaker.split()) > 3: #This is a sentence e.g. "The interview ends as follows"
                return None
            if 'Commentary' in speaker:
                return ("Commentary", None, content)
            if speaker.startswith(('Four days later', 'Dear Mr. L.', 'Dear Mrs. Dem', 'After session 47', 'First Interview', 'Volume 2', 'Volume 3', 'Fifth Interview', 'Source', 'Note', 'Introduction', 'THERAPIST', 'Carl Rogers', 'CARL ROGERS', 'Rogers')): # All of these are not part of the dialogue
                return None
            
    else: 
        return None

    return speaker, counter, content


def dialogue_to_str(dialogue):
    return '\n'.join([f"{message.get('speaker', message.get('role'))}: {message['content']}" for message in dialogue])

def split_into_dialogues(lines,fname):
    messages = []
    tags = set()
    last_none = False
    last_discussion = False
    dialogues = []
    for line in lines:
        line = line.strip()
        if line == '' or line.startswith('[') or line.startswith('(') or line.startswith('Translation'):
            continue
        message_tup = extract_message(line)
        if message_tup is None:
            is_discussion = (line.lower().lstrip().split()[0] in ['discussion', 'commentary', 'excerpt', 'comments']) and (':' not in line)
            if (last_none or is_discussion) and messages and messages[-1] is not None: # End of previous dialogue, add delimiter (None) and reset tag list
                if messages:
                    if not last_discussion:
                        dialogues.append(messages)
                    messages = []
                last_discussion = is_discussion
                tags = set()
            last_none = True
            continue
        last_none = False
        speaker, counter, content = message_tup
        if (counter is not None) and ((speaker,counter) in tags):
            if ("the counselor" not in content.lower()) and ("the client" not in content.lower()) and ('Bryan' not in fname):
                error_str = f"DS,{speaker},{counter},{content},{fname}\n"
                with open("error.txt","a") as f:
                    f.write(error_str)
            continue
        if any(delimiter in speaker for delimiter in (',', '‑', '-', '&')): # Skip commentary lines
            error_str = f"CL,{speaker},{counter},{content},{fname}\n"
            continue
        if speaker == 'Commentary':
            continue
        # print and set trace if the speaker speaks twice in a row
        if messages and messages[-1] is not None and messages[-1]['speaker'] == speaker:
            if (speaker not in ['Man', 'Woman', 'Participant', 'new']) and ('Reiko' not in fname) and ('Jim' not in fname):
                with open("error.txt","a") as f:
                    f.write(f"SS,{speaker},{counter},{content},{fname}\n")
        messages.append({'speaker': speaker, 'content': content})
        tags.add((speaker, counter))

    return dialogues


# argparse and main 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_dir', type=str, help='Directory containing transcripts', default='finetuning/raw_txt_transcripts')
    parser.add_argument('output_dir', type=str, help='Directory to write output to', default='finetuning/raw_jsonl_dialogues')
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    for fname in os.listdir(args.input_dir):
        if not fname.endswith('.txt'):
            continue
        print(f"\n\n\n\nThis is {fname}")

        with open(os.path.join(args.input_dir, fname), 'r') as f:
            lines = f.readlines()
        dialogues = split_into_dialogues(lines,fname)
        util.write_dialogues_to_jsonl(dialogues, os.path.join(args.output_dir, os.path.splitext(fname)[0] + '.jsonl'))

if __name__ == '__main__':
    main()

# Print some stats about our training examples
# print(f"Number of dialogues: {len(all_dialogues)}")
# print(f"Number of messages: {sum(len(dialogue) for dialogue in all_dialogues)}")
# print(f"Number of words: {sum(len(message['content'].split()) for dialogue in all_dialogues for message in dialogue)}")
# print(f"Number of tokens: {sum(num_tokens_from_message(message) for dialogue in all_dialogues for message in dialogue)}")
# # Print text of longest message for each role
# print("Longest messages:")
# for role in ['user', 'assistant']:
#     sorted_messages = sorted([message for dialogue in all_dialogues for message in dialogue if message['role'] == role], key=lambda x: len(x['content'].split()), reverse=True)
#     longest_message = sorted_messages[0]
#     print(f"{role}: {longest_message['content']}")
#     print(f"Length: {len(longest_message['content'].split())}")

# Make some graphs
# import matplotlib.pyplot as plt

# # Number of messages per dialogue
# plt.hist([len(dialogue) for dialogue in all_dialogues], bins=range(0, 500, 5))
# plt.title("Number of messages per dialogue")
# plt.xlabel("Number of messages")
# plt.ylabel("Number of dialogues")
# plt.savefig("num_messages_per_dialogue.png")

# # Number of words per message
# plt.clf()
# plt.hist([len(message['content'].split()) for dialogue in all_dialogues for message in dialogue], bins=range(0, 500, 5))
# plt.title("Number of words per message")
# plt.xlabel("Number of words")
# plt.ylabel("Number of messages")
# plt.savefig("num_words_per_message.png")

# # Number of words per message for user and assistant
# plt.clf()
# plt.hist([len(message['content'].split()) for dialogue in all_dialogues for message in dialogue if message['role'] == 'user'], bins=range(0, 500, 5), alpha=0.5, label='user')
# plt.hist([len(message['content'].split()) for dialogue in all_dialogues for message in dialogue if message['role'] == 'assistant'], bins=range(0, 500, 5), alpha=0.5, label='assistant')
# plt.title("Number of words per message")
# plt.xlabel("Number of words")
# plt.ylabel("Number of messages")
# plt.legend()
# plt.savefig("num_words_per_message_by_role.png")
