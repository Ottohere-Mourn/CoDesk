"""No-op defense (control): the hooks run but change nothing."""
from . import DefenseBase


class Defense(DefenseBase):
    pass
