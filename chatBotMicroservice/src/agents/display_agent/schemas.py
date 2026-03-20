from pydantic import BaseModel, Field
from typing import Union, List


class ChartConfigUseCase1(BaseModel):
    """Line Chart with one X and one Y axis"""
    usecase: str = Field(default="1", description="Use case identifier")
    update_layout_title: str = Field(..., description="Descriptive chart title")
    update_xaxis_title_text: str = Field(..., description="X axis label")
    update_yaxis_title_text: str = Field(..., description="Y axis label")
    name: str = Field(..., description="Legend name")
    mode: str = Field(default="lines+markers", description="Plot mode: lines+markers, markers, lines")
    x: str = Field(..., description="Exact column name for x-axis")
    y: str = Field(..., description="Exact column name for y-axis")


class ChartConfigUseCase2(BaseModel):
    """Scatter Plot with one X and one Y axis"""
    usecase: str = Field(default="2", description="Use case identifier")
    update_layout_title: str = Field(..., description="Descriptive chart title")
    update_xaxis_title_text: str = Field(..., description="X axis label")
    update_yaxis_title_text: str = Field(..., description="Y axis label")
    name: str = Field(..., description="Legend name")
    mode: str = Field(default="markers", description="Plot mode: markers")
    x: str = Field(..., description="Exact column name for x-axis")
    y: str = Field(..., description="Exact column name for y-axis")


class ChartConfigUseCase3(BaseModel):
    """Line Chart with one X and two Y axes"""
    usecase: str = Field(default="3", description="Use case identifier")
    update_layout_title: str = Field(..., description="Descriptive chart title")
    update_xaxis_title_text: str = Field(..., description="X axis label")
    update_yaxis_title_text: List[str] = Field(..., description="List of Y axis labels")
    name: List[str] = Field(..., description="List of legend names")
    mode: str = Field(default="lines+markers", description="Plot mode: lines+markers")
    x: str = Field(..., description="Exact column name for x-axis")
    y: List[str] = Field(..., description="List of exact column names for y-axes")


class ChartConfigError(BaseModel):
    """Error response when visualization cannot be generated"""
    error: str = Field(..., description="Reason why chart cannot be generated")


ChartConfig = Union[ChartConfigUseCase1, ChartConfigUseCase2, ChartConfigUseCase3, ChartConfigError]
