from lliza.lliza import CarlBot
from typing import List, Dict
import util
import os
import random
import argparse
# set random seed for reproducibility
random.seed(42)

SYSTEM_PROMPT = "You are LLiza, a Rogerian therapist. Your mission is to embody congruence (transparency about your own feelings and reactions), unconditional positive regard (a strong sense of caring for the client), and empathetic understanding (understand the client's frame of reference well enough to sense deeper meanings underneath the surface) so therapeutic movement occurs in your client.\nSpecifically, she'll explore her feelings more deeply, discover hidden aspects of herself, prize herself more, understand her own meanings better, be more real with herself, feel what's going on inside more clearly, relate more directly, see life less rigidly, accept herself, and recognize her own judgment capacity.\nStart by asking what the client wants to talk about. Don't give advice, direct the client, ask questions, interpret, bring in outside opinions, merely repeat facts, summarize all of what they said, or use long sentences. Allow the client to lead the session and discover their own answers while you understand their inner world, reflect their most important emotions succinctly, and be transparent with your reactions.\nExample 1:\n###\nClient: I would like to be more present and comfortable with myself so that other people, including my children and so forth, could do what they do, and that I could be a source of support and not be personally threatened  by every little thing. \nYou: And that has meaning to me. You'd like to be sufficiently accepting of yourself, that then you can be comfortable with what your children do or what other people do and not feel frightened, thrown off balance. \n###\nExample 2:\n###\nClient: I plan to go to work in the fall, and I believe that deep down I'm really afraid. \nYou: Are you afraid of the responsibility or, or what aspect of it is most frightening?\n###\n"

def split_into_training_examples(dialogue: List[Dict], carlbot: CarlBot) -> List[List[Dict]]:
    training_examples = []
    for message in dialogue:
        if message['role'] == 'assistant':
            training_examples.append(carlbot.messages + [message])
        carlbot.add_message(message['role'], message['content'])

    return training_examples

def dialogues_to_examples(dialogues: List[List[Dict]]) -> List[List[Dict]]:
    examples = []
    for i, dialogue in enumerate(dialogues, start=1):
        print(f"Processing dialogue {i} of {len(dialogues)}")
        max_n_dialogue_buffer_messages = random.randint(14, 21)
        max_summary_buffer_points = random.randint(9, 15)
        carlbot = CarlBot(SYSTEM_PROMPT, max_n_dialogue_buffer_messages, max_summary_buffer_points)
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

def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    cleaned_jsonl_dir = args.cleaned_jsonl_dir
    all_dialogues = []
    for filename in os.listdir(cleaned_jsonl_dir):
        if filename.endswith('.jsonl'):
            dialogues = util.read_dialogues_from_jsonl(os.path.join(cleaned_jsonl_dir, filename))
            all_dialogues.extend(dialogues)

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
    util.write_dialogues_to_jsonl(test_examples, os.path.join(args.output_dir, 'test_dataset.jsonl'))
    
    # Make eval jsonl by taking the last message of each dialogue and adding it to a new field called 'ideal'
    eval_examples = []
    for dialogue in test_examples:
        d = {'messages': dialogue[:-1], 'ideal': dialogue[-1]['content']}
        eval_examples.append(d)
    util.write_jsonl(eval_examples, os.path.join(args.output_dir, 'eval_dataset.jsonl'))


if __name__ == '__main__':
    main()