from pydantic import BaseModel, Field
from typing import List

class Character(BaseModel):
    name: str
    description: str = ""
    visual_anchor: str = ""
    voice_anchor: str = ""

class Location(BaseModel):
    name: str
    description: str = ""
    visual_anchor: str = ""

class Shot(BaseModel):
    number: int
    duration_s: float = 5.0
    shot_type: str = "medium"
    camera_move: str = "static"
    action: str = ""
    dialogue: str = ""
    mood: str = "neutral"
    characters: List[str] = Field(default_factory=list)
    location: str = ""
    assets: List[str] = Field(default_factory=list)

class Scene(BaseModel):
    id: str
    chapter: str
    title: str
    summary: str
    characters: List[str] = Field(default_factory=list)
    location: str = ""
    shots: List[Shot] = Field(default_factory=list)

class Project(BaseModel):
    id: str
    title: str
    source_filename: str
    style: str = "cinematic 3D animation"
    characters: List[Character] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)
    scenes: List[Scene] = Field(default_factory=list)
