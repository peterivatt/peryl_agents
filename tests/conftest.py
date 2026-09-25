import pytest

from sqlalchemy import create_engine
from peryl_db.base import Base
from peryl_db.models.vehicles import Vehicle, VehicleSpecs, VehicleSpecsMetadata


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite://",
                           execution_options={"schema_translate_map": {"vehicle": None}})
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            Base.metadata.create_all(connection,
                                     tables=[Vehicle.__table__, VehicleSpecs.__table__,
                                             VehicleSpecsMetadata.__table__])
        yield engine
    finally:
        engine.dispose()
