"""Stateful mock of adsk.core and adsk.fusion for offline unit testing."""

import re
import sys
import types
from unittest.mock import MagicMock


class FakeListItems:
    def __init__(self):
        self.items = []

    def add(self, name, is_selected=False, icon=""):
        item = types.SimpleNamespace(name=name, isSelected=is_selected, icon=icon)
        self.items.append(item)
        return item

    def clear(self):
        self.items.clear()


class FakeDropDownInput:
    def __init__(self, input_id, name):
        self.id = input_id
        self.name = name
        self.listItems = FakeListItems()
        self.isVisible = True
        self.isEnabled = True

    @property
    def selectedItem(self):
        for it in self.listItems.items:
            if it.isSelected:
                return it
        return self.listItems.items[0] if self.listItems.items else None

    def select(self, name):
        found = False
        for it in self.listItems.items:
            it.isSelected = it.name == name
            if it.isSelected:
                found = True
        if not found:
            raise ValueError(f"Dropdown {self.id} has no item {name!r}")


def _parse_expr_cm(expr: str) -> float:
    s = str(expr).strip()
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?|\d+/\d+)\s*(in|cm|mm|ft|deg)?$", s)
    if not m:
        return 0.0
    num_str, unit = m.group(1), m.group(2) or "cm"
    if "/" in num_str:
        a, b = num_str.split("/")
        val = float(a) / float(b)
    else:
        val = float(num_str)
    if unit == "in":
        return val * 2.54
    if unit == "mm":
        return val / 10.0
    if unit == "ft":
        return val * 12.0 * 2.54
    if unit == "deg":
        return val * (3.141592653589793 / 180.0)
    return val


class FakeValueInput:
    def __init__(self, input_id, name, unit_type, value_input):
        self.id = input_id
        self.name = name
        self.unitType = unit_type
        self.isVisible = True
        self._expression = ""
        self.value = 0.0
        if isinstance(value_input, tuple) and value_input[0] == "str":
            self.expression = value_input[1]
        elif isinstance(value_input, tuple) and value_input[0] == "real":
            self.value = float(value_input[1])

    @property
    def expression(self):
        return self._expression

    @expression.setter
    def expression(self, val):
        self._expression = val
        self.value = _parse_expr_cm(val)


class FakeBoolInput:
    def __init__(self, input_id, name, value=False):
        self.id = input_id
        self.name = name
        self.value = value
        self.isVisible = True


class FakeSpinnerInput:
    def __init__(self, input_id, name, value=1):
        self.id = input_id
        self.name = name
        self.value = value
        self.isVisible = True


class FakeTextBoxInput:
    def __init__(self, input_id, name, text=""):
        self.id = input_id
        self.name = name
        self.text = text
        self.isVisible = True


class FakeSelectionInput:
    def __init__(self, input_id, name, prompt=""):
        self.id = input_id
        self.name = name
        self.prompt = prompt
        self.isVisible = True
        self._entities = []

    def addSelectionFilter(self, _f):
        pass

    def setSelectionLimits(self, _mn, _mx):
        pass

    def set_entities(self, entities):
        self._entities = list(entities)

    @property
    def selectionCount(self):
        return len(self._entities)

    def selection(self, idx):
        return types.SimpleNamespace(entity=self._entities[idx])


class FakeCommandInputs:
    def __init__(self):
        self._items = {}

    def itemById(self, input_id):
        return self._items.get(input_id)

    def addDropDownCommandInput(self, input_id, name, _style):
        obj = FakeDropDownInput(input_id, name)
        self._items[input_id] = obj
        return obj

    def addValueInput(self, input_id, name, unit_type, default_val):
        obj = FakeValueInput(input_id, name, unit_type, default_val)
        self._items[input_id] = obj
        return obj

    def addBoolValueInput(self, input_id, name, _cb, _res, default_val):
        obj = FakeBoolInput(input_id, name, default_val)
        self._items[input_id] = obj
        return obj

    def addSelectionInput(self, input_id, name, prompt):
        obj = FakeSelectionInput(input_id, name, prompt)
        self._items[input_id] = obj
        return obj

    def addIntegerSpinnerCommandInput(self, input_id, name, _mn, _mx, _step, default_val):
        obj = FakeSpinnerInput(input_id, name, default_val)
        self._items[input_id] = obj
        return obj

    def addTextBoxCommandInput(self, input_id, name, text, _rows, _ro):
        obj = FakeTextBoxInput(input_id, name, text)
        self._items[input_id] = obj
        return obj


class FakeEvent:
    def __init__(self):
        self.handlers = []

    def add(self, h):
        self.handlers.append(h)


class FakeCommand:
    def __init__(self):
        self.commandInputs = FakeCommandInputs()
        self.execute = FakeEvent()
        self.executePreview = FakeEvent()
        self.inputChanged = FakeEvent()
        self.validateInputs = FakeEvent()


class FakeObjectCollection:
    def __init__(self):
        self._items = []

    @classmethod
    def create(cls):
        return cls()

    def add(self, item):
        self._items.append(item)

    @property
    def count(self):
        return len(self._items)

    def item(self, idx):
        return self._items[idx]


class FakeCollection:
    def __init__(self, items=None):
        self._items = list(items or [])

    @property
    def count(self):
        return len(self._items)

    def item(self, idx):
        return self._items[idx]

    def __iter__(self):
        return iter(self._items)


