import os
from options.test_options import TestOptions
from models import create_model
from util.visualizer import save_images
import numpy as np
import math
from PIL import Image
import torchvision.transforms as transforms
import torch
import random
import cv2
import argparse
from tqdm import tqdm
from util import html
from dfl.dfl_read import load_data

from scipy.io import loadmat

def AddUpSample(img):
    return img.resize((512, 512), Image.BICUBIC)


def get_part_location(dfl_image, image):
    Landmarks = dfl_image.get_landmarks()

    width, height = image.size
    if width != 512 or height != 512:
        width_scale = 512.0 / width
        height_scale = 512.0 / height

        Landmarks = Landmarks * np.array([width_scale, height_scale])

    Map_LE = list(np.hstack((range(17,22), range(36,42))))
    Map_RE = list(np.hstack((range(22,27), range(42,48))))
    Map_NO = list(range(29,36))
    Map_MO = list(range(48,68))

    #left eye
    Mean_LE = np.mean(Landmarks[Map_LE],0)
    L_LE = np.max((np.max(np.max(Landmarks[Map_LE],0) - np.min(Landmarks[Map_LE],0))/2,16))
    Location_LE = np.hstack((Mean_LE - L_LE + 1, Mean_LE + L_LE)).astype(int)
    #right eye
    Mean_RE = np.mean(Landmarks[Map_RE],0)
    L_RE = np.max((np.max(np.max(Landmarks[Map_RE],0) - np.min(Landmarks[Map_RE],0))/2,16))
    Location_RE = np.hstack((Mean_RE - L_RE + 1, Mean_RE + L_RE)).astype(int)

    #nose
    Mean_NO = np.mean(Landmarks[Map_NO],0)
    L_NO = np.max((np.max(np.max(Landmarks[Map_NO],0) - np.min(Landmarks[Map_NO],0))/2,16))
    Location_NO = np.hstack((Mean_NO - L_NO + 1, Mean_NO + L_NO)).astype(int)

    #mouth
    Mean_MO = np.mean(Landmarks[Map_MO],0)
    L_MO = np.max((np.max(np.max(Landmarks[Map_MO],0) - np.min(Landmarks[Map_MO],0))/2,16))
    Location_MO = np.hstack((Mean_MO - L_MO + 1, Mean_MO + L_MO)).astype(int)

    return torch.from_numpy(Location_LE).unsqueeze(0), torch.from_numpy(Location_RE).unsqueeze(0), torch.from_numpy(Location_NO).unsqueeze(0), torch.from_numpy(Location_MO).unsqueeze(0)

def obtain_inputs(img_path, img_name, Type):
    A_paths = os.path.join(img_path,img_name)
    Imgs = Image.open(A_paths).convert('RGB')
    dfl_image = load_data(A_paths)

    Part_locations = get_part_location(dfl_image, Imgs)
    if Part_locations == 0:
        print('wrong part_location')
        return 0
    width, height = Imgs.size
    L = min(width, height)

    #################################################
    A= Imgs
    C = A
    A = AddUpSample(A)

    A = transforms.ToTensor()(A) 
    C = transforms.ToTensor()(C)

    A = transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))(A) #
    C = transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))(C) #

    return {'A':A.unsqueeze(0), 'C':C.unsqueeze(0), 'A_paths': A_paths,'Part_locations': Part_locations}
    


if __name__ == '__main__':  
    opt = TestOptions().parse()
    opt.nThreads = 1   # test code only supports nThreads = 1
    opt.batchSize = 1  # test code only supports batchSize = 1
    opt.serial_batches = True  # no shuffle
    opt.no_flip = True  # no flip
    opt.display_id = -1  # no visdom display
    opt.which_epoch = 'latest' #

    ####################################################
    ##Test Param
    #####################################################
    IsReal = 0
    opt.gpu_ids = [0]
    TestImgPath = opt.input_folder #% test image path
    opt.results_dir = opt.output_folder #save path

    #####################################

    model = create_model(opt)
    model.setup(opt)
    # create website
    web_dir = os.path.join(opt.results_dir, opt.name)
    webpage = html.HTML(web_dir, 'Experiment = %s, Phase = %s, Epoch = %s' % (opt.name, opt.phase, opt.which_epoch))
    
    # test
    ImgNames = os.listdir(TestImgPath)
    ImgNames.sort()

    for i, ImgName in enumerate(tqdm(ImgNames)):
        torch.cuda.empty_cache()
        data = obtain_inputs(TestImgPath, ImgName, 'real')
        if data == 0:
            print ('Skipping ' + ImgName + ' data not found');
            continue
        model.set_input(data)
        model.test()
        visuals = model.get_current_visuals()
        img_path = model.get_image_paths()
        save_images(webpage, visuals, img_path, aspect_ratio=opt.aspect_ratio, width=opt.display_winsize)

    webpage.save()
