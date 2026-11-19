from pydantic import BaseModel


class SourceStatisticResponse(BaseModel):
    source_name: str
    chunk_count: int


class SourcesResponse(BaseModel):
    sources: list[SourceStatisticResponse]
    total_chunks: int


class ProjectResponse(BaseModel):
    name: str
    location: str = ""
    description: str
    source_url: str


class ProjectsResponse(BaseModel):
    projects: list[ProjectResponse]
