import argparse
import os.path as osp
import signal
import time

import cv2
import numpy as np
import torch
import torchvision
from torchvision.transforms import Compose, ToTensor, RandomCrop, RandomHorizontalFlip, ToPILImage, Resize, RandomResizedCrop, Normalize

import core
from core_XAI.utils.distance import *
from NeuralCleanse.neural_cleanse import NeuralCleanse


parser = argparse.ArgumentParser(description='Neural Cleanse Experiments Launcher for Trojaned Models on Datasets')
parser.add_argument('--model_type', default='torchvision', type=str)
parser.add_argument('--model_name', default='ResNet-18', type=str)
parser.add_argument('--model_path', default='/disk/yamengxi/Backdoor/XAI/Backdoor_XAI/evalxai/ResNet-18_ImageNet100_fixed_square_20x20.pth.tar', type=str)

parser.add_argument('--dataset_name', default='ImageNet100', type=str)
parser.add_argument('--dataset_root_path', default='/home/mengxiya/datasets', type=str)

parser.add_argument('--batch_size', default=128, type=int)
parser.add_argument('--num_workers', default=4, type=int)

parser.add_argument('--seed', default=666, type=int)
parser.add_argument('--deterministic', action='store_true', default=False)

parser.add_argument('--y_target', default=0, type=int)
parser.add_argument('--trigger_size', default=20, type=int)
parser.add_argument('--init_cost_rate', default=1.0, type=float)
parser.add_argument('--NC_epochs', default=10, type=int)
parser.add_argument('--NC_lr', default=0.1, type=float)
parser.add_argument('--NC_optim', default='Adam', type=str)
parser.add_argument('--NC_schedule', default='', type=str)
parser.add_argument('--NC_gamma', default=0.1, type=float)
parser.add_argument('--cost_multiplier', default=1.5, type=float)
parser.add_argument('--patience', default=10, type=int)
parser.add_argument('--attack_succ_threshold', default=0.99, type=float)
parser.add_argument('--early_stop_threshold', default=0.99, type=float)
parser.add_argument('--NC_norm', default=1.0, type=float)
parser.add_argument('--initialize_method', default='normal_distribution', type=str)
parser.add_argument('--save_trigger_path', default='./NeuralCleanse/now_experiments', type=str)
args = parser.parse_args()

model_type=args.model_type
model_name=args.model_name
model_path=args.model_path
dataset_name=args.dataset_name
dataset_root_path=args.dataset_root_path
batch_size=args.batch_size
num_workers=args.num_workers
seed=args.seed
deterministic=args.deterministic
y_target=args.y_target
trigger_size=args.trigger_size
init_cost_rate=args.init_cost_rate
NC_epochs=args.NC_epochs
NC_lr=args.NC_lr
NC_optim=args.NC_optim
NC_schedule=args.NC_schedule
NC_schedule=[int(item) for item in NC_schedule.split(',')]
NC_gamma=args.NC_gamma
cost_multiplier=args.cost_multiplier
patience=args.patience
attack_succ_threshold=args.attack_succ_threshold
early_stop_threshold=args.early_stop_threshold
NC_norm=args.NC_norm
initialize_method=args.initialize_method
save_trigger_path=args.save_trigger_path


save_trigger_path=osp.join(save_trigger_path, f"{model_name}_{dataset_name}_{trigger_size}x{trigger_size}_epochs{NC_epochs}_lr{NC_lr}_{NC_optim}_schedule{args.NC_schedule}_gamma{NC_gamma}_init_cost{0.001 * 9 / (trigger_size * trigger_size) * init_cost_rate:.10f}_{time.strftime('%Y-%m-%d_%H:%M:%S', time.localtime())}")


if dataset_name=='MNIST':
    num_classes=10
    dataset=torchvision.datasets.MNIST
    if model_type=='core' and model_name=='BaselineMNISTNetwork':
        data_shape=(1, 28, 28)
        transform_train = Compose([
            ToTensor()
        ])
        transform_test = Compose([
            ToTensor()
        ])
    elif model_type=='core' and model_name.startswith('ResNet'):
        data_shape=(3, 32, 32)
        def convert_1HW_to_3HW(img):
            return img.repeat(3, 1, 1)
        transform_train = Compose([
            RandomCrop((32, 32), pad_if_needed=True),
            ToTensor(),
            convert_1HW_to_3HW
        ])
        transform_test = Compose([
            RandomCrop((32, 32), pad_if_needed=True),
            ToTensor(),
            convert_1HW_to_3HW
        ])
    else:
        raise NotImplementedError(f"Unsupported dataset_name: {dataset_name}, model_type: {model_type} with model_name: {model_name}")
    std_pattern = torch.zeros(data_shape)
    std_pattern[:, -trigger_size-1:-1, -trigger_size-1:-1] = 1.0
    std_weight = torch.zeros(data_shape[1:])
    std_weight[-trigger_size-1:-1, -trigger_size-1:-1] = 1.0
    trainset = dataset(dataset_root_path, train=True, transform=transform_train, download=True)
    testset = dataset(dataset_root_path, train=False, transform=transform_test, download=True)
