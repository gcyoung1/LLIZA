# LLIZA

## Finetuning
- Put your doc files in finetuning/input_data/raw_doc_transcripts
- `cd finetuning`
- `bash doc_to_txt.sh`
- `python extract_dialogues.py input_data/raw_txt_transcripts input_data/raw_jsonl_dialogues`
- `python clean_dialogues.py input_data/raw_jsonl_dialogues input_data/cleaned_jsonl_dialogues`
- `python make_dataset.py input_data/cleaned_jsonl_dialogues datasets/example_dataset --num_dialogues 6`