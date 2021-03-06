import os
import os.path as osp
import sys
import google.protobuf as pb
import google.protobuf.text_format as text_format
from argparse import ArgumentParser

CAFFE_ROOT = osp.join(osp.dirname(__file__), '../build/install/')
if osp.join(CAFFE_ROOT, 'python') not in sys.path:
    sys.path.insert(0, osp.join(CAFFE_ROOT, 'python'))
import caffe
from caffe.proto import caffe_pb2

def _get_param(num_param, lr_mult):
    if num_param == 1:
        # only weight
        param = caffe_pb2.ParamSpec()
        param.lr_mult = lr_mult
        param.decay_mult = 0
        return [param]
    elif num_param == 2:
        # weight and bias
        param_w = caffe_pb2.ParamSpec()
        param_w.lr_mult = lr_mult
        param_w.decay_mult = 0
        param_b = caffe_pb2.ParamSpec()
        param_b.lr_mult = lr_mult
        param_b.decay_mult = 0
        return [param_w, param_b]
    else:
        raise ValueError("Unknown num_param {}".format(num_param))

def _get_primal_dual_param(param_name, lr_mult):
    param = caffe_pb2.ParamSpec()
    param.lr_mult = lr_mult
    param.decay_mult = 0
    param.name = param_name
    return [param]
   


def OctInput(name, top, batch_size, source, num_classes, preload_data):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctInput'
    layer.top.extend([top])

    layer.oct_input_param.batch_size = batch_size
    layer.oct_input_param.source = source
    layer.oct_input_param.num_classes = num_classes
    layer.oct_input_param.preload_data = preload_data
   
    return layer

def OctSingleChannelInput(name, top, batch_size, source, preload_data):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctSingleChannelInput'
    layer.top.extend([top])

    layer.oct_input_param.batch_size = batch_size
    layer.oct_input_param.source = source
    layer.oct_input_param.preload_data = preload_data
   
    return layer


def OctInputPrimalDual(name, tops, batch_size, height, width, depth, num_classes, nbh_size):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctInputPrimalDual'
    layer.top.extend(tops)

    layer.oct_input_primal_dual_param.batch_size = batch_size
    layer.oct_input_primal_dual_param.height = height
    layer.oct_input_primal_dual_param.width = width
    layer.oct_input_primal_dual_param.depth = depth
    layer.oct_input_primal_dual_param.num_classes = num_classes
    layer.oct_input_primal_dual_param.nbh_size = nbh_size
   
    return layer

def Scaling(name, bottom, scale):
    layer = caffe_pb2.LayerParameter()
    layer.type = 'Scaling'
    layer.name = name
    layer.scaling_param.scale = scale
    layer.bottom.extend([bottom])
    layer.top.extend([name])

    return layer

def OctLevelSampling(name, bottoms, input_key_layer, ref_key_layer, input_max_level):
    layer = caffe_pb2.LayerParameter()
    layer.type = 'OctLevelSampling'
    layer.name = name;
    layer.bottom.extend(bottoms);
    layer.top.extend([name]);
    layer.oct_level_sampling_param.input_key_layer = input_key_layer
    layer.oct_level_sampling_param.ref_key_layer = ref_key_layer
    layer.oct_level_sampling_param.input_max_level = input_max_level

    return layer

def OctConv(name, bottoms, output_channels, filter_size, w_std, w_lr_mult):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctConv'
    layer.bottom.extend(bottoms)
    layer.top.extend([name])
    layer.oct_conv_param.output_channels = output_channels
    layer.oct_conv_param.filter_size = filter_size
    layer.oct_conv_param.weight_filler.type = 'gaussian'
    layer.oct_conv_param.weight_filler.std = w_std
    layer.oct_conv_param.bias_filler.type = 'constant'

    layer.param.extend(_get_param(2, w_lr_mult))
 

    return layer

def Relu(name, bottom):
    layer = caffe_pb2.LayerParameter()
    layer.name = name + '_relu'
    layer.type = 'ReLU'
    layer.bottom.extend([bottom])
    layer.top.extend([name])
    layer.relu_param.engine = caffe_pb2.ReLUParameter.CAFFE
    return layer


def Add(name, bottoms):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'Eltwise'
    layer.eltwise_param.operation = caffe_pb2.EltwiseParameter.SUM
    layer.bottom.extend(bottoms)
    layer.top.extend([name])

    return layer


