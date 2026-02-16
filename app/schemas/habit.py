from pydantic import BaseModel


class HabitOut(BaseModel):
    key: str
    title: str

    class Config:
        from_attributes = True
