Running YoloV7 with TensorRT Engine on Jetson.
==========

This repository contains step by step guide to build and convert YoloV7 model into a TensorRT engine on Jetson. This has been tested on Jetson Nano or Jetson Xavier.

Please install Jetpack OS version 4.6 as mentioned by Nvidia and follow below steps. Please follow each steps exactly mentioned in the video links below :

Build YoloV7 TensorRT Engine on Jetson Nano: 

Object Detection YoloV7 TensorRT Engine on Jetson Nano: 

Jetson Xavier:

<img src="videos/out.jpg" width="800"/>

Install Libraries
=============
Please install below libraries::

    $ sudo apt-get update
	$ sudo apt-get install -y liblapack-dev libblas-dev gfortran libfreetype6-dev libopenblas-base libopenmpi-dev libjpeg-dev zlib1g-dev
	$ sudo apt-get install -y python3-pip
	

Install below python packages
=============
Numpy comes pre installed with Jetpack, so make sure you uninstall it first and then confirm if it's uninstalled or not. Upgrade pip3 as well and then install below packages:

    $ numpy==1.19.4
	$ pandas
	$ Pillow
	$ PyYAML
	$ scipy
	$ psutil
	$ tqdm
	$ imutils
	
If PyYAML is giving issues, run pip3 install "cython<3.0.0" && pip install --no-build-isolation pyyaml==6.0

Install PyCuda
=============
We need to first export few paths

	$ export PATH=/usr/local/cuda-10.2/bin${PATH:+:${PATH}}
	$ export LD_LIBRARY_PATH=/usr/local/cuda-10.2/lib64:$LD_LIBRARY_PATH
	$ python3 -m pip install pycuda --user

Note: I put the first 2 lines in my .bashrc


Install Seaborn
=============

    $ sudo apt install python3-seaborn
	
Install torch & torchvision
=============

	$ wget https://nvidia.box.com/shared/static/fjtbno0vpo676a25cgvuqc1wty0fkkg6.whl -O torch-1.10.0-cp36-cp36m-linux_aarch64.whl
	$ pip3 install torch-1.10.0-cp36-cp36m-linux_aarch64.whl
	$ git clone --branch v0.11.1 https://github.com/pytorch/vision torchvision
	$ cd torchvision
	$ sudo python3 setup.py install 
	
### Not required but good library
sudo python3 -m pip install -U jetson-stats==3.1.4

This marks the installation of all the required libraries.

------------------------------------------------------------------------------------------

Generate wts file from pt file
=============
Yolov7-tiny.pt is already provided in the repo. But if you want you can download any other version of the yolov7 model. Then run below command to convert .pt file into .wts file 

	$ python3 gen_wts.py -w yolov7-tiny.pt -o yolov7-tiny.wts
	
Make
=============
Create a build directory inside yolov5. Copy and paste generated wts file into build directory and run below commands. If using custom model, make sure to update kNumClas in yolov7/include/config.h

	$ cd yolov7/
	$ mkdir build
	$ cd build
	$ cp ../../yolov7-tiny.wts .
	$ cmake ..
	$ make 
	
Build Engine file 
=============

    $ sudo ./yolov7 -s yolov7-tiny.wts  yolov7-tiny.engine t
