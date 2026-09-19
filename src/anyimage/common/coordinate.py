"""Direction conversion between legacy UI parameters and canonical geometry."""


def canonical_direction_to_legacy(direction):
    """Encode a canonical direction as the legacy Direction parameter."""
    x, y, z = direction
    return (-x, -z, y)


def canonical_direction_to_symmetry_legacy(direction):
    """Encode a canonical direction as the symmetry legacy Direction parameter."""
    x, y, z = direction
    return (-x, -z, y)