def Softmax(name, bottom):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'Softmax'
    layer.bottom.extend([bottom])
    layer.top.extend([name])
    layer.softmax_param.axis = 1

    return layer

def Sigmoid(name, bottom):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'Sigmoid'
    layer.bottom.extend([bottom])
    layer.top.extend([name])
    layer.sigmoid_param.engine = caffe_pb2.ReLUParameter.CAFFE

    return layer



def OctDatacostEncoding(level, bottoms, nbh_bottoms, input_key_layer, ref_key_layer, input_max_level,
                            conv_output_channels, conv_filter_size, conv_w_std, conv_w_lr_mult):
    conv_bottoms = []
    layers = []
   
    layers.append(OctLevelSampling('datacost_prep{}'.format(level), bottoms,
                                    input_key_layer, ref_key_layer, input_max_level))

    conv_bottoms.append('datacost_prep{}'.format(level))
    conv_bottoms.extend(nbh_bottoms)
    layers.append(OctConv('conv0_l{}'.format(level), conv_bottoms, conv_output_channels, conv_filter_size, conv_w_std, conv_w_lr_mult))
    layers.append(Relu('conv0_l{}'.format(level), 'conv0_l{}'.format(level)))

    conv_bottoms[0] = 'conv0_l{}'.format(level)
    layers.append(OctConv('conv1_l{}'.format(level), conv_bottoms, conv_output_channels, conv_filter_size, conv_w_std, conv_w_lr_mult))
    layers.append(Relu('conv1_l{}'.format(level), 'conv1_l{}'.format(level)))

    conv_bottoms[0] = 'conv1_l{}'.format(level)
    layers.append(OctConv('conv2_l{}'.format(level), conv_bottoms, conv_output_channels, conv_filter_size, conv_w_std, conv_w_lr_mult))

    layers.append(Add('datacost_adding{}'.format(level), ['datacost_prep{}'.format(level), 'conv2_l{}'.format(level)]))

    return layers


def OctProbDecoding(level, bottom, nbh_bottoms, conv_output_channels, conv_filter_size,
                          conv_w_std, conv_w_lr_mult, softmax_scale):
    conv_bottoms = []
    layers = []
    
    conv_bottoms.append(bottom)
    conv_bottoms.extend(nbh_bottoms)
    layers.append(OctConv('conv3_l{}'.format(level), conv_bottoms, conv_output_channels, conv_filter_size, conv_w_std, conv_w_lr_mult))
    layers.append(Relu('conv3_l{}'.format(level), 'conv3_l{}'.format(level)))

    conv_bottoms[0] = 'conv3_l{}'.format(level)
    layers.append(OctConv('conv4_l{}'.format(level), conv_bottoms, conv_output_channels, conv_filter_size, conv_w_std, conv_w_lr_mult))
    layers.append(Relu('conv4_l{}'.format(level), 'conv4_l{}'.format(level)))

    conv_bottoms[0] = 'conv4_l{}'.format(level)
    layers.append(OctConv('conv5_l{}'.format(level), conv_bottoms, conv_output_channels, conv_filter_size, conv_w_std, conv_w_lr_mult))

    layers.append(Scaling('u_scaling{}'.format(level), bottom, softmax_scale))

    layers.append(Add('u_adding{}'.format(level), ['u_scaling{}'.format(level), 'conv5_l{}'.format(level)]))
    layers.append(Softmax('seg_prob{}'.format(level), 'u_adding{}'.format(level)))
   

    return layers


# def PropProbConv(name, bottoms, filter_size, w_std, w_lr_mult):
#     layer = caffe_pb2.LayerParameter()
#     layer.name = name
#     layer.type = 'OctConv'
#     layer.bottom.extend(bottoms)
#     layer.top.extend([name])
#     layer.oct_conv_param.output_channels = 1
#     layer.oct_conv_param.filter_size = filter_size
#     layer.oct_conv_param.weight_filler.type = 'gaussian'
#     layer.oct_conv_param.weight_filler.std = w_std
#     layer.oct_conv_param.bias_filler.type = 'constant'

#     layer.param.extend(_get_param(2, w_lr_mult))
    

#     return layer

