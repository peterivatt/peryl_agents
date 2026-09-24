from sqlalchemy import select
from sqlalchemy.orm import Session
from peryl_db.models.vehicles import Vehicle

def get_existing_vehicles(session:Session):

    statement = select(Vehicle.make,
                       Vehicle.model,
                       Vehicle.model_year_end,
                       Vehicle.model_year_start,
                       Vehicle.trim)

    return session.execute(statement).all()