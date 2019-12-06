import torch
import torch.nn as nn
import torch.nn.functional as F
import math
import numpy as np

norm_mean, norm_var = 0.0, 1.0

class DenseBasicBlock(nn.Module):
    def __init__(self, inplanes, filters, index, expansion=1, growthRate=12, dropRate=0):
        super(DenseBasicBlock, self).__init__()
        planes = expansion * growthRate

        self.bn1 = nn.BatchNorm2d(inplanes)
        self.conv1 = nn.Conv2d(filters, growthRate, kernel_size=3,
                               padding=1, bias=False)
        self.relu = nn.ReLU(inplace=True)
        self.dropRate = dropRate

    def forward(self, x):
        out = self.bn1(x)
        out = self.relu(out)
        out = self.conv1(out)
        if self.dropRate > 0:
            out = F.dropout(out, p=self.dropRate, training=self.training)

        out = torch.cat((x, out), 1)

        return out

class Transition(nn.Module):
    def __init__(self, inplanes, outplanes, filters, index):
        super(Transition, self).__init__()
        self.bn1 = nn.BatchNorm2d(inplanes)
        self.conv1 = nn.Conv2d(filters, outplanes, kernel_size=1,
                               bias=False)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        out = self.bn1(x)
        out = self.relu(out)
        out = self.conv1(out)
        out = F.avg_pool2d(out, 2)
        return out

class DenseNet(nn.Module):

    def __init__(self, depth=40, block=DenseBasicBlock,
        dropRate=0, num_classes=10, growthRate=12, compressionRate=2, filters=None, sketch_rate=None, indexes=None):
        super(DenseNet, self).__init__()

        assert (depth - 4) % 3 == 0, 'depth should be 3n+4'
        n = (depth - 4) // 3 if 'DenseBasicBlock' in str(block) else (depth - 4) // 6

        if sketch_rate is None:
            self.sketch_rate = [1] * 3
        else:
            self.sketch_rate = sketch_rate

        if filters == None:
            filters = []
            start = growthRate*2
            for i in range(3):
                filters.append([start + int(growthRate * self.sketch_rate[i]) * j for j in range(n+1)])
                start = (start + int(growthRate * self.sketch_rate[i]) * n) // compressionRate
            filters = [item for sub_list in filters for item in sub_list]

            indexes = []
            for f in filters:
                indexes.append(np.arange(f))

        self.growthRate = growthRate
        self.dropRate = dropRate

        self.inplanes = growthRate * 2
        self.conv1 = nn.Conv2d(3, self.inplanes, kernel_size=3, padding=1,
                               bias=False)
        self.growthRate = int(growthRate * self.sketch_rate[0])
        self.dense1 = self._make_denseblock(block, n, filters[0:n], indexes[0:n])
        self.trans1 = self._make_transition(Transition, compressionRate, filters[n], indexes[n])
        self.growthRate = int(growthRate * self.sketch_rate[1])
        self.dense2 = self._make_denseblock(block, n, filters[n+1:2*n+1], indexes[n+1:2*n+1])
        self.trans2 = self._make_transition(Transition, compressionRate, filters[2*n+1], indexes[2*n+1])
        self.growthRate = int(growthRate * self.sketch_rate[2])
        self.dense3 = self._make_denseblock(block, n, filters[2*n+2:3*n+2], indexes[2*n+2:3*n+2])
        self.bn = nn.BatchNorm2d(self.inplanes)
        self.relu = nn.ReLU(inplace=True)
        self.avgpool = nn.AvgPool2d(8)
        self.fc = nn.Linear(self.inplanes, num_classes)

        # Weight initialization
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_denseblock(self, block, blocks, filters, indexes):
        layers = []
        assert blocks == len(filters), 'Length of the filters parameter is not right.'
        assert blocks == len(indexes), 'Length of the indexes parameter is not right.'
        for i in range(blocks):
            # print("denseblock inplanes", filters[i])
            layers.append(block(self.inplanes, filters=filters[i], index=indexes[i], growthRate=self.growthRate, dropRate=self.dropRate))
            self.inplanes += self.growthRate

        return nn.Sequential(*layers)

    def _make_transition(self, transition, compressionRate, filters, index):
        inplanes = self.inplanes
        outplanes = int(math.floor(self.inplanes // compressionRate))
        self.inplanes = outplanes
        return transition(inplanes, outplanes, filters, index)


    def forward(self, x):
        x = self.conv1(x)

        x = self.dense1(x)
        x = self.trans1(x)
        x = self.dense2(x)
        x = self.trans2(x)
        x = self.dense3(x)
        x = self.bn(x)
        x = self.relu(x)

        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)

        return x

def densenet_40(sketch_rate=None, **kwargs):
    return DenseNet(depth=40, block=DenseBasicBlock, compressionRate=1, sketch_rate=sketch_rate, **kwargs)

def test():
    sketch_rate = [0.5, 0.6, 0.4]
    model = densenet_40(sketch_rate=sketch_rate)
    # ckpt = torch.load('../checkpoint/densenet_40.pt', map_location='cpu')
    # model.load_state_dict(ckpt['state_dict'])
    # y = model(torch.randn(1, 3, 32, 32))
    # print(y.size())
    print(model)
    # for k, v in model.state_dict().items():
    #     print(k, v.size())

    # for name, module in model.named_modules():
    #     if isinstance(module, DenseBasicBlock):
    #         print(name)

# test()