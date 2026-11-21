#!/usr/bin/env python3
"""Class-select navigation for PyBoy boots.

Class IDs stay 0=Wolfkin, 1=Sauran, 2=Corvin, 3=Picsean, 4=Vespine.
The class-select cursor now starts on Picsean (CLASS_SELECT_DEFAULT in
src/game/class_select.h). Do not use `for _ in range(class_id)` downs;
that only worked when the cursor started at Wolfkin (0).
"""

DEFAULT_CLASS_ID = 3  # Picsean; must match CLASS_SELECT_DEFAULT
N_CLASSES = 5


def downs_to_class(class_id, default=DEFAULT_CLASS_ID, n=N_CLASSES):
    """How many Down presses move the default cursor onto class_id."""
    return (int(class_id) - int(default)) % int(n)
