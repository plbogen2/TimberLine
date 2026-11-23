"""Lightweight mock of adsk.core and adsk.fusion for offline unit testing."""

import sys
import types
from unittest.mock import MagicMock


def install_adsk_mocks():
    """Install minimal adsk.core and adsk.fusion stubs into sys.modules."""
    if "adsk" in sys.modules:
        return

    adsk_pkg = types.ModuleType("adsk")
    core_mod = types.ModuleType("adsk.core")
    fusion_mod = types.ModuleType("adsk.fusion")

    class _BaseHandler:
        def __init__(self):
            pass

    class _Event:
        def __init__(self):
            self.handlers = []

        def add(self, h):
            self.handlers.append(h)

    class _Point3D:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x, self.y, self.z = x, y, z

        @classmethod
        def create(cls, x=0.0, y=0.0, z=0.0):
            return cls(x, y, z)

    class _Matrix3D:
        @classmethod
        def create(cls):
            return cls()

    class _ValueInput:
        @classmethod
        def createByReal(cls, v):
            return ("real", v)

        @classmethod
        def createByString(cls, s):
            return ("str", s)

    class _Castable:
        @classmethod
        def cast(cls, obj):
            return obj

    core_mod.CommandEventHandler = _BaseHandler
    core_mod.CommandCreatedEventHandler = _BaseHandler
    core_mod.InputChangedEventHandler = _BaseHandler
    core_mod.ValidateInputsEventHandler = _BaseHandler
    core_mod.Point3D = _Point3D
    core_mod.Matrix3D = _Matrix3D
    core_mod.ValueInput = _ValueInput
    core_mod.DropDownCommandInput = _Castable
    core_mod.ValueCommandInput = _Castable
    core_mod.BoolValueCommandInput = _Castable
    core_mod.SelectionCommandInput = _Castable
    core_mod.IntegerSpinnerCommandInput = _Castable
    core_mod.TextBoxCommandInput = _Castable
    core_mod.DropDownStyles = types.SimpleNamespace(TextListDropDownStyle=0)
    core_mod.DialogResults = types.SimpleNamespace(DialogOK=1)
    core_mod.ObjectCollection = types.SimpleNamespace(create=lambda: MagicMock())
    core_mod.Application = MagicMock()
    core_mod.UserInterface = MagicMock
    core_mod.CommandInputs = MagicMock
    core_mod.CommandEventArgs = _Castable
    core_mod.CommandCreatedEventArgs = _Castable
    core_mod.InputChangedEventArgs = _Castable
    core_mod.ValidateInputsEventArgs = _Castable

    fusion_mod.Design = _Castable
    fusion_mod.BRepFace = _Castable
    fusion_mod.BRepEdge = _Castable
    fusion_mod.Component = MagicMock
    fusion_mod.Sketch = MagicMock
    fusion_mod.ExtrudeFeature = MagicMock
    fusion_mod.FeatureOperations = types.SimpleNamespace(
        NewBodyFeatureOperation=0, CutFeatureOperation=1
    )

    adsk_pkg.core = core_mod
    adsk_pkg.fusion = fusion_mod
    sys.modules["adsk"] = adsk_pkg
    sys.modules["adsk.core"] = core_mod
    sys.modules["adsk.fusion"] = fusion_mod
