import torchvision
from torchvision.transforms import Compose, ToTensor, RandomHorizontalFlip, ToPILImage, Resize

import torch.nn as nn
import core_XAI
from core_XAI.utils.distance import *


# ========== Set global settings ==========
global_seed = 666
deterministic = False
torch.manual_seed(global_seed)
CUDA_VISIBLE_DEVICES = '6'
datasets_root_dir = '../datasets'


# ========== ResNet-18_CIFAR-10_BaseMix ==========
dataset = torchvision.datasets.CIFAR10

transform_train = Compose([
    RandomHorizontalFlip(),
    ToTensor()
])
trainset = dataset(datasets_root_dir, train=True, transform=transform_train, download=True)

transform_test = Compose([
    ToTensor()
])
testset = dataset(datasets_root_dir, train=False, transform=transform_test, download=True)

pattern = torch.zeros((32, 32), dtype=torch.uint8)
pattern[-4:-1, -4:-1] = 255
weight = torch.zeros((32, 32), dtype=torch.float32)
weight[-4:-1, -4:-1] = 1.0

base_mix = core_XAI.BaseMix(
    train_dataset=trainset,
    test_dataset=testset,
    model=core_XAI.models.ResNet(18),
    loss=nn.CrossEntropyLoss(reduction='none'),
    num_classes=10,
    y_target=1,
    pattern=pattern,
    weight=weight,
    schedule=None,
    seed=global_seed,
    deterministic=deterministic
)

schedule = {
    'device': 'GPU',
    'CUDA_VISIBLE_DEVICES': CUDA_VISIBLE_DEVICES,
    'GPU_num': 1,

    'batch_size': 128 * 3,
    'num_workers': 4,

    'distance': norm,
    # 'adv_lr': 1.0, # 2.269047498703003
    # 'adv_lr': 0.5, # 
    'adv_lr': 0.1, # 2.3150596618652344, 2.323528289794922, 2.3235280513763428
    'adv_betas': (0.5, 0.9),
    'adv_epochs': 100,
    'lambda_1': 1.0,
    'lambda_2': 1.0,

    # 'pretrain': ???,

    'lr': 0.1,
    'momentum': 0.9,
    'weight_decay': 5e-4,
    'gamma': 0.1,
    'schedule': [150, 180],

    'epochs': 200,

    'log_iteration_interval': 100,
    'test_epoch_interval': 10,
    'save_epoch_interval': 10,

    'save_dir': 'adv_experiments',
    'experiment_name': 'ResNet-18_CIFAR-10_BaseMix'
}
base_mix.train(schedule)



