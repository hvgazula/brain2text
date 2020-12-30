import argparse
import os
import pickle
from datetime import datetime
from itertools import islice

import gensim.downloader as api
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.utils.data as data
from transformers import (BertForMaskedLM, BertTokenizer, GPT2LMHeadModel,
                          GPT2Tokenizer)


def window(seq, n=2):
    "Returns a sliding window (of width n) over data from the iterable"
    "   s -> (s0,s1,...s[n-1]), (s1,s2,...,sn), ...                   "
    it = iter(seq)
    result = tuple(islice(it, n))
    if len(result) <= n:
        yield result
    for elem in it:
        result = result[1:] + (elem, )
        yield result


def save_pickle(item, file_name):
    """Write 'item' to 'file_name.pkl'
    """
    if '.pkl' not in file_name:
        add_ext = '.pkl'
    else:
        add_ext = ''

    file_name = os.path.join(os.getcwd(), 'pickles', file_name) + add_ext
    os.makedirs(os.path.dirname(file_name), exist_ok=True)

    with open(file_name, 'wb') as fh:
        pickle.dump(item, fh)
    return


def load_pickle(file):
    """Load the datum pickle and returns as a dataframe

    Args:
        file (string): labels pickle from 247-decoding/tfs_pickling.py

    Returns:
        DataFrame: pickle contents returned as dataframe
    """
    with open(file, 'rb') as fh:
        datum = pickle.load(fh)

    df = pd.DataFrame.from_dict(datum['labels'])

    return df


def tokenize_and_explode(df, tokenizer):
    """Tokenizes the words/labels and creates a row for each token

    Args:
        df (DataFrame): dataframe of labels
        tokenizer (tokenizer): from transformers

    Returns:
        DataFrame: a new dataframe object with the words tokenized
    """
    df['token'] = df.word.apply(tokenizer.tokenize)
    df = df.explode('token', ignore_index=True)
    df['token_id'] = df['token'].apply(tokenizer.convert_tokens_to_ids)
    return df


def load_pretrained_model(args):
    # Load pre-trained model
    model = args.model_class.from_pretrained(args.model_name,
                                             local_files_only=False,
                                             output_hidden_states=True)
    model = model.to(args.device)
    model.eval()  # evaluation mode to deactivate the DropOut modules


def setup_environ(args):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    base_name = f'{args.model_name}-c-{args.context_length}-{args.suffix}'

    args.gpus = torch.cuda.device_count()
    args.base_name = base_name
    args.device = device
    return


def select_token_model(args):

    args.pickle_name = args.subject + '_labels.pkl'

    if 'roberta' in args.model_name:
        tokenizer_class = RobertaTokenizer
        model_class = RobertaForMaskedLM
    elif 'bert' in args.model_name:
        tokenizer_class = BertTokenizer
        model_class = BertForMaskedLM
    elif 'bart' in args.model_name:
        tokenizer_class = BartTokenizer
        model_class = BartForConditionalGeneration
    else:
        print('No model found for', args.model_name)
        exit(1)

    args.tokenizer_class = tokenizer_class
    args.model_class = model_class

    tokenizer = tokenizer_class.from_pretrained(args.model_name)
    if args.context_length <= 0:
        args.context_length = tokenizer.max_len
    assert args.context_length <= tokenizer.max_len, \
        'given length is greater than max length'

    return tokenizer


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-name',
                        type=str,
                        default='bert-large-uncased-whole-word-masking')
    parser.add_argument('--embedding-type', type=str, default='glove')
    parser.add_argument('--context-length', type=int, default=512)
    parser.add_argument('--save-predictions',
                        action='store_true',
                        default=False)
    parser.add_argument('--save-hidden-states',
                        action='store_true',
                        default=False)
    parser.add_argument('--suffix', type=str, default='')
    parser.add_argument('--verbose', action='store_true', default=False)
    parser.add_argument('--subject', type=str, default='625')
    parser.add_argument('--history', action='store_true', default=False)

    args = parser.parse_args()
    return args


def get_vector(x, glove):
    try:
        return glove.get_vector(x)
    except KeyError:
        return None


def gen_word2vec_embeddings(args, df):
    glove = api.load('glove-wiki-gigaword-50')
    df['embeddings'] = df['word'].apply(lambda x: get_vector(x, glove))
    save_pickle(df.to_dict('records'), '625_glove50_embeddings')
    return


def map_embeddings_to_tokens(df, embed):

    multi = df.set_index(['conversation_id', 'sentence_idx', 'sentence'])
    unique_sentence_idx = multi.index.unique().values

    uniq_sentence_count = len(get_unique_sentences(df))
    assert uniq_sentence_count == len(embed)

    c = []
    for unique_idx, sentence_embedding in zip(unique_sentence_idx, embed):
        a = df['conversation_id'] == unique_idx[0]
        b = df['sentence_idx'] == unique_idx[1]
        num_tokens = sum(a & b)
        c.append(pd.Series(sentence_embedding[1:num_tokens + 1, :].tolist()))

    df['embeddings'] = pd.concat(c, ignore_index=True)
    return df


def get_unique_sentences(df):
    return df[['conversation_id', 'sentence_idx',
               'sentence']].drop_duplicates()['sentence'].tolist()


