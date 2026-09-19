"""Compress stored ONNX weights without changing graph arithmetic."""

import numpy as np
from onnx import TensorProto, helper, numpy_helper


def compress_weights(model):
    casts = []
    for initializer in model.graph.initializer:
        if initializer.data_type != TensorProto.FLOAT:
            continue
        name = initializer.name
        values = numpy_helper.to_array(initializer)
        if not np.isfinite(values).all() or np.max(np.abs(values), initial=0) > np.finfo(np.float16).max:
            continue
        array = values.astype(np.float16)
        stored_name = name + "__fp16_storage"
        initializer.CopyFrom(numpy_helper.from_array(array, stored_name))
        casts.append(helper.make_node(
            "Cast", [stored_name], [name], to=TensorProto.FLOAT,
            name=stored_name + "_restore",
        ))
    nodes = list(model.graph.node)
    del model.graph.node[:]
    model.graph.node.extend(casts + nodes)


def compress_exact_constants(model):
    """Compress only constant tensors that round-trip without any value change."""
    nodes = []
    for node in model.graph.node:
        nodes.append(node)
        if node.op_type != "Constant":
            continue
        attribute = next((item for item in node.attribute if item.name == "value"), None)
        if attribute is None or attribute.t.data_type != TensorProto.FLOAT:
            continue
        values = numpy_helper.to_array(attribute.t)
        if not np.isfinite(values).all() or np.max(np.abs(values), initial=0) > np.finfo(np.float16).max:
            continue
        stored = values.astype(np.float16)
        if values.nbytes < 64 or not np.array_equal(values, stored.astype(np.float32)):
            continue
        name = node.output[0]
        node.output[0] = name + "__fp16_constant"
        attribute.t.CopyFrom(numpy_helper.from_array(stored))
        nodes.append(helper.make_node("Cast", [node.output[0]], [name], to=TensorProto.FLOAT))
    del model.graph.node[:]
    model.graph.node.extend(nodes)
