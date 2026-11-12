"""Import-only smoke for the six locally registered candidate task classes."""
from oscombo.osworld import activate, load_task
activate()
for spec in ("v2/pgs1intake","v2/pgs1facilities","v2/pgk1filing","v2/pgk1service","v2/pgk2route","v2/pgk2defer"):
    task=load_task(spec)
    assert task.id==spec.removeprefix("v2/")
    assert len(task.instruction)>100
    print(spec,task.id,type(task).__name__)
