import csv
import os

import numpy as np
import pandas as pd
from tabulate import tabulate

from filter_utils import label_counts


def bigram_counts_to_csv(CONFIG, labels_list, classify=True, data_str=None):
    """Save train and test bigram counts to file

    Args:
        CONFIG ([type]): configuration information
        labels_list (list): list of labels (train and test)
        classify (bool, optional): classification or seq2seq. Defaults to True.
        data_str (str, optional): string indicating train/test.
                                  Defaults to None.
    """
    classify = CONFIG["classify"]
    labels, y_train, y_test = labels_list
    all_labels_counter = label_counts(labels, classify=classify)
    train_labels_counter = label_counts(y_train, classify=classify)
    test_labels_counter = label_counts(y_test, classify=classify)

    col_size = 1 if classify else len(list(all_labels_counter.keys())[0])

    col_names = [
        '_'.join(['word', str(num)]) for num in range(1, col_size + 1)
    ]
    df_all = pd.Series(all_labels_counter).rename_axis(
        col_names).sort_index().reset_index(name='Total_Count')
    df_train = pd.Series(train_labels_counter).rename_axis(
        col_names).sort_index().reset_index(name='Train_Count')
    df_test = pd.Series(test_labels_counter).rename_axis(
        col_names).sort_index().reset_index(name='Test_Count')

    if not data_str:
        print('No file name specified.')
    elif data_str == 'mixed':
        file_name = '_'.join(['train_test', 'gram', 'count']) + '.csv'
    else:
        file_name = '_'.join([data_str, 'count']) + '.csv'

    df = pd.merge(df_train, df_test, on=['word_1', 'word_2'])
    df = pd.merge(df, df_all, on=['word_1', 'word_2'])

    tabulate_and_print(CONFIG, df, file_name)


def save_word_counter(CONFIG, word2freq):
    """Write word frequency to file

    Args:
        CONFIG (dict): configuration
        word2freq (dict/counter): words and their corresponding frequencies
    """
    print("Saving word counter")
    df = pd.Series(word2freq).rename_axis(['Word'
                                           ]).reset_index(name='Frequency')
    tabulate_and_print(CONFIG, df, 'word2freq.csv')


def print_model(CONFIG, model):
    """Save model summary to file

    Args:
        CONFIG (dict): configuration information
        model (nn.Module): model object to be saved to file
    """
    print('Printing Model Summary')
    with open(os.path.join(CONFIG["SAVE_DIR"], 'model_summary'),
              'w') as file_h:
        print(model, file=file_h)


def tabulate_and_print(CONFIG, data, file_name, showindex=False):
    """Convert a dataframe into table and print to file

    Args:
        CONFIG (dict): configuration information
        data_frame (DataFrame): dataframe object to tabulate
        file_name (str): output filename
    """
    args_dict = dict(tablefmt='plain',
                     floatfmt=".4f",
                     numalign='center',
                     stralign='center',
                     colalign=("center", ))

    if isinstance(data, pd.DataFrame):
        mystrn = tabulate(data,
                          headers=data.columns,
                          showindex=showindex,
                          **args_dict)
    elif isinstance(data, (np.ndarray, np.generic)):
        mystrn = tabulate(data, **args_dict)
    elif isinstance(data, list):
        mystrn = tabulate(data, **args_dict)
    else:
        print('Unsupported datatype')

    with open(os.path.join(CONFIG["SAVE_DIR"], file_name), 'w') as f:
        f.writelines(mystrn)


def write_list_to_file(CONFIG, data_list, file_name):
    with open(os.path.join(CONFIG["SAVE_DIR"], file_name), 'a+') as myfile:
        wr = csv.writer(myfile, delimiter='\n')
        wr.writerow(data_list)
        wr.writerow('\n')