elif dataset_name=='CIFAR-10':
    num_classes=10
    data_shape=(3, 32, 32)
    std_pattern = torch.zeros(data_shape)
    std_pattern[:, -trigger_size-1:-1, -trigger_size-1:-1] = 1.0
    std_weight = torch.zeros(data_shape[1:])
    std_weight[-trigger_size-1:-1, -trigger_size-1:-1] = 1.0
    dataset=torchvision.datasets.CIFAR10
    transform_train = Compose([
        RandomHorizontalFlip(),
        ToTensor()
    ])
    transform_test = Compose([
        ToTensor()
    ])
    trainset = dataset(dataset_root_path, train=True, transform=transform_train, download=True)
    testset = dataset(dataset_root_path, train=False, transform=transform_test, download=True)
elif dataset_name=='GTSRB':
    num_classes=43
    data_shape=(3, 32, 32)
    std_pattern = torch.zeros(data_shape)
    std_pattern[:, -trigger_size-1:-1, -trigger_size-1:-1] = 1.0
    std_weight = torch.zeros(data_shape[1:])
    std_weight[-trigger_size-1:-1, -trigger_size-1:-1] = 1.0
    dataset=torchvision.datasets.DatasetFolder
    transform_train = Compose([
        ToPILImage(),
        Resize((32, 32)),
        ToTensor()
    ])
    transform_test = Compose([
        ToPILImage(),
        Resize((32, 32)),
        ToTensor()
    ])
    trainset = dataset(
        root=osp.join(dataset_root_path, 'GTSRB', 'train'),
        loader=cv2.imread,
        extensions=('png',),
        transform=transform_train,
        target_transform=None,
        is_valid_file=None)
    testset = DatasetFolder(
        root=osp.join(dataset_root_path, 'GTSRB', 'testset'),
        loader=cv2.imread,
        extensions=('png',),
        transform=transform_test,
        target_transform=None,
        is_valid_file=None)
elif dataset_name=='ImageNet100':
    num_classes=100
    data_shape=(3, 224, 224)
    std_pattern = torch.zeros(data_shape)
    std_pattern[:, -trigger_size:, -trigger_size:] = 1.0
    std_weight = torch.zeros(data_shape[1:])
    std_weight[-trigger_size:, -trigger_size:] = 1.0
    dataset=torchvision.datasets.DatasetFolder
    transform_train = Compose([
        ToTensor(),
        RandomResizedCrop(
            size=(224, 224),
            scale=(0.1, 1.0),
            ratio=(0.8, 1.25),
            interpolation=torchvision.transforms.InterpolationMode.BICUBIC
        ),
        RandomHorizontalFlip(),
        Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))
    ])
    transform_test = Compose([
        ToTensor(),
        Resize((256, 256)),
        RandomCrop((224, 224)),
        Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))
    ])
    def my_read_image(image_path):
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    trainset = dataset(
        root=osp.join(dataset_root_path, 'ImageNet_100', 'train'),
        loader=my_read_image,
        extensions=('jpeg',),
        transform=transform_train,
        target_transform=None,
        is_valid_file=None
    )
    testset = dataset(
        root=osp.join(dataset_root_path, 'ImageNet_100', 'val'),
        loader=my_read_image,
        extensions=('jpeg',),
        transform=transform_test,
        target_transform=None,
        is_valid_file=None
    )
else:
    raise NotImplementedError(f"Unsupported dataset {dataset_name}")

if model_type=='core':
    if model_name=='BaselineMNISTNetwork':
        model=core.models.BaselineMNISTNetwork()
        model.load_state_dict(torch.load(model_path, map_location='cpu'), strict=True)
    elif model_name.startswith('ResNet'):
        model=core.models.ResNet(int(model_name.split('-')[-1]), num_classes)
        model.load_state_dict(torch.load(model_path, map_location='cpu'), strict=True)
    else:
        raise NotImplementedError(f"Unsupported model_type: {model_type} and model_name: {model_name}")
elif model_type=='torchvision':
    model = torchvision.models.__dict__[model_name.lower().replace('-', '')](weights=None, num_classes=num_classes)
    checkpoint = torch.load(args.model_path, map_location='cpu')
    model.load_state_dict(checkpoint, strict=True)
else:
    raise NotImplementedError(f"Unsupported model_type: {model_type}")


