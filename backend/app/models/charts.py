from pydantic import BaseModel


class ChartDefinition(BaseModel):
    name: str
    slug: str
    category: str
    quick: list[str]
    assets: list[str]
    summary: str
    available: bool


class SeriesPoint(BaseModel):
    date: str
    value: float


class ChartSeries(BaseModel):
    name: str
    points: list[SeriesPoint]
