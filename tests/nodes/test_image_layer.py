import numpy as np
import pytest


from tests.support.materials import image_layer
from nodes.groups.image_depth_layer import build_image_depth_layer_group


def test_alpha_curve_preserves_endpoints_and_suppresses_soft_edges(image_layer):
    inputs = {
        item.name: item for item in image_layer.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT"
    }
    assert list(inputs) == [
        "Color", "Alpha", "Normal", "Normal Scale", "Bump Scale",
        "Alpha Fix", "Object Space",
    ]
    output = next(node for node in image_layer.nodes if node.type == "GROUP_OUTPUT")
    curve = output.inputs["Alpha"].links[0].from_node
    assert curve.type == "CURVE_FLOAT"
    assert curve.inputs["Value"].links[0].from_socket.name == "Alpha"
    assert curve.inputs["Factor"].links[0].from_socket.name == "Alpha Fix"
    mapping = curve.mapping
    samples = np.array([
        mapping.evaluate(mapping.curves[0], float(alpha))
        for alpha in np.linspace(0, 1, 1001)
    ])
    np.testing.assert_allclose(samples[:801], 0, atol=3e-4)
    assert samples[-1] == pytest.approx(1)


def test_depth_layer_keeps_foreground_alpha_threshold(image_layer):
    depth = build_image_depth_layer_group()
    output = next(node for node in depth.nodes if node.type == "GROUP_OUTPUT")
    threshold = output.inputs["Alpha"].links[0].from_node
    assert threshold.operation == "GREATER_THAN"
    assert threshold.inputs[1].default_value == 0.5
    assert threshold.inputs[0].links[0].from_socket.name == "Alpha"
