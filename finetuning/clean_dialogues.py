from typing import List, Dict
import os
import re
import random
import argparse

import util

# import openai

def get_speaker_to_role_map(dialogue):
    speakers = set([message['speaker'] for message in dialogue])
    if speakers == {'C', 'S'}:
        role_map = {'C': 'assistant', 'S': 'user'}
    elif speakers == {'T', 'C'}:
        role_map = {'C': 'user', 'T': 'assistant'}
    else:
        raise ValueError(f"Unrecognized speakers: {speakers}")
    
    return role_map

def convert_speakers_to_roles(dialogue:List[Dict[str, str]])->None:
    role_map = get_speaker_to_role_map(dialogue)
    for message in dialogue:
        message['role'] = role_map[message['speaker']]
        del message['speaker']

def parse_tuple(string:str)->tuple:
    tuples = re.findall(r'\"(.*?)\"', string)
    return tuple(tuples)

def make_fill_in_the_blank_prompt(dialogue:List[Dict[str, str]], n_blanks)->str:
    dialogue_str = '\n'.join([f"{i}. {message['role']}: {message['content']}" for i, message in enumerate(dialogue,start=1)])
    prompt = f"""
sentence with three blanks: Today is _ good _ for a _ .
prompt: fill in the missing words.
result: Today is a good day for a walk.
“”"
sentence with four blanks: _ cars _ and their owners _ do _ .
prompt: fill in the missing words.
result: Old cars break down and their owners can’t do anything.
“”"
sentence with {n_blanks} blank: {dialogue[-3]['content'].replace('(BLANK)', '_')}
prompt: fill in the missing words.
result:
"""
    return prompt

def remove_parentheticals(dialogue:List[Dict[str, str]])->List[Dict[str, str]]:
    parenthetical_pattern = r'(\([^)]*\))'
    for message in dialogue:
        blank_counter = 0
        matches = re.findall(parenthetical_pattern, message['content'])
        if not matches:
            continue
        for match in matches:
            if any(word in match.lower() for word in ['lost', 'miss', 'inaud', 'illegib', 'unintelligib', 'fade']) or match == '(?)':
                blank_counter += 1
                message['content'] = message['content'].replace(match, f"$BLANK{blank_counter}", 1)

            elif "laugh" in match.lower():
                laugh = random.choice(["haha", "heh", "hahaha", "hah"])
                message['content'] = message['content'].replace(match, f"({laugh})")
            else:
                message['content'] = message['content'].replace(match, '')
                if message['content'] == '':
                    blank_counter += 1 
                    message['content'] = f"$BLANK{blank_counter}"

        # prompt = make_fill_in_the_blank_prompt(dialogue[max(i-3, 0):i+1], blank_counter)
        # response = openai.Completion.create(
        #     model="gpt-3.5-turbo-instruct",
        #     prompt=prompt,
        #     max_tokens=50,  # 100 left unfinished bullets
        #     temperature=0.0,
        # )
        # print(matches)
        # fills = parse_tuple(response.choices[0].text)
        # for i, fill in enumerate(fills, start=1):
        #     print(fill)
        #     message['content'] = message['content'].replace(f"(BLANK{i})", fill)
        #     blank_counter -= 1
        # print(message['content'])
        # import pdb; pdb.set_trace()

def guess_blank(context:List[Dict[str, str]], user_input: bool)->Dict[str, str]:
    if user_input:
        print("\n\n\n\n\n")
        dialogue_str = '\n'.join([f"{i}. {message['role']}: {message['content']}" for i, message in enumerate(context,start=1)])
        print(dialogue_str)
        blank = input("Which word is missing? ")
        return blank

def fill_in_blanks(dialogue:List[Dict[str, str]])->None:
    for i, message in enumerate(dialogue):
        n_blanks = message['content'].count('$BLANK')
        for blank_num in range(1, n_blanks+1):
            blank = guess_blank(dialogue[max(i-10, 0):i+4], True)
            message['content'] = message['content'].replace(f"$BLANK{blank_num}", blank)

def remove_bracketed_text(dialogue:List[Dict[str, str]])->None:
    for message in dialogue:
        # Print the bracketed text
        if not re.search(r'\[.*?\]', message['content']):
            continue
        print(re.findall(r'\[.*?\]', message['content']))
        message['content'] = re.sub(r'\[.*?\]', '', message['content'])

def remove_ellipses(dialogue:List[Dict[str, str]])->None:
    for message in dialogue:
        # Remove " ."
        message['content'] = re.sub(r'\s+\.', '.', message['content'])
        
        # Truncate to single ellipsis
        message['content'] = re.sub(r'\.{2,}', '...', message['content'])

def remove_extraneous_whitespace(dialogue:List[Dict[str, str]])->None:
    for message in dialogue:
        message['content'] = re.sub(r'\t+', ' ', message['content'])
        message['content'] = re.sub(r'\s{2,}', ' ', message['content'])
        message['content'] = message['content'].strip()

### argparse and main ###
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_dir', type=str, default='finetuning/input_data/raw_jsonl_dialogues', help='Directory containing raw jsonl dialogues')
    parser.add_argument('output_dir', type=str, default='finetuning/input_data/cleaned_jsonl_dialogues', help='Directory to write cleaned transcripts to')
    args = parser.parse_args()
    return args

def main():
    args = parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    for filename in os.listdir(args.input_dir):
        if not filename.endswith('.jsonl'):
            continue
        print(f"Cleaning {filename}")
        dialogues = util.read_dialogues_from_jsonl(os.path.join(args.input_dir, filename))
        cleaned_dialogues = []
        for i, dialogue in enumerate(dialogues, start=1):
            print(f"Processing dialogue {i} of {len(dialogues)}")
            speakers = set([message['speaker'] for message in dialogue])
            if speakers != {'T', 'C'} and speakers != {'S', 'C'}:
                continue

            convert_speakers_to_roles(dialogue)
            remove_parentheticals(dialogue)
            num_blanks = sum(message['content'].count('BLANK') for message in dialogue)
            messages_per_blank = len(dialogue) / (num_blanks + 0.000000001)
            if messages_per_blank < 10:
                continue

            # Fill in blanks
            fill_in_blanks(dialogue)

            remove_bracketed_text(dialogue)
            remove_extraneous_whitespace(dialogue)
            remove_ellipses(dialogue)

            cleaned_dialogues.append(dialogue)
            

        util.write_dialogues_to_jsonl(cleaned_dialogues, os.path.join(args.output_dir, filename))

if __name__ == '__main__':
    main()