blended = core.Blended(
    train_dataset=trainset,
    test_dataset=testset,
    model=model,
    loss=torch.nn.CrossEntropyLoss(),
    y_target=y_target,
    poisoned_rate=0.05,
    pattern=std_pattern,
    weight=std_weight,
    poisoned_transform_train_index=len(trainset.transform.transforms),
    poisoned_transform_test_index=len(testset.transform.transforms),
    poisoned_target_transform_index=0,
    schedule=None,
    seed=int(time.time()),
    deterministic=deterministic
)

_, poisoned_testset = blended.get_poisoned_dataset()

schedule = {
    'device': 'GPU',
    # 'CUDA_SELECTED_DEVICES': '0',

    'batch_size': batch_size,
    'num_workers': num_workers,

    'metric': 'BA',

    'save_dir': save_trigger_path,
    'experiment_name': f'_std_trigger_test_BA'
}
top1_correct, top5_correct, total_num, mean_loss = core.utils.test(model, testset, schedule)

schedule = {
    'device': 'GPU',
    # 'CUDA_SELECTED_DEVICES': '0',

    'batch_size': batch_size,
    'num_workers': num_workers,

    'metric': 'ASR',

    'save_dir': save_trigger_path,
    'experiment_name': f'_std_trigger_test_ASR'
}
top1_correct, top5_correct, total_num, mean_loss = core.utils.test(model, poisoned_testset, schedule)


distance_functions = [
    ["1-norm loss, reduction='mean'", norm_loss],
    ["1-norm distance, reduction='mean'", norm],
    ["cross entropy loss distance, reduction='mean'", binary_cross_entropy],
    ["lovasz loss distance, reduction='mean'", lovasz_hinge],
    ["chamfer distance, reduction='mean'", chamfer_distance]
]
mean_losses = [mean_loss]
distances = [[0.0] for item in distance_functions]

dataloader = torch.utils.data.DataLoader(
    trainset,
    batch_size=batch_size,
    shuffle=False,
    num_workers=num_workers,
    drop_last=False,
    pin_memory=True
)

def my_handler(signum, frame):
    global stop
    stop = True
signal.signal(signal.SIGINT, my_handler)

iteration=0
stop = False
while not stop:
    iteration += 1
    model = model.cuda()
    neural_cleanse = NeuralCleanse(
        model,
        dataloader,
        None,
        num_epochs=NC_epochs,
        lr=NC_lr,
        optim=NC_optim,
        schedule=NC_schedule,
        gamma=NC_gamma,
        init_cost=0.001 * 9 / (trigger_size * trigger_size) * init_cost_rate,
        cost_multiplier=cost_multiplier,
        patience=patience,
        attack_succ_threshold=attack_succ_threshold,
        early_stop_threshold=early_stop_threshold,
        norm=NC_norm,
        num_classes=num_classes,
        data_shape=data_shape,
    )

    now_save_trigger_path=osp.join(save_trigger_path, f"{iteration}_{time.strftime('%Y-%m-%d_%H:%M:%S', time.localtime())}")
    mark_list, mask_list, loss_list = neural_cleanse.get_potential_triggers(
        now_save_trigger_path,
        y_target=y_target
    )

    blended = core.Blended(
        train_dataset=trainset,
        test_dataset=testset,
        model=model,
        loss=torch.nn.CrossEntropyLoss(),
        y_target=y_target,
        poisoned_rate=0.05,
        pattern=mark_list[0].cpu(),
        weight=mask_list[0].cpu(),
        poisoned_transform_train_index=len(trainset.transform.transforms),
        poisoned_transform_test_index=len(testset.transform.transforms),
        poisoned_target_transform_index=0,
        schedule=None,
        seed=int(time.time()),
        deterministic=deterministic
    )

    _, poisoned_testset = blended.get_poisoned_dataset()

    schedule = {
        'device': 'GPU',

        'batch_size': batch_size,
        'num_workers': num_workers,

        'metric': 'ASR',

        'save_dir': now_save_trigger_path,
        'experiment_name': f'NC_trigger_test_ASR'
    }
    top1_correct, top5_correct, total_num, mean_loss = core.utils.test(model, poisoned_testset, schedule)

    mean_losses.append(mean_loss)

    for i in range(len(distances)):
        std_weight_ = std_weight.clone().detach().cuda().unsqueeze(0)
        weight_ = mask_list.clone().detach().cuda()
        distances[i].append(distance_functions[i][1](weight_, std_weight_).cpu().item())


import matplotlib.pyplot as plt
distances = np.array(distances)
mean_losses = np.array(mean_losses)
os.makedirs(osp.join(save_trigger_path, f'__summary_experiments_results'), exist_ok=True)
np.savez(osp.join(save_trigger_path, f'__summary_experiments_results', f"{dataset_name}_{iteration}.npz"), distances=distances, mean_losses=mean_losses)

