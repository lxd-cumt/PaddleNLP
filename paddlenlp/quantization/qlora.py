# Copyright (c) 2023 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import paddle
from paddleslim.lc.quantizers.quant_func import dequantize_8bit, quantize_8bit
from paddleslim_ops import dequant_blockwise, quant_blockwise


def qlora_weight_quantize(
    weight, quant_type="nf4", double_quant=False, block_size=64, double_quant_block_size=256, linear_name=None
):
    quant_weight, quant_scale = quant_blockwise(weight, None, blocksize=block_size, quant_type=quant_type)
    if double_quant:
        quant_sacle_offset = quant_scale.mean()
        quant_scale -= quant_sacle_offset
        qquant_scale, double_quant_scale = quantize_8bit(
            quant_scale, None, double_quant_block_size, quant_type="dynamic_fp8"
        )
        qquant_scale_name = f"{linear_name}.qquant_scale" if linear_name else "qquant_scale"
        double_quant_scale_name = f"{linear_name}.double_quant_scale" if linear_name else "double_quant_scale"
        quant_sacle_offset_name = f"{linear_name}.quant_sacle_offset" if linear_name else "quant_sacle_offset"
        qlora_state_dict = {
            qquant_scale_name: qquant_scale,
            double_quant_scale_name: double_quant_scale,
            quant_sacle_offset_name: quant_sacle_offset,
        }
    else:
        quant_scale_name = f"{linear_name}.quant_scale" if linear_name else "quant_scale"
        qlora_state_dict = {quant_scale_name: quant_scale}
    quant_weight_name = f"{linear_name}.quant_weight" if linear_name else "quant_weight"
    if quant_type in ["nf4", "fp4"]:
        qlora_state_dict[quant_weight_name] = quant_weight.reshape([weight.shape[1] // 2, weight.shape[0]])
    return qlora_state_dict


def qlora_weight_dequantize(x, quant_type, state, double_quant=False, block_size=64, double_quant_block_size=256):
    if double_quant:
        qquant_scale, double_quant_scale, quant_sacle_offset = state
        quant_scale = dequantize_8bit(
            qquant_scale, None, double_quant_scale, double_quant_block_size, quant_type="dynamic_fp8"
        )
        quant_scale += quant_sacle_offset
    else:
        quant_scale = state

    out = dequant_blockwise(x, None, quant_scale, blocksize=block_size, quant_type=quant_type)
    return out


def qlora_weight_linear(
    x, weight, algo, state, double_quant=False, block_size=64, double_quant_block_size=256, bias=None
):
    weight = (
        qlora_weight_dequantize(weight, algo, state, double_quant, block_size, double_quant_block_size)
        .cast(x.dtype)
        .reshape((x.shape[-1], -1))
    )
    out = paddle.nn.functional.linear(x, weight, bias)
    return out