def Conv(name, bottom, w_std, w_lr_mult):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'Convolution'
    layer.bottom.extend([bottom])
    layer.top.extend([name])
    layer.convolution_param.num_output = 1
    layer.convolution_param.kernel_size.extend([1])
    layer.convolution_param.stride.extend([1])
    layer.convolution_param.weight_filler.type = 'gaussian'
    layer.convolution_param.weight_filler.std = w_std
    layer.convolution_param.bias_filler.type = 'constant'
    layer.convolution_param.engine = caffe_pb2.ConvolutionParameter.CAFFE
    layer.param.extend(_get_param(2, w_lr_mult))

    return layer

def PropProbConvBlock(level, bottoms, output_channels, filter_size, w_std, w_lr_mult):

    layers = []
    layers.append(OctConv('prop_prob{}_temp'.format(level), bottoms, output_channels, filter_size, w_std, w_lr_mult))
    layers.append(Relu('prop_prob{}_temp'.format(level), 'prop_prob{}_temp'.format(level)))
    layers.append(Conv('prop_prob{}'.format(level), 'prop_prob{}_temp'.format(level), w_std, w_lr_mult))
    return layers


def OctProp(name,tops, bottoms, key_layer, prop_mode):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.bottom.extend(bottoms)
    layer.top.extend(tops)
    layer.type = 'OctProp'
    layer.oct_prop_param.key_layer = key_layer

    if (prop_mode == "known"):
        layer.oct_prop_param.prop_mode = caffe_pb2.OctPropParameter.PROP_KNOWN
    elif(prop_mode == "pred"):
        layer.oct_prop_param.prop_mode = caffe_pb2.OctPropParameter.PROP_PRED

    return layer

def OctUpSampling(name, tops, bottoms, key_layer, nbh_size):

    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctUpSampling'
    layer.bottom.extend(bottoms)
    layer.top.extend(tops)

    layer.oct_upsampling_param.key_layer = key_layer
    layer.oct_upsampling_param.nbh_size = nbh_size

    return layer



def OctDualUpdate(name, top, bottoms, w_lr_mult, param_name, output_channels, filter_size, w_std, sigma):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctDualUpdate'
    layer.top.extend([top])
    layer.bottom.extend(bottoms)
    layer.param.extend(_get_primal_dual_param(param_name, w_lr_mult))


    layer.oct_dual_update_param.output_channels = output_channels
    layer.oct_dual_update_param.filter_size = filter_size
    layer.oct_dual_update_param.weight_filler.type = 'gaussian'
    layer.oct_dual_update_param.weight_filler.std = w_std
    layer.oct_dual_update_param.sigma = sigma
   
    
    return layer

def OctPrimalUpdate(name, top, bottoms, w_lr_mult, param_name, output_channels, filter_size, w_std, tau):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctPrimalUpdate'
    layer.top.extend([top])
    layer.bottom.extend(bottoms)
    layer.param.extend(_get_primal_dual_param(param_name, w_lr_mult))


    layer.oct_primal_update_param.output_channels = output_channels
    layer.oct_primal_update_param.filter_size = filter_size
    layer.oct_primal_update_param.weight_filler.type = 'gaussian'
    layer.oct_primal_update_param.weight_filler.std = w_std
    layer.oct_primal_update_param.tau = tau

    return layer

def OctLagrangianUpdate(name, top, bottoms, sigma):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctLagrangianUpdate'
    layer.top.extend([top])
    layer.bottom.extend(bottoms)
    layer.lagrangian_update_param.sigma = sigma

    
    return layer

def OctPrimalFurtherUpdate(name, top, bottoms):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctPrimalFurtherUpdate'
    layer.bottom.extend(bottoms)
    layer.top.extend([top])
    
    return layer

