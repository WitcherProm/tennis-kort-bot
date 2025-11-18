from pydantic import BaseModel
from typing import Optional
from datetime import date

class BookingCreate(BaseModel):
    user_id: int
    first_name: str
    court_type: str
    date: str
    time_slot: str

class SlotResponse(BaseModel):
    court_type: str
    date: str
    time_slot: str
    is_available: bool
    booked_by: Optional[str] = None

class BookingResponse(BaseModel):
    id: int
    court_type: str
    date: str
    time_slot: str