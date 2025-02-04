from pydantic import BaseModel, ConfigDict


class BaseAPIModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
