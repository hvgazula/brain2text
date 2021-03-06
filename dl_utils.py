import torch
import torch.utils.data as data
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import Dataset


class Brain2TextDataset(Dataset):
    """Brainwave-to-English Dataset (Pytorch Dataset wrapper)

    Args:
        Inherited from torch.utils.data.Dataset

    Returns:
        Dataset: tuple of (signal, label)
    """
    def __init__(self, signals, labels):
        """Create a tuple of signals and labels after sorting the
        signals on length (increasing).
        (This is for efficient padding in seq2seq models)

        Args:
            signals (list): brainwave examples.
            labels (list): english examples.
        """
        assert (len(signals) == len(labels))
        example_list = sorted(list(zip(signals, labels)), key=self.getKey)
        example_list = [(torch.from_numpy(k[0]).float(),
                         torch.tensor(k[1]).long()) for k in example_list]
        self.examples = example_list

    def getKey(self, item):
        return len(item[0])

    def __len__(self):
        """Denotes the total number of samples

        Returns:
            int: length of the dataset object
        """
        return len(self.examples)

    def __getitem__(self, idx):
        """Generates one sample of data

        Args:
            idx (int): index

        Returns:
            (torch.Float, torch.Long): (signal, label)
        """
        return self.examples[idx]


class MyCollator(object):
    def __init__(self, CONFIG, vocabulary):
        self.CONFIG = CONFIG
        self.vocabulary = vocabulary
        self.pad_token = CONFIG["pad_token"]

    def __call__(self, batch):
        """

        Args:
            batch (torch.tensor): batch dataset

        Returns:
            src (torch.tensor): input sequence
            trg (torch.tensor): target input sequence
            trg_y (torch.tensor): target output sequence
            pos_mask (torch.tensor): mask for target token
            pad_mask (torch.tensor): mask for pad token
        """
        src = pad_sequence([batch[i][0] for i in range(len(batch))],
                           batch_first=True,
                           padding_value=0.)
        labels = pad_sequence([batch[i][1] for i in range(len(batch))],
                              batch_first=True,
                              padding_value=self.vocabulary[self.pad_token])
        trg = torch.zeros(labels.size(0), labels.size(1),
                          len(self.vocabulary)).scatter_(
                              2, labels.unsqueeze(-1), 1)
        trg, trg_y = trg[:, :-1, :], labels[:, 1:]

        pos_mask, pad_mask = self.masks(trg_y)

        return src, trg, trg_y, pos_mask, pad_mask

    def masks(self, labels):
        """Create source and target masks for seq2seq models

        Args:
            labels (torch.tensor): index vector of labels

        Returns:
            pos_mask (torch.tensor): the additive mask for the trg sequence
            pad_mask (torch.tensor): the additive mask for the pad token
        """
        pos_mask = (torch.triu(torch.ones(labels.size(1),
                                          labels.size(1))) == 1).transpose(
                                              0, 1).unsqueeze(0)
        pos_mask = pos_mask.float().masked_fill(pos_mask == 0,
                                                float('-inf')).masked_fill(
                                                    pos_mask == 1, float(0.0))
        pad_mask = labels == self.vocabulary[self.pad_token]

        return pos_mask, pad_mask


def pitom_collate(batch):
    xx, yy = zip(*batch)
    xx_pad = torch.nn.utils.rnn.pad_sequence(
        [batch[i][0] for i in range(len(batch))],
        batch_first=True,
        padding_value=0.)

    return xx_pad, torch.tensor(yy)


def create_dl_objects(CONFIG, train_ds, valid_ds, vocab):
    classify = CONFIG["classify"]

    if classify and not CONFIG["nseq"]:
        my_collator = None
    elif classify and CONFIG["nseq"]:
        my_collator = pitom_collate
    else:
        my_collator = MyCollator(CONFIG, vocab)

    train_dl = data.DataLoader(train_ds,
                               batch_size=CONFIG["batch_size"],
                               shuffle=True,
                               num_workers=CONFIG["num_cpus"],
                               collate_fn=my_collator)
    valid_dl = data.DataLoader(valid_ds,
                               batch_size=CONFIG["batch_size"],
                               num_workers=CONFIG["num_cpus"],
                               collate_fn=my_collator)

    return train_dl, valid_dl
