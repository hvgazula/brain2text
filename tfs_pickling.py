'''
Filename: /scratch/gpfs/hgazula/247-project/tfs_pickling.py
Path: /scratch/gpfs/hgazula/247-project
Created Date: Tuesday, December 1st 2020, 8:19:27 pm
Author: Harshvardhan Gazula
Description: Contains code to pickle 247 data

Copyright (c) 2020 Your Company
'''
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from nltk.stem import PorterStemmer
from sklearn.model_selection import StratifiedKFold

from arg_parser import arg_parser
from build_matrices import build_design_matrices
from config import build_config


def save_pickle(item, file_name):
    """Write 'item' to 'file_name.pkl'
    """
    if '.pkl' not in file_name:
        file_name = file_name + '.pkl'

    with open(file_name, 'wb') as fh:
        pickle.dump(item, fh)
    return


def adjust_label_onsets(trimmed_stitch_index, labels):
    """Adjust label onsets to account for stitched signal length.
    Also peform stemming on the labels.

    Args:
        trimmed_stitch_index (list): stitch indices of trimmed signal
        labels (list): of tuples (word, speaker, onset, offset, accuracy)

    Returns:
        DataFrame: labels
    """
    trimmed_stitch_index.insert(0, 0)
    trimmed_stitch_index.pop(-1)

    new_labels = []
    ps = PorterStemmer()
    for start, sub_list in zip(trimmed_stitch_index, labels):
        modified_labels = [(ps.stem(*i[0]), i[1], i[2] + start, i[3] + start,
                            i[4]) for i in sub_list]
        new_labels.extend(modified_labels)

    df = pd.DataFrame(
        new_labels, columns=['word', 'speaker', 'onset', 'offset', 'accuracy'])

    return df


def create_label_pickles(args, df, file_string):
    # create and save folds
    df = df.groupby('word').filter(
        lambda x: len(x) >= args.vocab_min_freq).reset_index(drop=True)
    print(df.word.nunique())
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)

    # Extract only test folds
    folds = [t[1] for t in skf.split(df, df.word)]

    # Go through each fold, and split
    for i in range(5):
        # Shift the number of folds for this iteration
        # [0 1 2 3 4] -> [1 2 3 4 0] -> [2 3 4 0 1]
        #                       ^ dev fold
        #                         ^ test fold
        #                 | - | <- train folds
        fold_col = 'fold' + str(i)
        folds_ixs = np.roll(range(5), i)
        *train_fold, dev_fold, test_fold = folds_ixs

        df.loc[folds[test_fold], fold_col] = 'test'
        df.loc[folds[dev_fold], fold_col] = 'dev'
        df.loc[[
            *folds[train_fold[0]], *folds[train_fold[1]], *folds[train_fold[2]]
        ], fold_col] = 'train'

    label_folds = df.to_dict('records')
    save_pickle(label_folds, file_string + str(args.vocab_min_freq))

    return


def main():
    args = arg_parser()
    CONFIG = build_config(args, results_str='pickles')

    if CONFIG['pickle']:
        (full_signal, full_stitch_index, trimmed_signal, trimmed_stitch_index,
         binned_signal, bin_stitch_index, labels, convo_example_size,
         electrodes) = build_design_matrices(CONFIG, delimiter=" ")

        # Create pickle with full signal
        full_signal_dict = dict(full_signal=full_signal,
                                full_stitch_index=full_stitch_index,
                                electrodes=electrodes)
        save_pickle(full_signal_dict, '625_full_signal')

        # Create pickle with trimmed signal
        trimmed_signal_dict = dict(trimmed_signal=trimmed_signal,
                                   trimmed_stitch_index=trimmed_stitch_index,
                                   electrodes=electrodes)
        save_pickle(trimmed_signal_dict, '625_trimmed_signal')

        # Create pickle with binned signal
        binned_signal_dict = dict(binned_signal=binned_signal,
                                  bin_stitch_index=bin_stitch_index,
                                  electrodes=electrodes)
        save_pickle(binned_signal_dict, '625_binned_signal')

        # Create pickle with all labels
        labels_df = adjust_label_onsets(trimmed_stitch_index, labels)
        labels_dict = dict(labels=labels_df.to_dict('records'),
                           convo_label_size=convo_example_size)
        save_pickle(labels_dict, '625_all_labels')

        # Create pickle with both production & comprehension labels
        create_label_pickles(args, labels_df, '625_both_labels_MWF')

        # Create pickle with production labels
        prod_df = labels_df[labels_df['speaker'] == 'Speaker1']
        create_label_pickles(args, prod_df, '625_prod_labels_MWF')

        # Create pickle with comprehension labels
        comp_df = labels_df[labels_df['speaker'] != 'Speaker1']
        create_label_pickles(args, comp_df, '625_comp_labels_MWF')

    return


if __name__ == "__main__":
    start_time = datetime.now()
    print(f'Start Time: {start_time.strftime("%A %m/%d/%Y %H:%M:%S")}')

    main()

    end_time = datetime.now()
    print(f'End Time: {end_time.strftime("%A %m/%d/%Y %H:%M:%S")}')
    print(f'Total runtime: {end_time - start_time} (HH:MM:SS)')
