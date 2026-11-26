"""Print the PostgreSQL DDL for all models (used to generate schema.sql)."""
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.models import Base

for table in Base.metadata.sorted_tables:
    print(str(CreateTable(table).compile(dialect=postgresql.dialect())).strip() + ";\n")
    for index in sorted(table.indexes, key=lambda i: i.name):
        print(str(CreateIndex(index).compile(dialect=postgresql.dialect())).strip() + ";")
    print()