for i in range(len(distances)):
    plt.figure(figsize=(16,9), dpi=600)
    plt.scatter(distances[i], mean_losses, s=0.25)
    plt.savefig(osp.join(save_trigger_path, f'__summary_experiments_results', f"{dataset_name}_{iteration}_{distance_functions[i][0]}.png"))
    plt.close()

total_losses = mean_losses + 0.001 * 9 / (trigger_size * trigger_size) * init_cost_rate * distances[0]

with open(osp.join(save_trigger_path, f'__summary_experiments_results', 'trigger_statistics.log'),'w') as f:
    f.write(f'lr:{NC_lr:.10f}\n')
    f.write(f'epochs:{NC_epochs}\n')
    f.write(f'schedule:{args.NC_schedule}\n')
    f.write(f'init_cost:{0.001 * 9 / (trigger_size * trigger_size) * init_cost_rate:.10f}\n')

    f.write(f'NC样本数:{len(mean_losses) - 1}\n')

    f.write(f'total Loss (min):{total_losses[1:].min()}\n')
    f.write(f'total Loss (mean):{total_losses[1:].mean()}\n')
    f.write(f'total Loss (max):{total_losses[1:].max()}\n')
    f.write(f'total Loss (std):{total_losses[1:].std()}\n')

    # f.write(f'Poisoned Loss:{mean_losses[0]}\n')
    f.write(f'NC Loss (min):{mean_losses[1:].min()}\n')
    f.write(f'NC Loss (mean):{mean_losses[1:].mean()}\n')
    f.write(f'NC Loss (max):{mean_losses[1:].max()}\n')
    f.write(f'NC Loss (std):{mean_losses[1:].std()}\n')

    norm_losses = distances[0]
    f.write(f'NC norm loss (min):{norm_losses[1:].min()}\n')
    f.write(f'NC norm loss (mean):{norm_losses[1:].mean()}\n')
    f.write(f'NC norm loss (max):{norm_losses[1:].max()}\n')
    f.write(f'NC norm loss (std):{norm_losses[1:].std()}\n')

    f.write(f'{NC_lr:.10f}\n')
    f.write(f'{NC_epochs}\n')
    f.write(f'{args.NC_schedule}\n')
    f.write(f'{0.001 * 9 / (trigger_size * trigger_size) * init_cost_rate:.10f}\n')
    f.write(f'{len(mean_losses) - 1}\n')
    f.write(f'{total_losses[1:].min()}\n')
    f.write(f'{total_losses[1:].mean()}\n')
    f.write(f'{total_losses[1:].max()}\n')
    f.write(f'{total_losses[1:].std()}\n')
    f.write(f'{mean_losses[1:].min()}\n')
    f.write(f'{mean_losses[1:].mean()}\n')
    f.write(f'{mean_losses[1:].max()}\n')
    f.write(f'{mean_losses[1:].std()}\n')
    f.write(f'{norm_losses[1:].min()}\n')
    f.write(f'{norm_losses[1:].mean()}\n')
    f.write(f'{norm_losses[1:].max()}\n')
    f.write(f'{norm_losses[1:].std()}\n')


    # find top K
    norm_distances = distances[1]

    K = max(20, int(len(mean_losses) * 0.1))
    K = min(K, len(mean_losses))

    mean_losses = torch.from_numpy(mean_losses)
    topk = torch.topk(mean_losses, K, dim=0, largest=True, sorted=True)
    f.write(f'\n=========={K} Largest loss NC trigger==========\n')
    for i in range(len(topk.indices)):
        f.write(f'trigger id:{topk.indices[i]}, mean_loss:{mean_losses[topk.indices[i]]}, distance:{norm_distances[topk.indices[i]]}\n')
    topk = torch.topk(mean_losses, K, dim=0, largest=False, sorted=True)
    f.write(f'\n=========={K} Smallest loss NC trigger==========\n')
    for i in range(len(topk.indices)):
        f.write(f'trigger id:{topk.indices[i]}, mean_loss:{mean_losses[topk.indices[i]]}, distance:{norm_distances[topk.indices[i]]}\n')

    norm_distances = torch.from_numpy(norm_distances)
    topk = torch.topk(norm_distances, K, dim=0, largest=True, sorted=True)
    f.write(f'\n=========={K} Largest norm distance NC trigger==========\n')
    for i in range(len(topk.indices)):
        f.write(f'trigger id:{topk.indices[i]}, mean_loss:{mean_losses[topk.indices[i]]}, distance:{norm_distances[topk.indices[i]]}\n')
    topk = torch.topk(norm_distances, K, dim=0, largest=False, sorted=True)
    f.write(f'\n=========={K} Smallest norm distance NC trigger==========\n')
    for i in range(len(topk.indices)):
        f.write(f'trigger id:{topk.indices[i]}, mean_loss:{mean_losses[topk.indices[i]]}, distance:{norm_distances[topk.indices[i]]}\n')