def OctPrimalDualUpdate(level, iter, bottoms, w_lr_mult, w_std, num_classes, filter_size, tau, sigma, nlevels, num_iters):
    layers = []

    dual_bottoms = []
    dual_bottoms.extend([bottoms[2]])
    dual_bottoms.extend([bottoms[1]])
    dual_bottoms.extend([bottoms[5]])
    dual_bottoms.extend([bottoms[6]])
    dual_bottoms.extend([bottoms[7]])
    layers.append(OctDualUpdate('dual_update_{}_{}'.format(level, iter), 'm_{}_{}'.format(level, iter), dual_bottoms, w_lr_mult, 
                             'primal_dual_weight{}'.format(level), num_classes*3, filter_size, w_std, sigma))

    lag_bottoms = []
    lag_bottoms.extend([bottoms[3]])
    lag_bottoms.extend([bottoms[1]])
    layers.append(OctLagrangianUpdate('lagrangian_update_{}_{}'.format(level, iter), 'l_{}_{}'.format(level, iter), lag_bottoms, sigma))

    primal_bottoms = []
    primal_bottoms.extend([bottoms[0]])
    primal_bottoms.extend(['m_{}_{}'.format(level, iter)])
    primal_bottoms.extend(['l_{}_{}'.format(level, iter)])
    primal_bottoms.extend([bottoms[4]])
    primal_bottoms.extend([bottoms[5]])
    primal_bottoms.extend([bottoms[6]])
    primal_bottoms.extend([bottoms[7]])

    layers.append(OctPrimalUpdate('primal_update_{}_{}'.format(level, iter), 'u_{}_{}'.format(level, iter), primal_bottoms, w_lr_mult, 
                            'primal_dual_weight{}'.format(level), num_classes, filter_size, w_std, tau))

    
    if (iter == num_iters-1 and level == nlevels-1):
        return layers

    primal_further_bottoms = []
    primal_further_bottoms.extend(['u_{}_{}'.format(level, iter)])
    primal_further_bottoms.extend([bottoms[0]])
    layers.append(OctPrimalFurtherUpdate('primal_further_update_{}_{}'.format(level, iter), 'u_{}_{}_'.format(level, iter), 
                                    primal_further_bottoms))

    return layers

def OctPrimalDualUpdateUnrolled(level, variable_bottoms, variable_key_layer, datacost_bottom, datacost_key_layer, 
                                datacost_max_level, num_classes, encoding_filter_size, encoding_w_std, encoding_lr_mult,
                                update_lr_mult, update_w_std, update_filter_size, tau, sigma, nlevels, num_iters):

    layers = []

    layers.extend(OctDatacostEncoding(level, [datacost_bottom, variable_bottoms[0]], variable_bottoms[4:], datacost_key_layer, variable_key_layer,
                                        datacost_max_level, num_classes, encoding_filter_size, encoding_w_std, encoding_lr_mult))

    primal_dual_bottoms = []
    primal_dual_bottoms.extend(variable_bottoms[:4])
    primal_dual_bottoms.append('datacost_adding{}'.format(level))
    primal_dual_bottoms.extend(variable_bottoms[4:])


    for iter in range(num_iters):
        
        layers.extend(OctPrimalDualUpdate(level, iter, primal_dual_bottoms, update_lr_mult, update_w_std,
                        num_classes, update_filter_size, tau, sigma, nlevels, num_iters))

        primal_dual_bottoms = []
        primal_dual_bottoms.append('u_{}_{}'.format(level, iter))
        primal_dual_bottoms.append('u_{}_{}_'.format(level, iter))
        primal_dual_bottoms.append('m_{}_{}'.format(level, iter))
        primal_dual_bottoms.append('l_{}_{}'.format(level, iter))
        primal_dual_bottoms.append('datacost_adding{}'.format(level)) 
        primal_dual_bottoms.extend(variable_bottoms[4:])

    return layers
