from collections import Counter
from itertools import compress


def filter_by_labels(signals, labels, set_min_samples):
    label_flag = return_label_flag(labels, set_min_samples)
    signals = list(compress(signals, label_flag))
    labels = list(compress(labels, label_flag))
    return signals, labels


def filter_by_signals(signals, labels, set_max_seq_length):
    signal_flag = return_signal_flag(signals, set_max_seq_length)
    signals = list(compress(signals, signal_flag))
    labels = list(compress(labels, signal_flag))
    return signals, labels


def return_label_flag(labels, set_min_samples):
    label_counter = label_counts(labels)
    select_labels = [
        list(label) for label, count in label_counter.items()
        if count >= set_min_samples
    ]
    label_flag = [label in select_labels for label in labels]
    return label_flag


def return_signal_flag(signals, set_max_seq_length):
    seq_lengths = [len(signal) for signal in signals]
    signal_flag = [
        seq_length <= set_max_seq_length for seq_length in seq_lengths
    ]
    return signal_flag


def label_counts(labels):
    return Counter([tuple(label) for label in labels])