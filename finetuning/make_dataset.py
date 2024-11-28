from lliza.lliza import CarlBot
from typing import List, Dict
import util
import os
import random
import argparse
from openai import OpenAI

client = OpenAI()
# set random seed for reproducibility
random.seed(42)

def split_into_training_examples(dialogue: List[Dict], carlbot: CarlBot) -> List[List[Dict]]:
    training_examples = []
    for message in dialogue:
        if message['role'] == 'assistant' and len(carlbot.messages) > 1: # don't include the first message
            training_examples.append(carlbot.messages + [message])
        carlbot.add_message(message['role'], message['content'])

    return training_examples

def dialogues_to_examples(dialogues: List[List[Dict]]) -> List[List[Dict]]:
    examples = []
    for i, dialogue in enumerate(dialogues, start=1):
        print(f"Processing dialogue {i} of {len(dialogues)}")
        carlbot = CarlBot()
        carlbot.is_crisis = lambda x: False
        examples.extend(split_into_training_examples(dialogue, carlbot))

    return examples

### argparse and main ###
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('cleaned_jsonl_dir', type=str, default='finetuning/input_data/cleaned_jsonl_dialogues')
    parser.add_argument('output_dir', type=str, default='finetuning/datasets/example_dataset_name')
    parser.add_argument('--n_dialogues', type=int, default=6)
    return parser.parse_args()

def stringify(first_few):
    ret = '\n'.join([f"{message['role']}: {message['content']}" for message in first_few])
    return ret

def has_too_many_ellipses(dialogue: List[Dict]) -> bool:
    num_bad_messages = 0
    for message in dialogue:
        content = message['content']
        if content.count('...') > 5 or content.count('--') > 5:
            num_bad_messages += 1
    
    if num_bad_messages / len(dialogue) > 0.1:
        return True
    return False

def assistant_speaks_twice_in_a_row(dialogue: List[Dict]) -> bool:
    assistant_spoke_last = False
    for i, message in enumerate(dialogue):
        if message['role'] == 'assistant':
            if assistant_spoke_last:
                # allowable if it's the first two
                if i < 2:
                    continue
                return True
            assistant_spoke_last = True
        else:
            assistant_spoke_last = False
    return False

def contains_flagged_content(dialogue: List[Dict]) -> bool:
    for i, message in enumerate(dialogue):
        response = client.moderations.create(input=message['content'])
        if response.results[0].categories.sexual_minors:
            print(message['content'])
            return True
    return False


def dialogue_is_usable(dialogue: List[Dict]) -> bool:
    if has_too_many_ellipses(dialogue):
        print("Filtering bc ellipses")
        return False
    if assistant_speaks_twice_in_a_row(dialogue):
        print("Filtering bc assistant speaks twice")
        return False
    if len(dialogue) < 10:
        print("Filtering bc too short")
        return False
    if contains_flagged_content(dialogue):
        print("Filtering bc flagged content")
        return False
    return True

def combine_adjacent_messages(dialogue:List[Dict[str, str]])->List[Dict[str, str]]:
    combined_dialogue = []
    for message in dialogue:
        if combined_dialogue and combined_dialogue[-1]['role'] == message['role']:
            combined_dialogue[-1]['content'] += ' ' + message['content']
        else:
            combined_dialogue.append(message)
    return combined_dialogue
        
def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    cleaned_jsonl_dir = args.cleaned_jsonl_dir
    all_dialogues = []
    for filename in os.listdir(cleaned_jsonl_dir):
        if filename.endswith('.jsonl'):
            dialogues = util.read_dialogues_from_jsonl(os.path.join(cleaned_jsonl_dir, filename))
            dialogues = [combine_adjacent_messages(dialogue) for dialogue in dialogues]
            clipped_dialogues = [dialogue[:-6] for dialogue in dialogues]
            filtered_dialogues = [dialogue for dialogue in clipped_dialogues if dialogue_is_usable(dialogue)]
            
            all_dialogues.extend(filtered_dialogues)

    print(f"Loaded {len(all_dialogues)} dialogues")

    # Shuffle all dialogues and split into train, test, and eval
    random.shuffle(all_dialogues)
    dialogues_to_use = all_dialogues[:args.n_dialogues]
    train_dialogues = dialogues_to_use[:int(len(dialogues_to_use) * 0.95)]
    test_dialogues = dialogues_to_use[int(len(dialogues_to_use) * 0.95):]

    train_examples = dialogues_to_examples(train_dialogues)
    # Shuffle and split into chunks of 1500
    random.shuffle(train_examples)
    chunk_size = 1500
    for i in range(0, len(train_examples), chunk_size):
        chunk = train_examples[i:i + chunk_size]
        util.write_dialogues_to_jsonl(chunk, os.path.join(args.output_dir, f'train_dataset_{i}.jsonl'))

    test_examples = dialogues_to_examples(test_dialogues)
    util.write_dialogues_to_jsonl(test_examples, os.path.join(args.output_dir, 'validation_dataset.jsonl'))
    
    # Make eval jsonl by taking the last message of each dialogue and adding it to a new field called 'ideal'
    eval_examples = []
    for dialogue in test_examples:
        d = {'messages': dialogue[:-1], 'ideal': dialogue[-1]['content']}
        eval_examples.append(d)
    util.write_jsonl(eval_examples, os.path.join(args.output_dir, 'evals_dataset.jsonl'))


if __name__ == '__main__':
    main()