def OctPrimalDualUpdateFull(init_variable_bottoms, init_variable_key_layer, datacost_bottom, datacost_key_layer, 
                                input_max_level, num_classes, encoding_filter_size, encoding_w_std, encoding_lr_mult, 
                                update_lr_mult, update_w_std, update_filter_size, tau, sigma, 
                                decoding_filter_size, decoding_w_std, decoding_lr_mult, softmax_scale, 
                                nlevels, num_iters):
    
    variable_bottoms = []
    variable_bottoms.extend(init_variable_bottoms)
    variable_key_layer = init_variable_key_layer

    layers = []
    for level in range(nlevels):
        if level > 0:
            
            prop_prob_conv_bottoms = []
            prop_prob_conv_bottoms.append('seg_prob{}'.format(level-1));
            prop_prob_conv_bottoms.extend(variable_bottoms[4:])
            layers.extend(PropProbConvBlock(level-1, prop_prob_conv_bottoms, 96, decoding_filter_size, decoding_w_std, decoding_lr_mult))
            layers.append(Sigmoid('prop_prob{}_sig'.format(level-1),'prop_prob{}'.format(level-1)))
            prop_tops = []
            prop_tops.append('u_prop{}'.format(level-1))
            prop_tops.append('u_prop{}_'.format(level-1))
            prop_tops.append('m_prop{}'.format(level-1))
            prop_tops.append('l_prop{}'.format(level-1))

            prop_bottoms = []
            prop_bottoms.append('u_{}_{}'.format(level-1, num_iters[level-1]-1))
            prop_bottoms.append('u_{}_{}_'.format(level-1, num_iters[level-1]-1))
            prop_bottoms.append('m_{}_{}'.format(level-1, num_iters[level-1]-1))
            prop_bottoms.append('l_{}_{}'.format(level-1, num_iters[level-1]-1))
            prop_bottoms.append('prop_prob{}_sig'.format(level-1))

            layers.append(OctProp('prop{}'.format(level-1), prop_tops, prop_bottoms, variable_key_layer, 'pred'))
        

            variable_bottoms = []
            variable_bottoms.append('u_upsampling{}'.format(level-1))
            variable_bottoms.append('u_upsampling{}_'.format(level-1))
            variable_bottoms.append('m_upsampling{}'.format(level-1))
            variable_bottoms.append('l_upsampling{}'.format(level-1))
            variable_bottoms.append('num_upsampling{}'.format(level-1))
            variable_bottoms.append('nbh_upsampling{}'.format(level-1))
            variable_bottoms.append('nbh_of_upsampling{}'.format(level-1))
            layers.append(OctUpSampling('up_sampling{}'.format(level-1), variable_bottoms, prop_tops, 'prop{}'.format(level-1), update_filter_size))
    
            variable_key_layer = 'up_sampling{}'.format(level-1)


        layers.extend(OctPrimalDualUpdateUnrolled(level, variable_bottoms, variable_key_layer, datacost_bottom, datacost_key_layer,
                                                    input_max_level, num_classes, encoding_filter_size, encoding_w_std, encoding_lr_mult, 
                                                    update_lr_mult, update_w_std, update_filter_size, tau, sigma, nlevels, num_iters[level]))

        layers.extend(OctProbDecoding(level, 'u_{}_{}'.format(level, num_iters[level]-1), variable_bottoms[4:], num_classes, decoding_filter_size, decoding_w_std, 
                        decoding_lr_mult, softmax_scale))

        

    return layers

def OctOutput(name, top, bottoms, min_level, key_layers, prop_mode):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctOutput'
    layer.bottom.extend(bottoms)
    layer.top.extend([top])
    layer.oct_output_param.min_level = min_level
    layer.oct_output_param.key_layer.extend(key_layers)
    if (prop_mode == "known"):
        layer.oct_output_param.prop_mode = caffe_pb2.OctOutputParameter.PROP_KNOWN
    elif(prop_mode == "pred"):
        layer.oct_output_param.prop_mode = caffe_pb2.OctOutputParameter.PROP_PRED

    return layer

def OctSegAccuracy(name, tops, bottoms, gt_key_layer, pr_key_layer, max_level, freespace_label, unknown_label, ignore_seg_label):
    layer = caffe_pb2.LayerParameter()
    layer.name = name
    layer.type = 'OctSegAccuracy'
    layer.bottom.extend(bottoms)
    layer.top.extend(tops)
    layer.oct_accuracy_3dreconstruction_param.gt_key_layer = gt_key_layer
    layer.oct_accuracy_3dreconstruction_param.pr_key_layer = pr_key_layer
    layer.oct_accuracy_3dreconstruction_param.max_level = max_level
    layer.oct_accuracy_3dreconstruction_param.freespace_label = freespace_label
    layer.oct_accuracy_3dreconstruction_param.unknown_label = unknown_label
    layer.oct_accuracy_3dreconstruction_param.ignore_label = ignore_seg_label  

    return layer


