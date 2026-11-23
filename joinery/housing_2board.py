"""Two-board boolean housing / dado joinery for arbitrary intersection angles."""

import adsk.core
import adsk.fusion


def execute_two_board_housing(
    design: adsk.fusion.Design,
    inputs: adsk.core.CommandInputs,
) -> None:
    """Subtract the mating board from the target board while keeping both bodies."""
    tgt_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("targetBoard"))
    tool_sel = adsk.core.SelectionCommandInput.cast(inputs.itemById("refBoard"))
    if (
        not tgt_sel
        or not tool_sel
        or tgt_sel.selectionCount == 0
        or tool_sel.selectionCount == 0
    ):
        return

    target_body = tgt_sel.selection(0).entity
    tool_body = tool_sel.selection(0).entity
    comp = target_body.parentComponent or design.activeComponent

    tools = adsk.core.ObjectCollection.create()
    tools.add(tool_body)
    comb = comp.features.combineFeatures
    comb_in = comb.createInput(target_body, tools)
    comb_in.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    comb_in.isKeepToolBodies = True
    comb.add(comb_in)
