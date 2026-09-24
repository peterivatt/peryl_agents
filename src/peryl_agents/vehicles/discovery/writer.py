from sqlalchemy import select
from sqlalchemy.orm import Session

from peryl_db.models.vehicles import Vehicle
from peryl_agents.vehicles.discovery.validator import VehicleDiscoveryBatch, VehicleDiscovery

def save_vehicle_batch(session: Session,
                       batch: VehicleDiscoveryBatch) -> list[Vehicle]:

    vehicles = []

    for candidate in batch.vehicles:
        vehicle = _get_vehicle(session, candidate)

        if vehicle is None:
            vehicle = Vehicle(make=candidate.make,
                              model=candidate.model,
                              trim=candidate.trim,
                              model_year_start=candidate.model_year_start,
                              model_year_end=candidate.model_year_end)
            session.add(vehicle)

        vehicles.append(vehicle)

    session.commit()

    for vehicle in vehicles:
        session.refresh(vehicle)

    return vehicles

def _get_vehicle(session: Session,
                 candidate: VehicleDiscovery) -> Vehicle | None:

    statement = select(Vehicle).where(Vehicle.make == candidate.make,
                                      Vehicle.model == candidate.model,
                                      Vehicle.trim == candidate.trim,
                                      Vehicle.model_year_start == candidate.model_year_start,
                                      Vehicle.model_year_end == candidate.model_year_end)

    return session.scalar(statement)