def create_model(batch_size, num_classes, test_data_list_file, test_groundtruth_list_file, preload_data, 
                max_level, nlevels, niter_l0, niter_l1, niter_l2, sigma, tau, lam, softmax_scale, 
                freespace_label, unknown_label, ignore_seg_label):

    model = caffe_pb2.NetParameter()
    model.name = 'prop_known_levels_{}_iters_{}_{}_{}'.format(nlevels, niter_l0, niter_l1, niter_l2)
    layers = []

    ## input layer
    input_size = 2**max_level
    min_level = max_level-nlevels+1
    coarse_res = 2** min_level
    nbh_size = 3
    
    layers.append(OctInput('input_datacost', 'datacost', batch_size, test_data_list_file, num_classes, preload_data))
    layers.append(OctSingleChannelInput('input_gt', 'gt', batch_size, test_groundtruth_list_file, preload_data))
    layers.append(OctInputPrimalDual('init_variable', ['u', 'u_', 'm', 'l', 'num', 'nbh', 'nbh_of'], batch_size, 
                                coarse_res, coarse_res, coarse_res, num_classes, nbh_size))



    ## main network
    layers.append(Scaling('datacost_lam', 'datacost', lam))
    encoding_filter_size = nbh_size
    encoding_w_std = 0.01 * lam
    encoding_lr_mult = 1
    update_filter_size = nbh_size
    update_w_std = 0.001
    update_lr_mult = 1
    decoding_filter_size = nbh_size
    decoding_w_std = 0.01*softmax_scale
    decoding_lr_mult = encoding_lr_mult
    num_iters = [niter_l0, niter_l1, niter_l2]
    layers.extend(OctPrimalDualUpdateFull(['u', 'u_', 'm', 'l', 'num', 'nbh', 'nbh_of'], 'init_variable', 'datacost_lam', 'input_datacost', max_level, num_classes, 
                                        encoding_filter_size, encoding_w_std, encoding_lr_mult, 
                                        update_lr_mult, update_w_std, update_filter_size, tau, sigma, 
                                        decoding_filter_size, decoding_w_std, decoding_lr_mult, softmax_scale, 
                                        nlevels, num_iters))


    ## for evaluation
    oct_output_bottoms = []
    for level in range(nlevels-1):
        oct_output_bottoms.append('seg_prob{}'.format(level))
        oct_output_bottoms.append('prop_prob{}_sig'.format(level))

    oct_output_bottoms.append('seg_prob{}'.format(nlevels-1))

    key_layers = ['init_variable']
    for level in range(nlevels-1):
        key_layers.append('up_sampling{}'.format(level))


    layers.append(OctOutput('output_pred', 'pred', oct_output_bottoms, min_level, key_layers, 'pred'))
    layers.append(OctSegAccuracy('accuracy', ['freespace_accuracy', 'semantic_accuracy', 'overall_accuracy'], ['gt', 'pred'],
        'input_gt', 'output_pred', max_level, freespace_label, unknown_label, ignore_seg_label))


    model.layer.extend(layers)
    return model


def main(args):
    model = create_model(args.batch_size, args.num_classes, args.test_data_list_file, args.test_groundtruth_list_file, args.preload_data, 
                        args.max_level, args.nlevels, args.niter_l0, args.niter_l1, args.niter_l2, args.sig, args.tau, args.lam, args.softmax_scale,
                        args.freespace_label, args.unknown_label, args.ignore_seg_label)

    if args.output is None:
        args.output = osp.join(osp.dirname(__file__),
            'test_prop_conv_block_pred.prototxt')
    with open(args.output, 'w') as f:
        f.write(text_format.MessageToString(model))


if __name__ == '__main__':

    parser = ArgumentParser()

    parser.add_argument("--test_data_list_file", type=str, required=True)
    parser.add_argument("--test_groundtruth_list_file", type=str, required=True)
  
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--num_classes", type=int, default=38) 
    parser.add_argument("--max_level", type=int, default=7)
    parser.add_argument("--preload_data", type=bool, default=False)
   
    
    parser.add_argument("--nlevels", type=int, default=3)
    parser.add_argument("--niter_l0", type=int, default=50)
    parser.add_argument("--niter_l1", type=int, default=10)
    parser.add_argument("--niter_l2", type=int, default=10)
    parser.add_argument("--sig", type=float, default=0.2)
    parser.add_argument("--tau", type=float, default=0.2)
    parser.add_argument("--lam", type=float, default=1.0)
    parser.add_argument("--softmax_scale", type=float, default=10)

    
    parser.add_argument("--freespace_label", type=int, default=37)
    parser.add_argument("--unknown_label", type=int, default=36)
    parser.add_argument("--ignore_seg_label", type=int, default=35)
    
    parser.add_argument("-o", "--output", type=str)
    args = parser.parse_args()
    main(args)

