from pydantic import BaseModel


class GroupCreate(BaseModel):
    name: str

    class Config:
        from_attributes = True

class GroupRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class GroupUpdate(BaseModel):
    name: str

    class Config:
        from_attributes = True


class GroupUpsert(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