def gen_bert_embeddings(args, df):
    tokenizer = BertTokenizer.from_pretrained(
        'bert-large-uncased-whole-word-masking')
    model = BertForMaskedLM.from_pretrained(
        'bert-large-uncased-whole-word-masking', output_hidden_states=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    unique_sentence_list = get_unique_sentences(df)
    df = tokenize_and_explode(df, tokenizer)

    tokens = tokenizer.batch_encode_plus(unique_sentence_list,
                                         padding=True,
                                         return_tensors='pt')
    input_ids_val = tokens['input_ids']
    attention_masks_val = tokens['attention_mask']

    dataset = data.TensorDataset(input_ids_val, attention_masks_val)
    data_dl = data.DataLoader(dataset, batch_size=256, shuffle=True)

    concat_output = []
    with torch.no_grad():
        model = model.to(device)
        model.eval()
        for i, batch in enumerate(data_dl):
            batch = tuple(b.to(device) for b in batch)
            inputs = {
                'input_ids': batch[0],
                'attention_mask': batch[1],
            }
            model_output = model(**inputs)
            # The last hidden-state is the first element of the output tuple
            print(model_output[-1].shape)
            concat_output.append(model_output[-1].detach().cpu().numpy())
    embeddings = np.concatenate(concat_output, axis=0)

    emb_df = map_embeddings_to_tokens(df, embeddings)
    save_pickle(emb_df.to_dict('records'), '625_bert_embeddings')

    return


def build_context_for_gpt2(args, df, model, tokenizer):
    if args.gpus > 1:
        model = nn.DataParallel(model)

    model = model.to(args.device)
    model.eval()

    final_embeddings = []
    for conversation in df.conversation_id.unique():
        token_list = df[df.conversation_id ==
                        conversation]['token_id'].tolist()
        sliding_windows = list(window(token_list, 1024))
        print(
            f'conversation: {conversation}, tokens: {len(token_list)}, #sliding: {len(sliding_windows)}'
        )
        input_ids = torch.tensor(sliding_windows)
        batch_size = 1
        data_dl = data.DataLoader(input_ids,
                                  batch_size=batch_size,
                                  shuffle=True)
        concat_output = []
        for i, batch in enumerate(data_dl):
            batch = batch.to(args.device)
            print(i, batch.shape)
            model_output = model(batch)
            # print(model_output[-1][-1].shape)
            if i == 0:
                concat_output.append(
                    model_output[-1][-1].detach().cpu().numpy())
            else:
                concat_output.append(
                    model_output[-1][-1][:, -1, :].detach().cpu().unsqueeze(
                        0).numpy())

        extracted_embeddings = np.concatenate(concat_output, axis=1)
        extracted_embeddings = np.squeeze(extracted_embeddings, axis=0)
        assert extracted_embeddings.shape[0] == len(token_list)
        final_embeddings.append(extracted_embeddings)

    df['embeddings'] = pd.concat(final_embeddings, ignore_index=True)
    save_pickle(df.to_dict('records'), '625_gpt2_contextual_embeddings')

    return df


def gen_gpt2_embeddings(args, df):
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2', add_prefix_space=True)
    model = GPT2LMHeadModel.from_pretrained('gpt2', output_hidden_states=True)
    tokenizer.pad_token = tokenizer.eos_token

    unique_sentence_list = get_unique_sentences(df)
    df = tokenize_and_explode(df, tokenizer)

    if args.history:
        build_context_for_gpt2(args, df, model, tokenizer)
        return

    input_ids = tokenizer(unique_sentence_list,
                          padding=True,
                          return_tensors='pt')

    batch_size = 256
    data_dl = data.DataLoader(input_ids['input_ids'],
                              batch_size=batch_size,
                              shuffle=True)

    concat_output = []
    with torch.no_grad():
        model = model.to(args.device)
        model.eval()
        for i, batch in enumerate(data_dl):
            batch = batch.to(args.device)
            model_output = model(batch)
            concat_output.append(model_output[-1][-1].detach().cpu().numpy())
    embeddings = np.concatenate(concat_output, axis=0)
    emb_df = map_embeddings_to_tokens(df, embeddings)
    save_pickle(emb_df.to_dict('records'), '625_gpt2_embeddings')

    return


def main():

    args = parse_arguments()
    setup_environ(args)

    # tokenizer = select_token_model(args)
    # load_pretrained_model(args)

    args.pickle_name = args.subject + '_labels.pkl'
    utter_orig = load_pickle(args.pickle_name)

    if args.embedding_type == 'glove':
        gen_word2vec_embeddings(args, utter_orig)
    elif args.embedding_type == 'bert':
        gen_bert_embeddings(args, utter_orig)
    elif args.embedding_type == 'gpt2':
        gen_gpt2_embeddings(args, utter_orig)

    return


if __name__ == '__main__':
    start_time = datetime.now()
    print(f'Start Time: {start_time.strftime("%A %m/%d/%Y %H:%M:%S")}')

    main()

    end_time = datetime.now()
    print(f'End Time: {end_time.strftime("%A %m/%d/%Y %H:%M:%S")}')
    print(f'Total runtime: {end_time - start_time} (HH:MM:SS)')
