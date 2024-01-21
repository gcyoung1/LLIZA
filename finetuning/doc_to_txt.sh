#!/bin/bash

# Step 1: Create the output directory
mkdir input_data/raw_txt_transcripts

# Step 2: Navigate to the input directory
cd input_data/raw_doc_transcripts

# Step 3: Convert .doc files to .txt files
for file in *.doc; do
  textutil -convert txt "$file"
done

cd ../..
# Step 4: Move the converted .txt files to the output directory
mv input_data/raw_doc_transcripts/*.txt input_data/raw_txt_transcripts