class FakeVector3D:
    def __init__(self, x=0.0, y=0.0, z=1.0):
        self.x, self.y, self.z = x, y, z

    def normalize(self):
        mag = (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5
        if mag > 0:
            self.x /= mag
            self.y /= mag
            self.z /= mag

    def dotProduct(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z


class FakePoint3D:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z

    @classmethod
    def create(cls, x=0.0, y=0.0, z=0.0):
        return cls(x, y, z)

    def vectorTo(self, other):
        return FakeVector3D(other.x - self.x, other.y - self.y, other.z - self.z)


def make_fake_body(name="Body1", dx_cm=3.81, dy_cm=8.89, dz_cm=243.84, visible=True, parent=None):
    edge_cap = types.SimpleNamespace(entityToken="cap_e")
    edge_long = types.SimpleNamespace(entityToken="long_e")
    cap_face = types.SimpleNamespace(edges=FakeCollection([edge_cap]))
    body = types.SimpleNamespace(
        name=name,
        isVisible=visible,
        parentComponent=parent,
        edges=FakeCollection([edge_cap, edge_long]),
        boundingBox=types.SimpleNamespace(
            minPoint=FakePoint3D(0.0, 0.0, 0.0),
            maxPoint=FakePoint3D(dx_cm, dy_cm, dz_cm),
        ),
        _cap_face=cap_face,
    )
    return body


def make_fake_component(name="Root"):
    comp = types.SimpleNamespace(name=name)
    comp.xYConstructionPlane = "XY"
    comp.xZConstructionPlane = "XZ"
    comp.yZConstructionPlane = "YZ"
    comp.bRepBodies = []
    comp.allOccurrences = []

    def _add_sketch(_plane):
        sk = types.SimpleNamespace(name="Sketch")
        lines = types.SimpleNamespace(
            addTwoPointRectangle=lambda _p1, _p2: None,
            addByTwoPoints=lambda _p1, _p2: types.SimpleNamespace(isConstruction=False),
        )
        circles = types.SimpleNamespace(addByCenterRadius=lambda _c, _r: None)
        sk.sketchCurves = types.SimpleNamespace(sketchLines=lines, sketchCircles=circles)
        prof_single = types.SimpleNamespace(profileLoops=FakeCollection([1]))
        prof_double = types.SimpleNamespace(profileLoops=FakeCollection([1, 2]))
        sk.profiles = FakeCollection([prof_single, prof_double])
        sk.modelToSketchSpace = lambda pt: FakePoint3D(pt.x, pt.y, getattr(pt, "z", 0.0))
        sk.sketchToModelSpace = lambda pt: FakePoint3D(pt.x, pt.y, getattr(pt, "z", 0.0))
        sk.deleteMe = lambda: None
        return sk

    comp.sketches = types.SimpleNamespace(add=_add_sketch)

    def _create_ext_input(_prof, _op):
        return types.SimpleNamespace(setDistanceExtent=lambda _s, _d: None)

    def _add_extrude(_inp):
        body = make_fake_body(parent=comp)
        comp.bRepBodies.append(body)
        return types.SimpleNamespace(
            bodies=FakeCollection([body]),
            startFaces=FakeCollection([body._cap_face]),
            endFaces=FakeCollection([body._cap_face]),
        )

    extrudes = types.SimpleNamespace(createInput=_create_ext_input, add=_add_extrude)
    fillets = types.SimpleNamespace(
        createInput=lambda: types.SimpleNamespace(
            addConstantRadiusEdgeSet=lambda _e, _r, _t: None
        ),
        add=lambda _i: None,
    )
    combines = types.SimpleNamespace(
        createInput=lambda _t, _tools: types.SimpleNamespace(
            operation=None, isKeepToolBodies=False
        ),
        add=lambda _i: None,
    )
    comp.features = types.SimpleNamespace(
        extrudeFeatures=extrudes, filletFeatures=fillets, combineFeatures=combines
    )

    plane_normals = [FakeVector3D(1.0, 0.0, 0.0)]

    def _add_plane(_inp):
        n = plane_normals[0]
        # Flip on second call to test both branches when dotProduct > 0
        plane_normals[0] = FakeVector3D(-1.0, 0.0, 0.0)
        return types.SimpleNamespace(
            geometry=types.SimpleNamespace(normal=n),
            deleteMe=lambda: None,
        )

    comp.constructionPlanes = types.SimpleNamespace(
        createInput=lambda: types.SimpleNamespace(
            setByAngle=lambda _l, _a, _p: None,
            setByOffset=lambda _p, _d: None,
        ),
        add=_add_plane,
    )

    def _add_occ(_m):
        sub = make_fake_component("Sub")
        occ = types.SimpleNamespace(component=sub, isLightBulbOn=True, bRepBodies=sub.bRepBodies)
        comp.allOccurrences.append(occ)
        return occ

    comp.occurrences = types.SimpleNamespace(addNewComponent=_add_occ)
    return comp


def install_adsk_mocks():
    """Install stateful adsk.core and adsk.fusion stubs into sys.modules."""
    if "adsk" in sys.modules:
        return

    adsk_pkg = types.ModuleType("adsk")
    core_mod = types.ModuleType("adsk.core")
    fusion_mod = types.ModuleType("adsk.fusion")

    class _BaseHandler:
        def __init__(self):
            pass

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
    core_mod.Point3D = FakePoint3D
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
    core_mod.ObjectCollection = FakeObjectCollection
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
    fusion_mod.BRepBody = MagicMock
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
