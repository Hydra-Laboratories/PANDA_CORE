import yaml
from typing import List, Union, Literal
from pydantic import BaseModel, Field

class MoveAction(BaseModel):
    """
    Action to move the mill to a specific location.
    """
    action_type: Literal["move"] = "move"
    target_location: str
    tool: str = "center"
    z_offset: float = 0.0

class ImageAction(BaseModel):
    """
    Action to capture an image at a specific location.
    """
    action_type: Literal["image"] = "image"
    target_location: str
    label: str

class ExperimentSequence(BaseModel):
    """
    A sequence of actions to define an experiment.
    """
    name: str
    actions: List[Union[MoveAction, ImageAction]] = Field(..., description="List of actions to execute")

    @classmethod
    def from_yaml(cls, path: str) -> "ExperimentSequence":
        """Load experiment sequence from a YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)
