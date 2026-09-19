"""Socket endpoints for the node preview."""

from .flow import socket_links


def socket_position(socket, positions, sizes):
    node = socket.node
    x, y = positions[node]
    if node.bl_idname == "NodeReroute":
        return x + 8, y - 8
    return x + (sizes[node].width if socket.is_output else 0), y - sizes[node].sockets[socket]


def link_endpoints(link, positions, sizes):
    start = socket_position(link.from_socket, positions, sizes)
    x, y = socket_position(link.to_socket, positions, sizes)
    if link.to_socket.is_multi_input:
        siblings = socket_links(link.to_socket)
        y -= (siblings.index(link) - (len(siblings) - 1) / 2) * 8
    return start, (x, y)
