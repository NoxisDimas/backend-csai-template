from pydantic import BaseModel
from typing import List

class ProductResponse(BaseModel):
    id: str
    title: str
    handle: str
    product_type: str
    vendor: str
    tags: str
    image_url: str | None = None
    embedding_status: str

    model_config = {"from_attributes": True}
