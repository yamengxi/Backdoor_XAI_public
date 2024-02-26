import os
import os.path as osp
import time

import cv2
import torch
from torch.utils.data import DataLoader
import torchvision
from torchvision.transforms import Compose, ToTensor, RandomHorizontalFlip, ToPILImage, Resize
import torchvision.transforms as transforms
from torchvision.datasets import DatasetFolder

import core
from NeuralCleanse.neural_cleanse import NeuralCleanse


datasets_root_dir = '../datasets'
os.environ['CUDA_VISIBLE_DEVICES'] = '5'
device = torch.device("cuda:0")


iteration=1

while True:
    model = core.models.ResNet(18, 43)
    model.load_state_dict(torch.load('/data/yamengxi/XAI/BackdoorBox_XAI/experiments/ResNet-18_GTSRB_BadNets_2022-05-25_02:55:53/ckpt_epoch_30.pth'))
    save_trigger_dir = '/data/yamengxi/XAI/BackdoorBox_XAI/NeuralCleanse/experiments/' + __file__.split('/')[-1].split('.')[0] + f'_{iteration}_' + time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())

    model = model.to(device)

    transform_train = Compose([
        ToPILImage(),
        Resize((32, 32)),
        ToTensor()
    ])
    trainset = DatasetFolder(
        root=osp.join(datasets_root_dir, 'GTSRB', 'train'), # please replace this with path to your training set
        loader=cv2.imread,
        extensions=('png',),
        transform=transform_train,
        target_transform=None,
        is_valid_file=None)

    dataloader = DataLoader(
        trainset,
        batch_size=128,
        shuffle=False,
        num_workers=4,
        drop_last=False,
        pin_memory=True
    )

    neural_cleanse = NeuralCleanse(
        model,
        dataloader,
        None,
        num_classes=43,
        data_shape=[3, 32, 32]
    )
    neural_cleanse.get_potential_triggers(save_trigger_dir, y_target=1)

    iteration += 1

