#!/usr/bin/env python
from object_recognition_capture.orb_capture import *
from ecto.opts import scheduler_options, run_plasm
from ecto_opencv.calib import PoseDrawer, DepthValidDraw, DepthTo3d
from ecto_opencv.features2d import DrawKeypoints
from ecto_opencv.highgui import imshow, FPSDrawer, MatWriter, ImageSaver
from ecto_opencv.imgproc import cvtColor, Conversion
from ecto_openni import VGA_RES, SXGA_RES, FPS_15, FPS_30
from ecto_image_pipeline.io.source import create_source
import argparse
import ecto
import os

def parse_args():
    parser = argparse.ArgumentParser(description='Computes the ORB feature and descriptor template that may be used as a fiducial marker.')
    parser.add_argument('-o,--output', dest='output', type=str,
                        help='The output directory for this template. Default: %(default)s', default='./')
    parser.add_argument('-n_features', dest='n_features', type=int,
                        help='The number of features to detect for the template.,%(default)d',
                        default=5000)    
    scheduler_options(parser.add_argument_group('Scheduler'))
    options = parser.parse_args()
    if not os.path.exists(options.output):
        os.makedirs(options.output)
    return options


options = parse_args()
plasm = ecto.Plasm()

#setup the input source, grayscale conversion
source = create_source('image_pipeline','OpenNISource',image_mode=SXGA_RES,image_fps=FPS_15)
rgb2gray = cvtColor (flag=Conversion.RGB2GRAY)
depth_to_3d = DepthTo3d()
plasm.connect(source['image'] >> rgb2gray ['image'])

#convenience variable for the grayscale
img_src = rgb2gray['image']

#display the depth
plasm.connect(source['depth'] >> imshow(name='depth')[:],
              )

#connect up the test ORB
orb = FeatureFinder('ORB test', n_features=options.n_features, n_levels=3, scale_factor=1.2)
plasm.connect(img_src >> orb['image'],
              source['depth_raw'] >> depth_to_3d['depth'],
              source['K'] >> depth_to_3d['K'],
              depth_to_3d['points3d'] >> orb['points3d'],
              source['mask_depth'] >> orb['mask']
              )


#display test ORB
draw_kpts = DrawKeypoints()
fps = FPSDrawer()
orb_display = imshow('orb display', name='ORB', triggers=dict(save=ord('s')))
depth_valid_draw = DepthValidDraw()
plasm.connect(orb['keypoints'] >> draw_kpts['keypoints'],
              source['image'] >> depth_valid_draw['image'],
              source['mask_depth'] >> depth_valid_draw['mask'],
              depth_valid_draw['image'] >> draw_kpts['image'],
              draw_kpts['image'] >> fps[:],
             )

plane_est = PlaneEstimator(radius=50)
pose_draw = PoseDrawer()
plasm.connect(source['image'] >> plane_est['image'],
              depth_to_3d['points3d'] >> plane_est['points3d'],
              plane_est['R', 'T'] >> pose_draw['R', 'T'],
              source['K'] >> pose_draw['K'],
              fps[:] >> pose_draw['image'],
              pose_draw['output'] >> orb_display['image']
              )
#training 
points3d_writer = ecto.If("Points3d writer", cell=MatWriter(filename=os.path.join(options.output, 'points3d.yaml')))
points_writer = ecto.If("Points writer", cell=MatWriter(filename=os.path.join(options.output, 'points.yaml')))
descriptor_writer = ecto.If("Descriptor writer", cell=MatWriter(filename=os.path.join(options.output, 'descriptors.yaml')))
R_writer = ecto.If("R writer", cell=MatWriter(filename=os.path.join(options.output, 'R.yaml')))
T_writer = ecto.If("T writer", cell=MatWriter(filename=os.path.join(options.output, 'T.yaml')))
image_writer = ecto.If(cell=ImageSaver(filename_param=os.path.join(options.output, 'train.png')))

for y, x in (
            (orb['points3d'], points3d_writer),
            (orb['descriptors'], descriptor_writer),
            (orb['points'], points_writer),
            (plane_est['R'], R_writer),
            (plane_est['T'], T_writer)
            ):
    plasm.connect(orb_display['save'] >> x['__test__'],
                  y >> x['mat'],
              )
plasm.connect(orb_display['save'] >> image_writer['__test__'],
              source['image'] >> image_writer['image']
              )

run_plasm(options, plasm, locals=vars())
