import pickle
import numpy as np
import os
import torch
import torchvision
import torchvision.transforms as transforms
import clip
from tqdm import tqdm
from torch.utils.data import DataLoader, Dataset
import json
from PIL import Image, ImageFont, ImageDraw
import random

# random comment
def accuracy(output, target, topk=(1,)):
    pred = output.topk(max(topk), 1, True, True)[1].t()
    correct = pred.eq(target.view(1, -1).expand_as(pred))
    return [float(correct[:k].reshape(-1).float().sum(0, keepdim=True).cpu().numpy()) for k in topk]


def evaluate(loader):
    with torch.no_grad():
        top1 = 0.
        top5 = 0.
        n = 0.
        # with tqdm(testloader, unit="batch") as tepoch:
        for i, (images, target) in enumerate(tqdm(loader, unit='batch')):
            images = images.cuda()
            target = target.cuda()

            #prediction
            image_features = model.encode_image(images).float()
            image_features /= image_features.norm(dim=-1, keepdim=True)
            logits = 100. * image_features @ text_features.T

            #Calculate accuracy
            acc1, acc5 = accuracy(logits, target, topk=(1, 5))
            top1 += acc1
            top5 += acc5
            n += images.size(0)
    
    top1 = (top1 / n) * 100
    top5 = (top5 / n) * 100
    return top1, top5


def unpickle(file):
    import pickle
    with open(file, 'rb') as fo:
        dict = pickle.load(fo, encoding='latin1')
    return dict
    

def get_cifar10_classes(file):
    """
    Get the Cifar10 classes as a list for AddText transform
    """
    data = unpickle(file)
    classes = data['label_names']
    return classes


def get_cifar100_classes(file):
    """
    Get the Cifar100 classes as a list for AddText transform
    """
    data = unpickle(file)
    classes = data['fine_label_names']
    return classes


class AddText(object):
    """
    Add a randomly chosen class as text on the image
    """
    def __init__(self, classes, fontsize=5):
        self.classes = classes
        self.fontsize = fontsize
        self.font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf', self.fontsize)

    def __call__(self, sample):
        image = sample
        text_class = np.random.choice(self.classes)
        img_tf = ImageDraw.Draw(image)
        
        #Setting possible positions and colours of text and choosing one in random 
        text_locs = [(np.round(i * image.size[0]), np.round(j * image.size[1])) for (i,j) in [(0.25, 0.25), (0.25, 0.6), (0.75, 0.25), (0.6, 0.6)]]
        text_pos = random.choice(text_locs)
        text_cols = [(255,0,0), (0,255,0), (0,0,255), (0,0,0), (255,255,255)]
        text_col = random.choice(text_cols)
        img_tf.text(text_pos, text_class, text_col, font=self.font)

        return image



TEXT_CORRUPT = False
fontsize = 5
clip_models = clip.available_models()[0:4] + clip.available_models()[5:-2]
print(clip_models)
datasets = ['cifar10', 'cifar100']

for clipx in clip_models:
    accuracies = {}
    model, preprocess = clip.load(clipx)
    
    model.cuda().eval()
    input_resolution = model.visual.input_resolution
    context_length = model.context_length
    vocab_size = model.vocab_size

    print(f"Using CLIP model {clipx}")
    print("Model parameters:", f"{np.sum([int(np.prod(p.shape)) for p in model.parameters()]):,}")
    print("Input resolution:", input_resolution)
    print("Context length:", context_length)
    print("Vocab size:", vocab_size)
    for dataset in datasets:
        batch_size = 2
        if dataset == 'cifar10':
            cifar_classes = get_cifar10_classes('/home/jameel.hassan/Documents/AI701/data/cifar10/cifar-10-batches-py/batches.meta')
            print(cifar_classes)
            if TEXT_CORRUPT:
                preprocess = transforms.Compose([AddText(cifar_classes, fontsize=fontsize), preprocess])
                ### DO transform in evaluate function
            # trainset = torchvision.datasets.CIFAR10(root='/home/jameel.hassan/Documents/AI701/data/cifar10', train=True, download=False, transform=preprocess)
            # trainloader = torch.utils.data.DataLoader(trainset, batch_size=batch_size, shuffle=True, num_workers=2)

            testset = torchvision.datasets.CIFAR10(root='/home/jameel.hassan/Documents/AI701/data/cifar10', train=False, download=False, transform=preprocess)
            testloader = torch.utils.data.DataLoader(dataset=testset, batch_size=batch_size, shuffle=False, num_workers=2)
        elif dataset == 'cifar100':
            cifar_classes = get_cifar100_classes('/home/jameel.hassan/Documents/AI701/data/cifar100/cifar-100-python/meta')
            print(len(cifar_classes))
            if TEXT_CORRUPT:
                preprocess = transforms.Compose([AddText(cifar_classes, fontsize=fontsize), preprocess])
            # trainset = torchvision.datasets.CIFAR100(root='/home/jameel.hassan/Documents/AI701/data/cifar100', train=True, download=False, transform=preprocess)
            # trainloader = torch.utils.data.DataLoader(trainset, batch_size=batch_size, shuffle=True, num_workers=2)

            testset = torchvision.datasets.CIFAR100(root='/home/jameel.hassan/Documents/AI701/data/cifar100', train=False, download=False, transform=preprocess)
            testloader = torch.utils.data.DataLoader(dataset=testset, batch_size=batch_size, shuffle=False, num_workers=2)
        else:
            print("Dataset other than CIFAR requested.")

        print(f"Evaluating {dataset}")
        classes = testset.classes

        # Text label caption
        text_descriptions = [f"This is a photo of a {label}" for label in classes]
        text_tokens = clip.tokenize(text_descriptions).cuda()
        with torch.no_grad():
            text_features = model.encode_text(text_tokens).float()
            text_features /= text_features.norm(dim=-1, keepdim=True)

        top1, top5 = evaluate(loader=testloader)
        print(f"Top1 Accuracy: {top1:.2f}\nTop5 Accuracy: {top5:.2f}")
        accuracies[dataset] = {'Top1': top1, 'Top5': top5}

    savepath = f"./results/experiment_t{fontsize}/" if TEXT_CORRUPT else "./results/zeroshot/"
    if not os.path.exists(savepath):
        os.mkdir(savepath)
    savepath = savepath + "accuracies_" + clipx.replace('/' , '-') + ".json"
    with open(savepath, "w") as js:
        json.dump(accuracies, js)

