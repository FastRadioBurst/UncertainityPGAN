
import torch.utils.data as data
import os.path
import numpy as np
import random
import torch
import torchvision.transforms as transforms
import os

#from torchsummary import summary
import numpy as np
import pandas as pd
import PIL
from PIL import Image, ImageOps
from sklearn import metrics
import tqdm

from torchvision.utils import save_image

from src.networks import CasUNet_3head 
from src.networks import UNet_3head
from src.networks import NLayerDiscriminator
from src.utils import train_i2i_UNet3headGAN
from src.utils import train_i2i_Cas_UNet3headGAN
import src.losses


class CustomDataset(torch.utils.data.Dataset):
    def __init__(self, csv_path, image_path, image_target_path, transform = None):
        self.df = pd.read_csv(csv_path)
        self.image_path = image_path
        self.image_target_path = image_target_path
        self.transform = transform
    
    def __len__(self):
        return len(self.df)

    def __getitem__(self, index):
        #ID = str(self.df.loc[index, 'ID'])
        filename = str(self.df.loc[index, 'filename'])
        #filename2 = str(self.df.loc[index, 'Right-Fundus'])
        #label = self.df.loc[index, ['N', 'D', 'G', 'C', 'A', 'H', 'M', 'O']].to_numpy(dtype = int)
        image1 = PIL.Image.open(os.path.join(self.image_path, filename))
        image_target = PIL.Image.open(os.path.join(self.image_target_path, filename[:-3]+'png'))
        
        #image_target=transforms.Grayscale(num_output_channels=1)(image_target)
        if self.transform is not None:
            image1 = self.transform(image1)
            image_target = self.transform(image_target)
        return image1, image_target, filename#, label, int(ID)







if __name__ == '__main__':



    img_size=256
    batch_size=2
    num_epochs=5

    device = 'cuda'
    dtype = torch.cuda.FloatTensor

    path_checkpoint='./ckpt'

    if os.path.isdir(path_checkpoint) == False:
        os.makedirs(path_checkpoint)

    path_train_csv = './data/train.csv'
    path_train_image = './data/images'
    path_train_image_target = './data/soft_disc'

    path_test_csv = './data/test.csv'
    path_test_image = './data/images'
    path_test_image_target = './data/soft_disc'

    path_save_image_result =  './results'
    if os.path.isdir(path_save_image_result) == False:
        os.makedirs(path_save_image_result)




    transform_train = transforms.Compose([
                transforms.Resize((int(img_size),int(img_size))),
                transforms.Grayscale(num_output_channels=1),  
                transforms.ToTensor(),                 
    ])

    
    transform_test = transforms.Compose([
                transforms.Resize((int(img_size),int(img_size))),   
                transforms.Grayscale(num_output_channels=1),  
                transforms.ToTensor()
    ])


    trainset= CustomDataset(path_train_csv, path_train_image, path_train_image_target, transform_train)
    testset = CustomDataset(path_test_csv, path_test_image, path_test_image_target, transform_test)

    train_loader = torch.utils.data.DataLoader(trainset, batch_size = batch_size, num_workers=4, shuffle = True)
    test_loader = torch.utils.data.DataLoader(testset, batch_size = 1, num_workers=1, shuffle = False)


    ###############
    #''' train primary GAN'''
    ###############

    print('==> primary GAN training ...' )

    netG_A = CasUNet_3head(1,1)
    netD_A = NLayerDiscriminator(1, n_layers=4)
    netG_A, netD_A = train_i2i_UNet3headGAN(
        netG_A, netD_A,
        train_loader, test_loader,
        dtype = dtype,
        device= device,
        num_epochs=num_epochs,
        init_lr=1e-5,
        ckpt_path='./ckpt/i2i_0_UNet3headGAN',
        )

    ###############
    #''' train subsequent GAN #1'''
    ###############

    print('==> sebsequent GAN #1 training ...' )

    # first load the prior Generators 
    netG_A0 = CasUNet_3head(1,1)
    netG_A0.load_state_dict(torch.load('./ckpt/i2i_0_UNet3headGAN_eph' + str(num_epochs-1) + '_G_A.pth'))

    #initialize the current GAN
    netG_A1 = UNet_3head(4,1)
    netD_A = NLayerDiscriminator(1, n_layers=4)

    #train the cascaded framework
    list_netG_A, list_netD_A = train_i2i_Cas_UNet3headGAN(
        [netG_A0, netG_A1], [netD_A],
        train_loader, test_loader,
        dtype = dtype,
        device= device,
        num_epochs=num_epochs,
        init_lr=1e-5,
        ckpt_path='./ckpt/i2i_1_UNet3headGAN',
    )    

    ###############
    #''' train subsequent GAN #2'''
    ###############

    print('==> sebsequent GAN #2 training ...' )

    # first load the prior Generators 
    netG_A0 = CasUNet_3head(1,1)
    netG_A0.load_state_dict(torch.load('./ckpt/i2i_0_UNet3headGAN_eph' + str(num_epochs-1) + '_G_A.pth'))
    netG_A1 = UNet_3head(4,1)
    netG_A1.load_state_dict(torch.load('./ckpt/i2i_1_UNet3headGAN_eph' + str(num_epochs-1) + '_G_A.pth'))

    #initialize the current GAN
    netG_A2 = UNet_3head(4,1)
    netD_A = NLayerDiscriminator(1, n_layers=4)

    #train the cascaded framework
    list_netG_A, list_netD_A = train_i2i_Cas_UNet3headGAN(
        [netG_A0, netG_A1, netG_A2], [netD_A],
        train_loader, test_loader,
        dtype=torch.cuda.FloatTensor,
        device='cuda',
        num_epochs = num_epochs,
        init_lr=1e-5,
        ckpt_path='./ckpt/i2i_2_UNet3headGAN',
    )

    ###############
    #''' test'''
    ###############

    print('==> Testing ...' )

    netG_A0 = CasUNet_3head(1,1)
    netG_A0.load_state_dict(torch.load('./ckpt/i2i_0_UNet3headGAN_eph' + str(num_epochs-1) + '_G_A.pth'))
    netG_A1 = UNet_3head(4,1)
    netG_A1.load_state_dict(torch.load('./ckpt/i2i_1_UNet3headGAN_eph' + str(num_epochs-1) + '_G_A.pth'))
    netG_A2 = UNet_3head(4,1)
    netG_A2.load_state_dict(torch.load('./ckpt/i2i_2_UNet3headGAN_eph' + str(num_epochs-1) + '_G_A.pth'))

    for i, batch in enumerate(test_loader):  

        xA = batch[0]#.to(device).type(dtype)
        xB = batch[1]#.to(device).type(dtype)
        filename = batch[2]        
        filename = filename[0]
        #print(type(filename[0]))
        #calc all the required outputs
        rec_B, rec_alpha_B, rec_beta_B = netG_A0(xA)

        xch = torch.cat([rec_B, rec_alpha_B, rec_beta_B, xA], dim=1)
        rec_B, rec_alpha_B, rec_beta_B = netG_A1(xch)

        xch = torch.cat([rec_B, rec_alpha_B, rec_beta_B, xA], dim=1)
        rec_B, rec_alpha_B, rec_beta_B = netG_A2(xch)

        #print(type(rec_B))
        #print(rec_B)
        save_image(rec_B, os.path.join(path_save_image_result, filename[:-3]+'png'))
        # rec_B.detach()


