from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from peryl_db.base import Base
from peryl_agents.batch_class import DataBatch


DBModel = TypeVar("DBModel", bound=Base)


def get_existing_records(session: Session,
                         db_model: type[DBModel],
                         db_filter: dict|None = None) -> list[DBModel]:

    statement = select(db_model)

    if db_filter:
        statement = statement.filter_by(**db_filter)

    return list(session.scalars(statement))


def save_batch(session: Session,
               batch: DataBatch,
               db_model: type[DBModel]) -> list[DBModel]:

    records = []

    for candidate in batch.data:
        data = candidate.model_dump()
        statement = select(db_model).filter_by(**data)
        record = session.scalar(statement)

        if record is None:
            record = db_model(**data)
            session.add(record)

        records.append(record)

    session.commit()

    for record in records:
        session.refresh(record)

    return records
